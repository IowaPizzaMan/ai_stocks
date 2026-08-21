# frontend/src/components/earnings/EarningsFilterBar.tsx

**Added by specs/025-earnings-page-filters.**

## Purpose
All earnings-page filter controls in one bar: a date window (presets + custom dates),
two size floors, and a big-movers toggle. Filter state lives in URL search params via
`useSearchParams` — this component owns reading and writing them; it has no props for
filter values.

## Why presets instead of a slider
The original ask was a date-range slider. A continuous drag makes every intermediate
handle position a candidate provider request once date changes must refetch (rather than
re-filter a preloaded span) — see `specs/025-earnings-page-filters/spec.md` Clarifications
and `research.md` D8. A bounded set of one-click presets fires exactly one request per
click and caches cleanly; two custom `<input type="date">` fields cover anything the
presets don't.

## Params (read/write via `useSearchParams`)
| Param | Default when absent | Reaches the server? |
|---|---|---|
| `from`, `to` | today∓2 (`getDefaultWindow()`) | Yes — on preset click or committed custom date |
| `min_rev` | `DEFAULT_MIN_REV` = 10,000,000 | No — client-side only |
| `min_eps` | `DEFAULT_MIN_EPS` = 0.01 | No — client-side only |
| `movers` | absent (off) | No — client-side only |

## Props
```typescript
interface EarningsFilterBarProps {
  visibleCount?: number;  // post-filter row count, for the FR-021 count display
  totalCount?: number;    // pre-filter row count; shown only when it differs
}
```

## Date presets
Six fixed windows, resolved fresh against "today" on each click (not memoized against a
stale value): Today, ±2 days *(default)*, Last 7 days, Next 7 days, ±2 weeks, ±1 month.
The active preset is highlighted by comparing the resolved `from`/`to` against the current
URL params — typing a custom date that matches no preset clears the highlight automatically
(FR-001b), no separate "custom mode" flag needed.

Preset clicks write `from`/`to` immediately (one click = one request). Custom date edits
debounce ~400ms before writing (`InstitutionalFlowFilterBar`'s debounce pattern) so typing
a date doesn't fire a request per keystroke (FR-027a). An inverted custom range
(`start > end`) is never written to the URL — the component shows an inline validation
message instead (FR-004).

## Size sliders + big-movers toggle
Real `<input type="range">` controls, not presets — these filter client-side
(`lib/earningsFilters.ts`) and never touch the network, so continuous dragging is free.
`min_eps` is a magnitude floor (compared against `|eps|`), so a large loss is never
filtered out by a positive-only threshold. The big-movers toggle is a plain checkbox;
checking it writes `movers=1`, unchecking removes the param entirely (kept out of the URL
when off, matching the "defaults omitted" convention used for `min_rev`/`min_eps`).

## Dependencies
- `react-router-dom` (`useSearchParams`)
