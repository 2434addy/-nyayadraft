<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-28 | Updated: 2026-06-28 -->

# backend (Express RunPod proxy)

## Purpose
Standalone Express (Node ≥22) API that performs the actual model call for the
app. It was extracted from the Next.js route
(`nyayadraft/app/api/generate/route.ts`) so the slow RunPod run/poll loop runs on
a host **without serverless function time limits** (deployed on Render). It
builds the instruction prompt, calls the fine-tuned NyayaDraft model on a
**RunPod serverless (vLLM)** endpoint, polls to completion, cleans the output,
and returns `{ text }`. The Next.js app proxies to it; the RunPod key lives
**here**, never in the browser or the Next app.

## Key Files
| File | Description |
|------|-------------|
| `server.js` | Production entry (the `Procfile` target). CommonJS shim that boots the compiled `dist/server.js`, so `node server.js` behaves identically locally and on Render. |
| `package.json` | Scripts: `build` (`tsc`), `start` (`node server.js`), `dev` (`tsx watch src/server.ts`). Deps: `express`, `cors`, `dotenv`. `engines.node >=22` (the poll loop uses `Promise.withResolvers`). |
| `tsconfig.json` | Compiles `src/**/*.ts` → `dist/` as CommonJS (ES2021 target, strict). |
| `Procfile` | `web: node server.js` — the Render start command. |
| `.env.example` | `RUNPOD_API_URL`, `RUNPOD_API_KEY` (required), `PORT` (Render-injected), `FRONTEND_ORIGIN` (comma-separated CORS allow-list). |
| `README.md` | Endpoints, env vars, local run + smoke test, and the full Render deploy runbook. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `src/` | TypeScript sources: the Express app plus the shared `lib/` prompt assets (see `src/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- **RunPod contract (critical):** generation params MUST be nested under
  `input.sampling_params`. `src/server.ts` sends
  `{ input: { messages, sampling_params: { max_tokens: 4096, temperature: 0.3 } } }`.
  A **top-level** `max_tokens` is silently ignored by the worker, which falls back
  to its ~100-token default and truncates every document mid-sentence.
- The request is sent in **chat (`messages`) form** with the frozen system prompt
  (`src/lib/system-prompt.ts`) — this keeps the request in-distribution so the
  model does not prepend instruction preambles to the document.
- `server.js` boots `dist/`, so run `npm run build` after editing any `src/` file
  before `node server.js` reflects the change. `npm run dev` runs the TS source
  directly with hot reload.
- The client↔server contract is fixed: `POST /api/generate` with
  `{ doc_type, details }` → `{ text }` (200) or `{ error }` (non-200). The Next
  proxy and `nyayadraft/app/page.tsx` depend on this exact shape — do not change it
  unilaterally.

### Testing Requirements
- Type-check / build: `npm run build` (must be clean).
- Smoke test: `node server.js`, then `POST /api/generate` (see `README.md`).
  Needs real `RUNPOD_API_URL` + `RUNPOD_API_KEY`; the worker cold-starts in ~1–2
  min. Assert the result is long, ends naturally (not capped at ~100 tokens), and
  carries no meta-commentary.

## Dependencies

### Internal
- `src/lib/` mirrors `nyayadraft/lib/` (`prompt-templates.ts`, `documents.ts`)
  and `data-pipeline/system_prompt.txt` (the system prompt's ultimate source) —
  keep them in parity.

### External
- `express`, `cors`, `dotenv`.
- RunPod serverless vLLM endpoint (hosts the fine-tuned Qwen2.5-7B adapter).
- Render (deploy target; reads `Procfile` + `engines.node`).

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
