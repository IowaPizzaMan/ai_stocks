---

description: "Task list for feature implementation"
---

# Tasks: Decouple Macro Analysis From Ticker Research and Surface It in the UI

**Input**: Design documents from `/specs/020-surface-macro-ui/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included — Constitution Principle I ("Test-First & Comprehensive Coverage") is NON-NEGOTIABLE for this project; every story below ships its test tasks before/alongside implementation.

**Organization**: Tasks are grouped by user story (US1/US2/US3, matching [spec.md](./spec.md)) so each can be implemented, tested, and shipped independently — except the one hard technical dependency called out below.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and relative to the repo root

## Path Conventions (from plan.md)

Web app, three services: `agent-runner/` (Python 3.12, pytest + mongomock), `backend/` (Python 3.12/FastAPI, pytest), `frontend/` (React/TS, Vitest). Component specs under `specs/component-specs/`.

---

## Phase 1: Setup

**Purpose**: Confirm the baseline is green before changing anything.

- [X] T001 Confirm `020-surface-macro-ui` branch is checked out; run and record a passing baseline: `pytest agent-runner/tests -q`, `pytest backend/tests -q`, `cd frontend && npx vitest run`, `ruff check backend/ && ruff check agent-runner/ scripts/`

---

## Phase 2: Foundational

**Purpose**: N/A for this feature — no shared infrastructure, entities, or collections are introduced (research.md D1–D7 confirm every piece reuses an existing pattern: `macro_analysis_cache`, the agent-runner poll loop, the `market.py` router). Every task belongs to a specific user-story phase below. Proceed directly to Phase 3.

---

## Phase 3: User Story 1 - Ticker research no longer runs macro/economic analysis (Priority: P1) 🎯 MVP

**Goal**: Per-ticker analysis (`crew.py`) stops computing, storing, and synthesizing macro/economic data. Analysis runs get cheaper and faster; stored `sub_reports` never contain a `macro` key; the final verdict no longer weighs macro.

**Independent Test**: Trigger analysis for any ticker; confirm no macro-analyst LLM call happens during that run and the resulting `sub_reports` has exactly `{technical, fundamental, insider, institutional, sentiment, recommendation}` — no `macro`. See [quickstart.md](./quickstart.md) §2.

### Tests for User Story 1

> Write these first; they must FAIL against the current code before the implementation tasks below make them pass.

- [X] T002 [P] [US1] Update `agent-runner/tests/test_crew.py`: assert `set(doc["sub_reports"])` excludes `"macro"` (6 keys, not 7), assert LLM call count is 7 (was 8), and remove/retarget the cross-ticker macro-cache assertion (`test_macro_analyst_cached_across_tickers_in_same_sector`) since crew no longer exercises that path — per [contracts/macro-worker.md](./contracts/macro-worker.md) Part C, test obligation 1

### Implementation for User Story 1

- [X] T003 [US1] Remove the `"macro"` and `"yield_curve"` prefetch jobs from `Crew._prefetch` in `agent-runner/crew.py` (keep `"breadth"` — still used by gap_analysis/market_flow/recommender)
- [X] T004 [US1] Remove the `macro_analyst` import and its call, and drop `"macro"` from `sub_reports`, in `agent-runner/crew.py` (depends on T003, same file)
- [X] T005 [P] [US1] Remove the macro-weighting language from `SYSTEM` and instruction #2 in `agent-runner/agents/portfolio_strategist.py` (FR-003 — intentional verdict-behavior change per [research.md](./research.md) D3)
- [X] T006 [P] [US1] Update `specs/component-specs/agent-runner/crew.md` to describe the pipeline as 6 agents + strategist (macro removed from "Full Phase 5 roster")
- [X] T007 [US1] Run `pytest agent-runner/tests/test_crew.py -q` and `ruff check agent-runner/` to confirm User Story 1 is green (depends on T002, T004, T005)

**Checkpoint**: Ticker analysis is fully decoupled from macro. Deployable alone — cheaper/faster runs — but macro output is now computed nowhere. Proceed to US2 so it isn't invisible again.

---

## Phase 4: User Story 2 - Dedicated Macro page showing economy-wide context (Priority: P1)

**Goal**: A "Macro" nav entry opens a page showing market-breadth (NYMO/NAMO) divergence cards plus every sector's macro read, refreshed by an independent process (not triggered by any ticker analysis).

**Independent Test**: Click "Macro" in the nav; confirm the page shows breadth cards and per-sector reads with freshness, sourced from `GET /market/macro`, without any ticker analysis having run. See [quickstart.md](./quickstart.md) §3.

**⚠️ Hard dependency on US1**: `macro_analyst.run()`'s signature change (T008 below) MUST NOT land before `crew.py` stops calling the old ticker-based signature (US1's T004) — otherwise `crew.py` breaks mid-call. Complete Phase 3 fully before starting T008.

### Tests for User Story 2

- [X] T009 [P] [US2] Update `agent-runner/tests/test_phase5_agents.py`'s macro test (`test_macro_agent_attaches_hard_numbers`) to call `macro_analyst.run(sector, ...)` instead of `run(ticker, ...)` — per [contracts/macro-worker.md](./contracts/macro-worker.md) Part B
- [X] T010 [P] [US2] Update `agent-runner/tests/test_macro_analyst_cache.py` to the sector-based signature; cache-behavior assertions (per-sector upsert, 7-day freshness) carry over unchanged
- [X] T011 [US2] Write `agent-runner/tests/test_macro_worker.py` covering all 6 cases in [contracts/macro-worker.md](./contracts/macro-worker.md) Part A test obligations (no sectors → 0/untouched; new sector → refreshed; fresh doc → skipped; stale doc → refreshed; one sector's LLM failure doesn't block another; throttle window → second call is a no-op) — mongomock + fake LLM, must FAIL until T012 exists
- [X] T015 [US2] Write `backend/tests/test_market.py` cases for `GET /market/macro` per [contracts/macro-api.md](./contracts/macro-api.md) test obligations (empty collection → `{"sectors": [], "as_of": null}`; two seeded docs → newest-first, `as_of` correct, `_id` absent) — must FAIL until T016 exists
- [X] T019 [US2] Write `frontend/src/pages/Macro.test.tsx` per [contracts/frontend-pages.md](./contracts/frontend-pages.md) Macro page test obligations (sector cards render from mocked `/market/macro`; freshness text per card; breadth cards render from mocked flow events; empty state when both sources empty; stale read still renders with visible age) — must FAIL until T020 exists

### Implementation for User Story 2

- [X] T008 [US2] Refactor `agent-runner/agents/macro_analyst.py`: `run(sector: str, context: dict, client=None, db=None)` — drop the `ticker` parameter, remove ticker mentions from the prompt; keep SCHEMA, per-sector cache read/write, and `CACHE_DAYS = 7` unchanged — per [contracts/macro-worker.md](./contracts/macro-worker.md) Part B (blocked on US1 Phase 3 completion; unblocks T009, T010, T011, T012)
- [X] T012 [US2] Implement `agent-runner/macro_worker.py`: `run_macro_refresh_if_due(now, db=None, client=None) -> int` — hourly in-process throttle, `ticker_index.distinct("sector", ...)` enumeration, per-sector staleness check against `macro_analysis_cache`, per-sector try/except refresh via `macro_analyst.run` — per [contracts/macro-worker.md](./contracts/macro-worker.md) Part A (depends on T008, T011)
- [X] T013 [US2] Wire `run_macro_refresh_if_due(now=now)` into the loop in `agent-runner/main.py`, alongside `run_daily_breadth_if_due` — per [contracts/macro-worker.md](./contracts/macro-worker.md) Part D (depends on T012)
- [X] T014 [P] [US2] Add `MACRO_ANALYSIS_CACHE = "macro_analysis_cache"` constant to `backend/db.py`, matching `agent-runner/tools/db.py` (Constitution Principle VI)
- [X] T016 [US2] Implement `GET /market/macro` in `backend/routers/market.py`: project all `macro_analysis_cache` docs newest-`computed_at`-first, flatten `result` fields per [contracts/macro-api.md](./contracts/macro-api.md), `as_of` = newest `computed_at` or `null` (depends on T014, T015)
- [X] T017 [P] [US2] Add `SectorMacroRead` (`MacroReport & { sector: string; computed_at: string }`) and `MacroReads` (`{ sectors: SectorMacroRead[]; as_of: string | null }`) types to `frontend/src/api/types.ts`
- [X] T018 [US2] Add `useMacroReads()` hook (TanStack Query, `staleTime` 1 day, no polling) in `frontend/src/hooks/useMacro.ts` calling `GET /market/macro` (depends on T017)
- [X] T020 [US2] Implement `frontend/src/pages/Macro.tsx` per [contracts/frontend-pages.md](./contracts/frontend-pages.md): heading + freshness, market-breadth section (`MarketFlowCard`s via `useMarketFlowEvents`, `BreadthDivergenceChart` via `useMarketBreadth`), per-sector read grid (signal badge, confidence, all commentary fields, hard numbers, freshness), empty state when both sources are empty (depends on T018, T019)
- [X] T021 [US2] Add a "Macro" nav link (`/macro`) to `frontend/src/components/layout/Navbar.tsx`
- [X] T022 [US2] Register the `/macro` route with `Macro` page in `frontend/src/App.tsx` (depends on T020, T021)
- [X] T023 [P] [US2] Update component specs: `specs/component-specs/agent-runner/agents/macro_analyst.md` (sector-based signature) and `specs/component-specs/agent-runner/main.md` (new worker in the loop); add `specs/component-specs/agent-runner/macro_worker.md`, `specs/component-specs/frontend/pages/Macro.md`, and a `/market/macro` entry in the market router's component spec
- [X] T024 [US2] Run `pytest agent-runner/tests -q`, `pytest backend/tests/test_market.py -q`, `cd frontend && npx vitest run src/pages/Macro.test.tsx`, and both `ruff check` gates to confirm User Story 2 is green (depends on T009–T023)

**Checkpoint**: Macro is fully decoupled (US1) and fully visible again (US2) — the original problem is solved. `Feed`/home page still shows its now-redundant breadth cards; US3 cleans that up.

---

## Phase 5: User Story 3 - Stocks page simplified to stock-specific content only (Priority: P2)

**Goal**: The renamed "Stocks" page (formerly "Feed") shows only the filter bar and stock tile board — no breadth cards, no macro content, since both now live on the Macro page.

**Independent Test**: Open the app's landing page; nav/title read "Stocks", URL unchanged, only filter bar + tiles render. See [quickstart.md](./quickstart.md) §4.

**Dependency**: Requires Phase 4 (US2) complete — the breadth cards being removed here must already have a home on the Macro page.

### Tests for User Story 3

- [X] T025 [US3] `git mv frontend/src/pages/Feed.test.tsx frontend/src/pages/Stocks.test.tsx` and update: remove/relocate breadth-card assertions (now covered by `Macro.test.tsx`), update component import/name, add an assertion that no `MarketFlowCard` renders even when flow events exist — must FAIL until T026 exists

### Implementation for User Story 3

- [X] T026 [US3] `git mv frontend/src/pages/Feed.tsx frontend/src/pages/Stocks.tsx`; rename the component to `Stocks`, update `document.title` to `"StockAI — Stocks"`, remove the `MarketFlowCard` pinned block and the `useMarketFlowEvents`/`useMarketBreadth` imports/usage and `MARKET_EVENT_MAX_AGE_DAYS` filter logic; keep `FilterBar`, tile board, infinite scroll, skeleton/error/empty states unchanged (depends on T025)
- [X] T027 [US3] Update the `Feed` import/usage to `Stocks` in `frontend/src/App.tsx` (route stays `"/"`) (depends on T026)
- [X] T028 [US3] Update the nav label `"Feed"` → `"Stocks"` in `frontend/src/components/layout/Navbar.tsx` (depends on T021 from Phase 4, same file)
- [X] T029 [P] [US3] Update `specs/component-specs/frontend/pages/Feed.md` to describe the simplified Stocks page scope (rename file if the spec-doc convention expects it)
- [X] T030 [US3] Run `cd frontend && npx vitest run src/pages/Stocks.test.tsx` to confirm User Story 3 is green (depends on T025, T026, T027, T028)

**Checkpoint**: All three user stories independently functional. Stocks page is stock-specific only; Macro page is economy-specific only; ticker research no longer touches macro at all.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full-stack verification once all stories are in.

- [X] T031 [P] Run the full [quickstart.md](./quickstart.md) validation end-to-end. Rebuilt & restarted `agent-runner`/`backend`/`frontend` on this branch's code, then verified live against the real running stack (not just mocks):
  - §1 automated suites — see T033 (277+63+76 tests, ruff/tsc clean)
  - §2 (US1) — enqueued a real NVDA analysis (`POST /queue/NVDA`); the resulting doc (`timestamp: 2026-08-15T21:18:15`, post-rebuild) has `sub_reports` = exactly `{fundamental, insider, institutional, recommendation, sentiment, technical}` — no `macro`, confirming ticker analysis no longer touches it
  - §3 (US2) — this dev DB's `ticker_index` docs had no `sector` populated (pre-existing data gap, unrelated to this feature), so the worker correctly no-op'd; set NVDA's `sector: "Technology"` directly and restarted `agent-runner` to reset its in-process throttle — logs then showed `macro worker: refreshed 1/1 due sectors`, and `GET /market/macro` served the real LLM-generated Technology read (`sector_rotation_signal: "favorable"`, etc.) alongside the old pre-existing "unknown" sector doc, newest-first, `as_of` correct
  - §4 (US3) — `curl` confirmed `http://localhost:5173/` and `/macro` both return 200 with no frontend container errors; `chromium-cli` wasn't available in this Windows environment for a screenshot, so DOM-level confirmation (no breadth cards on Stocks, cards present on Macro) relies on the Vitest suites (T024/T030), which mock the exact API shapes just confirmed live above
  - §5 (verdict-input check) — `grep -i macro agent-runner/agents/portfolio_strategist.py` returns nothing
