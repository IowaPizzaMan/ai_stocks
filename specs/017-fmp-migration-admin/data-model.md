# Data Model: FMP Paid-Tier Migration & Admin Data Operations

**Feature**: `017-fmp-migration-admin` · **Date**: 2026-08-15 · Phase 1 output

MongoDB, database `stockai`. Collection/field name constants are duplicated in `backend/db.py` and `agent-runner/tools/db.py` (constitution V/VI); this file and the contracts are the written source of truth both must match.

## Modified collections

> **Correction (found during implementation)**: the `price_history` collection described below turned out to be written only by dead code (`agent-runner/data_fetcher.py`, deleted per tasks.md T029) — the live price path (`tools/price.py`) has never persisted bars to Mongo; it fetches fresh every call. There is no live deep price archive to preserve or reconcile. See research.md D3's implementation-time correction. The subsection below is kept as the design for *if* a persistent price cache is added later, not as something this migration builds.

### `work_queue` (extended — backward compatible)

Existing documents are unchanged; `job_type` is additive with an implicit default.

| Field | Type | Notes |
|---|---|---|
| `job_type` | string, optional | Absent or `"ticker_analysis"` ⇒ existing per-ticker crew run. New values: `"breadth_refresh"`, `"earnings_calendar_scan"`, `"fmp_entitlement_probe"`, `"sector_performance_pull"`, `"market_movers_pull"`, `"economics_pull"`, `"congress_trades_pull"`, `"insider_feed_pull"`, `"fund_holdings_pull"`, `"market_news_pull"` (final registry pinned in [contracts/admin-jobs-api.md](contracts/admin-jobs-api.md); no `superinvestor_pull` — Dataroma is retired, research D11) |
| `ticker` | string | **Required for** `ticker_analysis`; **absent** for admin jobs |
| `status` | enum | unchanged: `pending → running → done | failed` |
| `source` | string | unchanged (`manual`, `earnings_scanner`, …) + `"admin"` for admin-page triggers |
| `error` | string | unchanged — human-readable failure reason (FR-012) |
| `created_at / updated_at / started_at / completed_at` | datetime | unchanged lifecycle timestamps |

**New index**: `(job_type, created_at DESC)` — run-history queries. **Duplicate-run rule**: enqueue refused when a document with same `job_type` (admin jobs) or same `ticker` (ticker jobs, existing rule) is `pending|running`.

**State transitions** (unchanged, now shared by admin jobs): `pending → running` (worker claim) → `done` | `failed`; `running → pending` via stale-recovery after 30 min. Longer-running jobs use the handler table's optional `stale_minutes` override.

### `price_history` (semantics extended)

| Field | Type | Notes |
|---|---|---|
| *(existing)* `ticker, date, open, high, low, close, volume` | — | unchanged; `close` remains split+dividend adjusted (D3 convention) |
| `source` | string, optional | Absent ⇒ legacy yfinance-era document; `"fmp"` on all new documents |

No migration/rewrite of existing documents (FR-006). Uniqueness on `(ticker, date)` unchanged — delta-append only.

## New collections

### `fmp_entitlements` (probe output — D1)

One document per endpoint family, upserted per probe run.

| Field | Type | Notes |
|---|---|---|
| `family` | string (unique) | e.g. `"eod_prices"`, `"intraday_1h"`, `"batch_quote"`, `"insider_trading"`, `"form_13f"`, `"senate_house"`, `"sector_performance"`, `"movers"`, `"economic_calendar"`, `"earnings_calendar"`, `"analyst_grades"`, `"etf_holdings"`, `"transcripts"` |
| `probe_endpoint` | string | exact stable path tested |
| `result` | enum | `entitled` \| `payment_required` \| `error` |
| `http_status` | int | raw status observed |
| `checked_at` | datetime | |

### `dataset_meta` (freshness envelope — D9)

One document per market-wide dataset (FR-015/FR-018).

