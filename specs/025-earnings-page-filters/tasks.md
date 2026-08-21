# Tasks: Earnings Page Readability & Filters

**Input**: Design documents from `specs/025-earnings-page-filters/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/earnings-calendar.md](./contracts/earnings-calendar.md), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution Principle I is NON-NEGOTIABLE for this project — backend contract/unit tests and frontend component tests are required, not optional.

**Organization**: Tasks are grouped by user story (spec.md priorities) so each ships and is independently testable. US1 (date window) and US2 (surprise data) are both P1 and share the same endpoint change, so they are implemented together in Phase 3 — US1 provides the window, US2 provides what fills it, and neither is independently demoable without the other once the scan is gone. US3 (size filters/ordering) and US4 (ticker links) are P2 and layered on top.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3, US4 — maps to spec.md user stories
- File paths are exact and relative to repo root

## Path Conventions (from plan.md)

Web app: `backend/` (FastAPI) + `frontend/src/` (React). No new directories.

---

## Phase 1: Setup

**Purpose**: No new project scaffolding is needed (existing stack, no new dependencies per plan.md Technical Context). This phase only corrects the stale documentation that would otherwise mislead implementation.

- [X] T001 Correct the FMP truncation KNOWN_ISSUES entry in `KNOWN_ISSUES.md` per research.md D1 — the "~15 rows" claim no longer reproduces (verified: 789/2,347 rows on live probes 2026-08-17). Already drafted in the plan session; verify it's committed and matches research.md D1/D4/D7 wording.

**Checkpoint**: Docs no longer contradict the implementation about to happen.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared surprise-derivation logic and calendar fetch rewrite that both P1 stories depend on. No user-facing work is independently testable until this phase is done, because the current Finnhub-backed calendar has no actuals at all.

**⚠️ CRITICAL**: Nothing in Phase 3 onward can be implemented before this phase completes.

- [X] T002 [P] Write failing unit tests for `_surprise_pct(actual, estimate)` in `backend/tests/test_earnings_data.py`, covering the cases in data-model.md §4: normal beat/miss, negative-EPS beat (`-0.20` vs `-0.30` → `+33.33`), negative-EPS miss, zero estimate → `None`, missing actual → `None`, missing estimate → `None`. Confirm they fail (function doesn't exist yet).
- [X] T003 [P] Write failing unit tests for dedupe-and-order in `backend/tests/test_earnings_data.py`: duplicate symbols in a raw window collapse to one row keeping the latest `last_updated` (tie-break later `report_date`); output is sorted by `market_cap` descending with `ticker` ascending tie-break; a row absent from the universe is dropped entirely (data-model.md §5).
- [X] T004 [P] Write failing unit tests for `reporting_state` classification in `backend/tests/test_earnings_data.py`: future date + no actuals → `upcoming`; any actual present → `reported`; past date + both actuals null → `awaiting` (data-model.md §3).
- [X] T005 Implement `_surprise_pct(actual, estimate)` in `backend/earnings_data.py` per the pseudocode in data-model.md §4. Run T002 to green.
- [X] T006 Implement `_reporting_state(report_date, eps_actual, revenue_actual, today)` in `backend/earnings_data.py` per data-model.md §3. Run T004 to green.
- [X] T007 Rewrite `get_earnings_calendar` in `backend/earnings_data.py` to accept `(start: date, end: date, db)` instead of `days_ahead: int`: call `FMP_BASE + "earnings-calendar"` with `from`/`to` params via `backend.fmp.fmp_get` (not `_fmp_get`/bare `requests.get` — this closes the KNOWN_ISSUES budget-bypass item per research.md D6), join each row against `get_screener_universe(db)`, drop rows absent from the universe, dedupe, compute `eps_surprise_pct`/`revenue_surprise_pct`/`beat`/`reporting_state` per row, sort by `market_cap` desc / `ticker` asc, and return `(entries, total_before_screen)`. Cache under `earnings_cache` key `{"type": "calendar_range", "from": ..., "to": ...}` (TTL 4h via existing `_cache_get`/`_cache_put`, `CALENDAR_CACHE_HOURS`) — deliberately NOT `{"type": "calendar", ...}`, which the agent-runner still writes with a different shape (research.md D7). Run T003 to green.
- [X] T008 Handle `FmpBudgetExceededError` in `get_earnings_calendar` (`backend/earnings_data.py`): on budget exceeded, serve the newest cached doc for that exact window regardless of TTL age and mark it `stale=True`; if no cached doc exists at all, re-raise so the router can return 503 (contracts/earnings-calendar.md "Degraded and error responses"). Add unit tests for both branches to `backend/tests/test_earnings_data.py`.
- [X] T009 Rewrite `GET /earnings/calendar` in `backend/routers/earnings.py`: accept `from`/`to` query params (Pydantic-validated as dates), reject `from > to` and spans over 90 days with 422, call the rewritten `get_earnings_calendar`, and return the envelope `{"entries": [...], "total_before_screen": N, "stale": bool, "fetched_at": iso8601}` per contracts/earnings-calendar.md. Map `FmpBudgetExceededError`/no-cache to 503, provider/universe failures to 502.
- [X] T010 Update `backend/tests/test_earnings.py`: rewrite `test_calendar_is_read_only` and `test_calendar_serves_from_shared_cache` (and any other `?days=` callers) to use `?from=&to=` and assert against the new envelope shape instead of a bare array. Add new contract tests: inverted range → 422, span > 90 days → 422, response envelope has all four top-level keys, `entries` is sorted descending by `market_cap`. Keep the read-only assertion (`WORK_QUEUE`/`TICKER_INDEX` untouched) — this must keep passing per Constitution Principle II's traceability and the spec's explicit read-only requirement.
- [X] T011 Run `ruff check backend/` and fix any lint findings introduced by T005–T010 (Constitution Development Workflow gate).

**Checkpoint**: `GET /earnings/calendar?from=&to=` returns real actuals, surprise, and reporting state, budget-guarded and cached correctly. All backend tests green. Foundation ready for both P1 stories.

---

## Phase 3: User Story 1 + User Story 2 — Bounded date window with surprise data (Priority: P1) 🎯 MVP

**Goal**: Loading `/earnings` shows, with no button press, only companies reporting today−2 through today+2, ordered by market cap, with already-reported companies showing actual EPS/revenue and a signed, visually-distinct beat/miss surprise — and not-yet-reported companies showing estimates only.

**Independent Test**: Load the page cold. Confirm rows appear unprompted, all report dates fall in today−2..today+2, and manually verify (via the API or a known reporter) that a past-dated row in the window shows actuals + surprise while a future-dated row shows estimates only. This is the MVP — ship it and the page is already dramatically more readable even without size filters or ticker links.

### Tests for User Story 1 + 2 (write first, confirm failing)

- [X] T012 [P] [US1] Write a Vitest test file `frontend/src/hooks/useEarningsCalendar.test.ts` (new hook, replaces the `useEarningsCalendar` in `useEarningsScan.ts`): mocks `api.get` and asserts the query key is `["earnings-calendar", from, to]`, that it calls `/earnings/calendar?from=&to=`, and that `staleTime` prevents refetch within the cache window. Confirm it fails (hook doesn't exist in new form yet).
- [X] T013 [P] [US1] Write `frontend/src/components/earnings/EarningsFilterBar.test.tsx`: asserts the six presets from data-model.md §7 render, clicking "±2 days" writes `from`/`to` URL params matching today∓2, clicking a preset marks it active and populates the custom date inputs (FR-001c), typing a custom date that matches no preset clears the active-preset highlight (FR-001b), and an inverted custom range does not update the URL params (FR-004). Confirm it fails.
- [X] T014 [P] [US2] Write `frontend/src/components/earnings/EarningsTable.test.tsx` (new component, replaces `UpcomingEarningsTable`): given rows in each `reporting_state`, asserts an `upcoming` row shows estimates and "—" placeholders for actual/surprise (never `0`/blank), a `reported` row shows actual EPS/revenue and a surprise value with distinct beat/miss styling (not sign-character-only — assert a class or icon differs, not just text), and an `awaiting` row is visually distinguished from both and never rendered as a miss. Confirm it fails.

### Implementation for User Story 1 + 2

- [X] T015 [US1] Update `EarningsCalendarEntry` in `frontend/src/api/types.ts` per contracts/earnings-calendar.md "Breaking changes": remove `report_time`; add `eps_actual`, `revenue_actual`, `eps_surprise_pct`, `revenue_surprise_pct`, `beat`, `reporting_state` (`"upcoming" | "reported" | "awaiting"`), `last_updated`. Add a new `EarningsCalendarResponse` type for the `{entries, total_before_screen, stale, fetched_at}` envelope.
- [X] T016 [US1] In `frontend/src/hooks/useEarningsScan.ts`, replace `useEarningsCalendar(days)` with `useEarningsCalendar(from: string, to: string)`: query key `["earnings-calendar", from, to]`, calls `/earnings/calendar?from=${from}&to=${to}`, returns the full `EarningsCalendarResponse`, `staleTime` 4h to match the backend cache (research.md D6/D8), `refetchInterval: false` (Constitution Principle V). Run T012 to green.
- [X] T017 [US1] Create `frontend/src/components/earnings/EarningsFilterBar.tsx`: reads/writes `from`/`to` via `useSearchParams` (pattern from `InstitutionalFlowFilterBar.tsx`), renders the six presets from data-model.md §7 as buttons, highlights the active one per FR-001b, renders two custom date `<input type="date">` fields that debounce ~400ms into URL params on change (matching the existing `InstitutionalFlowFilterBar` debounce idiom) and reject `start > end` without writing params (FR-004). Also displays the active window as human-readable dates plus the visible-row count (FR-006, wired up in T019). Run T013 to green.
- [X] T018 [US2] Create `frontend/src/components/earnings/EarningsTable.tsx`: renders columns for ticker (plain text for now — link added in US4), company, report date, EPS est./actual, revenue est./actual, surprise, last updated. Renders per `reporting_state`: `upcoming` → actual/surprise columns show an explicit "—" placeholder (FR-014); `reported` → actual values plus surprise, with beat (`beat === true`) and miss (`beat === false`) using distinct color AND an icon/label (not sign character alone — FR-012); `awaiting` → a distinct "awaiting results" treatment, never styled as a miss (FR-013, spec Edge Cases). A `null` surprise (missing/zero estimate) always renders as unavailable, never `0%` (FR-011). Run T014 to green.
- [X] T019 [US1] Rewrite `frontend/src/pages/EarningsScan.tsx`: on mount, read `from`/`to` from `useSearchParams` defaulting to today∓2 (FR-002) if absent; call `useEarningsCalendar(from, to)`; render `EarningsFilterBar` and `EarningsTable`; show a loading state on initial load (FR-000c) and keep previous rows visible with a loading indicator during window changes rather than blanking (FR-027c); render an explicit empty state naming the active window when `entries` is empty (spec Edge Cases); render a staleness banner when `stale: true` and an explicit error state on request failure — never a bare empty table for either (FR-028, SC-010). Remove the manual scan trigger entirely — no button the user must press (FR-000, FR-000a).
- [X] T020 [US1] Remove the now-dead scan-only pieces from `frontend/src/pages/EarningsScan.tsx` and `frontend/src/hooks/useEarningsScan.ts`: delete `useEarningsScan()` (the polling hook — this is the app's only `refetchInterval` poll; removing it improves Constitution Principle V compliance per plan.md), remove `EarningsCalendarTable`, `EarningsCandidateCard`, `ScanControls` imports and usage.
- [X] T021 [P] [US1] Delete `frontend/src/components/earnings/UpcomingEarningsTable.tsx` and `UpcomingEarningsTable.test.tsx` (superseded by `EarningsTable`).
- [X] T022 [P] [US1] Delete `frontend/src/components/earnings/EarningsCalendarTable.tsx`, `EarningsCalendarTable.test.tsx`, `EarningsCandidateCard.tsx`, `ScanControls.tsx` (scan UI removed per FR-000b).
- [X] T023 [P] [US1] Remove now-unreferenced scan-only types (`EarningsScanDoc`, `EarningsScoreBreakdown`, and related scored-candidate types) from `frontend/src/api/types.ts` per plan.md's post-design constitution note. Leave backend `ScanRequest`/scan endpoints intact (dormant, not deleted — spec scopes deletion out).
- [X] T024 [US1] Run `cd frontend && npm run build` and fix any TypeScript errors surfaced by the type/component removals (T020–T023).

**Checkpoint**: `/earnings` loads automatically with the ±2-day default window, shows real surprise data for reported companies, and the old scan UI is gone. This is a demoable MVP.

---

## Phase 4: User Story 3 — Noise reduction and fixed market-cap ordering (Priority: P2)

**Goal**: Two size sliders (revenue floor, EPS magnitude floor) and a "big movers only" toggle filter the already-loaded table client-side with zero additional requests; rows are provably always ordered by market cap regardless of filters.

**Independent Test**: With Phase 3 shipped, load a heavy earnings day, confirm rows descend by market cap; raise the revenue slider and confirm sub-threshold and no-data rows vanish instantly with zero network activity; toggle "big movers only" and confirm only large-surprise rows remain with a stated reason when the result is empty.

### Tests for User Story 3

- [X] T025 [P] [US3] Extend `frontend/src/components/earnings/EarningsFilterBar.test.tsx`: revenue slider defaults to $10M, EPS slider defaults to $0.01, both write `min_rev`/`min_eps` URL params on change (not on every intermediate drag frame — debounced or on-release), big-movers toggle defaults off and writes `movers=1` when on, and moving any of the three never touches `from`/`to`.
- [X] T026 [P] [US3] Create `frontend/src/lib/earningsFilters.test.ts`: unit tests for the client-side predicate in data-model.md §6 — `min_rev`/`min_eps` at zero keep rows with no figure at all (FR-017); above zero, rows with no figure are excluded; `abs(eps)` means a large loss (e.g. `-2.50`) is NOT filtered out by a magnitude floor; `movers` toggle excludes `upcoming` rows and rows with no computable surprise, and requires `max(abs(eps_surprise_pct ?? 0), abs(revenue_surprise_pct ?? 0)) >= 10`; all three filters combine as AND (FR-018).
- [X] T027 [P] [US3] Extend `EarningsTable.test.tsx` or add `EarningsTable.ordering.test.tsx`: given entries already sorted by the mock API response, assert the table renders them in that order without re-sorting (FR-019) — i.e. the component must not apply its own sort.

### Implementation for User Story 3

- [X] T028 [US3] Create `frontend/src/lib/earningsFilters.ts` implementing the predicate from data-model.md §6 as a pure, exported function `filterEntries(entries, {minRev, minEps, moversOnly})`. Run T026 to green.
- [X] T029 [US3] Extend `EarningsFilterBar.tsx` with the revenue range slider (default $10M, adjustable to 0), EPS magnitude range slider (default $0.01, adjustable to 0), and a "big movers only" toggle (default off) — all writing to URL params `min_rev`, `min_eps`, `movers` via the same `useSearchParams` mechanism as the date controls, but with NO debounced network call: these three never trigger a fetch (FR-027b). Run T025 to green.
- [X] T030 [US3] In `EarningsScan.tsx`, read `min_rev`/`min_eps`/`movers` from `useSearchParams` (defaulting per data-model.md §6) and apply `filterEntries` from T028 via `useMemo` over the fetched `entries` before passing to `EarningsTable` — confirm `EarningsTable` itself does no sorting/filtering, only rendering (satisfies T027). Display the FR-021 counts: visible count and, when filters are active and exclude rows, the pre-filter count (`total_before_screen` from the API for the date dimension, `entries.length` before client-side filtering for the size/movers dimension).
- [X] T031 [US3] In `EarningsFilterBar.tsx` or `EarningsScan.tsx`, add the FR-016d messaging: when "big movers only" is on and it is the reason the table is empty or reduced, say so explicitly (not just a generic empty state) — distinguish this from the FR-005/Edge-Cases "no companies report in this window" empty state, which is about the date range, not the toggle.

**Checkpoint**: Filters are fully client-side, instant, and zero-network per SC-004/SC-009; ordering is guaranteed backend-side and preserved frontend-side.

---

## Phase 5: User Story 4 — Ticker links to the stock page (Priority: P2)

**Goal**: Every ticker in the table is a keyboard-accessible link to `/stock/:ticker` that doesn't interfere with the row's Queue action.

**Independent Test**: Click any ticker and confirm navigation to that stock's detail page; tab to a ticker and press Enter for the same result; confirm clicking the ticker never fires Queue and clicking Queue never navigates.

### Tests for User Story 4

- [X] T032 [P] [US4] Extend `EarningsTable.test.tsx`: ticker cell renders an anchor/`Link` with `to`/`href` `/stock/{TICKER}`; clicking the ticker link does not invoke the row's `onQueueTicker` callback; the link is focusable and activatable via keyboard (assert role="link" or equivalent, not a styled `<span>` with an onClick).

### Implementation for User Story 4

- [X] T033 [US4] In `EarningsTable.tsx`, wrap the ticker symbol in a React Router `Link` to `` `/stock/${ticker}` `` (pattern from `frontend/src/components/layout/Sidebar.tsx`), styled as a visually distinct link (FR-022, FR-023). Ensure the link and the row's Queue button are separate interactive elements with `stopPropagation` or equivalent so activating one never triggers the other (FR-024). Run T032 to green.

**Checkpoint**: All four user stories complete and independently verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Requirements that span stories, plus the documentation and resilience work called out in plan.md and quickstart.md.

- [X] T034 [P] Add out-of-order response protection test + confirm behavior: `frontend/src/hooks/useEarningsCalendar.test.ts` — TanStack Query's per-key caching already discards stale responses for abandoned query keys (research.md D8); add a regression test asserting a slow response for a previous `from`/`to` key never overwrites the current one (FR-027e).
- [X] T035 [P] Implement and test the degraded-response UI in `EarningsScan.tsx`: a `stale: true` response renders rows plus a visible staleness banner showing `fetched_at` age; a request failure (502/503) renders an explicit error state, never an empty table (FR-028, SC-010). Add a test to `EarningsScan.test.tsx` (new file) covering both branches — reuse the pattern from `calendar.isError` handling already used elsewhere in the codebase.
- [X] T036 [P] Update `specs/component-specs/backend/routers/earnings.md` to reflect the new `GET /earnings/calendar` signature and envelope (Constitution Principle II — traceability).
- [X] T037 [P] Update or replace `specs/component-specs/frontend/pages/EarningsScan.md` and the component specs for the deleted/replaced components (`EarningsCalendarTable.md`, `EarningsCandidateCard.md`) under `specs/component-specs/frontend/components/earnings/` — mark superseded ones as removed, add specs for `EarningsFilterBar` and `EarningsTable`.
- [X] T038 Log the agent-runner provider seam in `KNOWN_ISSUES.md` if not already fully captured by T001: the backend calendar now sources from FMP while `agent-runner/tools/earnings_calendar.py` stays on Finnhub for the scanner, and the two write different `earnings_cache` doc shapes (`calendar_range` vs `calendar`) — per research.md D7, this is a deliberate, documented seam, not silent divergence.
- [X] T039 Log the now-dormant scan endpoints in `KNOWN_ISSUES.md`: `POST /earnings/scan`, `GET /earnings/scan/{scan_id}`, `earnings_scan_worker.py`, and `agents/earnings_scanner.py` have no remaining caller after the scan UI removal (T020–T022) but are intentionally not deleted (spec scopes deletion out) — per plan.md's post-design constitution re-check.
- [X] T040 Run the full quickstart.md validation end to end (steps 1–8): automated gates, endpoint contract checks (ordering/screening/dedupe via the provided Python snippets), budget accounting, manual page walkthrough, filter network-count checks, payload size spot-check, degraded-mode check with `FMP_DAILY_SOFT_CAP=1`, and the regression sweep (no polling, clean build, `POST /earnings/analyze` still works).
- [X] T041 Final `ruff check backend/` and `cd frontend && npm run build && npm test` full-suite pass (Constitution Development Workflow gate — both MUST pass before this feature is considered mergeable).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Phase 1. **BLOCKS Phase 3 entirely** — there is no surprise data or `from`/`to` endpoint until T007–T009 land.
- **Phase 3 (US1+US2, P1, MVP)**: Depends on Phase 2. Must complete before Phase 4 and Phase 5 — both add controls/columns to the page and table `EarningsScan.tsx`/`EarningsTable.tsx` create in this phase.
- **Phase 4 (US3, P2)**: Depends on Phase 3 (extends `EarningsFilterBar.tsx` and `EarningsScan.tsx` built in Phase 3; does not touch the backend). Independent of Phase 5.
- **Phase 5 (US4, P2)**: Depends on Phase 3 (extends `EarningsTable.tsx` built in Phase 3). Independent of Phase 4 — **Phases 4 and 5 can run in parallel** once Phase 3 is done.
- **Polish (Phase 6)**: Depends on all preceding phases being complete.

### Within Each Phase

- Tests are written and confirmed failing before their corresponding implementation task (Constitution Principle I).
- Within Phase 2: T002–T004 (tests, parallel) → T005–T006 (parallel, pure functions) → T007 (needs T005+T006) → T008 → T009 (needs T007+T008) → T010 (needs T009) → T011.
- Within Phase 3: T012–T014 (tests, parallel) → T015 (types) → T016 (hook, needs T015) → T017/T018 (parallel, both need T015) → T019 (needs T016+T017+T018) → T020 (needs T019) → T021–T023 (parallel deletions, need T020) → T024 (needs everything above).
- Within Phase 4: T025–T027 (tests, parallel) → T028 (needs T026) → T029 (needs T025, extends T017) → T030 (needs T028+T029) → T031 (needs T030).
- Within Phase 5: T032 (test) → T033 (needs T032, extends T018).

### Parallel Opportunities

- Phase 2: T002, T003, T004 together; then T005, T006 together.
- Phase 3: T012, T013, T014 together; then T017, T018 together (different files); then T021, T022, T023 together (all deletions).
- Phase 4: T025, T026, T027 together.
- Phase 4 and Phase 5 as a whole can proceed in parallel once Phase 3's checkpoint is reached.
- Phase 6: T034, T035, T036, T037 together.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch the three foundational test-writing tasks together:
Task: "Write failing unit tests for _surprise_pct in backend/tests/test_earnings_data.py"
Task: "Write failing unit tests for dedupe-and-order in backend/tests/test_earnings_data.py"
Task: "Write failing unit tests for reporting_state classification in backend/tests/test_earnings_data.py"

# Then the two pure-function implementations together:
Task: "Implement _surprise_pct in backend/earnings_data.py"
Task: "Implement _reporting_state in backend/earnings_data.py"
```