- [X] T032 [P] Run `ruff check backend/ && ruff check agent-runner/ scripts/` as a final gate (Constitution Development Workflow)
- [X] T033 [P] Run full suites: `pytest agent-runner/tests -q`, `pytest backend/tests -q`, `cd frontend && npx vitest run` — confirm all green with no regressions outside this feature's scope
- [X] T034 [P] Update `specs/architecture.mermaid`: remove the `Prefetch --> TL_Macro` edge from the per-ticker agent flow, add the macro worker as an independent path from `TL_Macro` (mirroring the existing breadth-worker pattern), and add the Macro page node to the frontend section

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Empty for this feature — nothing blocks Phase 3.
- **User Story 1 (Phase 3)**: Depends on Setup only. Independently deployable.
- **User Story 2 (Phase 4)**: Depends on Setup **and** User Story 1 being fully complete (T008 cannot start before T004 lands — see the hard-dependency note in Phase 4). This is the one exception to story independence in this feature, driven by `macro_analyst.py`'s signature being a shared contract between the old caller (crew) and the new caller (worker).
- **User Story 3 (Phase 5)**: Depends on User Story 2 being complete (the breadth cards it removes must already be rendered on the Macro page).
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests written and failing before implementation (T002 before T003–T004; T009/T010/T011/T015/T019 before T008/T012/T016/T020; T025 before T026).
- Agent-runner changes before the backend endpoint that reads their output; backend endpoint before the frontend hook that calls it; hook before the page that renders it.
- Story complete (verification task) before moving to the next priority phase.

