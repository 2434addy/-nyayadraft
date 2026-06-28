<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-28 -->

# nyayadraft (web app)

## Purpose
Next.js 14 (App Router) web app — the product UI. The user picks one
of the 11 document types, fills a dynamically-rendered form, and the app asks the
fine-tuned NyayaDraft model to draft it. Output renders in a read-only textarea
with copy/download. The app no longer talks to RunPod directly: its
`/api/generate` route is a **thin server-side proxy** to the standalone Express
backend (`../backend/`), which owns prompt building, the RunPod run/poll loop, and
output cleaning. The RunPod key lives in the backend, never in this app.

Access is gated by **Supabase auth** (email/password + Google OAuth). Each
generated document is auto-saved to a per-user **draft history** shown in the
sidebar, where it can be searched, reloaded, renamed, downloaded, or deleted.

## Key Files
| File | Description |
|------|-------------|
| `package.json` | Scripts: `dev`, `build`, `start`, `lint`. Deps: Next 14.2, React 18, Tailwind, Radix/shadcn. |
| `tailwind.config.ts` | Tailwind theme (dark-mode default, CSS-variable tokens). |
| `components.json` | shadcn/ui generator config. |
| `tsconfig.json` | TS config; `@/*` path alias → app root. |
| `.env.local` / `.env.example` | `NEXT_PUBLIC_API_URL` (backend base URL) plus `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` (auth + draft history). RunPod creds live in `backend/.env`, not here. |
| `supabase/schema.sql` | The `drafts` table + RLS. **Run once** in the Supabase SQL editor before draft history works. |
| `lib/supabase.ts` / `lib/drafts.ts` | Browser Supabase client (singleton) and per-user drafts CRUD; `lib/draft-utils.ts` holds pure title/search/download helpers. |
| `components/auth-provider.tsx` | `AuthProvider` + `useAuth()` — live session/user/loading from Supabase, wrapped around the app in `app/layout.tsx`. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `app/` | App Router pages, layout, and the `/api/generate` proxy route (see `app/AGENTS.md`). |
| `lib/` | Document catalogue (the form) and the `cn` helper; dormant prompt copies (see `lib/AGENTS.md`). |
| `components/` | shadcn/ui primitives (see `components/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- The 11 doc types and their **form fields** live in `lib/documents.ts` (consumed
  by `app/page.tsx`). The matching **model prompts** now live in
  `backend/src/lib/prompt-templates.ts`. They are keyed by the same `doc_type`,
  and each field `key` here must match the placeholder the backend template reads
  via `field(d, "<key>")` — edit the two in lockstep across the app and backend.
- `app/api/generate/route.ts` is a proxy: it forwards `{ doc_type, details }` to
  `${NEXT_PUBLIC_API_URL}/api/generate` and relays the `{ text }` / `{ error }`
  response unchanged. To change any model behaviour, edit `backend/`, not this app.
- **RunPod contract (now in the backend, still critical):** generation params MUST
  be nested under `input.sampling_params`. A top-level `max_tokens` is silently
  ignored by the worker and output truncates to ~100 tokens. See
  `backend/src/server.ts`.
- **Auth & draft history (Supabase):** `lib/supabase.ts` is the browser client;
  `components/auth-provider.tsx` exposes `useAuth()`. `app/page.tsx` redirects to
  `/auth/login` when there is no session and forwards `Authorization: Bearer
  <access_token>` to `/api/generate` (the proxy and backend now require it).
  Generation auto-saves via `lib/drafts.ts`; the `drafts` table + RLS live in
  `supabase/schema.sql` and must be applied to the project once.

### Testing Requirements
- `npx tsc --noEmit`, `npx next lint`, and `npx next build` (all must be clean; no
  unit-test runner is configured — pure helpers in `lib/draft-utils.ts` are
  importable standalone under Bun for ad-hoc checks).
- To exercise generation end-to-end: start the backend
  (`cd backend && npm run build && node server.js`) with its `RUNPOD_API_URL` /
  `RUNPOD_API_KEY` set, point `NEXT_PUBLIC_API_URL` at it, then run the app. The
  worker cold-starts in ~1–2 min.

### Common Patterns
- shadcn/ui + Radix primitives, styled with Tailwind via the `cn()` class merger.
- `"use client"` page component with `useState`/`useMemo`; the route handler holds
  only proxy logic (no secrets, no model logic).

## Dependencies

### Internal
- `app/page.tsx` consumes `lib/documents.ts`, `lib/utils.ts`, and `components/ui/*`.
- `app/api/generate/route.ts` imports nothing from `lib/` — it proxies to the
  `backend/` service via `NEXT_PUBLIC_API_URL`.

### External
- `next`, `react`, `lucide-react` (icons), `clsx` + `tailwind-merge`,
  `@radix-ui/*`, `class-variance-authority`.
- The NyayaDraft Express backend (`../backend/`), which in turn calls the RunPod
  serverless vLLM endpoint hosting the fine-tuned Qwen2.5-7B adapter.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
