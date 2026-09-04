---

description: "Task list for Stocks Page Organization, Conviction Rework & Activity Trail"

---

# Tasks: Stocks Page Organization, Conviction Rework & Activity Trail

**Input**: Design documents from `/specs/037-stocks-conviction-and-activity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conviction-rules.md,
contracts/feed-ordering.md, contracts/stock-events-api.md, quickstart.md

**Tests**: Included — Constitution Principle I is NON-NEGOTIABLE for this repo ("Every feature
MUST ship with tests before it is considered done"; the new `skills/conviction.py` is exactly
the "pure functions with no LLM calls" surface that MUST have an exhaustive pytest suite, and
backend routers / agent-runner tools MUST have contract tests).

**Organization**: Tasks are grouped by user story (spec.md: US1 = board ordering P1, US2 =
conviction rework P1, US3 = activity feed P2, US4 = navigational breadcrumbs P3, US5 = per-stock
change history P3) so each can be delivered and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete sibling task)
- **[Story]**: Which user story this task belongs to (US1–US5) — omitted for Setup,
  Foundational, and Polish

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Register the new `stock_events` collection and the `analyses.conviction_rank`
index consistently across both services, per Constitution Principle VI.

- [X] T001 [P] Add `STOCK_EVENTS = "stock_events"` constant to `agent-runner/tools/db.py`, in the same style/section as the existing `MARKET_FLOW_EVENTS` constant
- [X] T002 [P] Add `STOCK_EVENTS = "stock_events"` constant to `backend/db.py`, matching `agent-runner/tools/db.py`
- [X] T003 Add new indexes to `backend/db.py::ensure_indexes()` per data-model.md: the `analyses` compound index `[("conviction_rank", DESCENDING), ("ticker", ASCENDING)]`, and the three `stock_events` indexes `[("occurred_at", DESCENDING)]`, `[("ticker", ASCENDING), ("occurred_at", DESCENDING)]`, `[("ticker", ASCENDING), ("event_type", ASCENDING)]` (depends on T002)
- [X] T004 [P] Mirror the same four indexes in `agent-runner/tools/db.py::ensure_indexes()` (depends on T001)
- [X] T005 [P] Extend `backend/tests/test_db_constants.py` with `test_stock_events_constant_pinned()` asserting `db.STOCK_EVENTS == "stock_events"`, following the existing `test_strategy_signals_constant_pinned()` pattern (depends on T001, T002). Mirrored assertion also added to `agent-runner/tests/test_db.py::test_stock_events_constant_pinned()`.

**Checkpoint**: `stock_events` collection and the `conviction_rank` index registered and indexed identically in both services.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the deterministic conviction engine and the event-log writer path — every
user story either sorts by, computes, reads, or reports on what this phase produces.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 ~~Widen `income_quarterly` limit~~ **DROPPED during implementation** — `KNOWN_ISSUES.md`'s "Upstream / API-tier constraints" section documents that this FMP plan 402s the *entire* `income-statement` call beyond ~4 quarterly periods, so a `limit=8` change would silently break the existing 4-quarter fetch rather than add rows (research R4 Amendment). No `financials.py` change is made by this feature; T007 is revised accordingly.
- [X] T007 [P] Create `agent-runner/tools/revenue.py::derive_revenue_trend(financials: dict) -> dict`: pure, returns `{growth_yoy, change_qoq, yoy_growing, qoq_declining, latest_period, missing}` per contracts/conviction-rules.md Rule 3 — `growth_yoy` reads `financials["growth"][0]["growthRevenue"]` (already-cached annual figure, same value `tools/screener.py` exposes as `revenue_growth_yoy`), `change_qoq` reads `financials["income_quarterly"][0]` vs `[1]` (needs only 2 of the already-cached 4 quarters); `None`/`missing` entries on an empty/short series or a zero denominator — never a silent skip
- [X] T008 [P] Exhaustive tests in `agent-runner/tests/test_revenue.py`: `growth` present with positive/negative `growthRevenue`, `growth` empty/missing, ≥2 quarters with QoQ growth/decline, exactly 1 quarter (QoQ `None`), empty quarterly series, zero-denominator guard (depends on T007). 11 tests, all passing.
- [X] T009 Create `agent-runner/skills/conviction.py::run(ticker: str, data: dict) -> dict`: pure rule-engine skill per contracts/conviction-rules.md — Rule 1 (per-strategy buy/not-buy/no-call mapping for `the_strat`, `accumulation`, `gap_analysis`, explicitly excluding `market_flow`/`position_management` from the gate per FR-006b), Rule 2 (20-period rolling z-score over `price_history["daily"]`/`["weekly"]`, bottom-quartile inclusive of the 25th percentile, `daily<60`/`weekly<30` samples → `no-call`), Rule 3 (revenue trend via T007's `derive_revenue_trend`), Rule 4 (high/medium/low level + `rank` assignment), plus a `describe_transition(old_detail, new_detail) -> str` helper composing a rule-derived reason sentence for a conviction change (used by T018); returns the full `conviction_detail` shape from data-model.md including `blockers`, `caveats` (from `market_flow`'s timing read, research R10), and `missing_inputs` (depends on T007)
- [X] T010 Exhaustive tests in `agent-runner/tests/test_conviction.py`: each strategy call outcome (buy/not-buy/no-call, including the `inside_bar_setup`/`kicking_*` non-trigger exclusion and `EARLY_ACCUMULATION` != buy), z-score quartile boundary (inclusive at p25, verified via a hand-constructed exact-equality fixture), daily-only vs weekly-only bottom-quartile (must fail), insufficient z-score sample size (boundary at exactly `MIN_*_Z_SAMPLE`), revenue YoY+QoQ truth table (growing+not-declining, growing+declining "losing ground", not-growing, missing), full high/medium/low truth table, `missing_inputs` forces non-high, flipping any single Rule 1/2/3 input drops a `high` stock (SC-004), `blockers` empty iff `high`, `market_flow` content changes only `caveats` never `level` (FR-006b), `describe_transition()` output names the flipped condition (depends on T009)
- [X] T011 Add a consistency-mirror test to `agent-runner/tests/test_conviction.py`: for the same hand-built `the_strat`/`gap_analysis` output fixtures, `conviction.run()`'s per-strategy buy-calls agree with `tools/strategy_signals.py`'s `_the_strat_block`/`_gap_analysis_block` directional results (research R2 cross-check; same file as T010, sequential). 44 tests total in test_conviction.py, all passing (`pytest tests/test_conviction.py tests/test_revenue.py tests/test_db.py` → 67 passed).
- [X] T012 Wire `skills/conviction.py` into `agent-runner/crew.py`: after the existing `the_strat`/`accumulation`/`gap_analysis`/`market_flow` calls, build the skill's input dict and call `conviction.run(ticker, ...)`, then set `synthesis["conviction"] = detail["level"]` (overwriting the LLM's value), `synthesis["conviction_rank"] = detail["rank"]`, `synthesis["conviction_detail"] = detail` before the final return (depends on T009)
- [X] T013 [P] Remove `conviction` from `agent-runner/agents/portfolio_strategist.py`'s `SCHEMA`, its `required` list, its returned dict, and the numbered prompt instructions, so no LLM-authored conviction can survive anywhere (contracts/conviction-rules.md Rule 5). Updated `tests/test_agents.py`'s stub fixture + added a regression assertion (`"conviction" not in out`).
- [X] T014 Tests in `agent-runner/tests/test_crew.py`: a full `Crew.run()` pass produces `conviction`/`conviction_rank`/`conviction_detail` matching a direct `conviction.run()` call on the same fixture data; `sub_reports.recommendation.conviction` (market_flow's own timing-confidence field, a different value with the same name) remains present and is asserted independent of the top-level `conviction` (naming-hazard regression, research R10); `portfolio_strategist`'s stubbed LLM response omitting `conviction` no longer breaks anything (depends on T012, T013). 4 new tests added; full file 15/15 passing.
- [X] T015 [P] Add `record_event(db, ticker, event_type, *, changed=False, changes=None, reason=None, source="agent_runner", occurred_at=None) -> None` to `agent-runner/tools/db.py`, inserting one `stock_events` document per data-model.md's shape (depends on T001). `source` vocabulary refined during implementation to `agent_runner`/`backend_api`/`backfill` (tags by which *service* wrote the row, not by module — see data-model.md note).
- [X] T016 Wire "added" event emission into `agent-runner/tools/db.py::register_ticker()`: after the existing `update_one(..., upsert=True)`, check `result.upserted_id is not None` and call `record_event(ticker, "added", occurred_at=now, db=db)` — atomic, race-free, and naturally idempotent on repeat registration (depends on T015, same file)
- [X] T017 [P] Mirror the same "added" event emission into `backend/registry.py::register_ticker()` (same `upserted_id`-guarded pattern; backend needs its own small `stock_events` insert since it shares no Python package with agent-runner — Principle VI's accepted duplication) (depends on T002)
- [X] T018 Wire "updated" event emission into `agent-runner/queue_worker.py::claim_and_run_next()`: reads the prior analysis document (`get_latest_analysis`) before `write_db(ANALYSES, result, upsert_key="ticker", db=db)` runs (mirrors crew.py's own pattern — needed for the OLD `conviction_detail`, which `changes_since_last` doesn't carry); after the write, derives `changed`/`changes` from `result.get("changes_since_last")`, derives `reason` via `conviction.describe_transition(previous_detail, new_detail)` when the conviction changed, and calls `record_event(ticker, "updated", changed=..., changes=..., reason=..., db=db)` (depends on T012, T015)
- [X] T019 [P] Tests in `agent-runner/tests/test_stock_events.py`: `register_ticker()` on a new ticker emits exactly one `added` event (`changed: false`, no `changes`/`reason`), calling it again does not duplicate, two different tickers each get their own; `queue_worker`'s persist path emits one `updated` event with `changed: false` on an unchanged re-analysis (and on a first-ever pull where `changes_since_last` is `None`), `changed: true` with a populated `changes`/rule-derived `reason` on a moved conviction, and `changed: true` with no `reason` on a signal-only change; the written field set (`STOCK_EVENT_FIELDS`) is the exact vocabulary `stock-events-api.md` documents (for the later backend mirror, T034) (depends on T016, T017, T018). 8 tests, all passing.

**Checkpoint**: Conviction is computed and persisted end-to-end (rank + detail), and `stock_events` records `added`/`updated` automatically as ticker registration and analysis persistence happen — all with passing cross-service tests. User story work can now begin.

---

## Phase 3: User Story 1 - Surface the best ideas first, then find any stock by position (Priority: P1) 🎯 MVP

**Goal**: Within each signal group, tiles run highest-conviction first, then A→Z within a level, and "Load more" only ever appends without moving already-visible tiles.

**Independent Test**: Load the Stocks page with several tickers per signal group at mixed conviction levels; confirm high→medium→low ordering with A→Z inside each level, and that clicking "Load more" never repositions an already-visible tile.

- [X] T020 [US1] Change `backend/routers/analysis.py::get_feed()`'s sort from `.sort("timestamp", -1)` to `.sort([("conviction_rank", -1), ("ticker", 1)])` per contracts/feed-ordering.md (depends on Foundational — needs T003's index and T012 populating `conviction_rank`)
- [X] T021 [P] [US1] Tests in `backend/tests/test_analysis_feed_ordering.py` per contracts/feed-ordering.md tests #1–6: rank-descending order, ticker-ascending ties, a document with no `conviction_rank` sorts last, page-1/page-2 boundary never reflows, ordering survives every existing filter, `conviction=high` filter stays ticker-ascending (depends on T020). 7 tests, all passing. Also updated a stale "newest first" comment on the pre-existing `test_feed_pagination_and_projection` (still passes — coincidentally correct via the ticker-ascending tie-break, since that fixture never sets `conviction_rank`).
- [X] T022 [US1] Change `frontend/src/lib/groupFeed.ts::groupBySignal()` to preserve the incoming order of `items` within each bucket instead of re-sorting by `timestamp` descending, per contracts/feed-ordering.md
- [X] T023 [P] [US1] Update `frontend/src/lib/groupFeed.test.ts` per contracts/feed-ordering.md tests #7–9: server order preserved per bucket (rewritten — no longer timestamp-based), a second appended page doesn't reindex earlier items (rewritten to prove no-reflow), an unrecognized signal still lands in `unknown` with order preserved (pre-existing test already covered this, unchanged) (depends on T022). 7 tests, all passing.
- [X] T024 [US1] Update `frontend/src/pages/Stocks.test.tsx` per contracts/feed-ordering.md tests #10–11: a Bullish group of mixed-conviction tickers renders high→medium→low with A→Z inside each level; clicking "Load more" leaves every previously rendered tile's position unchanged (depends on T022). 2 new tests added via a `tileTickerOrder()` helper reading tile aria-labels; full file 18/18 passing.
- [X] T025 [P] [US1] Update the top-of-file spec-reference comments in `frontend/src/pages/Stocks.tsx` and `frontend/src/lib/groupFeed.ts` to cite `specs/037-stocks-conviction-and-activity` and describe the conviction-then-ticker ordering rule (depends on T022)

**Checkpoint**: User Story 1 is fully functional and independently testable/demoable.

---

## Phase 4: User Story 2 - A high-conviction rating means "buy this now" (Priority: P1)

**Goal**: The conviction meter, the conviction filter, and the stock detail page all agree, and a **high** rating always comes with a plain-language rationale naming which rules passed.

**Independent Test**: Recompute conviction on a stock meeting all of contracts/conviction-rules.md's Rule 1–3 conditions; confirm **high** with an empty `blockers` list, then flip one input and confirm the rating drops with a named blocker.

- [X] T026 [US2] Create `frontend/src/components/stock/ConvictionRationale.tsx`: renders `conviction_detail`'s per-condition pass/fail (three strategy calls, daily+weekly z-score quartile status, revenue YoY/QoQ), `blockers`, and `caveats` in plain language (FR-010); when `conviction_detail` is absent on a legacy document, renders "rating not yet recomputed — re-run analysis" instead of erroring (contracts/conviction-rules.md Backward compatibility)
- [X] T027 [US2] Mount `ConvictionRationale` on `frontend/src/pages/StockDetail.tsx`'s Overview tab, alongside the existing signal/conviction display (depends on T026). Placed in its own "Why this rating" section, right after "Verdict".
- [X] T028 [P] [US2] Extend `frontend/src/api/types.ts`'s `AnalysisFeedItem` type with `conviction_rank?: number` and `conviction_detail?: ConvictionDetail`, plus new `ConvictionDetail`/`StrategyCallDetail`/`ZScoreQuartileStatus`/`StrategyCall` types per data-model.md (feed items already carry these fields — the feed projection only excludes `sub_reports`)
- [X] T029 [P] [US2] Tests in `frontend/src/components/stock/ConvictionRationale.test.tsx`: a **high** rating shows all three conditions passing with no blockers; a non-high rating names its blocker(s); a `missing_inputs` case shows the missing-data note; a legacy document with no `conviction_detail` shows the "not yet recomputed" fallback; caveats render without changing the displayed level (depends on T026, T028). 5 tests, all passing. `StockDetail.test.tsx`'s existing 16 tests confirmed unaffected.
- [X] T030 [US2] Add an aggregate-distribution assertion to `agent-runner/tests/test_conviction.py` over a representative mixed-input fixture set confirming **high** is the minority outcome (SC-002 sanity check, not a hard gate — the exhaustive per-condition truth table from T010 is the real proof). Implemented as a deterministic 64-combination sweep (2^6 across the six binary inputs): exactly 1 combination is high, high-share ≤ 25%, and all three levels are represented.

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - See what I recently added or changed (Priority: P2)

**Goal**: The Stocks page shows the last 100 add/update events, newest first, paged, with flagged/annotated entries when a re-analysis actually moved the signal or conviction.

**Independent Test**: Add a new ticker and confirm an "added" line dated today with a working link; re-analyze an existing ticker and confirm an "updated" line, flagged when it moved the rating.

- [X] T031 [US3] Create `backend/routers/events.py`: `GET /events` (paged, hard-capped at the 100 most recent events, `source` field excluded from the response) and `GET /events/{ticker}` (filtered to `added` + `changed: true`, `limit` 1–50, uppercased ticker, empty-not-404) per contracts/stock-events-api.md. Query bounds enforced via FastAPI `Query(...)` (422 outside range).
- [X] T032 Register the new router in `backend/main.py` (`app.include_router(events.router)`, alongside the existing router registrations) (depends on T031)
- [X] T033 [P] [US3] Tests in `backend/tests/test_events_router.py` per contracts/stock-events-api.md tests #1–7: newest-first ordering, the 100-event cap and its page-boundary behavior (incl. partial-page truncation), empty-collection response, the `changed`-only filter on `GET /events/{ticker}`, unknown ticker returns empty not 404, ticker uppercasing, `source` never exposed, `limit`/`page_size`/`page` range enforcement (depends on T031). 10 tests, all passing.
- [X] T034 [P] [US3] Tests in `backend/tests/test_stock_events_contract.py` per contracts/stock-events-api.md tests #8–10: `backend.db.STOCK_EVENTS == "stock_events"`, the declared `stock_events` indexes match the documented set (mirrored literal, `STRATEGY_SIGNALS`-style — not a cross-service import), and the router's exposed fields plus `source` together reconstruct the full writer vocabulary from `agent-runner/tests/test_stock_events.py` (T019) (depends on T031, T019). Mirrored index-key assertion also added to `agent-runner/tests/test_db.py`. 3 tests, all passing.
- [X] T035 [US3] Create `scripts/backfill_stock_events.py`: one-shot, idempotent — inserts one `added` event per `ticker_index` document with no existing `added` event, dated from that ticker's `first_seen_at` (not the run time), `source="backfill"`; does not create any `updated` events (FR-021a, clarification Q7). Connects via agent-runner's `tools.db` (sys.path insert), matching `scripts/backfill_financials.py`/`scripts/dedupe_analyses.py`'s convention.
- [X] T036 [P] [US3] Tests in `agent-runner/tests/test_backfill_stock_events.py` per contracts/stock-events-api.md tests #17–20: one event per existing ticker with the correct `occurred_at`/`source`, running twice creates no duplicates, a ticker with a live `added` event is skipped, zero `updated` events result, empty `ticker_index` backfills nothing (depends on T035). Placed alongside the script's test precedent (`test_dedupe_analyses.py`) in `agent-runner/tests/`, not `backend/tests/`. 5 tests, all passing.
- [X] T037 [US3] Create `frontend/src/hooks/useStockEvents.ts` with `useActivityFeed(page, pageSize)`: a paged `useQuery` (not infinite-scroll) against `GET /events`, `refetchInterval: false`. Also added `useChangeHistory(ticker, limit)` here for US5/T047 (same file).
- [X] T038 [US3] Create `frontend/src/components/feed/ActivityFeed.tsx`: renders `"{TICKER} was {added|updated} on {M/D}"` rows with `{TICKER}` as a `<Link to={`/stock/${ticker}`}>` (FR-016/FR-017), visually flags and annotates rows with `changed: true` (e.g. `conviction medium→high`, FR-018a), an empty-state message, and forward/back paging controls within the 100-event window (FR-019–FR-021) (depends on T037). Added `formatMonthDay()` to `lib/time.ts` for the "9/4" date format.
- [X] T039 [US3] Mount `ActivityFeed` inside `frontend/src/pages/Stocks.tsx`'s existing scrollable grid region so the page's bounded, viewport-relative layout is preserved (FR-022) (depends on T038). Extended `Stocks.test.tsx`'s `mockApi()` to stub `/events`.
- [X] T040 [P] [US3] Add a `StockEvent` type to `frontend/src/api/types.ts` matching contracts/stock-events-api.md's response shape (plus `StockEventChange`, `StockEventsResponse`, `TickerChangeHistoryResponse`)
- [X] T041 [P] [US3] Tests in `frontend/src/components/feed/ActivityFeed.test.tsx`: row copy/date formatting, ticker link target, flagged-vs-unflagged rendering with the transition annotation, forward/back paging, empty state (depends on T038, T040). 7 tests, all passing. Full frontend suite re-verified: 449/449, `tsc --noEmit` clean.

**Checkpoint**: User Stories 1, 2, and 3 all work independently.

---

## Phase 6: User Story 4 - Follow a breadcrumb trail while navigating (Priority: P3)

**Goal**: A navigational breadcrumb trail near the top of each page, derived from the current location (not navigation history), with every non-current segment a working link.

**Independent Test**: Paste a stock sub-tab URL directly into a fresh browser tab and confirm the full breadcrumb trail renders correctly with no prior in-app navigation.

- [X] T042 [P] [US4] Create `frontend/src/lib/breadcrumbs.ts::trailFor(pathname, hash) -> Crumb[]` covering the route table in research R8 (`/` → Stocks; `/stock/:ticker` → Stocks/TICKER; `/stock/:ticker#tab` → Stocks/TICKER/Tab; `/sectors/:sector?`; every other top-level route → its own page name only)
- [X] T043 [P] [US4] Tests in `frontend/src/lib/breadcrumbs.test.ts`: every route in the table, the hash-derived stock-tab crumb, the default (charts) tab and an unrecognized hash both omit the third segment, a top-level page has no trailing separator (FR-025), an unmatched route falls back gracefully, and a deep-link pathname+hash produces the identical trail a navigated visit would (FR-026) (depends on T042). 17 tests, all passing.
- [X] T044 [US4] Create `frontend/src/components/layout/Breadcrumbs.tsx`: consumes `useLocation()` and `trailFor()`, renders every crumb but the last as a `<Link>` (FR-024) (depends on T042)
- [X] T045 [US4] Mount `Breadcrumbs` once in `frontend/src/App.tsx`'s `<main>`, above `<Routes>` (FR-023) (depends on T044)
- [X] T046 [P] [US4] Tests in `frontend/src/components/layout/Breadcrumbs.test.tsx`: link targets for a multi-segment trail, the current (last) segment renders without a link (`aria-current="page"`), a top-level page renders no link at all, the Stocks page renders with no separator (depends on T044). 3 tests, all passing. Full frontend suite re-verified: 469/469, `tsc --noEmit` clean.

