<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-27 -->

# nyayadraft (web app)

## Purpose
Next.js 14 (App Router) single-page web app. The user picks one of the 11
document types, fills a dynamically-rendered form, and the app asks the
fine-tuned NyayaDraft model — served on **RunPod serverless (vLLM worker)** — to
draft it. Output renders in a read-only textarea with copy/download. All RunPod
calls happen **server-side** in the API route so the key is never exposed.

## Key Files
| File | Description |
|------|-------------|
| `package.json` | Scripts: `dev`, `build`, `start`, `lint`. Deps: Next 14.2, React 18, Tailwind, Radix/shadcn. |
| `tailwind.config.ts` | Tailwind theme (dark-mode default, CSS-variable tokens). |
| `components.json` | shadcn/ui generator config. |
| `tsconfig.json` | TS config; `@/*` path alias → app root. |
| `.env.local` / `.env.example` | `RUNPOD_API_URL` (the `/run` endpoint) and `RUNPOD_API_KEY`. Server-only. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `app/` | App Router pages, layout, and the `/api/generate` route (see `app/AGENTS.md`). |
| `lib/` | Document catalogue, prompt templates, and the `cn` helper (see `lib/AGENTS.md`). |
| `components/` | shadcn/ui primitives (see `components/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- The 11 doc types and their form fields live in `lib/documents.ts`; the matching
  model prompts live in `lib/prompt-templates.ts`. Both are keyed by the same
  `doc_type` value — edit them in lockstep.
- The RunPod request contract is subtle: generation params **must** be nested
  under `input.sampling_params` (see `app/api/generate/AGENTS.md`). A top-level
  `max_tokens` is silently ignored by the worker and output truncates to ~100
  tokens.

### Testing Requirements
- `npx tsc --noEmit` and `npx next lint` (both must be clean; no test runner is
  configured).
- To exercise generation end-to-end, the `/api/generate` route needs valid
  `RUNPOD_API_URL`/`RUNPOD_API_KEY` in `.env.local`; the worker cold-starts in
  ~1–2 min.

### Common Patterns
- shadcn/ui + Radix primitives, styled with Tailwind via the `cn()` class merger.
- `"use client"` page component with `useState`/`useMemo`; server logic isolated
  in the route handler.

## Dependencies

### Internal
- `app/page.tsx` consumes `lib/documents.ts`, `lib/utils.ts`, and `components/ui/*`.
- `app/api/generate/route.ts` consumes `lib/prompt-templates.ts`.

### External
- `next`, `react`, `lucide-react` (icons), `clsx` + `tailwind-merge`,
  `@radix-ui/*`, `class-variance-authority`.
- RunPod serverless vLLM endpoint (hosts the fine-tuned Qwen2.5-7B adapter).

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
