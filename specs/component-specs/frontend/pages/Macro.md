# frontend/src/pages/Macro.tsx

## Purpose
A market-wide dashboard, decoupled from any single ticker's analysis (specs/026-macro-market-dashboard): breadth, the Treasury yield curve, the economic calendar, and the standing growth/inflation/risk backdrop — in that fixed, decreasing-time-sensitivity order (FR-005). Reached via the "Macro" entry in the main navigation, at `/macro`.

Per-sector macro commentary (produced by `agent-runner/macro_worker.py`, served by `GET /market/macro`) previously lived on this page. It moved off (FR-003) — the worker keeps running and the endpoint keeps serving sector reads for a future Sectors-page feature (FR-004); this page simply stopped consuming it.

## Layout (top to bottom)

1. **Heading** — "Macro". No page-level freshness line; each section below carries its own.
2. **Breadth panel** (`MarketFlowCard` + `BreadthDivergenceChart`) — the page's one permanent market-flow visualization (FR-002a). Renders whenever `useMarketBreadth()` has data, regardless of whether a market-flow event is currently active:
   - **With an active event** (`useMarketFlowEvents()`, ≤14-day age cutoff): tinted outline matching `divergence_type`, event headline and body.
   - **With no active event**: neutral `border-zinc-800` outline, a static "Market breadth" label, chart and divergence caption still shown.
   - The embedded `BreadthDivergenceChart` plots NYMO **and** NAMO as two lines sharing one oscillator pane on one scale (not a toggle) below the SPY pane; the divergence overlay is drawn against NYMO only.
3. **Rates & yield curve** (`Section` wrapper + `YieldCurveChart` + `SpreadTiles`, from `useTreasuryCurve()`) — the latest session's curve with month-ago/year-ago overlays on a log-scale, proportional x-axis, plus the three tracked spread tiles (value, change, inverted badge, sparkline).
4. **Economic calendar** (`Section` + `EconomicCalendarPanel`, from `useEconomicCalendar()`) — upcoming US high/medium-impact releases and what's recently reported, with a strictly neutral above/below/in-line comparison (no market-direction color or wording, FR-021b).
5. **Growth, inflation & risk backdrop** (`Section` + `IndicatorTiles`, from `useEconomicIndicators()` + `useRiskPremium()`) — the four headline tiles plus the US equity risk-premium tile, each with its own as-of date and a "lagging" marker past 90 days.
6. **Empty state** — a single "No macro data yet" message, shown only once every section's query has settled (not loading) with nothing to show (breadth, curve, calendar, and indicators all absent). Never four separate error boxes, never a flash of empty state while queries are still in flight.

Each of sections 3–5 uses the shared local `Section` component: a title plus an as-of/stale indicator (FR-006, FR-028) — `relativeTime(freshness.as_of)` or "not computed yet", with a "· stale" suffix when the last `economics_pull` run failed. Every section renders and fails independently (FR-027): one query erroring or returning nothing never prevents its siblings from rendering.

## Data
- `useMarketFlowEvents()`, `useMarketBreadth()` (`frontend/src/hooks/useMarketBreadth.ts`) — unchanged.
- `useTreasuryCurve()`, `useEconomicCalendar()`, `useEconomicIndicators()`, `useRiskPremium()` (`frontend/src/hooks/useEconomics.ts`) — four independent queries against `GET /market/treasury-curve`, `/economic-calendar`, `/economic-indicators`, `/risk-premium`; `staleTime` 1 day, no polling (constitution V).
- `useMacroReads()` (`frontend/src/hooks/useMacro.ts`) still exists and still works — just not called from this page any more.

## Components
- `frontend/src/components/feed/MarketFlowCard.tsx` — `event` prop is now optional; renders a neutral variant when absent.
- `frontend/src/components/stock/BreadthDivergenceChart.tsx` — `oscillator` prop/toggle removed; always plots both `nymo` and `namo`.
- `frontend/src/components/macro/YieldCurveChart.tsx`, `SpreadTiles.tsx`, `EconomicCalendarPanel.tsx`, `IndicatorTiles.tsx` — new, one per section, each pure-display over its endpoint's response (all arithmetic and classification happens server-side, see `specs/component-specs/backend/routers/market.md`).

## Tests
`frontend/src/pages/Macro.test.tsx`: exactly one breadth visualization renders; it renders with and without an active market-flow event; zero sector-commentary elements anywhere on the page; each of the three new sections renders below breadth with its own freshness line; the composed empty state appears only once every query has settled with nothing to show, and disappears once any one section has data; a failing query in one section does not prevent siblings from rendering (FR-027).

Per-component coverage: `BreadthDivergenceChart.test.tsx` (NAMO as a second line, toggle removed), `MarketFlowCard.test.tsx` (optional-event variants), `YieldCurveChart.test.tsx`, `SpreadTiles.test.tsx`, `EconomicCalendarPanel.test.tsx` (neutral comparison styling), `IndicatorTiles.test.tsx` (null direction omitted, no color-by-direction), plus pure-function coverage in `frontend/src/lib/yieldCurve.test.ts` and `frontend/src/lib/time.test.ts`.
