"""Read-only Colab pre-flight for the NyayaDraft QLoRA dataset.

Run this on a box where ``transformers`` and the Qwen tokenizer are available
(e.g. Colab) BEFORE launching ``train_qlora.py``. It re-uses the *exact*
response template from ``train_qlora.py`` and Qwen's own chat template, then
verifies the four things that silently corrupt a QLoRA SFT run:

  1. (CRITICAL) the encoded response template ``<|im_start|>assistant\\n``
     appears as a contiguous token-id subsequence in 100% of records. If it
     does not, ``DataCollatorForCompletionOnlyLM`` masks the WHOLE record to
     -100 -> zero-loss row, training silently learns nothing.
  2. real token-length histogram per split / doc_type (median/p95/p99/max),
     using ``apply_chat_template(tokenize=True)`` (identical tokenization to the
     trainer's render-then-encode path for ChatML).
  3. truncation at ``--max-seq-len`` (default 4096): any record whose templated
     length exceeds it would have the END of the completion (the target) cut.
  4. EOS: every record's completion is terminated by ``<|im_end|>`` so the model
     learns to stop.

Nothing is written or modified. Exit code is 1 if the response-template check
fails on any record (the mandated gate); truncation / EOS failures are also
treated as fatal since both corrupt training. Exit 0 only when all pass.

Usage (no GPU needed — tokenizer only):
  python finetune/verify_finetune_data.py
  python finetune/verify_finetune_data.py --model Qwen/Qwen2.5-7B-Instruct \\
      --data-dir finetune/data --max-seq-len 4096
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPLITS = ("train", "val", "test")


def load_response_template() -> str:
    """Single source of truth: ``train_qlora.RESPONSE_TEMPLATE``.

    Import it directly when the trainer's deps are present; otherwise extract the
    string literal statically (AST) so this pre-flight still runs before the full
    torch/trl/peft stack is installed. Never executes the trainer.
    """
    try:
        from train_qlora import RESPONSE_TEMPLATE  # type: ignore

        return RESPONSE_TEMPLATE
    except Exception:
        src = (HERE / "train_qlora.py").read_text(encoding="utf-8")
        for node in ast.parse(src).body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "RESPONSE_TEMPLATE"
                for t in node.targets
            ):
                return ast.literal_eval(node.value)
        raise SystemExit("RESPONSE_TEMPLATE not found in train_qlora.py")


def load_split(data_dir: Path, split: str) -> list[dict]:
    path = data_dir / f"{split}.jsonl"
    if not path.exists():
        raise SystemExit(f"missing split file: {path}")
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["_split"] = split
            rows.append(rec)
    return rows


def find_subsequence(hay: list[int], needle: list[int]) -> int:
    """Start index of the first contiguous occurrence of ``needle`` in ``hay``,
    or -1. (The assistant header should occur exactly once per record.)"""
    if not needle:
        return -1
    m = len(needle)
    first = needle[0]
    for i in range(len(hay) - m + 1):
        if hay[i] == first and hay[i : i + m] == needle:
            return i
    return -1


def pct(xs_sorted: list[int], q: float) -> int:
    """Nearest-rank percentile of an already-sorted list."""
    if not xs_sorted:
        return 0
    k = min(len(xs_sorted) - 1, int(round((len(xs_sorted) - 1) * q)))
    return xs_sorted[k]


def fmt_row(label: str, xs: list[int]) -> str:
    s = sorted(xs)
    return (
        f"  {label:32s} n={len(s):4d}  med={pct(s, .5):5d}  "
        f"p95={pct(s, .95):5d}  p99={pct(s, .99):5d}  max={s[-1]:5d}"
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Read-only QLoRA dataset pre-flight (Qwen2.5 ChatML).")
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct",
                   help="HF model id whose tokenizer + chat template to use (match train_qlora.py).")
    p.add_argument("--data-dir", default=str(HERE / "data"),
                   help="Directory holding train.jsonl / val.jsonl / test.jsonl.")
    p.add_argument("--max-seq-len", type=int, default=4096,
                   help="Truncation threshold to check against (train_qlora default).")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "right"  # mirror train_qlora (does not affect per-record length)

    response_template = load_response_template()
    response_ids = tok.encode(response_template, add_special_tokens=False)
    im_end_id = tok.convert_tokens_to_ids("<|im_end|>")
    if im_end_id is None or im_end_id == tok.unk_token_id:
        im_end_id = tok.eos_token_id

    records: list[dict] = []
    for sp in SPLITS:
        records.extend(load_split(Path(args.data_dir), sp))
    total = len(records)
    if total == 0:
        raise SystemExit("no records loaded")

    print("=" * 72)
    print("NyayaDraft QLoRA dataset pre-flight (read-only)")
    print("=" * 72)
    print(f"  model            : {args.model}")
    print(f"  records          : {total}  ({' / '.join(str(sum(1 for r in records if r['_split']==s)) for s in SPLITS)} train/val/test)")
    print(f"  doc_types        : {len(set(r['doc_type'] for r in records))}")
    print(f"  response template: {response_template!r} -> ids {response_ids}")
    print(f"  <|im_end|> id    : {im_end_id}")
    print("-" * 72)

    lengths: dict[tuple[str, str], list[int]] = defaultdict(list)
    template_fail: list[dict] = []
    eos_fail: list[dict] = []
    truncated: list[tuple[dict, int]] = []

    for rec in records:
        ids = tok.apply_chat_template(
            rec["messages"], tokenize=True, add_generation_prompt=False
        )
        n = len(ids)
        sp, dt = rec["_split"], rec["doc_type"]
        lengths[("ALL", "ALL")].append(n)
        lengths[("split", sp)].append(n)
        lengths[("doc_type", dt)].append(n)

        start = find_subsequence(ids, response_ids)
        if start < 0:
            template_fail.append(rec)
        else:
            completion = ids[start + len(response_ids):]
            # Completion must be terminated by <|im_end|> (Qwen appends a trailing
            # newline after it, so accept it as the last or second-to-last token).
            if im_end_id not in completion[-2:]:
                eos_fail.append(rec)
        if n > args.max_seq_len:
            truncated.append((rec, n))

    # --- check 2: token-length histogram ---------------------------------- #
    print("Token-length distribution (full templated record):")
    print(fmt_row("ALL", lengths[("ALL", "ALL")]))
    for sp in SPLITS:
        print(fmt_row(f"split={sp}", lengths[("split", sp)]))
    for dt in sorted(k for s, k in lengths if s == "doc_type"):
        print(fmt_row(f"doc_type={dt}", lengths[("doc_type", dt)]))
    print("-" * 72)

    # --- check 1: response template (CRITICAL) ---------------------------- #
    ok1 = not template_fail
    print(f"[1] response-template subsequence : {'PASS' if ok1 else 'FAIL'}  "
          f"({total - len(template_fail)}/{total} records)")
    for rec in template_fail:
        print(f"      MISSING  id={rec['id']:32s} doc_type={rec['doc_type']} split={rec['_split']}")

    # --- check 3: truncation ---------------------------------------------- #
    ok3 = not truncated
    print(f"[3] no truncation @ {args.max_seq_len:<5d}         : {'PASS' if ok3 else 'FAIL'}  "
          f"({len(truncated)} over limit)")
    for rec, n in truncated:
        print(f"      OVER     id={rec['id']:32s} doc_type={rec['doc_type']} split={rec['_split']} tokens={n}")

    # --- check 4: EOS ----------------------------------------------------- #
    ok4 = not eos_fail
    print(f"[4] completion ends with <|im_end|> : {'PASS' if ok4 else 'FAIL'}  "
          f"({total - len(eos_fail)}/{total} records)")
    for rec in eos_fail[:20]:
        print(f"      NO-EOS   id={rec['id']:32s} doc_type={rec['doc_type']} split={rec['_split']}")
    if len(eos_fail) > 20:
        print(f"      ... and {len(eos_fail) - 20} more")

    print("=" * 72)
    overall = ok1 and ok3 and ok4
    print(f"SUMMARY: {'PASS' if overall else 'FAIL'}  "
          f"[template={'ok' if ok1 else 'FAIL'} truncation={'ok' if ok3 else 'FAIL'} eos={'ok' if ok4 else 'FAIL'}]")
    print("=" * 72)

    # Mandated gate: response-template failure -> exit 1. Truncation/EOS failures
    # also corrupt training, so they are fatal too.
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
