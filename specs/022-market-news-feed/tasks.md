# Tasks: Market News Feed on the Stocks Page

**Input**: Design documents from `specs/022-market-news-feed/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included — constitution Principle I (Test-First & Comprehensive Coverage) is NON-NEGOTIABLE: pytest for the backend router and budget guard, Vitest + React Testing Library for the panel and page.

**Organization**: Tasks are grouped by user story (spec.md priorities) so each story can be implemented and verified independently.

> **Revised 2026-08-16 after `/speckit-analyze`**: the endpoint is now cache-first in its first implementation task (finding D1 — the previous split briefly shipped an uncached FMP path, conflicting with constitution Principle IV), and a filter-independence test was added (finding E1 — FR-001b had implementation but no automated coverage, and Principle I names filtering explicitly).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to spec.md user stories (US1–US3)
- Every task names an exact file path

## Path Conventions (from plan.md)

- Backend: `backend/`, `backend/routers/`, `backend/tests/`
- Frontend: `frontend/src/hooks/`, `frontend/src/components/feed/`, `frontend/src/pages/`
- No agent-runner changes — this feature deliberately sits outside the analysis pipeline (FR-007/FR-008)

---

## Phase 1: Setup

**Purpose**: Collection names, settings, and the shared type — small, independent edits every later phase builds on.

- [X] T001 Add `MARKET_NEWS_CACHE = "market_news_cache"` and `FMP_USAGE = "fmp_usage"` to the collection-name block in `backend/db.py` (keeping the existing "keep in sync with agent-runner/tools/db.py" convention), and add a unique index on `key` for the new collection in `ensure_indexes` — **no TTL index**, per [research.md](./research.md) D4
- [X] T002 [P] Add `fmp_daily_soft_cap: int = 0` to `backend/settings.py`, mirroring the name and `0 = disabled` default already used in `agent-runner/settings.py`
- [X] T003 [P] Add `MarketNewsArticle` and the `/market/news` response type to `frontend/src/api/types.ts` per [contracts/market-news-endpoint.md](./contracts/market-news-endpoint.md) — kept separate from spec 021's `NewsArticle`, which carries sentiment fields this feature has no equivalent of ([data-model.md](./data-model.md) §4)

**Checkpoint**: Names, settings, and types exist; nothing behavioral yet.

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: The backend's first FMP budget guard. This blocks every story because the feature's very first external call must be guarded — adding the call now and the guard later would knowingly violate constitution Principle IV in between.

**⚠️ CRITICAL**: No user story work may call FMP until this phase is complete.

- [X] T004 pytest for the budget guard in `backend/tests/test_fmp_guard.py`: the day counter increments on the UTC `%Y-%m-%d` bucket in `fmp_usage`, a soft cap of `0` never raises, exceeding a non-zero cap raises `FmpBudgetExceededError`, and the returned count reflects the post-increment value
- [X] T005 Implement `backend/fmp.py`: `fmp_get(path, db)` that increments the shared `fmp_usage` counter via an upserting `find_one_and_update` (same contract as `agent-runner/tools/fmp_client.py`), raises `FmpBudgetExceededError` past `settings.fmp_daily_soft_cap`, appends the API key, and returns parsed JSON (depends on T001, T002, T004)

**Checkpoint**: The backend can make budget-accounted FMP calls; both services now increment one shared daily counter (Principle VI).

---

## Phase 3: User Story 1 - Market News Below the Stock Grid (Priority: P1) 🎯 MVP

**Goal**: The Stocks page shows the 20 most recent market-wide articles below the grid, each with time, source, ticker, and an outbound headline link; the list ends at 20; and the panel ignores the page's filter bar.

**Independent Test**: Open the Stocks page, scroll past the grid, count exactly 20 dated articles with headline/source/ticker, confirm scrolling further loads nothing more, and confirm applying a grid filter leaves the articles unchanged.

### Tests for User Story 1

- [X] T006 [P] [US1] pytest in `backend/tests/test_market_news.py`: `GET /market/news` returns normalized articles (camelCase → snake_case per [data-model.md](./data-model.md) §1), sorted newest first, capped at 20 even when the provider returns more, keeping the newest; rows missing `title` or `url` are dropped; `ticker` is `null` for untagged stories
- [X] T007 [P] [US1] Vitest in `frontend/src/components/feed/MarketNewsPanel.test.tsx`: renders one row per article with time, source, ticker badge, and headline; renders at most 20 rows; a `null` ticker renders without a badge; headlines carry `target="_blank"` and `rel="noreferrer"`; there is no "load more" control
- [X] T008 [P] [US1] Vitest in `frontend/src/pages/Stocks.test.tsx`: the market news panel renders after the analysis grid sections in DOM order
- [X] T009 [US1] Vitest in `frontend/src/pages/Stocks.test.tsx`: **filter independence (FR-001b)** — render `Stocks` with `?sector=Technology&signal=bullish&ticker=AAPL` in the router's search params and assert the news panel shows the same articles as with no filters, and that the news request carries no filter parameters. Constitution Principle I names filtering as frontend logic requiring RTL coverage, so this cannot be left to manual checking. **Not [P]** — same file as T008; add this case after T008 lands

### Implementation for User Story 1

- [X] T010 [US1] Add `GET /market/news` to `backend/routers/market.py`, **cache-first from the start**: read the `market_news_cache` document and serve it when `fetched_at` is within 60 minutes; otherwise fetch `news/stock-latest` through `backend/fmp.py`, normalize, sort newest-first, cap at 20, upsert, and return `{articles, as_of, stale}` per [contracts/market-news-endpoint.md](./contracts/market-news-endpoint.md). Freshness is compared in code — deliberately **not** a TTL index, so the stale-fallback copy survives for US3 ([data-model.md](./data-model.md) §2). *(Caching is included here rather than deferred so no intermediate state ships an uncached user-triggered FMP path — Principle IV.)* (depends on T005, T006)
- [X] T011 [P] [US1] Create `frontend/src/hooks/useMarketNews.ts`: TanStack Query hook calling `/market/news` with **no filter arguments and no filter state in the query key**, so grid filters cannot affect it (FR-001b, research D6)
- [X] T012 [US1] Create `frontend/src/components/feed/MarketNewsPanel.tsx`: section heading plus up to 20 rows (publish time, source, ticker badge linking to `/stocks/{ticker}`, headline linking out in a new tab), following the row treatment of spec 021's `NewsTab` so the two news surfaces read as one system; no images in v1 (research D7) (depends on T011)
- [X] T013 [US1] Render `MarketNewsPanel` in `frontend/src/pages/Stocks.tsx` below the grouped signal sections and after the existing infinite-scroll sentinel, leaving the grid's own infinite scroll untouched (depends on T012)

**Checkpoint**: US1 independently functional and **safe to leave running** — 20 market articles render below the grid, capped, filter-independent, and costing at most one provider call per hour.

---

## Phase 4: User Story 2 - Fresh on Visit, Not Kept as History (Priority: P1)

**Goal**: Verify and complete the freshness contract — news refreshes at most hourly, never polls, and never enters any ticker's analysis.

**Independent Test**: Hit the endpoint twice and confirm the second is served from cache with an unchanged `as_of`; confirm no market articles appear in any stored analysis; leave the page open and confirm no background refetching.

> The backend cache itself lands in T010 (US1) so no uncached state ever ships. This phase proves that behavior holds and adds the client-side half.

### Tests for User Story 2

- [X] T014 [P] [US2] pytest in `backend/tests/test_market_news.py`: a cached document younger than 60 minutes is served **without** calling the provider; a document older than 60 minutes triggers exactly one provider call and updates `fetched_at`; a cold cache fetches once and upserts; `as_of` reflects `fetched_at` (FR-011)
- [X] T015 [US2] pytest in `backend/tests/test_market_news.py`: the endpoint writes only to `market_news_cache` — no document is created or modified in `analyses` (FR-008). **Not [P]** — same file as T014; add this case after T014 lands
- [X] T016 [P] [US2] Vitest in `frontend/src/components/feed/MarketNewsPanel.test.tsx`: the query is configured with a 60-minute `staleTime` and no `refetchInterval`, so the panel never polls while the page sits open (FR-010)

### Implementation for User Story 2

- [X] T017 [US2] Set `staleTime` to 60 minutes and leave `refetchInterval` unset in `frontend/src/hooks/useMarketNews.ts`, matching the server-side window so in-session navigation does not even reach the backend (depends on T011, T016)

**Checkpoint**: The freshness contract is proven end to end — capped, current-on-visit news that costs at most one provider call per hour and leaves no history.

---

## Phase 5: User Story 3 - Graceful Degradation (Priority: P2)

**Goal**: A news failure never degrades the Stocks page, and an exhausted budget shows the last known articles rather than an error.

**Independent Test**: Break the provider and confirm the grid still renders with a news-specific message; exhaust the soft cap and confirm the endpoint still returns `200` with prior articles marked stale.

### Tests for User Story 3

- [X] T018 [P] [US3] pytest in `backend/tests/test_market_news.py`: a provider HTTP error on a cold cache returns `200` with the previously cached articles and `stale: true`; with no cache ever written it returns `200`, an empty list, and `stale: true` — never a 5xx (FR-012, FR-013)
- [X] T019 [US3] pytest in `backend/tests/test_market_news.py`: `FmpBudgetExceededError` is caught and degrades identically to a provider error, and no further provider call is attempted. **Not [P]** — same file as T018; add this case after T018 lands
- [X] T020 [P] [US3] Vitest in `frontend/src/components/feed/MarketNewsPanel.test.tsx`: renders a loading state while pending, a brief unavailable message on query error, an empty-state message for zero articles, and a "not current" indicator when the response carries `stale: true`
- [X] T021 [P] [US3] Vitest in `frontend/src/pages/Stocks.test.tsx`: when the news query fails, the analysis grid still renders fully — the failure is confined to the panel (FR-012)

### Implementation for User Story 3

- [X] T022 [US3] Wrap the fetch path in the `/market/news` handler in `backend/routers/market.py` so `FmpBudgetExceededError` and `requests` exceptions are caught, the last cached articles are returned with `stale: true`, and a warning is logged (depends on T010, T018, T019)
- [X] T023 [US3] Add loading, error, empty, and stale states to `frontend/src/components/feed/MarketNewsPanel.tsx`, rendered locally so the panel is never gated on the feed query's status (depends on T012, T020)

**Checkpoint**: All three stories functional; the Stocks page is resilient to a news outage and safe for the daily budget.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T024 [P] Log the pre-existing unguarded FMP call sites in `KNOWN_ISSUES.md`: `backend/routers/price.py` and `backend/earnings_data.py` call FMP with bare `requests.get` and never increment `fmp_usage`, so the shared daily counter under-reports true spend until they are routed through `backend/fmp.py` (research D3; deliberately out of scope for this feature)
- [X] T025 [P] Run `ruff check backend/` and fix any findings (constitution quality gate)
- [X] T026 Run the full suites — `backend`: `.\.venv\Scripts\python.exe -m pytest tests -q`; `frontend`: `npx vitest run` and `npx tsc --noEmit` — and confirm no regressions in the existing 69 backend / 171 frontend tests
- [ ] T027 Execute [quickstart.md](./quickstart.md) scenarios 1–5 against the running Docker Compose stack — **NOT RUN**: no containers were up. Partial live verification was done without Docker instead (below); the remaining gap is the rendered UI and the FR-014 per-ticker no-regression check in the browser.

### Live verification performed during implementation (no Docker required)

Called the real handler against the live FMP API with a mongomock database:

- **Cold cache** → 20 real articles from `news/stock-latest`, newest first, 18 of 20 ticker-tagged (2 legitimately untagged, exercising the `ticker: null` path).
- **Warm cache** → served with `fmp_get` replaced by a stub that raises if called; it never fired, so the second request made **zero** provider calls and returned an unchanged `as_of`.
- `market_news_cache` held exactly **1 document**; `fmp_usage` counted exactly **1 call** for the two requests — FR-011 and SC-004 behaving as specified end to end.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on T001/T002 — **blocks all stories**, because the feature's first FMP call must already be guarded.
- **US1 (Phase 3)**: Depends on Foundational. Delivers the endpoint (cache-first), hook, panel, and placement.
- **US2 (Phase 4)**: Depends on US1's endpoint (T010) and hook (T011). Verifies the caching contract and adds the client-side `staleTime`.
- **US3 (Phase 5)**: Depends on US1's cache (T010), since "serve the last cached articles" needs a cache to fall back to.
- **Polish (Phase 6)**: Depends on all desired stories.

### Story Independence

These stories are **layers on one endpoint**, not parallel slices — a deliberate difference from spec 021, where stories touched separate tabs. US1 delivers working, budget-safe news; US2 proves the freshness contract and stops the client polling; US3 covers what happens when a refresh fails. Each is independently testable and demoable, but they build on the same two files rather than shipping in any order.

| Story | Hard dependency | Independently testable? |
|-------|-----------------|--------------------------|
| US1 | Foundational | Yes — 20 capped, filter-independent articles below the grid |
| US2 | US1's endpoint + hook | Yes — cache hit/miss, no-analyses-writes, and no-polling verified on their own |
| US3 | US1's cache | Yes — failure and budget paths verified on their own |

### Parallel Opportunities

- T002 and T003 (Setup) run in parallel with each other and with T001.
- Test tasks are `[P]` only when they are the sole task targeting their file in that phase. This feature has just three test files, so several test tasks deliberately **lack** `[P]`: T009 follows T008 (`Stocks.test.tsx`), T015 follows T014 and T019 follows T018 (`test_market_news.py`). They are still quick sequential additions to a file that already exists — just never concurrent writes.
- T011 (frontend hook) can proceed in parallel with T010 (backend endpoint) once the contract is fixed, since they only meet at the HTTP boundary.
- T024 and T025 (Polish) run in parallel.
- Backend and frontend work proceed in parallel within each story once that story's contract behavior is agreed.

> **`[P]` discipline**: with only three test files in this feature, file collisions are the main parallelism hazard. Every `[P]` marker below has been checked so that no two `[P]` tasks in the same phase write the same path — safe for `/speckit-implement` to dispatch concurrently.

---

## Parallel Example: User Story 1

```bash
# Write these three failing tests together — three different files:
Task: "T006 pytest endpoint shaping/cap in backend/tests/test_market_news.py"
Task: "T007 Vitest panel rows/cap in frontend/src/components/feed/MarketNewsPanel.test.tsx"
Task: "T008 Vitest panel placement in frontend/src/pages/Stocks.test.tsx"

