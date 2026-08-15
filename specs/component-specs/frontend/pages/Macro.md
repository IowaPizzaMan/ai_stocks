# frontend/src/pages/Macro.tsx

## Purpose
Economy-wide context, decoupled from any single ticker (specs/020-surface-macro-ui): the market-breadth (NYMO/NAMO) divergence cards — relocated here from the Stocks page — plus every sector's macro read, produced independently by the agent-runner's `macro_worker.py` and served by `GET /market/macro`. Reached via the "Macro" entry in the main navigation, at `/macro`.

## Layout (top to bottom)
1. **Heading** — "Macro" plus an `as_of` freshness line (newest sector read's `computed_at`, via `relativeTime`).
2. **Market breadth section** — pinned `MarketFlowCard`s (`useMarketFlowEvents`, same ≤14-day age filter previously applied on the Stocks/Feed page) and `BreadthDivergenceChart` (`useMarketBreadth`, rendered whenever breadth data exists).
3. **Sector reads grid** — one card per `sectors[]` entry from `useMacroReads()`: sector name, `SignalBadge` for `overall_macro_signal`, `confidence`, inflation/rate/growth/consumer/rotation commentary, available hard numbers (CPI, Fed funds, yield-curve spread/inversion), and a per-card freshness line.
4. **Empty state** — shown only when there are no pinned events, no breadth data, and no sector reads; explains that macro reads appear after the first worker sweep. Never an error state.

## Data
- `useMacroReads()` (`frontend/src/hooks/useMacro.ts`) → `GET /market/macro`, `staleTime` 1 day, no polling.
- `useMarketFlowEvents()`, `useMarketBreadth()` (`frontend/src/hooks/useMarketBreadth.ts`) — unchanged, reused from the former Feed page.

## Tests
`frontend/src/pages/Macro.test.tsx`: sector cards render with commentary/signal; freshness indicator present; a stale sector read (>7 days) still renders with visible age; breadth cards render alongside sector reads; empty state renders with no error when nothing is available.
