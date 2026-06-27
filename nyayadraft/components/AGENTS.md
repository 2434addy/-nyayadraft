<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-27 -->

# components

## Purpose
Presentational React components for the app. Currently only the shadcn/ui
primitive set used to build the single page.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `ui/` | shadcn/ui primitives (Button, Card, Input, Label, Select, Textarea) — see `ui/AGENTS.md`. |

## For AI Agents

### Working In This Directory
- These are generated shadcn/ui components; regenerate via the shadcn CLI
  (`components.json`) rather than hand-rewriting their structure. App-specific
  composition lives in `app/page.tsx`, not here.

### Testing Requirements
- `npx tsc --noEmit`, `npx next lint`.

### Common Patterns
- Variant styling via `class-variance-authority`; class merging via `cn()` from
  `@/lib/utils`; Radix primitives under the hood.

## Dependencies

### Internal
- `@/lib/utils` (`cn`).

### External
- `@radix-ui/*`, `class-variance-authority`, `lucide-react`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
