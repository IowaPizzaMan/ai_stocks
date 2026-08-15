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

Consumed by `frontend/src/hooks/useMacro.ts` → `frontend/src/pages/Macro.tsx`.

## Tests
`backend/tests/test_market.py`: breadth alignment/omission/lookback cases; flow-event ordering/limit; macro empty-collection and newest-first/field-flattening cases.