### Parallel Opportunities

- T002 alongside baseline work has no parallel peer in Setup (single task).
- Within US1: T005 and T006 are `[P]` (different files, independent of T003/T004).
- Within US2: T009 and T010 are `[P]` of each other; T014 and T017 are `[P]` of the agent-runner track; T023 is `[P]` (docs only). T008 gates T009–T012 but T014/T017 don't depend on T008 and can start as soon as US1 is done.
- Within US3: T029 is `[P]` (docs only, independent of the code rename).
- All of Phase 6 (T031–T034) is `[P]` — independent verification/doc tasks.

---

## Parallel Example: User Story 2

```bash
# Once US1 (Phase 3) is complete, launch together:
Task: "Update agent-runner/tests/test_phase5_agents.py macro test to sector signature"
Task: "Update agent-runner/tests/test_macro_analyst_cache.py to sector signature"
Task: "Add MACRO_ANALYSIS_CACHE constant to backend/db.py"
Task: "Add SectorMacroRead/MacroReads types to frontend/src/api/types.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup.
2. Phase 2: Foundational — nothing to do, skip straight through.
3. Phase 3: User Story 1.
4. **STOP and VALIDATE**: `pytest agent-runner/tests/test_crew.py -q`; confirm 7 LLM calls, no `macro` in `sub_reports`.
5. This MVP delivers real value alone (cheaper/faster ticker analysis) but does not solve the original "macro is invisible" problem — that requires US2. Given both are P1 in the spec, treat US1+US2 together as the true MVP for this feature.

### Incremental Delivery

1. Setup → Phase 3 (US1) → validate → optionally ship (cost/speed win, macro temporarily uncomputed anywhere).
2. Phase 4 (US2) → validate → ship (macro fully decoupled and visible again — feature's core promise fulfilled).
3. Phase 5 (US3) → validate → ship (UI cleanup — Stocks page decluttered).
4. Phase 6 → final verification across all three.

### Parallel Team Strategy

Given the hard US1→US2 dependency, a two-person split works best as: Developer A takes US1 (Phase 3) solo first; once T004 lands, Developer A continues into US2's agent-runner/backend tasks (T008, T011–T016) while Developer B starts US2's frontend tasks (T017–T022) in parallel, since those only need the `/market/macro` contract shape (already fixed in [contracts/macro-api.md](./contracts/macro-api.md)), not the running endpoint. US3 (Phase 5) starts once US2 is fully merged.

---

## Notes

- `[P]` tasks touch different files with no unmet dependency.
- `[Story]` labels map every implementation task to spec.md's US1/US2/US3 for traceability (Constitution Principle II).
- The single cross-story dependency (US2 on US1) is intentional and documented, not an oversight — see [research.md](./research.md) D2/D3.
- Commit after each task or logical group; stop at each checkpoint to validate that story independently before continuing.
