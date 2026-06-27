<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-27 -->

# lib

## Purpose
Framework-agnostic app logic: the document catalogue (form definitions), the
server-side prompt templates, and a small class-name helper.

## Key Files
| File | Description |
|------|-------------|
| `documents.ts` | **Single source of truth** for the 11 doc types: `value` (doc_type id), `label`, `description`, and `fields` (key/label/type/placeholder). Drives the form in `app/page.tsx`. |
| `prompt-templates.ts` | One instruction template per doc type, keyed by the same `value`. `buildPrompt(docType, details)` selects a template and interpolates fields via the `field()` accessor (trim + empty fallback). Used server-side by the API route. |
| `utils.ts` | `cn(...)` — `clsx` + `tailwind-merge` class merger used across components. |

## For AI Agents

### Working In This Directory
- `documents.ts` `value`s and `prompt-templates.ts` keys MUST stay in sync, and
  the field `key`s in `documents.ts` must match the placeholders each template
  reads via `field(d, "<key>")`. Adding a doc type = add an entry in both files
  (and a matching `legal_rules/rules/<doc_type>.json` + meta-prompt spec).
- `buildPrompt` throws on an unknown `doc_type`; the API route surfaces that as a
  400. Keep templates pure string builders (no I/O).

### Testing Requirements
- `npx tsc --noEmit` (no unit-test runner configured). When changing a template,
  verify generation end-to-end through `/api/generate`.

### Common Patterns
- Every placeholder is coerced through `field()` for consistent trimming and empty
  handling — use it for new fields rather than reading `details[key]` directly.

## Dependencies

### External
- `clsx`, `tailwind-merge` (utils only). `documents.ts` / `prompt-templates.ts`
  are dependency-free.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