| Field | Type | Notes |
|---|---|---|
| `dataset` | string (unique) | matches admin `job_type` minus `_pull` suffix where sensible; pinned in contracts |
| `last_success_at` | datetime, nullable | null ⇒ never collected ⇒ frontend empty state |
| `last_run_status` | enum | `success` \| `failed` \| `never_run` |
| `record_count` | int | rows written by last successful run |
| `source` | string | `"fmp"`, `"dataroma"` |

### `sector_performance`

| Field | Type | Notes |
|---|---|---|
| `date` | date | snapshot day; unique with `sector` |
| `sector` | string | |
| `change_pct` | float | day change |
| `source`, `collected_at` | — | provenance envelope (D9) |

### `market_movers`

| Field | Type | Notes |
|---|---|---|
| `date` | date | unique with `(category, ticker)` |
| `category` | enum | `gainers` \| `losers` \| `actives` |
| `ticker`, `company` | string | ticker links to StockDetail (FR-019) |
| `price`, `change_pct`, `volume` | float | |
| `source`, `collected_at` | — | envelope |

### `economic_calendar_events`

| Field | Type | Notes |
|---|---|---|
| `event_id` | string (unique) | provider id or hash of (event, country, event_time) |
| `event`, `country` | string | US-focused filter at collect time |
| `event_time` | datetime | |
| `estimate`, `actual`, `previous` | float, nullable | filled as released |
| `impact` | string, nullable | provider's importance grading if present |
| `source`, `collected_at` | — | envelope |

### `congress_trades` (supersedes empty `congressional_trades` if unused)

| Field | Type | Notes |
|---|---|---|
| `trade_id` | string (unique) | hash of (chamber, name, ticker, transaction_date, amount_range) |
| `chamber` | enum | `senate` \| `house` |
| `politician` | string | |
| `ticker` | string, nullable | some disclosures are non-equity; kept for completeness, filtered in UI |
| `transaction_type` | string | buy/sell/exchange as provided |
| `amount_range` | string | disclosed band, not exact value |
| `transaction_date`, `disclosure_date` | date | |
| `source`, `collected_at` | — | envelope |

> Note: implementation must check whether the existing `congressional_trades` collection (indexed in `data_fetcher.ensure_indexes`, fed by the deferred Quiver integration) holds data; if empty, retire the constant in favor of `congress_trades`; if populated, reuse it and add the new fields (FR-016: one home per dataset).

### `fund_holdings` (replaces Dataroma superinvestor collection — D11)

| Field | Type | Notes |
|---|---|---|
| `fund_symbol` | string | ETF/fund identifier; unique with `(ticker, as_of_date)` |
| `fund_name` | string | |
| `ticker` | string | held asset — links to StockDetail (FR-019) |
| `shares`, `weight_pct`, `market_value` | float | as provided |
| `as_of_date` | date | holdings report date |
| `source`, `collected_at` | — | envelope (D9); `source: "fmp"` |

Legacy `SUPERINVESTOR_MOVES_CACHE` / `DATAROMA_META` collections: retained read-only, no new writes; UI marks them stale via freshness.

### `stock_news` (per-ticker, fetched during retrieval — D12)

| Field | Type | Notes |
|---|---|---|
| `article_id` | string (unique) | provider id or hash of (ticker, url) |
| `ticker` | string | indexed with `published_at DESC` |
| `headline`, `summary`, `url`, `site` | string | |
| `published_at` | datetime | delta-fetch cursor per ticker |
| `source`, `collected_at` | — | envelope; `source: "fmp"` |

### `market_news` (market-wide job — D12)

Same shape as `stock_news` minus `ticker` (nullable when FMP tags one); unique on `article_id` (hash of url). Feeds the Feed-page market-news section.

### `company_info` (per-ticker, 90-day refresh — D14)

