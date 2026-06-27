<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-27 -->

# data-pipeline (W1 — synthetic training data)

## Purpose
Turns per-doc-type meta-prompt specs + seed data into `instruction → document`
training pairs, validating every draft against the `legal_rules` statutory gate
before it is kept. Two generation paths exist:

1. **Anthropic API orchestrator** (`generate.py`) — batched API requests with a
   mandatory cost guard. Documented in the README/`docs/COSTS.md`.
2. **Local "own-knowledge" path** (`loop_fill.py` + `variation.py`) — no API
   key; hand-authored template knowledge parameterised with randomised facts,
   gate-validated before append. **`../CLAUDE.md` mandates this path** for actual
   dataset generation.

## Key Files
| File | Description |
|------|-------------|
| `config.yaml` | Central config: model, temperature, token caps, pricing, per-type counts, register mix, withhold probabilities, dedup threshold, splits, `seed: 20260610`. Edit here — no code changes. |
| `pipeline_config.py` | Cached loaders for `config.yaml`, meta-prompt specs, scenarios, seeds, and the system prompt (path-independent, `lru_cache`d). |
| `system_prompt.txt` | **Authoritative** wording of the safety rules baked into every training pair (placeholders, citations, structure, register, disclaimer). |
| `prompts.py` | Renders a meta-prompt for one spec+variation; `<<KEY>>` substitution with an unfilled-placeholder guard. |
| `variation.py` | Deterministic, seeded variation sampling — pure fn of `(seed, index)`: scenario, register, given-vs-withheld facts, synthesised values. |
| `generate.py` | API generation orchestrator: task planning, response parsing, gate validation, JSONL checkpoint/resume, cost guard (`YES` to proceed). |
| `loop_fill.py` | Autonomous, offline dataset-growth loop; appends one gate-passing doc per cycle, aborts on a gate failure. |
| `split_packages.py` | Splits authored doc-type "packages" into `meta_prompts/`, `legal_rules/rules/`, `seeds/scenarios.json`, and `docs/claim_audit.*`; lints rules at the end. |
| `fix_oos_resplit.py` | De-duplicates `out_of_scope` records and re-splits stratified by doc_type (whole scenarios kept together). |

## Subdirectories (data — not separately documented)
| Directory | Purpose |
|-----------|---------|
| `meta_prompts/` | Per-doc-type generation specs (`<doc_type>.json`) + shared `base*.txt` templates: structure, statutory requirements, field policies (`always`/`withholdable`/`optional`). |
| `seeds/` | Variation-engine seed data: `names.json`, `cities.json`, `scenarios.json`. |
| `tests/` | `pytest` suites for generate/variation/prompts/cost-guard. |

## For AI Agents

### Working In This Directory
- Determinism is a contract: `variation.build_variation(seed, index)` must stay a
  pure function — same inputs, same output, no mutation. Don't introduce unseeded
  randomness.
- Every generated document MUST pass `legal_rules.check_document(doc_type, text)`
  before being written; a failure should abort, not silently drop.
- Follow `../CLAUDE.md`: prefer the local generation path; do not run
  `generate.py`'s API path or request `ANTHROPIC_API_KEY` for dataset work.

### Testing Requirements
- `pytest data-pipeline/tests` (offline; the generator's I/O is dependency-injected
  and mocked).

### Common Patterns
- Config/asset access goes through `pipeline_config.py` loaders (cached, fail-loud
  on missing files) — don't re-read YAML/JSON ad hoc.

## Dependencies

### Internal
- `legal_rules` (the validation gate, shared with `finetune/eval_model.py`).

### External
- `anthropic` (API path only), `pyyaml`, `rapidfuzz` (dedup), stdlib `random`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