**Checkpoint**: User Stories 1–4 all work independently.

---

## Phase 7: User Story 5 - Trace why a stock's verdict changed over time (Priority: P3)

**Goal**: The stock detail page shows a dated trail of that ticker's meaningful signal/conviction changes, each with a rule-derived reason — a filtered view of the same event log US3 reads.

**Independent Test**: Re-analyze a stock across two runs where the conviction moves; confirm the detail page's change-history trail shows a dated entry naming the transition and the rule-derived reason, and that an unchanged re-analysis adds nothing there.

- [X] T047 [US5] Extend `frontend/src/hooks/useStockEvents.ts` with `useChangeHistory(ticker)`: a `useQuery` against `GET /events/{ticker}` (depends on T037, same file). Already added alongside `useActivityFeed` in T037.
- [X] T048 [US5] Create `frontend/src/components/stock/ChangeHistory.tsx`: dated entries showing the `signal`/`conviction` `from→to` transition and the `reason` line (omitted, not blank, when `reason` is null), and a near-empty state for a ticker with only its `added` event (FR-027–FR-030) (depends on T047). A ≤1-item history (0 or 1 — a first-ever analysis is never `changed: true` since there's nothing to diff against, so the backend filter already excludes it) collapses both "not yet analyzed" and "analyzed once" into the same near-empty message.
- [X] T049 [US5] Mount `ChangeHistory` on `frontend/src/pages/StockDetail.tsx`, alongside `ConvictionRationale` from US2 (depends on T048). Own "Change history" section, placed after Flags and before the Peers/Employee-count sections.
- [X] T050 [P] [US5] Tests in `frontend/src/components/stock/ChangeHistory.test.tsx`: transition formatting for signal-only, conviction-only, and both-changed entries; reason present vs. omitted; the added-only near-empty state; the zero-events state (depends on T048). 5 tests, all passing. Full frontend suite re-verified: 474/474, `tsc --noEmit` clean.

**Checkpoint**: All five user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T051 [P] Run `ruff check backend/ agent-runner/ scripts/` and fix any findings (Constitution: Development Workflow & Quality Gates). Found and fixed one unused-variable finding in `backend/tests/test_analysis_feed_ordering.py`; clean after.
- [X] T052 [P] Run the full test suites — `pytest` in `agent-runner/` and in `backend/` (each its own venv), `npm test` and `npm run typecheck` in `frontend/` — and fix any regressions. Backend: 500/500. Agent-runner: 648/650 (2 pre-existing failures in `test_economics.py`, confirmed via `git diff` to be unrelated to this feature — logged in `KNOWN_ISSUES.md`, T054). Frontend: 474/474, `tsc --noEmit` clean.
- [X] T053 Run quickstart.md's 6 validation sections end-to-end against a running Docker Compose stack; record the actual measured "% of stocks rated high" against SC-002's ≤25% target in the completion notes. Rebuilt+restarted `backend`/`agent-runner`/`frontend` images against the real Mongo (106 pre-existing tickers). Ran `scripts/backfill_stock_events.py` live: 106 "added" events seeded from real `first_seen_at`, confirmed idempotent on a second run. Queued a real `POST /queue/AVB` and let it run through the full pipeline (real Ollama `qwen3:14b`, ~3 min, no errors besides one pre-existing/expected FMP 402 soft-degrade). Result: `conviction` correctly recomputed from `high` (the old LLM-inflated value) → `low` (all three entry strategies not-buy, despite both z-scores and revenue passing — proving the all-must-pass gate), with a full real `conviction_detail` (daily z=-1.49 vs p25=-1.25, sample 232; weekly z=-2.94 vs p25=-1.33, sample 86; revenue +4.3% YoY / +0.97% QoQ) and a matching `stock_events` "updated" row (`changed: true`, rule-derived `reason`, no LLM prose). Confirmed live via curl: `GET /events` shows the update as the newest global entry; `GET /events/AVB` returns exactly the added+changed pair; `GET /analysis/feed?conviction=low` now includes AVB. The board-wide SC-002 percentage isn't meaningful yet with only 1 of 106 tickers re-analyzed under the new rules (the rest still carry pre-feature legacy conviction with no `conviction_rank`, sorting last) — the deterministic 64-combination sweep in `test_conviction.py` (T030) remains the authoritative SC-002 proof; re-analyzing the full board is a data-population step for the user, not a code gap. Breadcrumbs (quickstart section 6) validated via its 20 automated tests rather than a live click-through.
- [X] T054 [P] Log any limitations or deviations discovered during implementation in `KNOWN_ISSUES.md`, per the project's standing practice of tracking known issues there. Logged the pre-existing `test_economics.py` failure under "Open bugs" (T052).
- [X] T055 [P] Update the `Spec:`-reference docstrings/comments in touched files (`backend/routers/analysis.py`, `frontend/src/pages/Stocks.tsx`, `frontend/src/lib/groupFeed.ts`, `frontend/src/pages/StockDetail.tsx`, `agent-runner/agents/portfolio_strategist.py`, `agent-runner/crew.py`) to cite `specs/037-stocks-conviction-and-activity`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion (T004/T016/T017 need T001/T002's constants) — BLOCKS all user stories.
- **User Stories (Phase 3–7)**: All depend on Foundational (Phase 2) completion.
  - US1 (P1) needs `conviction_rank` populated (T012) and indexed (T003/T004) — otherwise independent of US2–US5.
  - US2 (P1) needs the conviction engine (T009–T014) — otherwise independent of US1/US3–US5.
  - US3 (P2) needs the `stock_events` writer path (T015–T019) — otherwise independent of US1/US2/US4/US5.
  - US4 (P3) is fully independent — pure frontend, no data dependency on any other story.
  - US5 (P3) reuses US3's `GET /events/{ticker}` endpoint (T031) and its shared frontend hook file (T037/T047 share `useStockEvents.ts`) — sequenced after US3, but its own rendering is independently testable once that endpoint exists.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### Within Each Phase

- Foundational: T006 is a no-op (dropped, see task note); T007 → T008; T007 → T009 → T010 → T011; T009 → T012; T013 independent of T012 but both feed T014; T012 → T014; T001 → T015 → T016; T002 → T017; (T012, T015) → T018; (T016, T017, T018) → T019.
- US1: T020 → T021; T022 → T023; T022 → T024; T022 → T025.
- US2: T026 → T027; T028 independent; (T026, T028) → T029; T030 stands alone (extends T010's file).
- US3: T031 → T032; T031 → T033; (T031, T019) → T034; T035 → T036; T037 → T038 → T039; T040 independent; (T038, T040) → T041.
- US4: T042 → T043; T042 → T044 → T045; T044 → T046.
- US5: T037 → T047 → T048 → T049; T048 → T050.

### Parallel Opportunities

- Setup: T001, T002 in parallel; T003 after T002; T004 after T001 (parallel with T003); T005 after both T001/T002.
- Foundational: T006 is a dropped no-op; T007 starts immediately; T008 after T007; T009 after T007; T010 then T011 (same file, sequential); T012/T013 can run in parallel with each other, both before T014; T015 after T001 can run in parallel with the revenue/conviction track; T016 after T015; T017 after T002, in parallel with T015/T016; T018 after T012 and T015; T019 after T016/T017/T018.
- US1: T021 after T020; T023/T024/T025 all after T022 and can run in parallel with each other.
- US2: T026, T028 in parallel; T027 after T026; T029 after T026+T028; T030 independent of the rest of the phase.
- US3: T033/T034 after T031, in parallel with each other; T036 after T035; T040 independent; T041 after T038+T040.
- US4: T043 after T042; T046 after T044; T045 after T044.
- US5: T050 after T048.
- Polish: T051, T052, T054, T055 can all run in parallel with each other; T053 benefits from running after T051/T052.

---

## Parallel Example: Foundational Phase

```bash
# Launch independent Foundational tasks together:
Task: "Create agent-runner/tools/revenue.py::derive_revenue_trend()"
Task: "Add record_event() to agent-runner/tools/db.py"
Task: "Trim conviction out of agent-runner/agents/portfolio_strategist.py's SCHEMA"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories; this is also where most of the
   engineering risk lives, since it includes the new `conviction.py` skill).
3. Complete Phase 3: User Story 1 (board ordering).
4. **STOP and VALIDATE**: run quickstart.md section 3 against a live stack — confirm ordering
   and no-reflow paging.
5. Deploy/demo if ready — even with US2's rating still stale on old documents, the ordering
   itself is already useful once a few tickers are re-analyzed.

### Incremental Delivery

1. Setup + Foundational → conviction computed and persisted, `stock_events` recording
   automatically, existing behavior otherwise unaffected.
2. Add US1 → board ordering works end-to-end → validate → demo.
3. Add US2 → rationale visible, meter/filter/detail page agree → validate → demo (this is
   "the core of the request" per spec.md — the point where "everything is a 3" is provably
   fixed, per SC-002).
4. Add US3 → activity feed + back-fill → validate → demo.
5. Add US4 → breadcrumbs → validate → demo.
6. Add US5 → per-stock change history → validate → demo.
7. Polish → lint, full suite, live quickstart pass, `KNOWN_ISSUES.md` update.

### Parallel Team Strategy

With multiple developers, once Foundational is done:

- Developer A: US1 (backend sort + frontend ordering)
- Developer B: US2 (rationale UI + distribution check)
- Developer C: US3 (events router + backfill + activity feed) — largest story, may want two people
- Developer D: US4 (breadcrumbs, fully independent, can even start during Foundational since it
  touches no shared data)
- US5 waits on US3's endpoint but its own component work can start once T031 lands

---

## Notes

- [P] tasks touch different files and have no dependency on an incomplete sibling task.
- The Foundational phase is the largest and most novel piece of this feature — `skills/conviction.py`
  is a new rule-engine skill in the Constitution's highest-value pure-function test surface, so
  T010's exhaustive suite is not optional scope, it is the primary proof this feature works.
- Two writer paths intentionally duplicate the same small "added" logic
  (`agent-runner/tools/db.py::register_ticker` and `backend/registry.py::register_ticker`,
  T016/T017) — this is the Constitution Principle VI pattern (consistency enforced by a mirrored
  test, T019/T034, not by a shared import) already used for `strategy_signals`/`STOCK_EVENTS`-style
  constants.
- `stock_events` is deliberately kept out of the chat semantic layer this feature (research R9) —
  no task here touches `backend/semantic/schema.py` or `query_guard.READABLE_COLLECTIONS`.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
