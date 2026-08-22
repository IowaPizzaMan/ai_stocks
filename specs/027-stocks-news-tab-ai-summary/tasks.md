# Tasks: Stocks Page News Tab and Cross-Stock AI Summary

**Input**: Design documents from `specs/027-stocks-news-tab-ai-summary/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included — constitution Principle I (Test-First & Comprehensive Coverage) is NON-NEGOTIABLE: pytest for the new backend router and the agent-runner tool/agent/job handler, Vitest + React Testing Library for the Stocks page and the new digest panel.

**Organization**: Tasks are grouped by user story (spec.md priorities) so each story can be implemented and verified independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to spec.md user stories (US1–US3)
- Every task names an exact file path

## Path Conventions (from plan.md)

- Backend: `backend/db.py`, `backend/routers/`, `backend/main.py`, `backend/tests/`
- Agent-runner: `agent-runner/tools/`, `agent-runner/agents/`, `agent-runner/tests/`
- Frontend: `frontend/src/api/`, `frontend/src/hooks/`, `frontend/src/components/`, `frontend/src/pages/`

---

## Phase 1: Setup

**Purpose**: Collection-name constant and the shared frontend types every later phase reads or writes against.

- [X] T001 [P] Add `PORTFOLIO_DIGEST_CACHE = "portfolio_digest_cache"` to the collection-name block in `backend/db.py` (per [data-model.md](./data-model.md), a singleton document — no unique-key index needed, callers use `find_one({})`/`replace_one({}, ..., upsert=True)`)
- [X] T002 [P] Add the same `PORTFOLIO_DIGEST_CACHE = "portfolio_digest_cache"` constant to `agent-runner/tools/db.py`, keeping the two services' collection names in sync (constitution Principle VI)
- [X] T003 [P] Add `PortfolioDigestHighlight` and `PortfolioDigestResponse` to `frontend/src/api/types.ts` per [contracts/portfolio-digest-api.md](./contracts/portfolio-digest-api.md), and change `QueueJob.ticker` to optional (`ticker?: string`) plus add `job_type?: string`, per [data-model.md](./data-model.md)

**Checkpoint**: Names and types exist; nothing behavioral yet.

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: A shared tab-bar component. US1 needs it to add tabs to the Stocks page; extracting it from `StockDetail.tsx` first (rather than copy-pasting tab markup) is what keeps the two tabbed pages consistent (research.md R3, constitution Principle VI).

**⚠️ CRITICAL**: No Stocks-page tab work (US1, and everything layered on it) may begin until this phase is complete.

- [X] T004 [P] Vitest in `frontend/src/components/shared/TabBar.test.tsx`: renders one button per tab, applies the active style to the tab matching `activeTab`, calls the provided select handler with a tab's `id` on click, and renders optional trailing content (the detail page's "analyzed X ago" slot) when provided
- [X] T005 Implement `frontend/src/components/shared/TabBar.tsx`: extract the `<nav>` tab-button markup currently inline in `frontend/src/pages/StockDetail.tsx` (lines ~162–182) into a reusable component taking `tabs: {id, label}[]`, `activeTab: string`, `onSelect: (id: string) => void`, and an optional trailing-content slot (depends on T004)
- [X] T006 Refactor `frontend/src/pages/StockDetail.tsx` to render `TabBar` in place of its inline tab `<nav>`, passing its existing `TABS`, `activeTab`, and a select handler that calls `navigate(#${id}, {replace: true})` — no behavior change; existing `StockDetail` tests must continue to pass unmodified (depends on T005)

**Checkpoint**: `TabBar` exists and is proven not to regress the one page already using tabs — Stocks-page tab work can now begin.

---

## Phase 3: User Story 1 - Dedicated News Tab (Priority: P1) 🎯 MVP

**Goal**: The Stocks page's default view shows only the filter bar and stock grid; a new **News** tab shows the market-wide headline list that used to sit below the grid, unchanged in content and behavior.

**Independent Test**: Open the Stocks page — default view has no news list. Select the News tab — the same ≤20-article, no-infinite-scroll market news list (spec 022) appears there.

### Tests for User Story 1

- [X] T007 [P] [US1] Vitest in `frontend/src/pages/Stocks.test.tsx`: with no hash in the URL, the rendered page includes the filter bar and the analysis grid, and does **not** render `MarketNewsPanel`'s content
- [X] T008 [US1] Vitest in `frontend/src/pages/Stocks.test.tsx`: with `#news` in the URL hash, the rendered page shows `MarketNewsPanel`'s content and does **not** render the filter bar/grid. **Not [P]** — same file as T007; add after T007 lands
- [X] T009 [US1] Vitest in `frontend/src/pages/Stocks.test.tsx`: an unrecognized hash (e.g. `#bogus`) falls back to the default (grid) tab, mirroring `StockDetail`'s existing fallback behavior (spec 021 FR-027). **Not [P]** — same file as T007/T008

### Implementation for User Story 1

- [X] T010 [US1] In `frontend/src/pages/Stocks.tsx`, add a `TABS` array (`{id: "grid", label: "Stocks"}`, `{id: "news", label: "News"}`), hash-based `activeTab` derivation with fallback to `"grid"` (same pattern as `StockDetail.tsx`), and render the `TabBar` from Phase 2 (depends on T006, T007–T009)
- [X] T011 [US1] In `frontend/src/pages/Stocks.tsx`, move `<MarketNewsPanel />` out of the always-rendered flow into the `news` tab's content branch; the filter bar and grid render only in the `grid` tab's content branch (depends on T010)

**Unplanned fix found during T010/T011**: `FilterBar.tsx`'s ticker-sync `useEffect` called `setSearchParams` unconditionally on every mount (even when nothing changed). React Router's `setSearchParams` navigates via a hash-less relative URL, which silently cleared the page's `#news` hash on mount — breaking hash-based tab selection before it could ever render. Fixed by guarding the effect to only call `setSearchParams` when the debounced value actually differs from the current URL param.

**Unplanned fix found during T034**: `frontend/src/pages/Stocks.market-news.test.tsx` (a pre-existing spec-022 test file) asserted the old inline placement (news rendered alongside the grid on the default view). Updated it to navigate to `#news` for the news-specific assertions — content/behavior (filter independence, graceful degradation) is unchanged per FR-002, only the location moved — and added a new test confirming the grid tab no longer requests `/market/news` at all now that the panel isn't mounted there.

**Checkpoint**: US1 independently functional — News lives on its own tab, default tab shows only filter bar + grid (grid still auto-fetches on scroll at this point; that's US2).

---

## Phase 4: User Story 2 - Bounded Grid, No Auto-Scroll Fetching (Priority: P1)

**Goal**: The grid tab's content sits in a bounded, internally scrollable region; the browser window never needs to scroll to see the filter bar/tab bar; loading more analyses requires an explicit action instead of happening automatically on scroll.

**Independent Test**: With enough tracked stocks to overflow one screen, confirm the filter bar and tab bar stay in view without scrolling the page, scrolling inside the grid area triggers no network request by itself, and a visible "Load more" control fetches the next page on click.

### Tests for User Story 2

- [X] T012 [US2] Vitest in `frontend/src/pages/Stocks.test.tsx`: rendering the grid tab does not call `fetchNextPage` on mount or on a simulated scroll/intersection event (no `IntersectionObserver` wiring remains); a "Load more" button is rendered whenever `hasNextPage` is true and calls `fetchNextPage` when clicked. **Not [P]** — same file as US1's tab tests
- [X] T013 [US2] Vitest in `frontend/src/pages/Stocks.test.tsx`: the grid tab's content renders inside a wrapper carrying a scrollable-container class (structural stand-in for "only this region scrolls"), and that wrapper is a sibling of, not a descendant of, the filter bar/tab bar elements. **Not [P]** — same file

### Implementation for User Story 2

- [X] T014 [US2] In `frontend/src/pages/Stocks.tsx`, remove the `useIntersectionObserver` import/call and the `loadMoreRef` sentinel `<div>`; add a "Load more" `<button>` in the grid tab that calls `fetchNextPage()` when `hasNextPage && !isFetchingNextPage` (depends on T012)
- [X] T015 [US2] Restructure `frontend/src/pages/Stocks.tsx`'s root into a bounded flex layout per [research.md R1](./research.md#r1--bounded-layout-scoped-to-the-stocks-page-only): a non-shrinking header (title/filter bar/tab bar) and a `flex-1 overflow-y-auto` body holding the active tab's content, sized via a viewport-relative height scoped to this page only — no changes to `App.tsx`, `Navbar.tsx`, or `Sidebar.tsx` (depends on T013, T014)

**Checkpoint**: US1 + US2 — News on its own tab, default tab bounded and free of auto-scroll fetching. Deep-linking to an unknown tab still falls back correctly (US1's T009 covers this after US2's restructuring too — re-run it).

---

## Phase 5: User Story 3 - Cross-Stock AI Summary with Manual Regeneration (Priority: P2)

**Goal**: The default tab includes a summary panel synthesizing every tracked stock's stored AI analysis into an overview plus specific guidance, with a manual regenerate control that reuses the existing `work_queue` job-dispatch mechanism.

**Independent Test**: With at least one analyzed stock, the panel shows synthesized guidance and a last-generated timestamp; clicking regenerate shows a busy state, then updates the panel; a failed regeneration leaves the prior summary visible, marked stale.

### Tests for User Story 3

**Backend**

- [X] T016 [P] [US3] pytest in `backend/tests/test_portfolio.py`: `GET /portfolio/digest` — no stored document → `as_of`/`overview` `null`, `stock_count`/`total_tracked_count` `0`, `capped: false`, `stale: false`; a document with only success fields → `stale: false`; a document whose `last_error_at` is newer than `generated_at` → `stale: true`; a document whose `last_error_at` is older than `generated_at` → `stale: false`
- [X] T017 [US3] pytest in `backend/tests/test_portfolio.py`: `POST /portfolio/digest/regenerate` inserts a `work_queue` document with `job_type="portfolio_digest"` and no `ticker`; a second call while one is `pending`/`running` returns `already_queued` and does not insert a second document. **Not [P]** — same file as T016

**Agent-runner**

- [X] T018 [P] [US3] pytest in `agent-runner/tests/test_portfolio_digest.py`: `tools/portfolio.py`'s gather/condense/rank function — zero `analyses` documents → empty list, `total_tracked_count: 0`; ≤25 documents → all included, `capped: False`; >25 documents → exactly 25 returned, sorted by conviction (high → medium → low, ties broken by most-recently-analyzed), `capped: True`; each condensed entry carries `{ticker, signal, conviction, summary, key_trends, flags, news_stance}` per [research.md R5](./research.md#r5--synthesis-input-source-shape-and-cap)
- [X] T019 [US3] pytest in `agent-runner/tests/test_portfolio_digest.py`: `agents/portfolio_digest.py`'s `run()` — with `generate_json` mocked, the prompt includes every condensed stock passed in, and the parsed `{overview, highlights}` matches the declared schema. **Not [P]** — same file as T018
- [X] T020 [P] [US3] pytest in `agent-runner/tests/test_admin_jobs.py`: `run_portfolio_digest(db)` — zero `analyses` documents → success outcome, `stock_count: 0`, no LLM call, `portfolio_digest_cache` written with empty `overview`/`highlights`; >25 documents → exactly 25 passed through to the agent; an LLM failure writes `last_error`/`last_error_at` to `portfolio_digest_cache`, re-raises, and leaves any prior `generated_at`/`overview` untouched
- [X] T021 [P] [US3] pytest in `agent-runner/tests/test_queue_worker.py`: a `work_queue` document with `job_type="portfolio_digest"` and no `ticker` is claimed by `claim_and_run_next` and dispatched through `_run_admin_job` to the registered handler — first real exercise of that dispatch branch for a job type other than `economics_pull`

**Frontend**

- [X] T022 [P] [US3] Vitest in `frontend/src/components/feed/PortfolioDigestPanel.test.tsx`: renders an empty/prompt state when `as_of` is `null`; renders `overview` text and `highlights` (each linking its ticker to `/stocks/{ticker}`) when populated; shows a stale indicator (without hiding the content) when `stale: true`; shows a "not all tracked stocks included" note when `capped: true`; disables the regenerate control and shows a busy indicator when a `portfolio_digest` job is passed in as pending/running
- [X] T023 [US3] Vitest in `frontend/src/pages/Stocks.test.tsx`: applying a sector/signal/ticker/conviction filter does not change the digest panel's rendered content and fires no new digest request (FR-007a). **Not [P]** — same file as US1/US2's Stocks tests

### Implementation for User Story 3

**Backend**

- [X] T024 [US3] Implement `backend/routers/portfolio.py`: `GET /portfolio/digest` (reads the `portfolio_digest_cache` singleton, derives `stale` by comparing `last_error_at` to `generated_at`) and `POST /portfolio/digest/regenerate` (dedup-enqueues a `job_type="portfolio_digest"` document into `work_queue`) per [contracts/portfolio-digest-api.md](./contracts/portfolio-digest-api.md) (depends on T001, T016, T017)
- [X] T025 [US3] Register the new router in `backend/main.py` (`from routers import portfolio` + `app.include_router(portfolio.router)`, alongside the existing router registrations) (depends on T024)

**Agent-runner**

- [X] T026 [US3] Implement the gather/condense/rank function in `agent-runner/tools/portfolio.py`: read every `analyses` document, condense each to `{ticker, signal, conviction, summary, key_trends, flags, news_stance}` (news_stance from `sub_reports.news.stance`), sort by conviction then recency, cap at 25, return the capped list plus `total_tracked_count` and `capped` (depends on T018)
- [X] T027 [US3] Implement `agent-runner/agents/portfolio_digest.py`: `SYSTEM` prompt, JSON schema for `{overview: string, highlights: [{ticker, signal, conviction, note}]}`, and `run(stocks: list, client=None) -> dict` calling `llm.generate_json`, mirroring `agents/portfolio_strategist.py`'s structure (depends on T019, T026)
- [X] T028 [US3] Implement `run_portfolio_digest(db) -> int` in `agent-runner/tools/portfolio.py`: calls the gather/condense/rank function and the agent, upserts `portfolio_digest_cache` with `generated_at`/`overview`/`highlights`/`stock_count`/`total_tracked_count`/`capped` on success; on any exception writes `last_error`/`last_error_at` (leaving prior success fields untouched) and re-raises; returns `stock_count` (depends on T020, T026, T027)
- [X] T029 [US3] Register `JOB_HANDLERS["portfolio_digest"] = run_portfolio_digest` in `agent-runner/tools/admin_jobs.py` (deliberately **not** added to `JOB_DATASETS` — freshness is read from `portfolio_digest_cache`, not `dataset_meta`, per [research.md R6](./research.md#r6--persisting-the-digest-and-representing-staleness)) (depends on T021, T028)

**Frontend**

- [X] T030 [P] [US3] Create `frontend/src/hooks/usePortfolioDigest.ts`: TanStack Query hook for `GET /portfolio/digest`, no arguments, no filter state in the query key, no `refetchInterval` (depends on T003)
- [X] T031 [P] [US3] Create `frontend/src/hooks/usePortfolioDigestRegenerate.ts`: mutation hook for `POST /portfolio/digest/regenerate` whose `onSuccess` invalidates the `["queue"]` query key (depends on T003)
- [X] T032 [US3] Extend `useQueueStatus`'s drain-invalidate list in `frontend/src/hooks/useQueue.ts` to also invalidate `["portfolio-digest"]` when the queue empties, alongside its existing `["feed"]`/`["analysis"]`/`["pull-metrics"]`/`["price"]` invalidations (depends on T030)
- [X] T033 [US3] Create `frontend/src/components/feed/PortfolioDigestPanel.tsx`: renders `overview` (via `FormattedProse`), `highlights` (ticker links, signal/conviction pills, note text), an "as of"/stale label, a capped note, and a regenerate button wired to `usePortfolioDigestRegenerate` with its busy state derived from `useQueueStatus`'s `pending`/`running` arrays (looking for `job_type === "portfolio_digest"`) (depends on T022, T030, T031, T032)
- [X] T034 [US3] Render `<PortfolioDigestPanel />` at the top of the grid tab's scrollable content in `frontend/src/pages/Stocks.tsx`, above the grouped signal sections (depends on T023, T033, and US1/US2's T011/T015 for the tab + bounded-layout skeleton it renders inside)

**Superseded by Phase 7**: T034's stacked-above placement was implemented before the spec was clarified further (2026-08-22, FR-007b) to require the digest panel beside the grid instead. See Phase 7 below — T034's checkbox is left checked as a historical record of what was built and verified at the time, not as a claim that the current layout still matches the spec.

**Checkpoint**: All three stories independently functional — News on its own tab, bounded auto-fetch-free grid, and a manually-regenerable cross-stock summary that survives a failed regeneration without going blank.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T035 [P] Run `ruff check backend/` and `ruff check agent-runner/ scripts/` and fix any findings (constitution quality gate)
- [X] T036 Run the full suites — backend: `cd backend; .\.venv\Scripts\python.exe -m pytest tests -q`; agent-runner: `cd agent-runner; .\.venv\Scripts\python.exe -m pytest tests -q`; frontend: `npx vitest run` and `npx tsc --noEmit` — confirm no regressions. Results: backend 196/196, agent-runner 425/425, frontend 335/335 (40 files), `tsc --noEmit` clean.
- [X] T037 Execute [quickstart.md](./quickstart.md) scenarios against the running stack — **partially run live, against the user's real already-running Docker Compose stack and real tracked-stock data** (discovered mid-task; see note below).

**T037 results**: The user's stack (mongodb/backend/agent-runner/frontend/ollama) was already up from ~40 minutes earlier. Ran the backend locally (`.venv`) against the same live MongoDB on an unused port to avoid touching the live backend container, and invoked `queue_worker.claim_and_run_next` directly from the agent-runner `.venv` against the same live Ollama:
- Scenario 3 (empty state): confirmed — `GET /portfolio/digest` returned the all-null/zero empty state before any regeneration.
- Scenario 4 (regenerate produces guidance): confirmed with **real data** — enqueued, ran via the actual local Ollama model against 41 real tracked stocks, produced a genuine multi-paragraph overview and 14 ticker-specific highlights (e.g. CBRS/MOS/EL/VIK real narratives), persisted to `portfolio_digest_cache`, and re-fetched correctly via the API. Dedup on a second immediate `POST /regenerate` while pending also confirmed live (`already_queued`, same `job_id`).
- Scenario 7 (cap/priority): confirmed with real data — 41 tracked stocks, `stock_count: 25`, `capped: true`.
- Scenario 8 (market news unchanged): confirmed — `/market/news` still serves normally.
- Scenario 5 (failure → stale) was **not** cleanly verified live: stopping the live Ollama container to test it raced against the user's own long-running `agent-runner` container, which claimed the retry job first and failed it with "no handler for job_type" — an artifact of that container having imported `admin_jobs.py` into memory *before* this session's code changes landed on disk (plain `python main.py` has no hot-reload), not a defect in the feature. This exact failure/stale path **is** deterministically covered by `agent-runner/tests/test_admin_jobs.py::test_llm_failure_writes_last_error_and_reraises_leaving_prior_success_untouched`, which passes.
- Scenarios 1, 2, 6 (tabs, bounded layout, filter independence) are UI/browser scenarios not exercised live in this pass — covered by the Vitest suites (T007–T013, T023, T029) instead.

**Side effects and cleanup**: stopping/restarting the live Ollama container to test the failure path was an unplanned interaction with the user's running environment — Ollama was restarted immediately after (confirmed healthy again) and my ad-hoc backend instance was killed. The real `portfolio_digest_cache` document written during the successful run was left in place (desired feature behavior, not test pollution). **The user's live `backend` and `agent-runner` containers are still running pre-027 code** (unrebuilt since ~40 minutes before this session's changes) — they will need `docker compose up -d --build` (or equivalent) before the new tab/News/digest behavior appears in their running app; this was not done automatically since rebuilding/restarting their live containers is a user decision.

---

## Phase 7: FR-007b Follow-up - Digest Panel Beside the Grid (Priority: P2, US3)

**Why this phase exists**: Spec 027 was clarified again on 2026-08-22 (FR-007b), after Phases 1-6 above were already fully implemented and verified: the digest panel must render **beside** the stock grid as a second column (grid in the primary/left position), not stacked above it as T034 originally built it. [research.md R9](./research.md#r9--digest-panel-placement-side-by-side-with-the-grid-not-stacked) records the decision. This phase is the minimal delta on top of the completed feature — no backend, agent-runner, or panel-internals changes are needed; only `Stocks.tsx`'s markup and its structural test change.

**Goal**: On the grid tab, the stock grid and `<PortfolioDigestPanel />` render as two columns inside the existing bounded/scrollable body (T015), grid first/primary, digest panel second — not stacked.

**Independent Test**: Open the Stocks page's default tab. Confirm the digest panel appears alongside the grid (a second column), not above or below it, and that the grid still occupies the primary/first position.

- [X] T038 [US3] Update the structural Vitest assertion in `frontend/src/pages/Stocks.test.tsx` (extends/replaces the digest-placement portion of T023/T034's coverage): assert the grid tab's grouped signal sections and `<PortfolioDigestPanel />` render as sibling columns of a two-column row wrapper, with the grid column preceding the digest column in DOM order, per [research.md R9](./research.md#r9--digest-panel-placement-side-by-side-with-the-grid-not-stacked). **Not [P]** — same file as existing Stocks tests
- [X] T039 [US3] Restructure the grid tab's body markup in `frontend/src/pages/Stocks.tsx`: wrap the grouped signal sections and `<PortfolioDigestPanel />` in a two-column row (grid in the first/primary column, `<PortfolioDigestPanel />` in a second column alongside it) instead of the panel sitting above the grouped sections; keep both inside the existing `flex-1 overflow-y-auto` scroll region from T015 (depends on T038; supersedes T034's stacked-above placement)
- [X] T040 Run `npx vitest run frontend/src/pages/Stocks.test.tsx frontend/src/components/feed/PortfolioDigestPanel.test.tsx` and `npx tsc --noEmit`; confirm no regressions in either suite

**Checkpoint**: Digest panel placement matches FR-007b; no other behavior (data, regenerate, staleness, filter independence) changes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: No hard dependency on Phase 1, but naturally follows it. **Blocks US1** (and everything layered on US1) — the Stocks page's tab bar needs `TabBar` to exist first.
- **US1 (Phase 3)**: Depends on Foundational (T005/T006). Delivers the tab skeleton and moves news behind it.
- **US2 (Phase 4)**: Depends on US1 (T010/T011) — bounds and de-auto-fetches the `grid` tab content US1 created.
- **US3 (Phase 5)**: Backend (T016, T017, T024, T025) and agent-runner (T018–T021, T026–T029) work is independent of US1/US2, and Phase 1 (T001/T002) is its only real prerequisite — it can proceed in parallel with Phases 3–4. Only the final frontend placement task (T034) needs US1/US2's tab + bounded-layout skeleton to exist.
- **Polish (Phase 6)**: Depends on all desired stories.
- **FR-007b Follow-up (Phase 7)**: Depends on Phase 5 (T033/T034 — `PortfolioDigestPanel` and its original placement must exist before being rearranged). Independent of Phase 6's lint/suite/quickstart runs; can precede or follow it.

### Story Independence

| Story | Hard dependency | Independently testable? |
|-------|-----------------|--------------------------|
| US1 | Foundational (`TabBar`) | Yes — default tab has no news, News tab has the relocated list |
| US2 | US1's tab skeleton (same file, layered) | Yes — no auto-fetch on scroll, page shell stays in view |
| US3 | Setup only (T001–T003); T034 alone needs US1/US2's skeleton | Backend/agent-runner: yes, fully. Frontend panel: yes, once placed |

US1 → US2 are **layers on the same file** (`Stocks.tsx`), not parallel slices — the same shape spec 022 used for its own three stories. US3 is a genuinely separate vertical (new router, new agent-runner module, new components) that only meets US1/US2 at one placement line.

### Parallel Opportunities

- T001, T002, T003 (Setup) all run in parallel — three different files.
- T004 (Foundational test) has no same-phase file conflicts — `[P]`.
- Within US1's tests, only T007 is `[P]`; T008 and T009 share `Stocks.test.tsx` and must follow sequentially.
- Within US2's tests, T012/T013 both extend `Stocks.test.tsx` from US1 — sequential, not `[P]`.
- **US3's backend chain** (T016→T017→T024→T025) and **agent-runner chain** (T018→T019→T026→T027→T028→T029, with T020/T021 feeding in) and **frontend chain** (T022, T030, T031 in parallel → T032 → T033 → T034) can all proceed in parallel with **Phases 3–4** (US1/US2), since they touch entirely different files until T034.
- Within US3's test tasks: T016, T018, T020, T021 are `[P]` (four different files); T017/T019 are sequential additions to files T016/T018 just created. T030 and T031 are `[P]` (different hook files).
- T035 (Polish) is `[P]`; T036/T037 are sequential validation gates run last.

---

## Parallel Example: User Story 3 (fully parallel with US1/US2)

```bash
# Backend, agent-runner, and frontend chains for US3 can all start immediately
# after Phase 1 (Setup), running alongside Phases 3-4 (US1/US2) on Stocks.tsx:

# Backend:
Task: "T016 pytest GET /portfolio/digest states in backend/tests/test_portfolio.py"
# then T017 (same file) -> T024 -> T025

# Agent-runner (three files in parallel):
Task: "T018 pytest condense/rank/cap in agent-runner/tests/test_portfolio_digest.py"
Task: "T020 pytest run_portfolio_digest handler in agent-runner/tests/test_admin_jobs.py"
Task: "T021 pytest job_type dispatch in agent-runner/tests/test_queue_worker.py"
# then T019 (same file as T018) -> T026 -> T027 -> T028 -> T029

# Frontend (two hooks in parallel):
Task: "T030 usePortfolioDigest hook in frontend/src/hooks/usePortfolioDigest.ts"
Task: "T031 usePortfolioDigestRegenerate hook in frontend/src/hooks/usePortfolioDigestRegenerate.ts"
# then T032 -> T033; T034 waits for US1/US2's T011/T015 to land in Stocks.tsx
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (Setup) + Phase 2 (Foundational `TabBar`).
2. Phase 3 (US1): tabs added, News relocated.
3. **STOP and VALIDATE**: quickstart Scenario 1 (News tab shows relocated content, default tab does not).
4. Demo — the reorganization is visible even before the grid is bounded or the digest exists.

### Incremental Delivery

1. Setup + Foundational → shared types/constants exist, `TabBar` proven against `StockDetail`.
2. US1 → News on its own tab → validate Scenario 1 → demo.
3. US2 → bounded grid, no auto-fetch → validate Scenario 2 → demo.
4. US3 → cross-stock summary, regenerate, stale-on-failure → validate Scenarios 3–7 → demo.
5. Polish → lint, full suites, full quickstart (Scenario 8 confirms no regression in spec 022's untouched behavior).

### Parallel Team Strategy

With two developers, after Setup + Foundational:

- Developer A: `Stocks.tsx` chain — US1 (T007–T011) → US2 (T012–T015) → US3's placement task (T023, T034)
- Developer B: US3's backend + agent-runner chain (T016–T021, T024–T029), then the frontend hooks/panel (T022, T030–T033), independently of Developer A until the final placement task
- They synchronize only at T034, once both the tab/layout skeleton (Developer A) and the digest panel (Developer B) exist.

---

## Notes

- `[P]` tasks touch different files with no unmet dependencies.
- Constitution Principle I: every implementation task has a preceding test task in the same phase — write it, watch it fail, then implement.
- Constitution Principle III: `tools/portfolio.py`'s gather/condense/rank function is pure and deterministic; only `agents/portfolio_digest.py`'s `run()` calls the LLM, and only for narrative synthesis — no stock's stored `signal`/`conviction` is overridden.
- Constitution Principle IV: the digest makes zero new external provider calls — only reads from `analyses` and calls local Ollama, so no FMP budget guard is needed here.
- Constitution Principle V: no new queue, service, or scheduler — T029 (registering the handler) is the entire integration point with existing infrastructure.
- Constitution Principle VI: `PORTFOLIO_DIGEST_CACHE` (T001/T002) must stay identical between `backend/db.py` and `agent-runner/tools/db.py`; the digest document shape must stay identical between `contracts/portfolio-digest-api.md` and what T028 actually writes.
- FR-002 (market news content/behavior unchanged by the move) is a no-regression requirement — T037's quickstart Scenario 8 verifies it explicitly.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