## Parallel Example: Phase 3 (US1+US2)

```bash
# Launch the three test files together:
Task: "Write frontend/src/hooks/useEarningsCalendar.test.ts"
Task: "Write frontend/src/components/earnings/EarningsFilterBar.test.tsx"
Task: "Write frontend/src/components/earnings/EarningsTable.test.tsx"

# After types (T015) and hook (T016) land, build both components together:
Task: "Create EarningsFilterBar.tsx"
Task: "Create EarningsTable.tsx"

# Once the page is rewired (T020), delete dead components together:
Task: "Delete UpcomingEarningsTable.tsx + test"
Task: "Delete EarningsCalendarTable.tsx, EarningsCandidateCard.tsx, ScanControls.tsx + tests"
Task: "Remove unreferenced scan types from api/types.ts"
```

---

## Implementation Strategy

### MVP First (Phases 1–3)

1. Phase 1: correct the stale KNOWN_ISSUES entry.
2. Phase 2: rewrite the calendar fetch onto FMP with surprise derivation — nothing user-facing yet, but everything downstream needs it.
3. Phase 3: ship US1+US2 together — the auto-loading, date-windowed, surprise-annotated table.
4. **STOP and VALIDATE**: run quickstart.md steps 1–4 against just the MVP. This alone is the "make the earnings page easier to read" ask — a bounded window with real beat/miss data and no button to press.

