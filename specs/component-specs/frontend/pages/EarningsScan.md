# frontend/src/pages/EarningsScan.tsx

**Superseded by specs/025-earnings-page-filters — rewritten below.** The manual scan
trigger, `ScanControls`, `EarningsCalendarTable` (scored-candidate table), and
`EarningsCandidateCard` are removed from this page. See KNOWN_ISSUES.md for the now-dormant
backend scan endpoints this leaves behind.

## Purpose
URL: `/earnings`. Not conversational. Auto-loading, date-windowed earnings calendar: on
arrival, with no button press, shows companies reporting today−2 through today+2, ordered
by market cap, with actual EPS/revenue and a beat/miss surprise for anything already
reported. Filters live in URL search params.

## Layout
```
┌─────────────────────────────────────────────────────────────┐
│  Earnings                                                    │
├─────────────────────────────────────────────────────────────┤
│  [EarningsFilterBar]  — presets, custom dates, sliders,      │
│                          big-movers toggle, window/count      │
│  [staleness banner]   — only when calendar.data.stale         │
│  [EarningsTable]       — always market-cap-sorted             │
│  [empty-state message] — date-window-empty or filters-emptied │
└─────────────────────────────────────────────────────────────┘
```

## State
Filter state lives entirely in URL search params (`from`, `to`, `min_rev`, `min_eps`,
`movers`), read via `useSearchParams`. The only component state is the local
`queuedTickers: Set<string>` set for the Queue button's optimistic "Queued" badge —
identical to the old page's pattern.

## Key Behaviors

### 1. Auto-load, no trigger
`useEarningsCalendar(from, to)` fires on mount with the resolved window (defaulting to
today∓2 via `EarningsFilterBar`'s `getDefaultWindow()` when no URL params are present).
There is no scan button anywhere on this page.

### 2. Client-side filtering
`filterEntries(entries, { minRev, minEps, moversOnly })`
(`frontend/src/lib/earningsFilters.ts`) runs in a `useMemo` over the fetched entries. It
never triggers a request — only a `from`/`to` change does that.

### 3. Click ticker → enqueue directly
Unchanged from the old page: `EarningsTable`'s Queue button calls
`useAnalyzeTickers().mutate([ticker])`, which posts to `/earnings/analyze`. The ticker
symbol itself is now a `<Link to="/stock/:ticker">` and does not trigger the Queue action
(FR-024) — the two are separate interactive elements in the same cell.

### 4. Degraded states
- `calendar.isError` → explicit error message, not an empty table.
- `calendar.data.stale` → amber banner above the table; rows still render.
- `rawEntries.length === 0` → "no companies report in this window" (date-driven empty
  state).
- `filteredEntries.length === 0 && rawEntries.length > 0` → distinguishes the big-movers
  toggle as the cause (FR-016d) from the size sliders.
- `calendar.isFetching && !isInitialLoad` → prior rows stay visible with a small "Updating
  window…" indicator (FR-027c) rather than blanking the table; enabled by
  `useEarningsCalendar`'s `placeholderData: (previous) => previous`.

## Sub-components
- `EarningsFilterBar` (own spec below) — date presets/custom dates, size sliders,
  big-movers toggle.
- `EarningsTable` (own spec below) — the single results table.

## Dependencies
- `useEarningsCalendar`, `useAnalyzeTickers` (`hooks/useEarningsScan.ts`)
- `filterEntries` (`lib/earningsFilters.ts`)
