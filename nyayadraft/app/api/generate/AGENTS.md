<!-- Parent: ../../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-27 -->

# api/generate

## Purpose
The single server-side API route. Validates the request, builds the model prompt
from `doc_type` + `details`, calls the RunPod serverless (vLLM) endpoint, polls
for completion, normalises the worker's output shape, strips any stray
meta-commentary, and returns `{ text }`.

## Key Files
| File | Description |
|------|-------------|
| `route.ts` | `POST` handler (`runtime = "nodejs"`, `maxDuration = 300`). Submits the job to `RUNPOD_API_URL`, polls `/status/<id>` every 2s up to 5 min, then returns the cleaned document. |

## For AI Agents

### Working In This Directory
- **RunPod contract (critical):** generation params MUST be nested under
  `input.sampling_params`:
  ```ts
  body: JSON.stringify({
    input: { prompt, sampling_params: { max_tokens: 4096, temperature: 0.7 } },
  })
  ```
  A **top-level** `max_tokens` is silently ignored by the worker, which then
  falls back to its ~100-token default and truncates every document mid-sentence.
  Verify via `usage.output` in the response: a real document is ~1000–1500 tokens.
- `max_tokens: 4096` is sized to the training `--max-seq-len` (4096; longest
  record ~3.6k tokens) so even the longest doc types finish at natural EOS.
- `extractText()` must concatenate **all** array chunks (vLLM may return an
  ordered list of token batches) — accumulate every chunk's first choice; never
  return on the first chunk, or streamed output truncates.
- `cleanOutput()` strips known preamble/postamble artifacts. The model is trained
  to emit no commentary, but it can prepend a stray empty `()` — extend the
  cleaner if that needs removing.
- Prompts are built by `@/lib/prompt-templates` (`buildPrompt`), keyed by the
  same `doc_type` ids used everywhere else.

### Testing Requirements
- Type/lint: `npx tsc --noEmit`, `npx next lint`.
- End-to-end requires `RUNPOD_API_URL` + `RUNPOD_API_KEY` in `../../../.env.local`;
  the worker cold-starts in ~1–2 min. Assert the result is long and ends naturally
  (not capped at ~100 tokens) and carries no meta-commentary.

## Dependencies

### Internal
- `@/lib/prompt-templates` (`buildPrompt`).

### External
- RunPod serverless vLLM endpoint; Next.js `NextResponse`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
