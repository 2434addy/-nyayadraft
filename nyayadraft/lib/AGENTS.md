<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-28 -->

# lib

## Purpose
Framework-agnostic app logic: the document catalogue that drives the form, a
small class-name helper, and **dormant copies** of the prompt templates and
system prompt. Since the `/api/generate` route became a proxy, the live prompt
assets are served from `backend/src/lib/`; the prompt files here are no longer
imported by the app.

## Key Files
| File | Description |
|------|-------------|
| `documents.ts` | **Single source of truth for the form**: the 11 doc types — `value` (doc_type id), `label`, `description`, and `fields` (key/label/type/placeholder). Consumed by `app/page.tsx`. Each field `key` must match the placeholder the backend template reads. |
| `utils.ts` | `cn(...)` — `clsx` + `tailwind-merge` class merger used across components. |
| `prompt-templates.ts` | `buildPrompt(docType, details)` + per-type templates. **Dormant** — the route no longer imports it; the served copy is `backend/src/lib/prompt-templates.ts`. |
| `system-prompt.ts` | `NYAYADRAFT_SYSTEM_PROMPT`, a copy of `data-pipeline/system_prompt.txt`. **Dormant** — the served copy is `backend/src/lib/system-prompt.ts`. |

## For AI Agents

### Working In This Directory
- `documents.ts` is the live file here: its `value`s and field `key`s must stay in
  sync with `backend/src/lib/prompt-templates.ts` (the placeholders read via
  `field(d, "<key>")`). Adding a doc type touches `documents.ts` here,
  `backend/src/lib/{documents,prompt-templates}.ts`, `legal_rules/rules/`, and
  `data-pipeline/meta_prompts/`.
- `prompt-templates.ts` and `system-prompt.ts` here are **not imported by the app**
  (the route proxies to `backend/`). Treat `backend/src/lib/` as authoritative; if
  you edit prompt behaviour, do it there. Keep these copies in sync only if you
  intend the app to ever build prompts locally again.
- Templates are pure string builders (no I/O); every placeholder goes through
  `field()` for consistent trimming/empty handling.

### Testing Requirements
- `npx tsc --noEmit` (no unit-test runner configured). A `documents.ts` change →
  verify the form renders in `app/page.tsx`. A prompt change → verify end-to-end
  through the backend (`backend/`), since the app no longer builds prompts.

### Common Patterns
- Coerce every placeholder through `field()` rather than reading `details[key]`
  directly.

## Dependencies

### External
- `clsx`, `tailwind-merge` (`utils.ts` only). `documents.ts`,
  `prompt-templates.ts`, and `system-prompt.ts` are dependency-free and mirror the
  authoritative copies under `backend/src/lib/`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