### Incremental Delivery

1. Phases 1–2 → foundation ready, nothing visible yet.
2. Phase 3 → MVP demoable: bounded window, surprise data, scan UI gone.
3. Phase 4 → noise filters and guaranteed ordering layer on top.
4. Phase 5 → ticker navigation layers on top (can ship before or after Phase 4 — no shared files).
5. Phase 6 → docs, resilience, and final gate pass.

### Parallel Team Strategy

With two developers: both do Phases 1–2 together (small, sequential-heavy). One takes Phase 3 solo (it's the critical path — Phase 4/5 both depend on its output). Once Phase 3's checkpoint lands, split: developer A takes Phase 4 (filters), developer B takes Phase 5 (ticker links) — different files (`EarningsFilterBar.tsx`/`earningsFilters.ts` vs `EarningsTable.tsx`), genuinely parallel.

---

## Notes

- [P] tasks touch different files with no completed-task dependency between them.
- Every test task must be run and confirmed **failing** before its implementation task starts (Constitution Principle I: "A pull request that adds behavior without a corresponding test is incomplete, not tested later").
- T007 is the pivotal task: it's where Finnhub is replaced with FMP and where the KNOWN_ISSUES budget-bypass fix and the D7 cache-key seam both land. Get its tests (T002–T004) solid before touching it.
- Do not skip T011/T024/T041 (lint/build gates) — Constitution's Development Workflow gate blocks merge on `ruff` and the frontend build/test suite, and hooks must not be bypassed with `--no-verify`.
- Commit after each task or logical group, referencing `specs/025-earnings-page-filters/` per the constitution's traceability convention.
