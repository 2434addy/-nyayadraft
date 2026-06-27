<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-27 -->

# legal_rules (statutory/structural rule engine)

## Purpose
The shared, JSON-driven contract for "what a valid NyayaDraft document looks
like". Each doc type has a spec in `rules/<doc_type>.json` declaring required
regex patterns (statutory elements), forbidden patterns, length bounds, and the
disclaimer-footer policy. Imported by **both** the data pipeline (generation
quality gate) and the eval harness (hard checks) so both measure documents
against identical rules.

## Key Files
| File | Description |
|------|-------------|
| `checker.py` | Compiles a doc type's rules (`load_rules`, `lru_cache`d), runs all checks (`check_document` → `CheckResult`), and lints every rules file (`lint_all_rules`). Exposes `DISCLAIMER`, `list_doc_types`. |
| `__init__.py` | Package surface: re-exports `check_document`, `load_rules`, `lint_all_rules`, `list_doc_types`, `CheckResult`, `CompiledRules`, `DISCLAIMER`. |

## Subdirectories (data/tests — not separately documented)
| Directory | Purpose |
|-----------|---------|
| `rules/` | One `<doc_type>.json` per type (11 doc types + `out_of_scope`). Each pattern carries `legal_basis` = `CONFIDENT` or `VERIFY`; VERIFY items feed `docs/CLAIM_AUDIT.md`. |
| `tests/` | `pytest` suites: `test_checker.py` (behaviour) and `test_rules_integrity.py` (every rules file loads/compiles/is sane). |

## For AI Agents

### Working In This Directory
- This is a **contract** consumed by multiple stages — a change to a rules file
  or to `check_document` shifts both what the pipeline accepts and how the model
  is scored. Treat edits as breaking and re-run dependents' tests.
- The disclaimer footer is exact text (`DISCLAIMER`): documents missing it fail;
  refusal (`out_of_scope`) texts carrying it also fail. Don't loosen this.
- Tag every new statutory claim `CONFIDENT` or `VERIFY` (`legal_basis`); VERIFY
  claims must surface in `docs/CLAIM_AUDIT.md` for lawyer review.

### Testing Requirements
- `pytest legal_rules/tests`. Also run `python -c "from legal_rules import lint_all_rules; print(lint_all_rules())"` after editing any rules file.

### Common Patterns
- Pure, frozen dataclasses (`CheckResult`, `CompiledRules`); compiled patterns are
  cached per doc type. Rules are data (JSON), not code — prefer editing JSON.

## Dependencies

### Internal
- Consumed by `../data-pipeline` (generation gate) and `../finetune/eval_model.py`
  (eval gate).

### External
- Standard library only (`json`, `re`, `dataclasses`, `functools`, `pathlib`).

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
