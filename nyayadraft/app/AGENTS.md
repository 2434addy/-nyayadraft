<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-27 -->

# app (App Router)

## Purpose
The Next.js App Router tree: the single client page, the root layout, global
styles/fonts, and the server-side generation API route.

## Key Files
| File | Description |
|------|-------------|
| `page.tsx` | `"use client"` single page: doc-type `Select`, dynamic form rendered from `lib/documents.ts` fields, `POST /api/generate`, read-only result textarea, copy + download `.txt`. |
| `layout.tsx` | Root layout; dark theme by default; loads local Geist Sans/Mono fonts; page metadata. |
| `globals.css` | Tailwind layers + CSS-variable design tokens. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `api/generate/` | Thin server-side proxy that forwards generation requests to the standalone Express backend (see `api/generate/AGENTS.md`). |
| `fonts/` | Local Geist variable-font `.woff` files used by `layout.tsx`. |

## For AI Agents

### Working In This Directory
- `page.tsx` is the only client component; it holds form state and posts
  `{ doc_type, details }` to `/api/generate`. Form fields come from
  `lib/documents.ts` — render logic keys off each doc type's `fields`.
- Keep secrets out of client code. RunPod access now lives in the standalone Express backend (`../../backend/`); the route only proxies to `NEXT_PUBLIC_API_URL`.

### Testing Requirements
- `npx tsc --noEmit` and `npx next lint` from the app root (`nyayadraft/`).

### Common Patterns
- shadcn/ui primitives from `@/components/ui/*`; `cn()` for class merging;
  `lucide-react` icons.

## Dependencies

### Internal
- `@/lib/documents`, `@/lib/utils`, `@/components/ui/*` (page). The route imports nothing from `@/lib` — it proxies to the backend.

### External
- `next`, `react`, `lucide-react`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
