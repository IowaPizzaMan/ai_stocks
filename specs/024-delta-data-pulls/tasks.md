---

description: "Task list for 024-delta-data-pulls"
---

# Tasks: Delta-Only Data Pulls

**Input**: Design documents from `/specs/024-delta-data-pulls/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: **REQUIRED — not optional.** Constitution Principle I is non-negotiable: "A pull request that adds behavior without a corresponding test is incomplete, not tested later." Every story phase below writes tests first.

**Organization**: Grouped by user story so each can be implemented, tested, and stopped at independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3, US4, US5 — maps to spec.md user stories
- Exact file paths in every description

## Path Conventions

Three-part repo (per plan.md Structure Decision): `agent-runner/`, `backend/`, `frontend/src/`. Each Python service has its own venv and its own `tests/` directory; there is no shared package (constitution Principle V).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Collection constants and indexes both new stores depend on.

- [X] T001 [P] Add `PRICE_HISTORY = "price_history"` and `PULL_METRICS = "pull_metrics"` constants to `agent-runner/tools/db.py` in the 024 section, with a comment pointing at `backend/db.py`
- [X] T002 [P] Add the same two constants to `backend/db.py`, with a comment pointing at `agent-runner/tools/db.py` (Principle VI hand-sync pattern)
- [X] T003 Add indexes to `ensure_indexes()` in `agent-runner/tools/db.py`: unique `{ticker: 1}` on `price_history`; `{ticker: 1, started_at: -1}` and `{started_at: 1}` with `expireAfterSeconds=2592000` on `pull_metrics` (per data-model.md)
- [X] T004 [P] Extend `agent-runner/tests/test_db.py` to assert the two new index sets exist after `ensure_indexes()`
- [X] T005 Record a baseline: run `docker compose exec agent-runner python -m pytest tests/ -q`, `docker compose exec backend python -m pytest tests/ -q`, `cd frontend; npm run test -- --run`, and `ruff check backend/ agent-runner/ scripts/` — all must be green before any behavior change

**Checkpoint**: Collections and indexes exist; baseline is green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Per-stage request/byte attribution. Blocking because every later story reports `retrieval`, `requests`, and `bytes` per FR-002 — US2, US3, and US4 cannot report their own savings without it.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T006 Create `agent-runner/tools/metrics.py` with a `stage_recorder(name)` context manager backed by `threading.local` (NOT `contextvars` — see research D7; `ThreadPoolExecutor` does not propagate contextvars, which would silently record nothing on the parallel-prefetch path), exposing `record_call(bytes)` and `current_stage()`
- [X] T007 Instrument `fmp_get()` in `agent-runner/tools/fmp_client.py` to call `metrics.record_call(len(r.content))` after a successful response, attributing to the current stage; a missing stage context must be a silent no-op, never an error (FR-005)
- [X] T008 Instrument `finnhub_get()` in `agent-runner/tools/finnhub_client.py` the same way
- [X] T009 [P] Write `agent-runner/tests/test_metrics.py`: attribution is correct when stages run **sequentially**, and still correct when they run inside a `ThreadPoolExecutor` — this is the specific trap research D7 exists to prevent, so assert both paths explicitly
- [X] T010 [P] Add a test to `agent-runner/tests/test_metrics.py` proving a raised exception inside `stage_recorder` still records the stage and re-raises (FR-005: measurement never fails the pull)

**Checkpoint**: Any code path can be wrapped in a stage and its provider cost measured, in both execution modes.

---

## Phase 3: User Story 1 - See where pull time actually goes (Priority: P1) 🎯 MVP

**Goal**: After a pull, the operator can see a per-stage breakdown of elapsed time, request count, bytes, and outcome — ranked by cost.

**Independent Test**: Trigger a pull on a stock, expand the pull-cost panel, and read the three most expensive stages without opening a log or the code (quickstart.md Scenario 1).

### Tests for User Story 1 ⚠️ Write first, confirm they fail

- [X] T011 [P] [US1] Write `agent-runner/tests/test_pull_metrics.py`: a completed crew run writes one `pull_metrics` document whose `stages[]` covers every prefetch stage, and whose `sum(stages[].elapsed_ms) <= total_ms` (FR-004)
- [X] T012 [P] [US1] Add to `agent-runner/tests/test_pull_metrics.py`: a stage that degrades to stored data records `outcome: "degraded"`, never `"fetched"` (FR-002)
- [X] T013 [P] [US1] Add to `agent-runner/tests/test_queue_worker.py`: a raised exception while writing `pull_metrics` does not fail the job or lose the analysis result (FR-005)
- [X] T014 [P] [US1] Add to `backend/tests/test_routers.py`: `GET /stocks/{ticker}/pull-metrics` returns `stages` sorted by `elapsed_ms` descending, includes `accounted_ms`/`unaccounted_ms`, honours `limit` (default 1, max 20), and 404s when no pull exists (contracts/queue-pull-mode.md)
- [X] T015 [P] [US1] Write `frontend/src/components/stock/PullCostPanel.test.tsx`: renders top-three stages collapsed, shows each stage's retrieval kind and outcome, shows pull mode, shows unaccounted time, and renders an empty state on 404

### Implementation for User Story 1

- [X] T016 [US1] Wrap each job in `Crew._prefetch` in `agent-runner/crew.py` with `stage_recorder(key)`, so the wrapper is inside the callable (works in both the sequential and `ThreadPoolExecutor` branches at `crew.py:155-159`)
- [X] T017 [US1] Have `Crew.run` in `agent-runner/crew.py` collect the stage records and return them alongside the analysis result without changing the analysis payload shape (FR-020)
- [X] T018 [US1] In `agent-runner/queue_worker.py::claim_and_run_next`, write the `pull_metrics` document per data-model.md after the analysis is persisted, wrapped so any failure is logged and swallowed (FR-005)
- [X] T019 [US1] Add `GET /stocks/{ticker}/pull-metrics` to `backend/routers/stocks.py` per contracts/queue-pull-mode.md — sort stages server-side, compute `accounted_ms`/`unaccounted_ms`, clamp `limit` to 20
- [X] T020 [P] [US1] Add `PullMetrics` and `PullStage` types to `frontend/src/api/types.ts`
- [X] T021 [US1] Create `frontend/src/hooks/usePullMetrics.ts` with `refetchInterval: false` (constitution: the frontend never polls)
- [X] T022 [US1] Create `frontend/src/components/stock/PullCostPanel.tsx` — collapsed by default, top three stages readable without expanding (SC-006)
- [X] T023 [US1] Mount `PullCostPanel` in `frontend/src/pages/StockDetail.tsx` and invalidate `["pull-metrics"]` from the queue-drain handler in `frontend/src/hooks/useQueue.ts` (reuse the existing invalidation at `useQueue.ts:16-25`)
- [X] T024 [US1] Run quickstart.md Scenario 1 against the live stack

**Checkpoint**: US1 is complete and shippable on its own. **Read the measurement before continuing** — if fetch time proves to be a small fraction of pull wall-time (research D1 warns a bounded FMP price request costs the same one call as an unbounded one), restate SC-001's 50% target against the fetch portion in spec.md before building Phase 4.

---

## Phase 4: User Story 2 - Price history fetched incrementally (Priority: P2)

**Goal**: A pull retrieves only new trading days; every chart resolution derives from one stored daily series; no dataset is downloaded twice in a pull.

**Independent Test**: Pull a stock twice and confirm the second is incremental with far fewer bytes; switch chart resolutions and confirm the FMP counter does not move (quickstart.md Scenarios 2, 3, 4).

**⚠️ Do not switch delta on as the default until Phase 5 (US5) ships** — spec US5 "Why this priority": delta must not become the default until the operator can undo it.

### Tests for User Story 2 ⚠️ Write first, confirm they fail

- [X] T025 [P] [US2] Write the shared merge case table as a plain data fixture in `agent-runner/tests/test_price_store.py`: empty baseline, exact-boundary overlap, mid-series gap, out-of-order rows, duplicate dates, corrected bar replacing an older one, empty fetch (non-trading day). Fetched wins on a date collision (research D5)
- [X] T026 [P] [US2] Copy the identical case table into `backend/tests/test_price_store.py`. **These two files must stay byte-identical in their case data** — this is what enforces Principle VI, and divergence must fail a test rather than corrupt data (research D4)
- [X] T027 [P] [US2] Test `delta_start()` in both `test_price_store.py` files: no coverage → `None`; `last_date` older than 730 days → `None` (FR-011, research D11); otherwise `last_date − 1 day`. Assert the back-off is minus-one, never plus-one — plus-one silently drops a trading day (research D5)
- [X] T028 [P] [US2] Test `build_coverage()` in both files: a delta advances `extended_at` only and preserves `established_at`; a full build sets both (FR-010, FR-025)
- [X] T029 [P] [US2] Add to `agent-runner/tests/test_price_store.py`: a fetch failure leaves the stored series untouched and returns it with `outcome: "degraded"`; `FmpBudgetExceededError` does the same (FR-012, FR-030)
- [X] T030 [P] [US2] Add to `agent-runner/tests/test_crew.py`: one pull makes at most **one** price retrieval — `indicators` reports `retrieval: "stored"`, `requests: 0` (FR-014, SC-003)
- [X] T031 [P] [US2] Add to `backend/tests/test_price.py`: all four resolutions are served from one stored series with **zero** provider requests (FR-016, SC-004)

### Implementation for User Story 2

- [X] T032 [US2] Create `agent-runner/tools/price_store.py` with the pure functions `merge_bars()`, `delta_start()`, `build_coverage()` — no Mongo, no HTTP (contracts/price-store.md)
- [X] T033 [US2] Add `get_series(ticker, refresh, db)` to `agent-runner/tools/price_store.py` with explicit `refresh` in `{"none","delta","full"}` and no implicit time-based freshness (research D6). Build the merged series fully in memory, then a single atomic `replace_one` (FR-030)
- [X] T034 [US2] Add a `start: date | None` parameter to `fetch_eod_history()` in `agent-runner/tools/fmp_client.py`, appending `&from=` when present; keep the returned DataFrame shape byte-identical so downstream resample/indicator code is untouched (FR-020)
- [X] T035 [US2] Rewire `get_price_history`, `get_technical_indicators`, and `get_accumulation_score` in `agent-runner/tools/price.py` to `price_store.get_series(..., refresh="none")`
- [X] T036 [US2] In `Crew._prefetch` (`agent-runner/crew.py`), refresh the series **once** before the job map is built; every job reads with `refresh="none"` (FR-014)
- [X] T037 [P] [US2] Rewire `agent-runner/tools/breadth.py:123` and `:181` to `price_store.get_series(..., refresh="delta")`
- [X] T038 [P] [US2] Rewire `agent-runner/tools/earnings_calendar.py:178` to `price_store.get_series(..., refresh="delta")`
- [X] T039 [US2] Create `backend/price_store.py` as a hand-synced mirror of the agent-runner module, with a header comment naming its counterpart and routing provider calls through `backend/fmp.py::fmp_get`
- [X] T040 [US2] Rewrite `get_price` in `backend/routers/price.py` to read the stored daily series and resample locally per resolution. Delete `PRICE_CACHE`, `CACHE_MINUTES`, `_fetch_eod`, and the per-resolution fetch matrix; keep `RESOLUTIONS` as a resample-rule + display-window map
- [X] T041 [US2] Confirm T040 removed the bare `requests.get` at `backend/routers/price.py:87` — this closes half of the logged `KNOWN_ISSUES.md` budget-bypass entry (research D9). Update that entry to note `price.py` is fixed and only `earnings_data.py::_fmp_get` remains
- [X] T042 [US2] Drop the retired collection: `docker compose exec mongodb mongosh stockai --quiet --eval "db.price_cache.drop()"` (pure cache, nothing lost)
- [X] T043 [US2] Run quickstart.md Scenarios 2, 3, and 4

**Checkpoint**: Price is incremental and resolution switching is free — but delta is not yet the shipped default. Continue to Phase 5.

---

## Phase 5: User Story 5 - Force a full refresh when data looks wrong (Priority: P2)

**Goal**: One operator action rebuilds every delta-maintained dataset for a stock and re-runs the analysis on it.

**Independent Test**: Corrupt a stored series, press Full Refresh, confirm the corruption is gone and the analysis re-ran (quickstart.md Scenario 6).

**Gates US2/US3/US4 going live as the default path.**

### Tests for User Story 5 ⚠️ Write first, confirm they fail

- [X] T044 [P] [US5] Add to `backend/tests/test_routers.py`: `POST /queue/{ticker}?mode=full` echoes `mode: "full"`; absent `mode` yields `delta`; an unrecognized value is a 422, never a silent fallback to delta (contracts/queue-pull-mode.md)
- [X] T045 [P] [US5] Add to `backend/tests/test_routers.py`: a `mode=full` request while a **pending** delta job exists returns `status: "upgraded_to_full"` and mutates the job — it must never return `already_queued`, which would tell the operator their request was handled and then give them a delta pull (research D8)
- [X] T046 [P] [US5] Add to `backend/tests/test_routers.py`: a `mode=full` request while a job is **running** returns `already_queued` with the running job's mode
- [X] T047 [P] [US5] Add to `agent-runner/tests/test_queue_worker.py`: `mode: "full"` reaches `Crew.run`; an absent `mode` field on a legacy job is treated as delta (FR-021)
- [X] T048 [P] [US5] Add to `agent-runner/tests/test_price_store.py`: a full refresh interrupted mid-fetch leaves the previous complete series intact — same `bar_count`, same `established_at`, never empty or truncated (FR-030, SC-013)
- [X] T049 [P] [US5] Add to `agent-runner/tests/test_price_store.py`: a full refresh under an exhausted budget degrades to stored data and the pull still completes (FR-027, SC-009)
- [X] T050 [P] [US5] Write `frontend/src/components/stock/FullRefreshButton.test.tsx`: renders distinctly from `Pull ▶`, requires confirmation before firing, posts `mode=full`, stays enabled for a ticker with no stored data (FR-029), and surfaces the "a pull is already running, your refresh was not queued" case

### Implementation for User Story 5

- [X] T051 [US5] Add the `mode` query parameter to `POST /queue/{ticker}` in `backend/routers/queue.py`, validated to `delta|full` with a 422 otherwise; persist `mode` on the `work_queue` document; echo it in the response
- [X] T052 [US5] Implement the pending-job upgrade rule in `_enqueue` (`backend/routers/queue.py`) returning `upgraded_to_full`; leave `POST /queue/all` delta-only with no `mode` parameter (spec Out of Scope)
- [X] T053 [US5] Include `mode` in each job returned by `GET /queue` in `backend/routers/queue.py`, defaulting absent to `delta`
- [X] T054 [US5] Read `job.get("mode", "delta")` in `agent-runner/queue_worker.py::claim_and_run_next` and pass it to `Crew.run`
- [X] T055 [US5] Add a `mode` parameter to `Crew.run` in `agent-runner/crew.py`; on `"full"` refresh the price series with `refresh="full"` and pass a full-rebuild flag to the news and insider fetchers; record `mode` on the pull-metrics document (FR-028)
- [X] T056 [P] [US5] Add `mode` to `EnqueueResponse` in `frontend/src/api/types.ts`
- [X] T057 [US5] Extend `useEnqueueTicker` in `frontend/src/hooks/useQueue.ts` to accept `{ticker, mode}` while keeping the existing bare-ticker call sites working
- [X] T058 [US5] Create `frontend/src/components/stock/FullRefreshButton.tsx` with a confirmation step following the pattern in `frontend/src/components/feed/RemoveTickerConfirm.tsx` — it replaces stored data and spends real budget, so it should not fire on a single click
- [X] T059 [US5] Mount `FullRefreshButton` beside `Pull ▶` in `frontend/src/pages/StockDetail.tsx` and extend the status chip to name the in-flight mode (FR-028) — `analyzing…` alone is not enough
- [X] T060 [US5] Run quickstart.md Scenarios 6, 7, 8, and 9

**Checkpoint**: Delta-by-default is now safe to ship — US2 and US5 release together.

---

## Phase 6: User Story 3 - News fetched incrementally (Priority: P3)

**Goal**: Only articles published since the newest stored one are retrieved; the retained window stays bounded.

**Independent Test**: Pull a heavily-covered mega-cap twice; the second pull costs one page instead of several (quickstart.md Scenario 5).

### Tests for User Story 3 ⚠️ Write first, confirm they fail

- [X] T061 [P] [US3] Add to `agent-runner/tests/test_news.py`: with a coverage envelope present, the fetch window starts at `newest_published − 1 day`, not the full 30 days
- [X] T062 [P] [US3] Add to `agent-runner/tests/test_news.py`: merged articles are unique by `url`, and a re-fetched article overwrites its stored copy rather than duplicating (FR-008)
- [X] T063 [P] [US3] Add to `agent-runner/tests/test_news.py`: articles older than `NEWS_DAYS` are dropped on merge so storage stays bounded (FR-017)
- [X] T064 [P] [US3] Add to `agent-runner/tests/test_news.py`: `timeline`, `trend`, and `news_count` are computed over the **full retained window**, not only newly-arrived articles (FR-018)
- [X] T065 [P] [US3] Add to `agent-runner/tests/test_news.py`: a document with no `coverage` block (pre-feature) triggers one full-window fetch that writes the envelope (FR-021)

### Implementation for User Story 3

- [X] T066 [US3] Add the `coverage` sub-document to `stock_news_cache` writes in `agent-runner/tools/news.py` per data-model.md
- [X] T067 [US3] Make `_fetch_window` in `agent-runner/tools/news.py` start from `coverage.newest_published − 1 day` when an envelope exists, and honour the full-rebuild flag from T055
- [X] T068 [US3] Add a merge step in `get_stock_news` (`agent-runner/tools/news.py`) that unions fetched with stored articles by `url`, drops anything older than `NEWS_DAYS`, and re-derives the timeline and trend from the merged set
- [X] T069 [US3] **Drop the 24h TTL index on `stock_news_cache.fetched_at`** — in `ensure_indexes()` (`agent-runner/tools/db.py`) and once operationally via `mongosh` (quickstart.md). The TTL deletes the document the delta baseline lives in; leaving it silently restores full-window fetching with no error
- [X] T070 [US3] Run quickstart.md Scenario 5

**Checkpoint**: News paging collapses on repeat pulls.

---

## Phase 7: User Story 4 - Filings and event feeds fetched incrementally (Priority: P4)

**Goal**: Insider transactions are requested only from the newest stored event forward.

**Independent Test**: Pull a stock twice; the second insider fetch requests a narrow window and the merged result matches a full-window fetch.

**Scope note**: FMP `earnings` is bounded by `limit`, not by date, and is already effectively incremental at `limit=8` — it is **excluded** per research D2. Institutional holdings are already read-only from cache. This phase is insider transactions only.

### Tests for User Story 4 ⚠️ Write first, confirm they fail

- [X] T071 [P] [US4] Add to `agent-runner/tests/test_insider.py`: with stored events present, the Finnhub `from` bound is the newest stored event date minus one day rather than `LOOKBACK_DAYS`
- [X] T072 [P] [US4] Add to `agent-runner/tests/test_insider.py`: merge identity is `(filingDate, name, transactionType)`; an amended filing replaces its stored predecessor rather than duplicating (FR-019)
- [X] T073 [P] [US4] Add to `agent-runner/tests/test_insider.py`: a feed the plan does not cover still degrades to stored data and the rest of the pull proceeds (US4 acceptance scenario 3)

### Implementation for User Story 4

- [X] T074 [US4] Add an insider coverage envelope and store to `agent-runner/tools/insider.py`, mirroring the news envelope shape from data-model.md
- [X] T075 [US4] Make `get_insider_activity` in `agent-runner/tools/insider.py` bound its `from` date by stored coverage, falling back to `LOOKBACK_DAYS` with no baseline, and honour the full-rebuild flag from T055
- [X] T076 [US4] Add the merge step keyed on `(filingDate, name, transactionType)` with fetched-wins semantics, trimming to `LOOKBACK_DAYS` on write

**Checkpoint**: All four delta datasets are incremental.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T077 Record the accepted limitation in `KNOWN_ISSUES.md` under **Design limitations (accepted for now)**: a stock that splits between pulls keeps stale pre-split bars until someone triggers a full refresh; nothing detects or warns. Cite clarification Q5 and spec Assumptions. **Shipping this limitation without recording it is the actual failure mode** (spec Assumptions; quickstart.md)
- [X] T078 [P] Reconcile SC-001's 50% target in `spec.md` against what US1 actually measured, restating it against the fetch portion of the pull if LLM time dominates (research D1)
- [X] T079 [P] Update `specs/DATA_SOURCES.md` to describe delta-by-default retrieval and the operator-initiated full refresh
- [X] T080 [P] Add module header comments to `agent-runner/tools/price_store.py` and `backend/price_store.py` each naming the other as its hand-synced counterpart, matching the precedent in `backend/fmp.py` and `backend/earnings_data.py`
- [X] T081 Run the full gate: both pytest suites, `npm run test -- --run`, and `ruff check backend/ agent-runner/ scripts/`. Hooks must not be skipped (constitution Development Workflow)
- [X] T082 Run every quickstart.md scenario end to end against the live stack, including the one-time migration steps

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: needs Phase 1 — **blocks every user story**
- **US1 (Phase 3)**: needs Phase 2
- **US2 (Phase 4)**: needs Phase 2; its measurement claims need Phase 3
- **US5 (Phase 5)**: needs Phase 4 (a full refresh needs a store to rebuild)
- **US3 (Phase 6)**: needs Phase 2; needs T055 from Phase 5 for the full-rebuild flag
- **US4 (Phase 7)**: needs Phase 2; needs T055 from Phase 5 for the full-rebuild flag
- **Polish (Phase 8)**: needs every shipped story

### The one hard release constraint

**US2 must not go live as the default without US5.** Delta-by-default with no way to rebuild leaves the operator no remedy for corrupted data — the spec makes US5 P2 for exactly this reason. Phases 4 and 5 release together.

### Within Each Story

Tests first and failing → pure functions → store/service → endpoint → UI → quickstart scenario.

### Parallel Opportunities

- T001/T002 (the two `db.py` files) in parallel
- All Phase 2 tests (T009, T010) in parallel once T006–T008 land
- All US1 tests (T011–T015) in parallel — four different files
- All US2 tests (T025–T031) in parallel; T037/T038 in parallel (different modules)
- All US5 tests (T044–T050) in parallel
- All US3 tests (T061–T065) and US4 tests (T071–T073) in parallel within their phase
- T078/T079/T080 in parallel

---

## Parallel Example: User Story 2

```bash
# All US2 tests together — seven independent files/assertions:
Task: "Shared merge case table in agent-runner/tests/test_price_store.py"
Task: "Identical case table in backend/tests/test_price_store.py"
Task: "delta_start boundary tests in both test_price_store.py files"
Task: "build_coverage timestamp tests in both test_price_store.py files"
Task: "Degrade-on-failure tests in agent-runner/tests/test_price_store.py"
Task: "Single-price-retrieval-per-pull test in agent-runner/tests/test_crew.py"
Task: "Zero-request resolution switching test in backend/tests/test_price.py"

# Then the two independent rewiring tasks:
Task: "Rewire agent-runner/tools/breadth.py to price_store"
Task: "Rewire agent-runner/tools/earnings_calendar.py to price_store"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1
2. **STOP and read the numbers.** US1 is the MVP precisely because it answers the question the user actually asked — *how do I make the pull faster* — before any refactor is committed to.
3. If fetch time turns out to be a small fraction of pull wall-time, revise SC-001 (T078) and reconsider the scope of Phases 4–7 before building them. That is the measurement doing its job, not a failure.

### Incremental Delivery

1. Setup + Foundational → attribution works
2. **US1** → cost is visible → ship (MVP)
3. **US2 + US5 together** → price is incremental *and* undoable → ship
4. **US3** → news paging collapses → ship
5. **US4** → insider feed incremental → ship
6. Polish → limitation recorded, targets reconciled, full gate green

### Notes

- `[P]` means different files with no incomplete dependency
- Verify each test fails before implementing against it (Principle I)
- Commit per task or logical group, referencing `specs/024-delta-data-pulls/` for traceability (constitution Development Workflow)
- Two tasks are load-bearing and easy to skip: **T069** (drop the news TTL — leaving it silently defeats US3 with no error) and **T077** (record the accepted split-drift limitation)
