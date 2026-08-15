# Quickstart: Validating FMP Migration & Admin Operations

**Feature**: `017-fmp-migration-admin` · Phase 1 output

Runnable scenarios proving the feature end-to-end. Contracts: [admin-jobs-api.md](contracts/admin-jobs-api.md) · [market-data-api.md](contracts/market-data-api.md) · [fmp-migration-map.md](contracts/fmp-migration-map.md). Data shapes: [data-model.md](data-model.md).

## Prerequisites

- `.env` contains the paid-tier `FMP_API_KEY` (plus existing Mongo/Finnhub/FRED keys)
- Stack up: `docker compose up -d` (mongodb, backend, frontend, agent-runner, ollama)
- Test suites runnable locally: `pytest backend/`, `pytest agent-runner/`, `npm test` in `frontend/`, `ruff check backend/ agent-runner/ scripts/`

## Scenario 0 — Entitlement probe (verification of the remaining ambiguous families)

1. Open `/admin` in the frontend → trigger **fmp_entitlement_probe** (or `curl -X POST localhost:8000/admin/jobs/fmp_entitlement_probe/run`).
2. After completion: `db.fmp_entitlements.find()` has one row per family from the migration map, each `entitled`/`payment_required`.
3. **Expected**: `eod_prices` is `entitled` (hard requirement); batch-quote, intraday-resolution, and analyst-grades results recorded — these decide D4's breadth path and row 2/5 of the migration map. User-verified families (insider, senate/house, fund holdings, news, company info, economics) should probe `entitled`; a mismatch is worth investigating before proceeding.

## Scenario 1 — Price migration (US1 / SC-001–003)

1. Pick a ticker with existing deep history (e.g. AAPL) and one that failed under yfinance (check `ticker_index` for `removed_from_market` false-positives).
2. Trigger analysis from the UI (or `POST /queue/AAPL`).
3. **Expected**: run completes; new `price_history` rows carry `source: "fmp"`; pre-existing rows (no `source`) untouched; chart in StockDetail renders continuously across the migration date with no visible seam; the previously failing ticker now loads history.
4. `grep -ri yfinance backend/ agent-runner/ scripts/ --include='*.py'` → zero code hits; `yfinance` absent from both `requirements.txt`.
5. Full regression: `pytest agent-runner/ backend/` and frontend `npm test` all green.

## Scenario 2 — Breadth under FMP (US1)

1. Trigger **breadth_refresh** from `/admin`.
2. **Expected**: job reaches `done` in ≤5 min; breadth chart (NYMO/NAMO) shows a new datapoint continuous with history; agent-runner log shows throttled FMP calls, no rate-limit errors.

## Scenario 3 — Admin section (US2 / SC-004)

1. From app load: nav → **Admin** (≤3 clicks to any trigger).
2. **Expected**: every registry job listed with description, last-run time/outcome, freshness.
3. Trigger **fund_holdings_pull**; while it runs, its button is disabled with reason; re-POSTing returns `already_queued` with the same job id (FR-011).
4. Kill the network mid-run (or point the FMP base URL at a black hole) and re-run: job ends `failed` with a human-readable `error` shown in the UI (FR-012).
5. Status appears on page reload / manual refresh only — devtools network tab shows **no** background polling.

## Scenario 4 — Market-wide collection + visualization (US3/US4 / SC-006)

1. Before any pull: open **Market Overview** → each section shows an empty state linking to `/admin` (FR-018) — no broken charts.
2. Trigger `sector_performance_pull`, `market_movers_pull`, `economics_pull`, `congress_trades_pull`, `insider_feed_pull`, `fund_holdings_pull`, `market_news_pull`.
3. **Expected**: each collection populated with envelope fields (`source`, `collected_at`); `dataset_meta` rows updated; Market Overview sections render with freshness badges; clicking any ticker (e.g. in movers or fund holdings) navigates to its StockDetail (FR-019).
4. Re-trigger one pull: `record_count` stable or grown, **no duplicate rows** (idempotent upserts, FR-016).
5. **News**: Feed page shows a market-news section with fresh articles; run one ticker analysis and confirm `stock_news` gained rows for it and StockDetail lists them (FR-022). Devtools confirms no polling.
6. **Economics seam (D13)**: existing macro tab (FRED-backed) renders unchanged; `GET /market/economics` returns treasury curve + MRP; `economic_indicators` contains **no** series from `macro.py`'s DEFAULT_INDICATORS list (FR-016/FR-024).
7. **Dataroma retirement (FR-021)**: admin lists no superinvestor job; agent-runner log shows no Playwright/Dataroma activity; any legacy superinvestor view renders stored data with a stale/retired freshness note.

## Scenario 5 — Budget guard & degradation (SC-007)

1. Set `FMP_DAILY_SOFT_CAP=5` in `.env`, restart agent-runner.
2. Trigger a breadth refresh (needs ≫5 calls).
3. **Expected**: guard logs the cap breach, serves stale cache where available, job completes (possibly with stale note) or fails with a clear reason — **no crash, no unhandled exception in logs**; analyses on cached tickers still run.
4. Reset the cap; confirm normal behavior returns with no code change (FR-005 / free-tier downgrade edge case).

## Scenario 6 — Documentation gate (FR-007, FR-013)

- `specs/DATA_SOURCES.md`: yfinance section removed/annotated as retired; coverage map has no "yfinance" primary; FMP section rewritten against `stable/` paths.
- [fmp-gap-review.md](fmp-gap-review.md): every family has a final decision; zero crypto adopts; probe results appended.
