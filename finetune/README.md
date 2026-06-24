# NyayaDraft — Qwen2.5-7B QLoRA fine-tuning

Everything here is prepared **without a GPU**. You run steps 2–4 on a rented
cloud GPU; the data split (step 1) is already materialized.

```
finetune/
  prepare_split.py     # scenario-stratified 80/10/10 split (already run)
  data/
    train.jsonl        # 747 records
    val.jsonl          # 106 records  (early-stopping / model selection)
    test.jsonl         #  67 records  (held-out final eval)
  train_qlora.py       # 4-bit QLoRA SFT (Qwen2.5-7B)
  eval_model.py        # held-out eval + baseline comparison
  requirements.txt     # pinned, mutually-compatible stack
  README.md            # this file
```

The split is **held out by scenario** — every `(doc_type, scenario_id)` lives in
exactly one split, so val/test are *unseen scenarios* (no phrasing leakage).
Counts: **train 747 / val 106 / test 67 = 920** across all 11 doc types.

---

## 0. Get the data onto the GPU box

`data/*.jsonl` (and `out/full/dataset.jsonl`) are generated documents and are
gitignored by repo policy. Either:

- **upload** the `finetune/` folder (with `data/`) to the GPU box, **or**
- copy `out/full/dataset.jsonl` + the repo and re-run the split there:
  ```bash
  python finetune/prepare_split.py     # deterministic; reproduces the same split
  ```

The repo's `legal_rules/` package must be importable (the eval gate uses it) —
keep `finetune/` inside the repo so `legal_rules` resolves.

---

## 1. Pick a GPU (VRAM)

QLoRA loads the 7B in 4-bit (~4.5 GB weights); the rest is activations +
optimizer state for the small LoRA params, with gradient checkpointing on.

| Tier | VRAM | Examples | Settings | Notes |
|------|------|----------|----------|-------|
| **Minimum** | 16 GB | T4 (Colab free), RTX 4060 Ti 16G | `--max-seq-len 2048 --grad-accum 32` + fp16¹ | longest docs may truncate; slow |
| **Recommended** | 24 GB | RTX 4090 / 3090, A10G, L4 | defaults (`--max-seq-len 4096`) | comfortable, full context |
| **Comfortable** | 40–48 GB | A100-40G, A6000, L40S | defaults, can raise `--batch-size 2` | fastest; roomy for eval |

¹ T4/Turing and V100/Volta lack bf16; `train_qlora.py` auto-detects this
(`torch.cuda.is_bf16_supported()`) and falls back to fp16 — no manual edit needed.

**Eval/inference** needs far less (7B 4-bit generation ≈ 6–8 GB) — any 16 GB+ GPU.

Training time: ~747 examples × 3 epochs, effective batch 16 ≈ **~140 optimizer
steps** → roughly **30–90 min** on a single 24–40 GB GPU. Trivial cost
(≈ \$0.30–\$1.50 at typical RunPod/Lambda hourly rates).

---

## 2. Environment

```bash
# match torch to the box's CUDA first (example: CUDA 12.1)
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu121
pip install -r finetune/requirements.txt
```

Qwen2.5 is an open model — no HF token / gating. The Anthropic deps are only
needed for the optional Claude baseline/judge in eval.

---

## 3. Train

```bash
python finetune/train_qlora.py \
    --model Qwen/Qwen2.5-7B-Instruct \
    --data-dir finetune/data \
    --output-dir finetune/out/qwen2.5-7b-nyayadraft-qlora
```

What it does:
- 4-bit **NF4** double-quant base, bf16 compute.
- **LoRA** `r=16, alpha=32, dropout=0.05` on all attn+MLP projections
  (`q,k,v,o,gate,up,down`).
- **Completion-only loss** — Qwen's chat template is applied to `messages`, then
  the prompt (system+user) is masked so loss is computed only on the document.
- Small-data overfitting guards: **3 epochs max, eval + early-stopping on val
  loss (patience 2), `load_best_model_at_end`, weight decay 0.01, LoRA dropout**.
- Effective batch 16 (`bs 1 × grad-accum 16`), cosine LR `2e-4`, warmup 3%,
  `paged_adamw_8bit`, gradient checkpointing.

Saves the best adapter + tokenizer to `--output-dir`. Add `--merge` to also write
a standalone fp16 model (`<output-dir>/merged-fp16`).

Conservative variant if you see val loss diverging early: `--lora-r 8 --epochs 2`.

---

## 4. Evaluate on the held-out test set

```bash
# fine-tuned vs off-the-shelf base Qwen (objective, no API):
python finetune/eval_model.py \
    --base-model Qwen/Qwen2.5-7B-Instruct \
    --adapter finetune/out/qwen2.5-7b-nyayadraft-qlora \
    --models finetuned base \
    --out finetune/out/eval_report.json

# add the vanilla-Claude baseline and an LLM-judge (needs ANTHROPIC_API_KEY, costs $):
export ANTHROPIC_API_KEY=sk-...
python finetune/eval_model.py \
    --base-model Qwen/Qwen2.5-7B-Instruct \
    --adapter finetune/out/qwen2.5-7b-nyayadraft-qlora \
    --models finetuned base claude --judge
```

Each generated doc is scored against the **same `legal_rules` gate** that built
the dataset. Reported per model and per doc_type:

- `gate_pass` — passes `check_document` (statutory + structural)
- `required_match` — mean fraction of required statutory patterns present
- `forbidden_clean` — no forbidden pattern (e.g. lessor/lessee, markdown, AI voice)
- `length_ok` — within `[min_chars, max_chars]`
- `disclaimer_ok` — correct disclaimer-footer policy (present for docs, absent for refusals)
- `judge_quality` — optional 1–5 Claude rating vs the gold reference

The success criterion: **fine-tuned ≫ base Qwen** on `gate_pass`/`required_match`,
and competitive with vanilla Claude at a fraction of the inference cost.

---

## Notes

- **Base vs Instruct**: default is `Qwen2.5-7B-Instruct` (chat template +
  system-prompt support out of the box). Pass `Qwen/Qwen2.5-7B` only if you want
  to teach the chat format from scratch.
- **Chat template**: never hardcoded — `train_qlora.py` calls
  `tokenizer.apply_chat_template(...)`, i.e. Qwen's own ChatML, and
  `eval_model.py` does the same for prompting.
- **Reproducibility**: split + training seed = `20260610` (from `config.yaml`).
- Do **not** commit `data/` or `out/` (generated documents / weights).
