# Contract: Frontend Pages & Navigation

**Feature**: `specs/020-surface-macro-ui`

## Navigation (`Navbar.tsx`, `App.tsx`)

| Link | Route | Page | Change |
|---|---|---|---|
| Stocks | `/` | `pages/Stocks.tsx` | Renamed from "Feed" / `Feed.tsx`; route unchanged (FR-008) |
| Macro | `/macro` | `pages/Macro.tsx` | New (FR-005) |
| Institutional Flow | `/institutional-flow` | unchanged | — |
| Sectors | `/sectors/:sector?` | unchanged | — |
| Earnings | `/earnings` | unchanged | — |

## Stocks page (renamed from Feed) — FR-008/009/010

- Document title: `StockAI — Stocks`.
- Renders **only**: `FilterBar` + signal-grouped `AnalysisTile` board + skeleton/error/empty states + infinite scroll. 
- Removed: `MarketFlowCard` pinned block, `useMarketFlowEvents`, `useMarketBreadth`, the `MARKET_EVENT_MAX_AGE_DAYS` filter logic (moves to Macro page).
- Everything else byte-for-byte behavior-identical: URL filter params, `groupBySignal`, intersection-observer paging, empty-state copy.

**Tests** (`Stocks.test.tsx`, from `Feed.test.tsx`): existing filtering/grouping/empty-state cases pass unchanged; breadth-card rendering cases move to `Macro.test.tsx`; add an assertion that no market-flow card renders even when flow events exist.

## Macro page (new) — FR-006/007

Layout, top to bottom:

1. **Heading** with `as_of` freshness line (from `useMacroReads`).
2. **Market breadth section**: pinned `MarketFlowCard`s (via `useMarketFlowEvents`, same ≤14-day age filter previously applied on Feed) and the `BreadthDivergenceChart` (via `useMarketBreadth`) — the chart renders whenever breadth data exists, so the NYMO/SPY relationship stays inspectable even with no divergence event in force (FR-007: cards *moved*, not duplicated).
3. **Sector reads grid**: one card per `sectors[]` entry from `GET /market/macro`, each showing: sector name, `overall_macro_signal` (existing `SignalBadge`), confidence, inflation trend + sector commentary, rate direction + valuation commentary, recession signal + commentary, consumer backdrop, rotation signal, available hard numbers (CPI, Fed funds, curve spread/inversion), and a `computed_at` freshness line (relative time, consistent with the app's `relativeTime` util).
4. **Empty state** (no sector reads AND no breadth data): explains that macro reads appear after the first refresh runs — no error styling.

- Document title: `StockAI — Macro`.
- Data: `useMacroReads()` (new, `staleTime` 1 day), `useMarketBreadth()`, `useMarketFlowEvents()` — all fetch-on-navigation, no polling (constitution).
- Partially formed reads: render present fields, omit absent ones (spec edge case).

**Tests** (`Macro.test.tsx`): sector cards render from mocked `/market/macro`; freshness text present per card; breadth cards render from mocked flow events; empty state renders when both sources are empty; stale read (> 7 days) still renders with its age shown.

## Types (`api/types.ts`)

- Add `SectorMacroRead = MacroReport & { sector: string; computed_at: string }` and `MacroReads = { sectors: SectorMacroRead[]; as_of: string | null }`.
- `Analysis.sub_reports.macro?: MacroReport` stays (historical docs) but is rendered nowhere.
