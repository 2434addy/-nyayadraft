<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-28 | Updated: 2026-06-28 -->

# lib (backend prompt assets)

## Purpose
The model-facing prompt assets for the backend: the per-doc-type instruction
builder, the frozen system prompt, and the doc-type field catalogue. These are
the **served, authoritative** copies — they are what actually reaches the model on
every request. The matching files under `nyayadraft/lib/` are the frontend's
now-dormant copies (the Next route is a proxy and no longer imports them).

## Key Files
| File | Description |
|------|-------------|
| `prompt-templates.ts` | `buildPrompt(docType, details)` — one instruction `Template` per doc type, keyed by `doc_type`. Reads every field through `field(details, key)` (trim + empty fallback) and appends `NO_PLACEHOLDERS`. Throws on an unknown `doc_type` (the handler surfaces it as 400). **Imported by `server.ts`.** |
| `system-prompt.ts` | `NYAYADRAFT_SYSTEM_PROMPT` — verbatim copy of `data-pipeline/system_prompt.txt`, the exact system message the model was fine-tuned with. Sent as the `system` role to keep requests in-distribution. **Imported by `server.ts`.** |
| `documents.ts` | `DOC_TYPES` — the 11-doc-type field catalogue (`value`/`label`/`description`/`fields`). Carried for schema parity with the frontend; **not imported by the backend at runtime** (`server.ts` needs only `buildPrompt` + the system prompt). |

## For AI Agents

### Working In This Directory
- **Lockstep contract:** a field `key` in `documents.ts` must match the
  placeholder each template reads via `field(d, "<key>")`, and the `doc_type` ids
  here must match `documents.ts` `value`s, the frontend `nyayadraft/lib/`,
  `legal_rules/rules/`, and `data-pipeline/meta_prompts/`. Adding a doc type
  touches all of them.
- `system-prompt.ts` is **frozen** — keep it byte-identical to
  `data-pipeline/system_prompt.txt`; drift here puts the request
  out-of-distribution and the model starts echoing instructions.
- Templates are pure string builders (no I/O). Use `field()` for every placeholder
  rather than reading `details[key]` directly.

### Testing Requirements
- `npm run build` (tsc). Verify a template change end-to-end via
  `POST /api/generate`.

## Dependencies

### Internal
- Consumed by `../server.ts`. Mirrors `nyayadraft/lib/{prompt-templates,documents}.ts`
  and `data-pipeline/system_prompt.txt`.

### External
- None (dependency-free TypeScript).

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
