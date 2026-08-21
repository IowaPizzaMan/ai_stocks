# backend/routers/market.py

## Purpose
Read-only views over market-wide (ticker-less) data the agent-runner already computed and cached — no computation happens in this router. Prefix: `/market`.

## Endpoints

### `GET /market/breadth`
Cached NYMO/NAMO oscillator series + SPY closes + current/resolved breadth divergences. `lookback_days` query param (default 60, 10–250). Source: `breadth_cache`, `breadth_meta`, `breadth_divergences` (written by `agent-runner/breadth_worker.py`).

### `GET /market/flow-events`
Market-wide feed events (currently breadth divergences), newest first, `limit` query param (default 5, 1–50). Ticker-less, so these ride their own pinned block rather than the per-ticker analysis feed. Source: `market_flow_events`.

### `GET /market/macro`
Every sector's macro/economic read, newest `computed_at` first. Source: `macro_analysis_cache`, written by `agent-runner/macro_worker.py` — **not** by any per-ticker analysis (specs/020-surface-macro-ui decoupled macro from `crew.py` entirely). `sectors: []` and `as_of: null` on an empty collection — never an error.

```json
{
  "sectors": [
    {
      "sector": "Technology",
      "computed_at": "2026-08-14T21:03:11Z",
      "inflation_impact": { "trend": "stable", "impact_on_sector": "...", "cpi_latest": 330.1 },
      "rate_impact": { "direction": "holding", "impact_on_valuation": "...", "fed_funds_rate": 4.25 },
      "growth_backdrop": { "recession_signal": "mild", "commentary": "...", "yield_curve_spread": 0.4, "curve_inverted": false },
      "consumer_backdrop": "...",
      "sector_rotation_signal": "...",
      "overall_macro_signal": "neutral",
      "confidence": "medium"
    }
  ],
  "as_of": "2026-08-14T21:03:11Z"
}
```

Consumed by `frontend/src/hooks/useMacro.ts`. As of specs/026-macro-market-dashboard, no page renders sector reads any more (the Macro page moved to a market-wide dashboard, FR-003) — the worker keeps producing them and this endpoint keeps serving them for a future Sectors-page feature (FR-004).

---

## Economics dashboard — specs/026-macro-market-dashboard

Read-only shapes over what `agent-runner/tools/economics.py`'s `economics_pull` job wrote to `treasury_rates`, `economic_calendar_events`, `economic_indicators`, `market_risk_premium` — no provider call belongs on this request path (constitution IV). All four always return 200; a missing or failed `economics_pull` run shows up in the freshness envelope (`as_of`/`stale`), never as an HTTP error (FR-028). Full response shapes: [specs/026-macro-market-dashboard/contracts/macro-api.md](../../../026-macro-market-dashboard/contracts/macro-api.md).

### `GET /market/treasury-curve`
The latest session's yield curve (1M–30Y) with month-ago/year-ago overlays, plus the three tracked spreads (10y–2y, 30y–10y, 10y–3m) — value, change vs. the prior *stored* session, inverted flag, and a trend series. `lookback_days` query param (default 180, 30–750) bounds only the spread trend series, never the curve itself. All arithmetic (`spread_bps`, `spread_series`, `session_change`, `is_inverted`, `nearest_session`, `align_curve`) is computed here, not stored — `treasury_rates` holds raw provider snapshots only.

### `GET /market/economic-calendar`
Upcoming US high/medium-impact releases (`forward_days`, default 14) and what's reported in the trailing window (`back_days`, default 7), split on `date > now` — an event later today is still "upcoming" (FR-023). Reported rows carry a *mechanical* `classify()`/`surprise()` comparison (above/below/in_line vs. estimate) with no market-direction polarity anywhere (FR-021b) — `null` when no estimate was published, never defaulted to `in_line`. Times are labeled `"America/New_York"` explicitly.

### `GET /market/economic-indicators`
The four headline tiles (growth/GDP, inflation, employment, policy rate) plus optional consumer-strength tiles, in that fixed order. `direction()`/`is_lagging()` are computed from the two most recent stored readings per series — `direction` is `null` (not `"flat"`) when no prior reading has been retained yet, and `lagging` is `true` once a reading's period is more than 90 days old (expected to be the normal case for this source, not an error). A series never fetched is omitted from the array entirely.

### `GET /market/risk-premium`
The single stored US row (`total_equity_risk_premium`, `country_risk_premium`) — never an array. The provider supplies no date field for this one, so `collected_at` (when the row was written) is the as-of proxy.

## Tests
`backend/tests/test_market.py`: breadth alignment/omission/lookback cases; flow-event ordering/limit; macro empty-collection and newest-first/field-flattening cases.
`backend/tests/test_market_economics.py`: contract tests for all four economics endpoints — curve/spread math against known inputs, null-maturity and missing-history edge cases, calendar upcoming/reported split and neutral classification, indicator direction/lagging/omission rules, risk-premium single-row shape.
