# Contract: Market-Wide Data Read API

**Feature**: `017-fmp-migration-admin` · Phase 1 output
**Consumers**: `frontend` (`useMarketOverview.ts`, `MarketOverview.tsx`) · `backend/routers/market.py`

Read-only endpoints serving collected market-wide datasets. All responses embed the freshness envelope so the frontend renders badges and empty states from one payload (FR-018) — no separate meta round-trip.

## Common envelope

Every endpoint wraps its payload:

```jsonc
{
  "data": [ … ],                       // dataset-specific rows; [] when never collected
  "freshness": {
    "last_success_at": "2026-08-15T20:31:00Z",  // null ⇒ never collected ⇒ empty state pointing to /admin
    "last_run_status": "success",               // "success" | "failed" | "never_run"
    "record_count": 11,
    "source": "fmp"
  }
}
```

## Endpoints (extend existing `routers/market.py`)

### `GET /market/sector-performance?days=1`

`data`: `[ { "date": "2026-08-15", "sector": "Technology", "change_pct": 1.42 } ]` — latest snapshot by default; `days>1` returns the trailing window for trend rendering.

### `GET /market/movers?category=gainers|losers|actives`

`data`: `[ { "ticker": "NVDA", "company": "NVIDIA Corp", "price": 182.11, "change_pct": 4.8, "volume": 51234567 } ]` — latest collected day only. Omitting `category` returns all three keyed lists: `{ "gainers": […], "losers": […], "actives": […] }`.

### `GET /market/economic-calendar?from=2026-08-15&to=2026-08-29`

`data`: `[ { "event": "CPI (YoY)", "country": "US", "event_time": "…", "estimate": 2.9, "actual": null, "previous": 3.0, "impact": "High" } ]` — defaults to today → +14 days.

### `GET /market/congress-trades?limit=50&ticker=NVDA`

> **SUPERSEDED (2026-08-22) by `specs/028-dashboard-tweaks-batch`.** This endpoint was
> never implemented — it was designed for a "Market Overview" page that was not built, so
> it has no consumer and there is no compatibility cost to relocating it. Spec 028 builds a
> dedicated Congress page and serves it from a new `backend/routers/congress.py`
> (`GET /congress/trades`, `GET /congress/summary`, `POST /congress/refresh`), adding
> `politician` and `chamber` filters this sketch lacked. See
> `specs/028-dashboard-tweaks-batch/contracts/congress-api.md` and its research R10.
>
> The **`congress_trades` collection schema below and in this spec's data-model.md remains
> canonical** — 028 reuses it unchanged rather than defining a parallel shape (Principle VI).

`data`: `[ { "chamber": "senate", "politician": "…", "ticker": "NVDA", "transaction_type": "buy", "amount_range": "$15,001–$50,000", "transaction_date": "…", "disclosure_date": "…" } ]` — newest by `disclosure_date`; `ticker` filter optional (StockDetail reuse).

### `GET /market/insider-feed?limit=50`

`data`: newest market-wide insider transactions (existing `insider_transactions` shape + envelope) — powers a Market Overview section; per-ticker insider views keep their existing endpoint.

### `GET /market/fund-holdings?fund=SPY` · `GET /market/fund-holdings/by-ticker/{ticker}`

`data`: `[ { "fund_symbol": "SPY", "fund_name": "…", "ticker": "AAPL", "shares": 178e6, "weight_pct": 6.9, "market_value": 3.2e10, "as_of_date": "…" } ]` — by fund (what does SPY hold) and inverted by ticker (which funds hold AAPL; StockDetail reuse). Replaces the retired Dataroma-backed superinvestor views' data source.

### `GET /market/news?limit=30` · `GET /stocks/{ticker}/news?limit=20`

`data`: `[ { "headline": "…", "summary": "…", "url": "…", "site": "…", "published_at": "…", "ticker": null } ]` — market-wide feeds the Feed page's news section; per-ticker feeds StockDetail. Full feed redesign is out of scope (research D12).

### `GET /market/economics`

`data`: `{ "treasury_rates": { "date": "…", "y2": 4.1, "y10": 4.6, … }, "market_risk_premium": { "country": "US", "total_equity_risk_premium": 5.2, … }, "indicators": [ { "indicator": "…", "date": "…", "value": … } ] }` — latest snapshot of each economics dataset (full-curve treasury, MRP, non-FRED indicators). Existing FRED-backed macro endpoints/views are unchanged (research D13); the economic releases calendar stays on `GET /market/economic-calendar` above.

## Rules

- Endpoints read Mongo only — a page load never triggers an FMP call (constitution IV; collection happens via admin jobs).
- Every ticker string in any payload must be navigable to `/stocks/{ticker}` by the frontend (FR-019).
- Endpoints for datasets the gap review rejects/defers are simply not built; the frontend renders sections from the endpoints that exist. No feature-flag machinery (constitution V).
