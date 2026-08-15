# Tasks: FMP Paid-Tier Migration & Admin Data Operations

**Input**: Design documents from `/specs/017-fmp-migration-admin/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md), [fmp-gap-review.md](fmp-gap-review.md)

**Tests**: Included and REQUIRED — the project constitution's Principle I ("Test-First & Comprehensive Coverage") is marked NON-NEGOTIABLE and was already relied on as a PASS condition in plan.md's Constitution Check. Every tool/router/hook change below ships with its test task.

**Organization**: Tasks are grouped by user story (P1–P4 from spec.md) so each can be implemented, tested, and demoed independently, in priority order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 (migration) · US2 (admin section) · US3 (gap review + new datasets) · US4 (visualization)
- Every task names its exact file path(s)

## Path Conventions

Existing three-service layout — no new services: `agent-runner/` (Python collectors + queue worker), `backend/` (FastAPI routers), `frontend/src/` (React). See [plan.md](plan.md) Project Structure for the full tree.

---

## Phase 1: Setup

**Purpose**: New settings, module skeletons, and shared collection-name constants that every later phase reads.

- [X] T001 [P] Add `fmp_calls_per_minute` (default 250) and `fmp_daily_soft_cap` (default 0 = disabled) settings to `agent-runner/settings.py`
- [X] T002 [P] Create `agent-runner/tools/fmp_client.py` module skeleton: `FMP_BASE = "https://financialmodelingprep.com/stable/"`, imports, module docstring referencing research D1/D5
- [X] T003 [P] Add new collection name constants to `agent-runner/tools/db.py`: `FMP_ENTITLEMENTS`, `DATASET_META`, `SECTOR_PERFORMANCE`, `MARKET_MOVERS`, `ECONOMIC_CALENDAR_EVENTS`, `TREASURY_RATES`, `MARKET_RISK_PREMIUM`, `ECONOMIC_INDICATORS`, `CONGRESS_TRADES`, `FUND_HOLDINGS`, `STOCK_NEWS`, `MARKET_NEWS`, `COMPANY_INFO` (per [data-model.md](data-model.md))
- [X] T004 [P] Mirror the same collection name constants in `backend/db.py` (constitution Principle VI — keep in sync)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared plumbing every user story depends on — the FMP client, `work_queue`'s `job_type` dispatch, and the freshness envelope. No user-story-specific surface yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement a token-bucket per-minute throttle + soft daily cap + fail-soft degrade/log in `agent-runner/tools/fmp_client.py`, replacing/extending `track_fmp_call()` from `agent-runner/tools/db.py` (research D5) — depends on T001–T003
- [X] T006 Move `fmp_get()` from `agent-runner/tools/financials.py` into `agent-runner/tools/fmp_client.py`; update the `from tools.financials import fmp_get` import in `agent-runner/tools/breadth.py` and the call site in `agent-runner/tools/financials.py` itself — depends on T005
- [X] T007 [P] Implement `fmp_entitlement_probe()` in `agent-runner/tools/fmp_client.py`: one minimal request per endpoint family (per [contracts/fmp-migration-map.md](contracts/fmp-migration-map.md) probe-family column), upserting `{family, probe_endpoint, result, http_status, checked_at}` into the `fmp_entitlements` collection (research D1) — depends on T005, T006
- [X] T008 [P] Add `job_type` field support + `(job_type, created_at DESC)` index to `ensure_indexes()` in `agent-runner/tools/db.py`
- [X] T009 [P] Mirror the `work_queue` index addition in `ensure_indexes()` in `backend/db.py`
- [X] T010 [P] Implement a `write_dataset_meta(dataset, status, record_count, source)` helper in `agent-runner/tools/db.py` that upserts the `dataset_meta` envelope, only advancing `last_success_at` on a successful run (research D9, data-model.md validation rule)
- [X] T011 [P] Create `agent-runner/tools/admin_jobs.py` with `JOB_HANDLERS: dict[str, Callable] = {}` and `STALE_MINUTES: dict[str, int] = {}` (populated incrementally by US2/US3)
- [X] T012 Implement `job_type` dispatch in `claim_and_run_next()` in `agent-runner/queue_worker.py`: absent/`"ticker_analysis"` keeps today's crew-run path unchanged; a present `job_type` looks up `tools.admin_jobs.JOB_HANDLERS`, calls the handler, and writes `dataset_meta` via T010 on success/failure; an unrecognized `job_type` marks the job `failed` with `error: "no handler for job_type"` — depends on T008, T010, T011
- [X] T013 Implement the per-job `stale_minutes` override (from `admin_jobs.STALE_MINUTES`, default 30) in `recover_stale_jobs()` in `agent-runner/queue_worker.py` — depends on T011, T012

**Checkpoint**: Foundation ready — FMP client, dispatch, and freshness plumbing all work with zero registered jobs. User story implementation can now begin.

---

## Phase 3: User Story 1 - Yahoo Finance Fully Replaced by FMP (Priority: P1) 🎯 MVP

**Goal**: Every yfinance call site (price, breadth, earnings history, delisting check, institutional holders) is re-sourced from FMP or explicitly, consciously dropped; `yfinance` is removed from both services.

**Independent Test**: Run analysis on a previously-Yahoo-failing ticker and confirm price history now loads; run breadth refresh and confirm sane NYMO/NAMO output; confirm zero `yfinance` code references remain (quickstart Scenarios 1–2).

### Tests for User Story 1

- [ ] T014 [P] [US1] Rewrite FMP fakes in `agent-runner/tests/test_price.py`: mock `historical-price-eod/full` and `quote` instead of yfinance; add a case proving weekly/monthly/quarterly/yearly resample from one daily fetch
- [ ] T015 [P] [US1] Rewrite FMP fakes in `agent-runner/tests/test_breadth.py`: mock batch quote / per-symbol EOD delta instead of `yf.download`
- [ ] T016 [P] [US1] Update `agent-runner/tests/test_institutional.py` to assert read-only/no-refresh behavior: no network call, cache-only serve, staleness flag present
- [X] T017 [P] [US1] Update FMP fakes in `agent-runner/tests/test_earnings_calendar.py` (history function only) and `agent-runner/tests/test_financials.py` (earnings/estimates block)
- [X] T018 [P] [US1] Add `agent-runner/tests/test_fmp_client.py`: throttle behavior under burst load, soft-daily-cap fail-soft degrade (stale cache + log, no raise), entitlement-probe result parsing for `entitled`/`payment_required`/`error`
- [X] T019 [P] [US1] Update FMP fakes in `backend/tests/test_price.py` (replace yfinance mocks)

### Implementation for User Story 1

- [X] T020 [US1] Implement an FMP EOD full-history fetch + delta-append helper (in `agent-runner/tools/fmp_client.py` or `tools/price.py`) returning an OHLCV DataFrame shaped like yfinance's (`Open/High/Low/Close/Volume`, DatetimeIndex) so downstream consumers need no changes — depends on T005, T006
- [X] T021 [US1] Replace `_history()` in `agent-runner/tools/price.py` to call T020's fetch; resample weekly/monthly/quarterly/yearly locally from one 5-year daily fetch instead of the current 3 separate network calls in `get_price_history()` — depends on T020
- [X] T022 [US1] ~~Price-continuity reconciliation~~ — SCOPE CORRECTED during implementation: `tools/price.py` never persisted bars to Mongo (only the now-deleted dead-code `data_fetcher.py` did — see T029), so there is no live deep history to reconcile against. No reconciliation code needed; research D3 and data-model.md updated to record this finding — depends on T020
- [X] T023 [US1] [P] Replace `is_ticker_valid()` in `agent-runner/tools/price.py` with an FMP `quote` check, preserving the same True/False contract `crew.py` relies on (migration-map row 7) — depends on T020
- [X] T024 [US1] Replace `_download_closes()` and `_download_spy()` in `agent-runner/tools/breadth.py` with FMP batch quote (if T007 probes `batch_quote` entitled) or the throttled per-symbol EOD delta fallback, preserving the wide-Close-DataFrame / Series shape so `compute_mcclellan()`/divergence code is untouched (research D4) — depends on T005–T007, T020. Implemented the safe per-symbol fallback directly (batch-quote optimization deferred, noted in code comment)
- [X] T025 [US1] Replace yfinance in `get_earnings_history()` in `agent-runner/tools/earnings_calendar.py` (only `get_earnings_dates` + `history` — `get_earnings_calendar()` already runs on Finnhub and is untouched) with FMP `earnings` + EOD equivalents, preserving the returned dict shape — depends on T020. ALSO migrated the duplicate mirror in `backend/earnings_data.py` (discovered during implementation — a real live yfinance import in the backend service, not previously in the migration map)
- [X] T026 [US1] Replace yfinance in `get_earnings_data()` in `agent-runner/tools/financials.py`, AND in `_eps_revision_direction()` in `agent-runner/agents/earnings_scanner.py` (discovered during implementation — a 9th yfinance call site), with FMP analyst-estimates/grades endpoints, else keep the existing Finnhub recommendation/price-target calls as fallback (migration-map row 5, updated) — depends on T007
- [X] T027 [US1] [P] Convert `agent-runner/tools/institutional.py` to read-only/no-refresh mode: remove the yfinance fetch entirely, serve only existing `institutional_cache` data, add a `stale: true` / no-refresh indicator to the returned dict (migration-map row 6 — 13F confirmed not entitled)
- [X] T028 [US1] [P] Replace yfinance in `_fetch_history()` in `backend/routers/price.py` with FMP intraday/EOD stable endpoints via the throttled client, keeping the existing `price_cache` 1-hour Mongo cache mechanism unchanged
- [X] T029 [US1] [P] Delete unused `agent-runner/data_fetcher.py` (confirmed zero live imports — fully superseded by `tools/*.py`) and annotate/retire `specs/data_fetcher.py` accordingly
- [X] T030 [US1] Remove `yfinance` from `agent-runner/requirements.txt` and `backend/requirements.txt`; run `grep -ri yfinance backend/ agent-runner/ scripts/ --include='*.py'` and confirm zero code hits (SC-002 gate, migration-map "Removal gate") — depends on T021, T023–T029. Confirmed zero source-code hits (only historical/documentation comments remain, e.g. "previously yfinance")
- [X] T031 [US1] [P] Rewrite `specs/DATA_SOURCES.md`: retire the yfinance section, rewrite the FMP section against `stable/` paths, update the Coverage Map's primary/backup ownership (FR-007)
- [X] T032 [US1] [P] Update component specs for changed tools: `specs/component-specs/agent-runner/tools/price.md`, `breadth.md`, `institutional.md`, `earnings_calendar.md`, `financials.md` (constitution Principle II)
- [X] T033 [US1] Run full regression — `pytest agent-runner/`, `pytest backend/`, `ruff check backend/ agent-runner/ scripts/` — all green (SC-003 gate) — depends on T014–T030. **262 agent-runner tests + 61 backend tests pass, ruff clean**

**Checkpoint**: User Story 1 delivers independently — all Yahoo-sourced data now comes from FMP, `yfinance` is fully removed, existing views are unaffected (quickstart Scenarios 1–2).

---

## Phase 4: User Story 2 - Admin Section for Market-Wide Data Jobs (Priority: P2)

**Goal**: A working admin section that lists, triggers, and shows outcomes for non-ticker jobs — starting with breadth refresh, earnings-calendar scan, the entitlement probe, and the new fund-holdings pull that replaces the retired Dataroma scraper.

**Independent Test**: Open `/admin`, trigger the breadth refresh, watch it reach a terminal status with a visible outcome (quickstart Scenario 3).

### Tests for User Story 2

- [ ] T034 [P] [US2] Contract tests for `backend/routers/admin.py` in `backend/tests/test_admin_router.py`: `GET /admin/jobs` response shape, `POST /admin/jobs/{name}/run` (enqueue + `already_queued` on duplicate + 404 on unknown name), `GET /admin/jobs/{name}/runs`
- [ ] T035 [P] [US2] Unit tests for the `job_type` dispatch in `agent-runner/tests/test_queue_worker.py`: a registered admin `job_type` calls its handler and writes `dataset_meta`; an unregistered one fails with a clear error
- [ ] T036 [P] [US2] Unit tests in `agent-runner/tests/test_fund_holdings.py`: FMP fake, idempotent upsert on the `(ticker, as_of_date)` unique key, `dataset_meta` write

### Implementation for User Story 2

- [ ] T037 [US2] Implement `GET /admin/jobs` in `backend/routers/admin.py`: define an `ADMIN_JOBS` registry constant (`name`, `description`, `dataset`, `stale_minutes`) starting with `breadth_refresh`, `earnings_calendar_scan`, `fmp_entitlement_probe`, `fund_holdings_pull`; merge with `work_queue` current/last-run state and `dataset_meta` freshness per [contracts/admin-jobs-api.md](contracts/admin-jobs-api.md)
- [ ] T038 [US2] Implement `POST /admin/jobs/{name}/run` in `backend/routers/admin.py`: 404 on an unknown name, enqueue via `work_queue` with `job_type` + `source: "admin"`, return `already_queued` with the existing job id on a duplicate active run (FR-011) — depends on T037
- [ ] T039 [US2] Implement `GET /admin/jobs/{name}/runs` in `backend/routers/admin.py` (reads `work_queue` filtered by `job_type`, newest first) — depends on T037
- [ ] T040 [US2] Register the admin router in the backend app entrypoint — depends on T037–T039
- [ ] T041 [US2] Wire `agent-runner/tools/admin_jobs.py` `JOB_HANDLERS`: `breadth_refresh` → the breadth refresh entrypoint in `tools/breadth.py`, `earnings_calendar_scan` → the scan entrypoint in `tools/earnings_calendar.py`, `fmp_entitlement_probe` → `tools/fmp_client.fmp_entitlement_probe` (T007); each handler writes `dataset_meta` via T010 — depends on T007, T010, T011
- [ ] T042 [US2] Create `agent-runner/tools/fund_holdings.py`: FMP ETF/fund-holdings collector, idempotent upsert into `fund_holdings` (unique key `ticker` + `as_of_date`), writes `dataset_meta("fund_holdings")` — depends on T005, T010
- [ ] T043 [US2] Register `fund_holdings_pull` in `agent-runner/tools/admin_jobs.py` `JOB_HANDLERS` and in `backend/routers/admin.py` `ADMIN_JOBS` — depends on T037, T041, T042
- [ ] T044 [US2] [P] Retire `agent-runner/tools/superinvestor.py`: remove any active timer/queue wiring, add a module-level retirement note, verify `superinvestor_moves_cache` / `dataroma_meta` stay readable with no new writes (research D11)
- [ ] T045 [P] [US2] Add `AdminJob` / `AdminJobRun` response types to `frontend/src/api/types.ts` matching [contracts/admin-jobs-api.md](contracts/admin-jobs-api.md)
- [ ] T046 [US2] Create `frontend/src/hooks/useAdminJobs.ts`: job-list query (fetch on mount + manual refetch only, `refetchInterval: false`), trigger mutation, run-history query — depends on T037–T040, T045
- [ ] T047 [US2] Create `frontend/src/pages/Admin.tsx`: job cards (description, last-run time/outcome, freshness), trigger button (disabled + reason while running), failed-run error text, manual refresh control — depends on T046
- [ ] T048 [US2] Add the `/admin` route in `frontend/src/App.tsx` and an "Admin" nav link in `frontend/src/components/layout/Navbar.tsx` — depends on T047
- [ ] T049 [US2] Run quickstart.md Scenario 3 manually: trigger, duplicate-reject, failure display, confirm no background polling in devtools — depends on T034–T048

**Checkpoint**: User Story 2 delivers independently — admin section triggers/monitors breadth, earnings-calendar, entitlement-probe, and fund-holdings jobs; Dataroma is retired.

---

## Phase 5: User Story 3 - FMP Coverage Gap Review & New Market-Wide Datasets (Priority: P3)

**Goal**: The gap review is finalized against the live entitlement probe, and every adopted dataset (sector performance, movers, economics, congress trades, insider feed, market + per-ticker news, company info) actually collects and is readable via the API.

**Independent Test**: Read [fmp-gap-review.md](fmp-gap-review.md) for completeness; trigger each new admin job and confirm data lands in storage (quickstart Scenario 4, steps 1–4/6/7).

### Tests for User Story 3

- [ ] T050 [P] [US3] Unit tests for `agent-runner/tools/market_wide.py` collectors (sector performance, movers, economics ×4, congress trades, insider feed) in `agent-runner/tests/test_market_wide.py` — FMP fakes, idempotent-upsert assertions, `dataset_meta` writes
- [ ] T051 [P] [US3] Unit tests for `agent-runner/tools/news.py` in `agent-runner/tests/test_news.py`: per-ticker delta-fetch cursor behavior, market-wide news idempotency
- [ ] T052 [P] [US3] Unit tests for `agent-runner/tools/company_info.py` in `agent-runner/tests/test_company_info.py`: 90-day refresh gate, FMP fake
- [ ] T053 [P] [US3] Contract tests for the new backend read endpoints in `backend/tests/test_market_router.py` and `backend/tests/test_stocks_news.py`: envelope shape, `freshness.last_success_at: null` when never collected

### Implementation for User Story 3

- [ ] T054 [US3] Implement the sector-performance collector in `agent-runner/tools/market_wide.py` → `sector_performance` collection — depends on T005, T010
- [ ] T055 [US3] Implement the market-movers collector (gainers/losers/actives) in `agent-runner/tools/market_wide.py` → `market_movers` collection — depends on T005, T010
- [ ] T056 [US3] Implement the economics collector in `agent-runner/tools/market_wide.py` → `treasury_rates`, `market_risk_premium`, `economic_calendar_events`, `economic_indicators` collections, filtering indicators against `agent-runner/tools/macro.py`'s `DEFAULT_INDICATORS` so nothing duplicates FRED (FR-016, research D13) — depends on T005, T010
- [ ] T057 [US3] Implement the congress-trades collector (senate + house) in `agent-runner/tools/market_wide.py` → `congress_trades`; check whether the existing `congressional_trades` collection holds data and retire or merge per [data-model.md](data-model.md)'s note — depends on T005, T010
- [ ] T058 [US3] Implement the insider-feed collector in `agent-runner/tools/market_wide.py` → upserts into the existing `insider_transactions` collection with envelope fields, writes `dataset_meta("insider_feed")` — depends on T005, T010
- [ ] T059 [US3] Create `agent-runner/tools/news.py`: `get_stock_news(ticker)` (delta-fetch on `published_at` cursor) → `stock_news`; `get_market_news()` → `market_news` — depends on T005
- [ ] T060 [US3] Wire `get_stock_news()` into the per-ticker prefetch step in `agent-runner/crew.py`, alongside the existing financials/price calls (FR-022) — depends on T059
- [ ] T061 [US3] Create `agent-runner/tools/company_info.py`: `get_company_info(ticker)` with a 90-day refresh gate → `company_info` collection — depends on T005
- [ ] T062 [US3] Wire `get_company_info()` into the per-ticker prefetch step in `agent-runner/crew.py` (FR-023) — depends on T061
- [ ] T063 [US3] Register `sector_performance_pull`, `market_movers_pull`, `economics_pull`, `congress_trades_pull`, `insider_feed_pull`, `market_news_pull` in `agent-runner/tools/admin_jobs.py` `JOB_HANDLERS` and `backend/routers/admin.py` `ADMIN_JOBS` — depends on T054–T059, T037, T041
- [ ] T064 [US3] Add `GET /market/sector-performance`, `/market/movers`, `/market/economics`, `/market/congress-trades`, `/market/insider-feed` to `backend/routers/market.py`, each wrapped in the freshness envelope from `dataset_meta` (per [contracts/market-data-api.md](contracts/market-data-api.md)) — depends on T054–T058
- [ ] T065 [US3] [P] Add `GET /market/fund-holdings` and `GET /market/fund-holdings/by-ticker/{ticker}` to `backend/routers/market.py` (reads the `fund_holdings` collection from T042) — depends on T042
- [ ] T066 [US3] Add `GET /market/news` to `backend/routers/market.py` and `GET /stocks/{ticker}/news` to `backend/routers/stocks.py` — depends on T059
- [ ] T067 [US3] Trigger the `fmp_entitlement_probe` admin job against the live key and append the resulting probe table to [fmp-gap-review.md](fmp-gap-review.md), confirming no drift from the user-verified decisions (FR-013, SC-005) — depends on T007, T041, T048
- [ ] T068 [US3] [P] Update `specs/DATA_SOURCES.md`'s coverage map with all newly adopted market-wide/per-ticker datasets (continues T031) — depends on T054–T062
- [ ] T069 [US3] Run full regression — `pytest agent-runner/`, `pytest backend/`, `ruff check backend/ agent-runner/ scripts/` — depends on T050–T066

**Checkpoint**: User Story 3 delivers independently — gap review finalized against live entitlements, every adopted dataset collecting and readable via the API.

---

## Phase 6: User Story 4 - Visual Consumption of Market-Wide Data (Priority: P4)

**Goal**: Every adopted market-wide dataset is viewable through an appropriate visual treatment, with freshness indicators, admin-pointing empty states, and click-through to `StockDetail`.

**Independent Test**: Open Market Overview before any collection (empty states point to admin); trigger collection; reopen and confirm each section renders with freshness and ticker navigation (quickstart Scenario 4).

### Tests for User Story 4

- [ ] T070 [P] [US4] Vitest tests for `useMarketOverview.ts` and each `market/*` section component in `frontend/src/hooks/useMarketOverview.test.tsx`: empty state, freshness badge, ticker-link navigation
- [ ] T071 [P] [US4] Vitest tests for the Feed.tsx market-news section and the StockDetail.tsx news/company-info additions

### Implementation for User Story 4

> Before building any chart/visual component below, load the `dataviz` skill per its trigger rules (chart, ranking, dashboard visuals).

- [ ] T072 [P] [US4] Add `SectorPerformance`/`MarketMover`/`EconomicsSnapshot`/`CongressTrade`/`InsiderFeedItem`/`FundHolding`/`NewsArticle` response types to `frontend/src/api/types.ts` — depends on T064–T066
- [ ] T073 [US4] Create `frontend/src/hooks/useMarketOverview.ts`: fetch-on-navigation queries (no polling) for sector-performance, movers, economics, congress-trades, insider-feed, fund-holdings, market-news — depends on T072
- [ ] T074 [P] [US4] Create `frontend/src/components/market/FreshnessBadge.tsx` and `EmptyState.tsx` (shared across sections, empty state points to `/admin`)
- [ ] T075 [US4] Create `frontend/src/components/market/SectorPerformanceSection.tsx` (ranked bar visual) — depends on T073, T074
- [ ] T076 [US4] Create `frontend/src/components/market/MarketMoversSection.tsx` (gainers/losers/actives, ticker links to StockDetail) — depends on T073, T074
- [ ] T077 [US4] Create `frontend/src/components/market/EconomicsSection.tsx` (treasury curve, market risk premium, releases calendar) — depends on T073, T074
- [ ] T078 [US4] Create `frontend/src/components/market/CongressTradesSection.tsx` (recent trades table, ticker links) — depends on T073, T074
- [ ] T079 [US4] Create `frontend/src/components/market/InsiderFeedSection.tsx` (market-wide insider feed table, ticker links) — depends on T073, T074
- [ ] T080 [US4] Create `frontend/src/components/market/FundHoldingsSection.tsx` (by-fund / by-ticker views, ticker links) — depends on T073, T074
- [ ] T081 [US4] Assemble `frontend/src/pages/MarketOverview.tsx` from T075–T080 — depends on T075–T080
- [ ] T082 [US4] Add the `/market-overview` route in `frontend/src/App.tsx` and a nav link in `frontend/src/components/layout/Navbar.tsx` — depends on T081
- [ ] T083 [US4] [P] Add a market-news section to `frontend/src/pages/Feed.tsx` (reads `GET /market/news`) — depends on T066, T073
- [ ] T084 [US4] [P] Add a per-ticker news list and company-info header fields to `frontend/src/pages/StockDetail.tsx` (reads `GET /stocks/{ticker}/news` and `company_info` data) — depends on T066, T061
- [ ] T085 [US4] Run quickstart.md Scenario 4 manually: empty states before collection, freshness badges after, ticker-click navigation — depends on T070–T084

**Checkpoint**: User Story 4 delivers independently — every adopted dataset is visually consumable; all four user stories are now independently functional together.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T086 [P] Update `specs/component-specs/` for new/changed frontend components: `Admin.tsx`, `MarketOverview.tsx`, `market/*` sections, `Feed.tsx` and `StockDetail.tsx` additions
- [ ] T087 [P] Update `specs/component-specs/` for changed backend routers (`admin.py`, `market.py`, `stocks.py`) and agent-runner tools (`fmp_client.py`, `market_wide.py`, `news.py`, `company_info.py`, `fund_holdings.py`, `admin_jobs.py`)
- [ ] T088 [P] Record a follow-up note (in this feature's directory or as a TODO) that `Playwright` is now removable from the constitution's stack list since Dataroma is retired — do not amend the constitution inline as part of this feature
- [ ] T089 Run quickstart.md Scenario 0 (entitlement probe) and Scenario 5 (budget-guard degradation under a forced low `FMP_DAILY_SOFT_CAP`) end-to-end
- [ ] T090 Run quickstart.md Scenario 6 (documentation gate): confirm `specs/DATA_SOURCES.md` and `fmp-gap-review.md` are complete
- [ ] T091 Full final regression: `pytest backend/`, `pytest agent-runner/`, `npm test` in `frontend/`, `ruff check backend/ agent-runner/ scripts/` — all green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational only
- **US2 (Phase 4)**: Depends on Foundational only (breadth/earnings-calendar handlers it wires already exist as functions regardless of whether US1's FMP migration has landed yet, but running US2 after US1 avoids wiring jobs that still call yfinance)
- **US3 (Phase 5)**: Depends on Foundational + US1 (needs the settled FMP client/throttle) + US2 (needs the admin dispatch/registry pattern and `fund_holdings` collection it extends)
- **US4 (Phase 6)**: Depends on US3 (visualizes the datasets US3 collects) + US2's `fund_holdings`
- **Polish (Phase 7)**: Depends on all four user stories being complete

### Recommended Order

Sequential by priority is strongly recommended over parallelizing stories, since US3 explicitly depends on US1+US2 and US4 depends on US3 (per spec.md's own "Why this priority" rationale for each story) — this is a single-developer project, not a staffed team split.

### Parallel Opportunities

- All Setup tasks (T001–T004) run in parallel
- Within Foundational, T007/T008/T009/T010/T011 run in parallel once T005/T006 land
- Within each story, all tasks marked `[P]` (mostly test-file tasks and independent-file implementation tasks) run in parallel; sequential tasks touching the same file (e.g., `tools/price.py`'s `_history()` chain, or the `backend/routers/admin.py` endpoint trio) do not

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all US1 test-file updates together (different files, no shared state):
Task: "Rewrite FMP fakes in agent-runner/tests/test_price.py"
Task: "Rewrite FMP fakes in agent-runner/tests/test_breadth.py"
Task: "Update agent-runner/tests/test_institutional.py for read-only behavior"
Task: "Update FMP fakes in agent-runner/tests/test_earnings_calendar.py and test_financials.py"
Task: "Add agent-runner/tests/test_fmp_client.py"
Task: "Update FMP fakes in backend/tests/test_price.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational)
2. Complete Phase 3 (US1) — the system now runs entirely on the paid FMP subscription, yfinance is gone
3. **STOP and VALIDATE**: run quickstart Scenarios 1–2, confirm SC-001/002/003
4. This alone resolves the original pain point (Yahoo coverage gaps) and is deployable on its own

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → validate → deploy (MVP: FMP-only data, no more Yahoo risk)
3. US2 → validate → deploy (admin section live; Dataroma retired, fund holdings collecting)
4. US3 → validate → deploy (gap review finalized; sector/movers/economics/congress/insider/news/company-info all collecting)
5. US4 → validate → deploy (Market Overview page; all of it visible)
6. Polish → docs, final regression

### Solo-Developer Note

With no team to split across stories, follow the phase order above top-to-bottom. Each checkpoint is a legitimate stopping point — commit and validate before continuing.

---

## Notes

- `[P]` = different files, no unfinished-task dependency within the phase
- `[Story]` maps every phase-3+ task to its user story for traceability back to spec.md
- Tests are written before their corresponding implementation task within each story, per constitution Principle I
- Stop at any checkpoint to validate a story independently via its quickstart.md scenario before continuing
- Avoid: vague tasks, two tasks editing the same file marked `[P]`, cross-story dependencies that break a story's independent testability
