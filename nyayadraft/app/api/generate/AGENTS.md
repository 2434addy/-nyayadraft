<!-- Parent: ../../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-28 -->

# api/generate

## Purpose
The single server-side API route, now a thin **proxy**. It validates that the
request body is JSON, forwards `{ doc_type, details }` to the standalone
generation backend at `${NEXT_PUBLIC_API_URL}/api/generate`, and relays the
backend's JSON response and HTTP status unchanged. All RunPod interaction
(prompt building, the run/poll loop, output cleaning) now lives in `backend/`
(an Express service), not here.

## Key Files
| File | Description |
|------|-------------|
| `route.ts` | `POST` handler (`runtime = "nodejs"`, `maxDuration = 300`). Reads `NEXT_PUBLIC_API_URL`, POSTs the body to `<base>/api/generate`, and returns the upstream `{ text }` / `{ error }` with its status. |

## For AI Agents

### Working In This Directory
- This route owns **no** model logic. To change prompt building, the RunPod
  run/poll loop, `extractText`, or `cleanOutput`, edit `backend/src/server.ts`
  (and `backend/src/lib/*`) — not this file.
- The client→server contract is unchanged: `page.tsx` still POSTs
  `{ doc_type, details }` to `/api/generate` and reads `{ text }` / `{ error }`.
  This route preserves that shape, so the proxy is transparent to the client.
- `NEXT_PUBLIC_API_URL` (no trailing slash) selects the backend:
  `http://localhost:3001` in `.env.local` for local dev, the Railway URL in
  production.
- **RunPod contract (moved to the backend, still critical):** generation params
  MUST be nested under `input.sampling_params`. A **top-level** `max_tokens` is
  silently ignored by the worker, which falls back to its ~100-token default and
  truncates every document mid-sentence. See `backend/src/server.ts`.

### Testing Requirements
- Type/lint: `npx tsc --noEmit`, `npx next lint`.
- End-to-end: start the backend (`cd backend && npm run build && node server.js`)
  with its own `RUNPOD_API_URL` + `RUNPOD_API_KEY` set, point
  `NEXT_PUBLIC_API_URL` at it, then `POST /api/generate`. Assert the result is
  long, ends naturally (not capped at ~100 tokens), and carries no
  meta-commentary.

## Dependencies

### Internal
- None — the route no longer imports `@/lib/*`; prompt building moved to
  `backend/`.

### External
- The NyayaDraft Express backend (`backend/`); Next.js `NextResponse`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
