<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-28 -->

# finetune (QLoRA training + eval)

## Purpose
QLoRA supervised fine-tuning of Qwen2.5-7B-Instruct on the NyayaDraft dataset,
plus the scenario-stratified split and the held-out evaluation harness. Data prep
runs CPU-only; training/eval run on a rented cloud GPU. See `README.md` here for
the full GPU runbook (VRAM tiers, environment pins, commands).

## Key Files
| File | Description |
|------|-------------|
| `README.md` | Full fine-tuning runbook: data upload, GPU/VRAM tiers, pinned env, train + eval commands, reproducibility notes. |
| `train_qlora.py` | 4-bit NF4 QLoRA SFT. LoRA r=16/α=32 on all attn+MLP projections; **completion-only loss** (prompt masked via `<|im_start|>assistant\n`); early-stopping on val loss; `--max-seq-len 4096` (longest record ~3.6k tok). |
| `eval_model.py` | Held-out eval. `HFGenerator` (local 4-bit), optional `ClaudeGenerator` baseline + LLM-judge. Scores each doc against the **same `legal_rules` gate** (gate_pass, required_match, forbidden_clean, length_ok, disclaimer_ok). |
| `prepare_split.py` | Deterministic 80/10/10 split **held out by scenario** (no phrasing leakage); writes `data/{train,val,test}.jsonl` as template-agnostic `messages` records + metadata. |
| `verify_finetune_data.py` | Read-only pre-flight (run on a box with the Qwen tokenizer): asserts the response template tokenises contiguously in 100% of records (else loss is masked to nothing), reports token-length histograms, flags `--max-seq-len` truncation, checks EOS. |
| `requirements.txt` | Pinned, mutually-compatible stack (torch 2.4 / transformers 4.46 / trl 0.12 / peft 0.13 / bitsandbytes 0.44). |

## Subdirectories (data/outputs — not separately documented)
| Directory | Purpose |
|-----------|---------|
| `data/` | `train.jsonl` / `val.jsonl` / `test.jsonl`. **Gitignored** generated data. |
| `out/` | Trained adapter(s) + zipped archives. **Gitignored** weights. |

## For AI Agents

### Working In This Directory
- **Chat template is never hardcoded** — both training and eval call
  `tokenizer.apply_chat_template(...)` (Qwen ChatML). Keep it that way.
- The response template string in `train_qlora.py` and `verify_finetune_data.py`
  must stay identical; the collator masks everything before it. If you change one,
  change both and re-run `verify_finetune_data.py`.
- Greedy decoding (`do_sample=False`) is intentional in eval for reproducible
  legal text. (The live app/backend uses temperature 0.3 — a separate product choice.)
- Eval imports `legal_rules`; keep this folder inside the repo so it resolves.

### Testing Requirements
- No GPU on the prep machine: `python prepare_split.py` is deterministic and safe
  to run anywhere. Run `verify_finetune_data.py` before any training launch.
- Training/eval are GPU-only (see `README.md`).

## Dependencies

### Internal
- `../legal_rules` (eval scoring gate); `../data-pipeline` (upstream dataset source).

### External
- transformers, peft, trl, bitsandbytes, accelerate, datasets; anthropic
  (optional baseline/judge).

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