# T009 (filter independence) also lives in Stocks.test.tsx — add it after T008,
# never alongside it, or the two writes collide.

# Then implement across the HTTP boundary in parallel — different files:
Task: "T010 Cache-first GET /market/news in backend/routers/market.py"
Task: "T011 useMarketNews hook in frontend/src/hooks/useMarketNews.ts"
```

---

## Implementation Strategy

### MVP (US1 only)

1. Phase 1 (Setup) + Phase 2 (Foundational budget guard).
2. Phase 3 (US1): cache-first endpoint + hook + panel + placement.
3. **STOP and VALIDATE**: quickstart Scenario 1 (20 articles below the grid, capped, links working) and Scenario 3 (filter independence).
4. Demo. Unlike the pre-analysis plan, this checkpoint is **safe to leave running**: the endpoint caches from its first commit, so it cannot spend more than one provider call per hour.

### Incremental Delivery

1. Setup + Foundational → guarded FMP access exists.
2. US1 → news visible, capped, filter-independent, budget-safe → validate → demo (MVP).
3. US2 → freshness contract proven, client stops polling → validate Scenario 2 → demo.
4. US3 → failure and budget resilience → validate Scenario 4 → demo.
5. Polish → KNOWN_ISSUES entry, lint, full suites, full quickstart.

### Parallel Team Strategy

With two developers, after Setup + Foundational:

- Developer A: backend chain T010 → T022 (both in `routers/market.py`, so sequential)
- Developer B: frontend chain T011/T012/T013 → T017 → T023
- They synchronize on the response contract only, which [contracts/market-news-endpoint.md](./contracts/market-news-endpoint.md) fixes up front.

---

## Notes

- [P] tasks touch different files with no unmet dependencies.
- Constitution Principle I: every implementation task has preceding test tasks in the same phase — write them, watch them fail, then implement.
- Constitution Principle IV: the new endpoint MUST call FMP only through `backend/fmp.py`, and MUST be cache-first from its first commit (T010) — a bare `requests.get`, or a deferred cache, would repeat the very gap this feature is fixing.
- Constitution Principle VI: `MARKET_NEWS_CACHE`/`FMP_USAGE` names and the counter's document shape must match `agent-runner/tools/db.py` exactly.
- FR-014 is a no-regression requirement, not new work — T027 verifies per-ticker news is untouched.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
