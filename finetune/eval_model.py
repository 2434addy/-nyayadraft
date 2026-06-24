"""Evaluate a fine-tuned NyayaDraft model on the held-out test set.

Runs one or more model variants over finetune/data/test.jsonl, scores each
generated document against the SAME statutory gate used to build the dataset
(legal_rules.checker), and prints a side-by-side comparison so you can see what
the QLoRA adapter buys over the off-the-shelf model.

Models (``--models``):
  finetuned   base model + LoRA adapter   (--adapter DIR required)
  base        the off-the-shelf base model (no adapter) — the headline baseline
  claude      vanilla Claude via the Anthropic API (optional; costs money,
              needs ANTHROPIC_API_KEY). Same system+user prompt, no fine-tuning.

Objective metrics (no judge needed), per model and per doc_type:
  gate_pass       fraction whose generated text passes legal_rules.check_document
  required_match  mean fraction of required statutory patterns matched
  forbidden_clean fraction with NO forbidden-pattern hit
  length_ok       fraction within [min_chars, max_chars]
  disclaimer_ok   fraction with the correct disclaimer footer policy
Optional ``--judge`` adds a 1-5 Claude quality score (gen vs reference).

GPU needed for the local (finetuned/base) variants. ``--models claude`` alone
runs CPU-only. Does NOT train anything.

Example:
  python finetune/eval_model.py \
      --base-model Qwen/Qwen2.5-7B-Instruct \
      --adapter finetune/out/qwen2.5-7b-nyayadraft-qlora \
      --models finetuned base \
      --out finetune/out/eval_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from legal_rules.checker import DISCLAIMER, check_document, load_rules  # noqa: E402


# --------------------------------------------------------------------------- #
# Scoring (pure, reusable, no model needed)
# --------------------------------------------------------------------------- #
def score_doc(doc_type: str, text: str) -> dict:
    """Objective quality metrics for one generated text vs its doc_type rules."""
    rules = load_rules(doc_type)
    result = check_document(doc_type, text)
    n_req = len(rules.required)
    req_hit = sum(1 for _id, _d, pat in rules.required if pat.search(text))
    forb_hit = sum(1 for _id, _d, pat in rules.forbidden if pat.search(text))
    n = len(text)
    if rules.require_disclaimer:
        disclaimer_ok = text.rstrip().rstrip('"').rstrip("'").rstrip().endswith(DISCLAIMER)
    else:  # refusals (is_document=False) must NOT carry the disclaimer footer
        disclaimer_ok = DISCLAIMER not in text
    return {
        "gate_pass": bool(result.ok),
        "required_match": (req_hit / n_req) if n_req else 1.0,
        "forbidden_clean": forb_hit == 0,
        "length_ok": rules.min_chars <= n <= rules.max_chars,
        "disclaimer_ok": disclaimer_ok,
        "failures": list(result.failures),
        "n_chars": n,
    }


# --------------------------------------------------------------------------- #
# Generators
# --------------------------------------------------------------------------- #
class HFGenerator:
    """Local Qwen (4-bit) generation, optionally with a LoRA adapter."""

    def __init__(self, base_model: str, adapter: str | None, max_new_tokens: int):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        self.max_new_tokens = max_new_tokens
        src = adapter or base_model
        self.tok = AutoTokenizer.from_pretrained(src, use_fast=True)
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            base_model, quantization_config=bnb, device_map="auto",
            torch_dtype=torch.bfloat16,
        )
        if adapter:
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, adapter)
        model.eval()
        self.model = model
        self.torch = torch

    def generate(self, prompt_messages: list[dict]) -> str:
        inputs = self.tok.apply_chat_template(
            prompt_messages, add_generation_prompt=True,
            return_tensors="pt", return_dict=True,
        ).to(self.model.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,  # greedy → reproducible legal text
                repetition_penalty=1.05,
                pad_token_id=self.tok.pad_token_id,
                eos_token_id=self.tok.eos_token_id,
            )
        new = out[0][inputs["input_ids"].shape[1]:]
        text = self.tok.decode(new, skip_special_tokens=True)
        return text.strip()


class ClaudeGenerator:
    """Vanilla Claude baseline via the Anthropic API (optional)."""

    def __init__(self, model: str, max_tokens: int):
        from anthropic import Anthropic  # noqa: F401
        self.model = model
        self.max_tokens = max_tokens
        self.client = Anthropic()  # reads ANTHROPIC_API_KEY

    def generate(self, prompt_messages: list[dict]) -> str:
        system = next((m["content"] for m in prompt_messages if m["role"] == "system"), "")
        user = [{"role": m["role"], "content": m["content"]}
                for m in prompt_messages if m["role"] != "system"]
        resp = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system, messages=user,
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()


# --------------------------------------------------------------------------- #
# Optional LLM-as-judge (Claude)
# --------------------------------------------------------------------------- #
def judge_quality(client, judge_model: str, doc_type: str, reference: str, gen: str) -> int | None:
    prompt = (
        f"You are grading a generated Indian legal '{doc_type}' draft against a "
        f"gold reference. Score 1-5 (5=indistinguishable in legal soundness, "
        f"structure, and use of provided facts; 1=unusable). Reply with ONLY the "
        f"integer.\n\n=== REFERENCE ===\n{reference}\n\n=== GENERATED ===\n{gen}"
    )
    resp = client.messages.create(
        model=judge_model, max_tokens=4,
        messages=[{"role": "user", "content": prompt}],
    )
    txt = "".join(b.text for b in resp.content if b.type == "text").strip()
    for ch in txt:
        if ch.isdigit():
            return int(ch)
    return None


def aggregate(rows: list[dict]) -> dict:
    keys = ["gate_pass", "required_match", "forbidden_clean", "length_ok", "disclaimer_ok"]
    n = len(rows)
    if n == 0:
        return {**{k: 0.0 for k in keys}, "n": 0}
    agg = {k: sum(float(r["score"][k]) for r in rows) / n for k in keys}
    judged = [r["judge"] for r in rows if r.get("judge") is not None]
    if judged:
        agg["judge_quality"] = sum(judged) / len(judged)
    agg["n"] = n
    return agg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate NyayaDraft models on test set.")
    p.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--adapter", default=None, help="LoRA adapter dir (for 'finetuned').")
    p.add_argument("--data", default="finetune/data/test.jsonl")
    p.add_argument("--models", nargs="+", default=["finetuned", "base"],
                   choices=["finetuned", "base", "claude"])
    p.add_argument("--max-new-tokens", type=int, default=3600)
    p.add_argument("--claude-model", default="claude-sonnet-4-5",
                   help="Anthropic model id for the 'claude' baseline.")
    p.add_argument("--judge", action="store_true", help="Add Claude LLM-judge score.")
    p.add_argument("--judge-model", default="claude-sonnet-4-5")
    p.add_argument("--limit", type=int, default=0, help="Cap test records (0=all).")
    p.add_argument("--out", default="finetune/out/eval_report.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    records = [json.loads(l) for l in Path(args.data).open(encoding="utf-8") if l.strip()]
    if args.limit:
        records = records[: args.limit]
    print(f"Evaluating {len(records)} held-out test records on: {', '.join(args.models)}")

    judge_client = None
    if args.judge or "claude" in args.models:
        from anthropic import Anthropic
        judge_client = Anthropic()

    report: dict = {"data": args.data, "n": len(records), "models": {}}

    for name in args.models:
        if name == "finetuned":
            if not args.adapter:
                raise SystemExit("--adapter is required for the 'finetuned' model")
            gen = HFGenerator(args.base_model, args.adapter, args.max_new_tokens)
        elif name == "base":
            gen = HFGenerator(args.base_model, None, args.max_new_tokens)
        else:  # claude
            gen = ClaudeGenerator(args.claude_model, args.max_new_tokens)

        rows = []
        for rec in records:
            messages = rec["messages"]
            prompt = messages[:-1]          # system + user
            reference = messages[-1]["content"]
            text = gen.generate(prompt)
            score = score_doc(rec["doc_type"], text)
            row = {"id": rec["id"], "doc_type": rec["doc_type"], "score": score}
            if args.judge and judge_client is not None:
                row["judge"] = judge_quality(
                    judge_client, args.judge_model, rec["doc_type"], reference, text)
            rows.append(row)

        overall = aggregate(rows)
        per_type = {
            dt: aggregate([r for r in rows if r["doc_type"] == dt])
            for dt in sorted({r["doc_type"] for r in rows})
        }
        report["models"][name] = {"overall": overall, "per_type": per_type, "rows": rows}
        print(f"\n[{name}] overall: " + "  ".join(
            f"{k}={v:.3f}" for k, v in overall.items() if k != "n"))

    # --- comparison table --------------------------------------------------
    metrics = ["gate_pass", "required_match", "forbidden_clean", "length_ok",
               "disclaimer_ok", "judge_quality"]
    print("\n" + "=" * 78)
    print(f"  {'metric':16s}" + "".join(f"{m:>14s}" for m in args.models))
    print("-" * 78)
    for met in metrics:
        vals = [report["models"][m]["overall"].get(met) for m in args.models]
        if all(v is None for v in vals):
            continue
        cells = "".join(f"{(v if v is not None else float('nan')):>14.3f}" for v in vals)
        print(f"  {met:16s}{cells}")
    print("=" * 78)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFull report -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
