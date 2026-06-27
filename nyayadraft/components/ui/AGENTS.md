<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-27 | Updated: 2026-06-27 -->

# ui

## Purpose
shadcn/ui primitive components (Radix + Tailwind) consumed by `app/page.tsx`.

## Key Files
| File | Description |
|------|-------------|
| `button.tsx` | Button with `cva` variants/sizes; supports `asChild` via Radix `Slot`. |
| `card.tsx` | Card container parts: `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`. |
| `input.tsx` | Styled text input. |
| `label.tsx` | Radix Label wrapper. |
| `select.tsx` | Radix Select composition (`Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem`) — the doc-type picker. |
| `textarea.tsx` | Styled textarea; used for the read-only generated document. |

## For AI Agents

### Working In This Directory
- Stock shadcn/ui output — prefer regenerating via the shadcn CLI over manual
  edits. Keep the `cn()` + `cva` conventions if you do edit.

### Testing Requirements
- `npx tsc --noEmit`, `npx next lint`.

## Dependencies

### Internal
- `@/lib/utils` (`cn`).

### External
- `@radix-ui/react-slot`, `@radix-ui/react-select`, `@radix-ui/react-label`,
  `class-variance-authority`, `lucide-react`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
