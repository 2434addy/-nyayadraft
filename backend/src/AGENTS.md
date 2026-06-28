<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-28 | Updated: 2026-06-28 -->

# src (backend TypeScript sources)

## Purpose
The Express application and its prompt assets. Compiled to `dist/` by
`npm run build` (`tsc`); the package-root `server.js` boots the compiled
`dist/server.js`.

## Key Files
| File | Description |
|------|-------------|
| `server.ts` | The whole service: CORS (`FRONTEND_ORIGIN` allow-list, else reflect origin), `express.json` (1mb), `GET /health`, and `POST /api/generate`. The POST handler validates `{ doc_type, details }`, builds the prompt, fires the RunPod `/run`, then polls `/status/<id>` every 2s up to 150× (~5 min) before `cleanOutput(extractText(...))`. Helpers: `extractText` (concatenates vLLM chunk/choice/token shapes), `cleanOutput` (strips instruction-echo preambles + non-`[VERIFY:]` bracket artefacts), `sleep`. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `lib/` | Prompt builder, frozen system prompt, and the doc-type field catalogue (see `lib/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- `server.ts` is the only logic file. Prompt building is delegated to
  `lib/prompt-templates.ts` (`buildPrompt`); the system prompt comes from
  `lib/system-prompt.ts`. Keep all model/RunPod logic here, not in the Next route
  (which is now a thin proxy).
- **`extractText` must concatenate, not early-return** — RunPod vLLM returns the
  document as an ordered list of chunks; returning the first chunk truncates
  streamed output.
- **`cleanOutput` must preserve `[VERIFY: ...]` flags** while removing every other
  bracketed token (signature labels, instruction echoes). The final regex handles
  one level of nesting so no dangling fragment is left behind.
- The async handler is wrapped in `try/catch`: Express 4 has no error boundary for
  rejected async handlers, so the catch guarantees the client always receives JSON.

### Testing Requirements
- `npm run build` (tsc, strict) must be clean.
- End-to-end via `POST /api/generate` against a live RunPod endpoint (see
  `../README.md`).

## Dependencies

### Internal
- `./lib/prompt-templates` (`buildPrompt`), `./lib/system-prompt`
  (`NYAYADRAFT_SYSTEM_PROMPT`).

### External
- `express`, `cors`, `dotenv`; global `fetch` (Node ≥22).

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
