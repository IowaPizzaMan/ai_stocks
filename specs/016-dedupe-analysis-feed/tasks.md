---

description: "Task list template for feature implementation"
---

# Tasks: Deduplicate Analysis Feed & Storage

**Input**: Design documents from `/specs/016-dedupe-analysis-feed/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Constitution Principle I ("Test-First & Comprehensive Coverage") is
NON-NEGOTIABLE for this project — every task below that changes behavior ships with a
matching pytest/mongomock (or Vitest) test as part of the same task, not as an optional
add-on.

**Organization**: Tasks are grouped by user story (US1/US2/US3, per spec.md's priorities)
to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact, from `plan.md`'s Project Structure section

## Important cross-story note

Per `research.md` D2, the Feed router (`GET /analysis/feed`) requires **no code change** —
its correctness follows entirely from the storage invariant User Story 2 establishes (at
most one document per ticker). This breaks the usual "P1 stories are independent" pattern:
**User Story 1's real-world behavior depends on User Story 2 being implemented**, even
though both are P1. User Story 1's tasks below are test-only and can be written and merged
first (they pass today against seeded single-doc-per-ticker fixtures, matching the existing
test style), but the end-to-end acceptance scenario (two real analyses → one Feed card) only
holds once User Story 2's write-path fix (T007) lands.

---

## Phase 1: Setup

No new setup required. This feature adds no new dependencies, services, or scaffolding — it
modifies four existing files (`agent-runner/queue_worker.py`, `agent-runner/tools/db.py`,
`backend/db.py`, `backend/routers/analysis.py`), two existing frontend files, and adds one
new script + its tests, all using tooling already in place. Proceed directly to Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The unique-index safety net (`research.md` D6) that both services' startup
paths share, and that Constitution Principle VI requires be kept identical between them.
Not strictly blocking for US1/US2/US3's own logic (index creation is fail-soft), but it's
shared cross-service infrastructure best landed before story work so it isn't forgotten.

- [X] T001 [P] In `agent-runner/tools/db.py`, add a unique index on `analyses.ticker` inside
      `ensure_indexes()` (after the existing `{ticker:1, timestamp:-1}` index at line 49):
      `db[ANALYSES].create_index([("ticker", ASCENDING)], unique=True)`, wrapped in a
      `try/except` that catches the duplicate-key failure and logs a warning (e.g.
      "unique ticker index on analyses blocked by existing duplicates — run
      scripts/dedupe_analyses.py") instead of raising, per `research.md` D6 and
      `data-model.md` Index changes
- [X] T002 [P] Mirror T001 exactly in `backend/db.py`'s own `ensure_indexes()` (after the
      existing indexes at lines 37-38) — same unique index, same fail-soft
      try/except+log pattern, keeping the two copies in sync per Constitution Principle VI
- [X] T003 [P] Add `test_ensure_indexes_unique_ticker_index_is_fail_soft` in
      `agent-runner/tests/test_db.py`: insert two `ANALYSES` docs sharing a `ticker`, call
      `ensure_indexes(db)` and assert it does not raise; then remove the duplicate and call
      `ensure_indexes(db)` again, assert `db[ANALYSES].index_information()` now contains the
      unique index on `ticker`

**Checkpoint**: Shared index infrastructure in place in both services; story work can begin.

---

## Phase 3: User Story 1 - One feed card per ticker (Priority: P1) 🎯 MVP

**Goal**: The Feed shows at most one entry per ticker, reflecting that ticker's most recent
analysis, with pagination/count/filtering all honoring that invariant (FR-001, FR-002, FR-003).

**Independent Test**: Trigger two analyses for the same ticker (e.g. AAPL) at different
times, load the Feed, confirm only one AAPL card appears reflecting the second analysis. (Per
the cross-story note above, this scenario is only *fully* exercisable once T007 lands — the
tasks here validate the Feed router's own behavior given a deduplicated collection, which is
what `research.md` D2 established requires no router changes.)

- [X] T004 [US1] Add `test_feed_shows_one_card_after_reanalysis` in
      `backend/tests/test_routers.py`: insert an "old" AAPL analysis doc, then
      `db[ANALYSES].replace_one({"ticker": "AAPL"}, new_doc, upsert=True)` to simulate the
      upsert write path (T007) producing a second, newer analysis; assert
      `GET /analysis/feed` returns exactly one AAPL entry whose `signal`/`conviction`/`summary`
      match the newer doc (Acceptance Scenario 1)
- [X] T005 [US1] Extend `test_feed_pagination_and_projection` in
      `backend/tests/test_routers.py`: after the existing 25 one-doc-per-ticker inserts, add
      one extra older doc for an existing ticker (e.g. another `T00` doc at an earlier
      timestamp via `replace_one(..., upsert=True)` so it collapses rather than adding a
      26th distinct row) and assert `total` stays `25`, not `26` (FR-002)
- [X] T006 [US1] Add `test_feed_filters_use_latest_value_per_ticker` in
      `backend/tests/test_routers.py`: give one ticker an older doc with `signal="bearish"`
      and, via `replace_one(upsert=True)`, a newer doc with `signal="bullish"`; assert
      `?signal=bullish` returns it and `?signal=bearish` does not (FR-003, Acceptance
      Scenario 2)

**Checkpoint**: Feed router behavior is verified correct given a deduplicated collection —
no production code in `backend/routers/analysis.py`'s `get_feed` needed changing.

---

## Phase 4: User Story 2 - Storage keeps only the latest analysis per ticker (Priority: P1)

**Goal**: A completed analysis for a ticker replaces that ticker's existing stored record
instead of adding a new one (FR-004, FR-008), and per-ticker lookups return only that single
current record (FR-005).

**Independent Test**: Run analysis for a ticker twice in a row; after the second run,
querying storage for that ticker returns exactly one record matching the second run's output.

### Write path (root-cause fix)

- [X] T007 [US2] In `agent-runner/queue_worker.py`: add `write_db` to the existing
      `from tools.db import ...` line (line 15), then replace
      `db[ANALYSES].insert_one(result)` (line 72) with
      `write_db(ANALYSES, result, upsert_key="ticker", db=db)` — see
      `contracts/analysis_write_path.md`
- [X] T008 [P] [US2] Add `test_second_job_for_same_ticker_replaces_analysis` in
      `agent-runner/tests/test_queue_worker.py`: run `claim_and_run_next` for ticker AAPL
      with a `FakeCrew` result of `signal="bullish"`, then enqueue and run a second job for
      AAPL with a `FakeCrew` result of `signal="bearish", conviction="low"`; assert
      `db[ANALYSES].count_documents({"ticker": "AAPL"}) == 1` and the stored doc's `signal`/
      `conviction` match the second run (Acceptance Scenario 2). Note:
      `test_successful_job_writes_analysis_and_marks_done` already covers a first-time
      ticker producing exactly one record (Acceptance Scenario 1) and needs no change.

### Per-ticker lookup (FR-005 consequence of the storage invariant)

- [X] T009 [US2] In `backend/routers/analysis.py`, change `get_ticker_analysis` (lines
      67-73): drop the `limit: int = 10` parameter, replace
      `.find({"ticker": ticker.upper()}, {"_id": 0}).sort("timestamp", -1).limit(limit)`
      with `.find_one({"ticker": ticker.upper()}, {"_id": 0})`, returning the single doc or
      `None` — see `contracts/analysis_ticker_endpoint.md`
- [X] T010 [US2] Rewrite `test_ticker_history` in `backend/tests/test_routers.py`: seed one
      AAPL doc and one MSFT doc, assert `GET /analysis/aapl` returns a single object (not a
      list) matching the AAPL doc including `sub_reports`; add a case asserting
      `GET /analysis/zzzz` (unknown ticker) returns `null` with a 200
- [X] T011 [US2] In `frontend/src/hooks/useAnalysis.ts`, change `useTickerAnalysis`'s
      `queryFn` return type from `Analysis[]` to `Analysis | null` (line 32:
      `api.get<Analysis[]>` → `api.get<Analysis | null>`)
- [X] T012 [US2] In `frontend/src/pages/StockDetail.tsx`, update lines 43 and 54: rename
      `const { data: analyses, isLoading } = useTickerAnalysis(symbol)` to
      `const { data: analysis, isLoading } = useTickerAnalysis(symbol)` and remove the
      `const latest = analyses?.[0]` line, using `analysis` directly everywhere `latest` was
      used
- [X] T013 [P] [US2] Remove the "6. Analysis History Timeline" bullet (lines 75-77) from
      `specs/component-specs/frontend/components/stock/AISummaryTab.md` — never implemented,
      no longer planned per FR-005 (`research.md` D4)

**Checkpoint**: Storage invariant holds end-to-end (write path + per-ticker read path). User
Story 1's Feed tests (Phase 3) now reflect real system behavior, not just simulated state.

---

## Phase 5: User Story 3 - Existing duplicates are cleaned up (Priority: P2)

**Goal**: A one-time, safely-re-runnable script collapses any pre-existing duplicate
analysis records down to one per ticker, keeping the most recent (FR-006, FR-007).

**Independent Test**: Seed a ticker with 5 stored analyses at different timestamps, run the
cleanup, confirm exactly 1 record remains (the latest); run it again, confirm no further
changes.

- [X] T014 [US3] Create `scripts/dedupe_analyses.py`, modeled on
      `scripts/backfill_financials.py`'s structure (same `sys.path` bootstrap into
      `agent-runner/`, same `logging_config.get_logger(__name__, component="scripts")`):
      implement `dedupe(db) -> int` per `contracts/dedupe_analyses_script.md` — aggregate
      `ANALYSES` grouped by `ticker` (`$sort` by `timestamp` desc — BSON type-ordering
      naturally sorts missing/malformed timestamps after valid dates, satisfying FR-006's
      malformed-timestamp handling with no special-casing — `$group` with
      `keep: {"$first": "$_id"}` and `ids: {"$push": "$_id"}`), delete every id in a group
      except `keep`, return the count removed; call `ensure_indexes(db)` after cleanup; add
      a `if __name__ == "__main__":` entry point that prints a summary (tickers processed,
      docs removed) — satisfies FR-006's reporting requirement
- [X] T015 [US3] Create `agent-runner/tests/test_dedupe_analyses.py` with five tests: (1)
      `test_dedupe_collapses_to_latest_per_ticker` — seed one ticker with 5 docs at distinct
      timestamps plus one ticker with a single doc, run `dedupe(db)`, assert exactly 1 doc
      remains for the first ticker (matching the latest `timestamp`) and the second ticker's
      doc is untouched; (2) `test_dedupe_is_idempotent` — run `dedupe(db)` twice back to
      back, assert the second call returns `0` and the collection is unchanged (FR-007); (3)
      `test_dedupe_enables_unique_index` — seed duplicates, run `dedupe(db)`, assert
      `db[ANALYSES].index_information()` now includes the unique index on `ticker` (T001
      succeeding now that duplicates are gone); (4)
      `test_dedupe_treats_missing_timestamp_as_oldest` — seed a ticker with one doc missing
      the `timestamp` field and one with a valid, older-than-now timestamp, run `dedupe(db)`,
      assert the valid-timestamp doc is the one kept (FR-006); (5)
      `test_dedupe_survives_simulated_interruption` — seed two tickers with duplicates, call
      `dedupe(db)` once, manually re-insert a duplicate for only one of the two tickers
      (simulating a run that stopped after the first ticker), call `dedupe(db)` again, assert
      both tickers end up with exactly one record and no error occurs (FR-007)

**Checkpoint**: Pre-existing duplicates collapsed; SC-003 holds (total stored analyses ==
distinct tickers ever analyzed) once run against the real dev-stack database.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Close out remaining coverage gaps and validate the feature end-to-end against
the running stack.

- [X] T016 [P] Add `frontend/src/hooks/useAnalysis.test.tsx` (new file — no existing test
      covers this hook or `StockDetail.tsx` today; `.tsx` not `.ts`, since the test wraps the
      hook in a JSX `QueryClientProvider`) with a Vitest test confirming `useTickerAnalysis`
      returns `null` gracefully when the API responds with `null` and the fetched object
      directly when one exists (Constitution Principle I: frontend hooks touching
      user-facing logic need coverage)
- [X] T017 Ran `python scripts/dedupe_analyses.py` (via `agent-runner/.venv`) against the
      real dev-stack MongoDB after rebuilding/restarting the `backend`/`agent-runner`
      containers: removed 10 pre-existing duplicate records (34 → 24), confirmed
      `count(*) == count(DISTINCT ticker) == 24` (SC-003), and confirmed the unique index on
      `analyses.ticker` built successfully on the next restart (no more fail-soft warning)
- [X] T018 Validated live against the rebuilt Docker Compose stack: `GET /analysis/feed`
      returns 24 distinct-ticker items with `total: 24`; `GET /analysis/{ticker}` returns a
      single object for a known ticker and `null` for an unknown one (SC-001, SC-002).
      SC-004 (perceived Feed load <1s) not separately timed — the query is unchanged from
      before this feature and the collection only got smaller, so no regression is expected
- [X] T019 Ran the full `pytest` suite for both services: 56/56 backend, 248/248
      agent-runner, plus 38/38 frontend Vitest — all passing. `ruff` is not installed in
      either service's `.venv` in this environment (not in `requirements.txt` despite being
      named in the constitution's tech stack) and could not be run — pre-existing gap,
      unrelated to this feature's changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None — no tasks.
- **Foundational (Phase 2)**: No dependencies — can start immediately. Not a hard blocker
  for US1-US3 (index creation is fail-soft), but lands first since it's small, shared, and
  easy to forget once story work starts.
- **User Story 1 (Phase 3)**: Can be written immediately (tests only, self-contained
  fixtures) — but only reflects *real* system behavior once Phase 4 (T007) lands. See
  "Important cross-story note" above.
- **User Story 2 (Phase 4)**: No dependency on Phase 3. This is the root-cause fix everything
  else's real-world correctness depends on.
- **User Story 3 (Phase 5)**: No dependency on Phases 3-4 to function (it operates on
  whatever duplicates already exist), but is only meaningful to run in practice after Phase
  4's write-path fix ships (otherwise new duplicates would reappear immediately after cleanup).
- **Polish (Phase 6)**: Depends on Phases 2-5 all being complete.

### Within Each Phase

- T001/T002/T003 (Foundational) are independent of each other — different files.
- T004/T005/T006 (US1) all edit `backend/tests/test_routers.py` — implement sequentially to
  avoid merge conflicts, even though none are logically dependent on each other's outcome.
- T007 (US2 write path) has no dependency; T008 depends on T007 existing to be a meaningful
  regression test (write it after, or write it first and watch it fail, per standard
  test-first practice).
- T009 → T010 (implement the endpoint change, then the test) both touch
  `backend/routers/analysis.py` / `backend/tests/test_routers.py` respectively — different
  files, but T010 depends on T009's shape change to assert against.
- T011 → T012 (frontend hook type, then its one consumer) — T012 depends on T011.
- T013 is independent of T011/T012 — different file (a spec doc).
- T014 → T015 (script, then its tests) — T015 depends on T014 existing.

### Parallel Opportunities

- T001, T002, T003 can run in parallel (Foundational).
- T008 and T013 can run in parallel with other US2 tasks in progress (different files, no
  dependency chain into them).
- Phase 3 (US1) and Phase 4 (US2) can be staffed in parallel by two people, given the tests
  in Phase 3 use direct `replace_one(upsert=True)` simulation rather than importing
  agent-runner code — they don't need to wait on T007 to be *written*, only to be *true* in
  production.
- Phase 5 (US3) can be staffed in parallel with Phases 3-4 — it's a standalone script with
  its own new test file.

---

## Parallel Example: Foundational

```bash
Task: "Add fail-soft unique index to ensure_indexes() in agent-runner/tools/db.py"
Task: "Mirror the fail-soft unique index in backend/db.py"
Task: "Add ensure_indexes fail-soft test in agent-runner/tests/test_db.py"
```

## Parallel Example: User Story 2

```bash
Task: "Add test_second_job_for_same_ticker_replaces_analysis in agent-runner/tests/test_queue_worker.py"
Task: "Remove stale Analysis History Timeline section from AISummaryTab.md"
```

---

## Implementation Strategy

### MVP First (User Story 2, despite being listed second)

Because US1's real-world behavior is entirely dependent on US2's write-path fix
(`research.md` D2), the true minimum viable slice is:

1. Complete Phase 2: Foundational (T001-T003)
2. Complete Phase 4: User Story 2 (T007-T013) — this is what actually stops new duplicates
   from forming and fixes the per-ticker view
3. Complete Phase 3: User Story 1 (T004-T006) — confirms the Feed reflects it correctly
4. **STOP and VALIDATE**: run `quickstart.md` steps 1-3
5. Deploy/demo if ready — new analyses stop duplicating from this point forward

### Incremental Delivery

1. Foundational (index safety net) ready
2. Add User Story 2 → the actual bug is fixed for all *future* analyses → demo
3. Add User Story 1 → Feed/read-path correctness formally verified → demo
4. Add User Story 3 → pre-existing duplicate backlog cleaned up, unique index now fully
   enforced → demo (SC-003 fully satisfied)
5. Polish → close remaining test gap, full quickstart pass, lint/test gate green

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability; Foundational and Polish
  tasks carry no story label by convention.
- Constitution Principle I is non-negotiable here: every behavior-changing task above ships
  with its test in the same task, not deferred.
- Commit after each task or logical group.
- Stop at either checkpoint (Phase 2 or Phase 4) to validate independently before continuing.