| Field | Type | Notes |
|---|---|---|
| `ticker` | string (unique) | one document per ticker, replaced on refresh |
| `name`, `description`, `sector`, `industry`, `exchange`, `ceo`, `website`, `logo_url` | string | from FMP company-info/profile route |
| `employees`, `shares_outstanding`, `float_shares` | number, nullable | as provided |
| `refreshed_at` | datetime | 90-day staleness gate (financials discipline) |
| `source` | string | `"fmp"` |

### `treasury_rates` (economics — D13)

| Field | Type | Notes |
|---|---|---|
| `date` | date (unique) | one full-curve snapshot per day |
| `m1, m3, m6, y1, y2, y3, y5, y7, y10, y20, y30` | float, nullable | maturities as provided by FMP |
| `source`, `collected_at` | — | envelope. FRED's DGS10/DGS2 series remain canonical for macro-tab history (D13 seam) |

### `market_risk_premium` (economics — D13)

| Field | Type | Notes |
|---|---|---|
| `country` | string | unique with `date`; US-filtered at collect time unless all-country is cheap |
| `date` | date | |
| `total_equity_risk_premium`, `country_risk_premium` | float | |
| `source`, `collected_at` | — | envelope |

### `economic_indicators` (economics — D13, non-FRED series only)

| Field | Type | Notes |
|---|---|---|
| `indicator` | string | unique with `date`; ~~only series NOT in `tools/macro.py` DEFAULT_INDICATORS (FR-016)~~ — **amended, see note below** |
| `date` | date | |
| `value` | float | |
| `source`, `collected_at` | — | envelope |

> **Amendment (2026-08-21, specs/026-macro-market-dashboard)**
>
> Two shapes in this section were written before the endpoints were exercised, and 026 corrected them:
>
> 1. **`economic_indicators` — the non-FRED-only restriction is lifted.** 026's clarification session selected FMP `economic-indicators` as the *single* source for the Macro page's growth / inflation / employment / policy-rate tiles, which overlap FRED's `GDP`/`CPIAUCSL`/`UNRATE`/`FEDFUNDS`. This collection may now hold series that duplicate `tools/macro.py` DEFAULT_INDICATORS. Nothing read or wrote the collection at the time of amendment, so there is no migration. `tools/macro.py`'s FRED path is unchanged and continues to serve the sector macro worker; no code blends the two sources. See 026 research.md D3 and plan.md Complexity Tracking.
>
> 2. **`market_risk_premium` has no provider `date` field.** The live response carries only `country`, `continent`, `countryRiskPremium`, `totalEquityRiskPremium`. The unique key is `country` alone, and `collected_at` serves as the as-of date. See 026 research.md D5.

### `insider_feed` note

The market-wide insider feed (`insider_feed_pull`) upserts into the **existing** `insider_transactions` collection (same unique key), adding the envelope fields — one home for insider data (FR-016). `dataset_meta.dataset = "insider_feed"` tracks the market-wide job's freshness separately from per-ticker pulls.

## Entities without new collections

- **Admin Job (registry)**: static constant list in both services — `name` (= `job_type`), `description`, `dataset` (nullable — probe job feeds `fmp_entitlements`), `stale_minutes` override. Not stored in Mongo; run state lives in `work_queue`, data state in `dataset_meta`.
- **Job Run**: a `work_queue` document with `job_type` set — no separate collection.
- **Gap-Review Decision**: documentation artifact ([fmp-gap-review.md](fmp-gap-review.md)), not runtime data; the runtime reflection of its tier-gated subset is `fmp_entitlements`.

## Validation rules

- Admin enqueue: reject unknown `job_type` (404 from registry lookup); reject duplicate active job (409-style body, FR-011).
- Collectors: writes are idempotent upserts on each collection's unique key — re-running a job never duplicates rows (FR-016).
- Price delta-append: reject/log any FMP bar whose `(ticker, date)` already exists with a differing close beyond the D3 drift threshold instead of silently overwriting.
- `dataset_meta.last_success_at` is written only after all writes for the run committed — a failed run must not advance freshness.
