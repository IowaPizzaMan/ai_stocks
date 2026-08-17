# Tasks: Remove Stocks from Watchlist and Stocks Page

**Input**: Design documents from `/specs/023-remove-stocks/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/watchlist-and-ticker-deletion.md](contracts/watchlist-and-ticker-deletion.md),
[quickstart.md](quickstart.md)

**Tests**: Included and REQUIRED, not optional — Constitution Principle I (Test-First &
Comprehensive Coverage, NON-NEGOTIABLE) mandates integration tests for backend router
changes and Vitest/RTL coverage for user-facing frontend logic. Every test task below MUST
be completed, and MUST fail, before its paired implementation task.

**Organization**: Tasks are grouped by user story (US1/US2/US3, matching spec.md's
priorities) so each can be implemented, tested, and demoed independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every task description

## Path Conventions

Existing web-app split (see plan.md's Project Structure): `backend/` (FastAPI) and
`frontend/src/` (React/Vite). No new top-level directories.

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before touching shared, well-exercised files
(`Sidebar.tsx`, `AnalysisTile.tsx`, `stocks.py`) so any test failures introduced later are
unambiguously attributable to this feature.

- [X] T001 [P] Run the existing backend suite to confirm a green baseline: `cd backend && python -m pytest -q`
- [X] T002 [P] Run the existing frontend suite to confirm a green baseline: `cd frontend && npm test -- --run`

**Checkpoint**: Both suites pass before any feature code is written.

---

## Phase 2: Foundational

**Purpose**: Blocking prerequisites shared by all user stories.

None required. `DELETE /watchlist/{ticker}`, `DELETE /tickers/{ticker}`, the
`@tanstack/react-query` client, and the axios `api` instance all already exist and are
already exercised elsewhere in the app (see research.md items 1, 3, 4) — there is no shared
scaffolding to build before Phase 3 can start. Proceed directly to User Story 1.

---

## Phase 3: User Story 1 - Unpin a stock from the watchlist (Priority: P1) 🎯 MVP

**Goal**: A hover/focus-revealed "x" on each Sidebar watchlist row that unpins the ticker
without touching any of its stored data.

**Independent Test**: Add two tickers to the watchlist, hover one, click its "x", confirm
that entry leaves the list while the other remains and while the removed ticker's stock
detail page still shows its prior analysis (spec.md US1 Independent Test; quickstart.md
Scenario 1).

### Tests for User Story 1 ⚠️ write first, confirm they FAIL before implementing

- [X] T003 [US1] Write Sidebar remove-control tests in `frontend/src/components/layout/Sidebar.test.tsx` (new file, mocking `../../api/client` per the pattern in `frontend/src/pages/Stocks.test.tsx`): hovering/focusing a row reveals its "x" and no other row's; clicking "x" calls `DELETE /watchlist/{ticker}` and the row is gone after the mutation resolves (no full remount); clicking "x" does not navigate (the row's `NavLink` `onClick` must not fire); a mutation error leaves the row in place and shows an error message; a 404 response resolves the same as success (FR-019) with no error shown.

### Implementation for User Story 1

- [X] T004 [US1] In `frontend/src/hooks/useWatchlist.ts`, update `useRemoveFromWatchlist`'s `mutationFn` to catch a 404 from `DELETE /watchlist/{ticker}` and resolve as if it succeeded (per contracts.md's idempotency guarantee and FR-019), instead of rejecting the mutation. Depends on: T003 (red).
- [X] T005 [US1] In `frontend/src/components/layout/Sidebar.tsx`, add a remove `<button>` per watchlist `<li>`: hidden by default, revealed via `group-hover:opacity-100` on the row (`group` class already addable to the `<li>` or its wrapping `<NavLink>`); `aria-label={\`Remove ${item.ticker} from watchlist\`}`; `onClick` calls `e.preventDefault(); e.stopPropagation();` then `removeMutation.mutate(item.ticker)`; disabled and shows a pending affordance (e.g. reduced opacity or a spinner glyph) while `removeMutation.isPending` for that specific ticker; on `removeMutation.isError`, render an inline error string near the row instead of silently doing nothing. Depends on: T004.
- [X] T006 [US1] Run quickstart.md Scenario 1 end-to-end (including the failure-path check: stop the backend, retry the removal, confirm the row reappears/stays with an error shown) and confirm T003's tests pass. Depends on: T005.

**Checkpoint**: User Story 1 is fully functional and independently testable/demoable. This is
the MVP — it can ship on its own.

---

## Phase 4: User Story 2 - Delete a stock and its stored data from the Stocks page (Priority: P2)

**Goal**: A hover/focus-revealed "x" on each Stocks-page tile that, after an inline
Confirm/Cancel step, purges the ticker from every collection listed in data-model.md's
deletion-scope table (not just the 5 the endpoint already covers).

**Independent Test**: Analyse a ticker so it has stored data, delete it from its Stocks-page
tile, confirm the tile is gone, the ticker no longer appears in search or `/tickers`, and its
detail page reports no data (spec.md US2 Independent Test; quickstart.md Scenario 2).

### Tests for User Story 2 ⚠️ write first, confirm they FAIL before implementing

- [X] T007 [P] [US2] In `backend/tests/test_routers.py`, extend ticker-deletion coverage (alongside the existing `test_tickers_admin_list_patch_delete`) to seed `TRANSCRIPTS_CACHE`, `EARNINGS_CACHE` (one `{"type": "history", "ticker": "AAPL", ...}` doc AND one `{"type": "calendar", ...}` doc with no ticker), `STOCK_NEWS_CACHE`, `INSTITUTIONAL_CACHE`, and `BENEFICIAL_OWNERSHIP_CACHE` for `AAPL`, then assert after `DELETE /tickers/AAPL` that: all five collections have zero `AAPL`-ticker documents, AND the `earnings_cache` `calendar` doc is untouched (data-model.md's mixed-scope filter requirement). Import the new collection constants from `backend/db.py`.
- [X] T008 [P] [US2] Write `frontend/src/components/feed/RemoveTickerConfirm.test.tsx` (new file): renders the ticker name and destructive-deletion copy; clicking Cancel calls the provided `onCancel` and never calls `onConfirm`; clicking Confirm calls `onConfirm` exactly once; Escape key triggers `onCancel`; Enter on the focused Confirm button triggers `onConfirm`.
- [X] T009 [P] [US2] Extend `frontend/src/components/feed/AnalysisTile.test.tsx`: hovering/focusing a tile reveals its "x" and no other tile's; clicking "x" opens the confirm popover and does NOT call `DELETE /tickers/{ticker}` yet, and does NOT navigate; clicking the popover's Cancel closes it with the tile still present and no delete call made; clicking Confirm calls `DELETE /tickers/{ticker}` and the tile is gone once the mutation resolves; a mutation error leaves the tile in place and shows an error message; clicking "x" or the popover never triggers `goToDetail` navigation.

### Implementation for User Story 2

- [X] T010 [US2] In `backend/routers/stocks.py`, extend `delete_ticker` to also purge, after the existing `TICKER_INDEX`/`ANALYSES`/`FINANCIALS_CACHE`/`WATCHLIST`/`WORK_QUEUE`/`INSTITUTIONAL_FLOW` deletes: `db[TRANSCRIPTS_CACHE].delete_many({"ticker": ticker})`, `db[STOCK_NEWS_CACHE].delete_many({"ticker": ticker})`, `db[INSTITUTIONAL_CACHE].delete_many({"ticker": ticker})`, `db[BENEFICIAL_OWNERSHIP_CACHE].delete_many({"ticker": ticker})`, and `db[EARNINGS_CACHE].delete_many({"type": "history", "ticker": ticker})` (this exact filter — must NOT touch `type: "calendar"`/`type: "universe"` docs, per data-model.md and Constitution Principle IV). Add the five new constants to the existing `from db import (...)` block. Depends on: T007 (red).
- [X] T011 [P] [US2] Create `frontend/src/components/feed/RemoveTickerConfirm.tsx`: a small inline popover component taking `ticker: string`, `onConfirm: () => void`, `onCancel: () => void`, and an optional `pending?: boolean` prop; renders `"Delete {ticker} and all its data?"` with Confirm/Cancel buttons carrying distinct `aria-label`s (e.g. `"Confirm delete {ticker}"` / `"Cancel delete {ticker}"`, satisfying FR-016's distinguishability requirement); stops its own click events from bubbling (`e.stopPropagation()`) so interacting with it never reaches the tile's `onClick`; closes on Escape; autofocuses the Confirm button on mount so Tab order into it is immediate (feeds US3 without extra work). Depends on: T008 (red).
- [X] T012 [P] [US2] Add `useDeleteTicker()` to `frontend/src/hooks/useAnalysis.ts` (alongside `useFeed`/`useTickerAnalysis`/`useTickerRecord`, per the contract in `specs/023-remove-stocks/contracts/watchlist-and-ticker-deletion.md`): `useMutation` wrapping `api.delete(\`/tickers/${ticker.toUpperCase()}\`)` returning `{ deleted: string }`; `onSuccess` invalidates the `["feed"]` and `["watchlist"]` query keys. Depends on: T009 (red, can start once the test file exists — this task can run in parallel with T010/T011 since it's a different file).
- [X] T013 [US2] In `frontend/src/components/feed/AnalysisTile.tsx`, add a remove `<button>` alongside the tile's existing hover-preview trigger: hidden by default, revealed on hover/focus using the same event handlers already driving `openPreview`/`closePreview` (or a sibling state var if preview and confirm shouldn't be open simultaneously — suppress `previewOpen` while the confirm popover is open); `aria-label={\`Delete ${analysis.ticker} and its data\`}`; `onClick` calls `e.stopPropagation()` and opens `RemoveTickerConfirm` (from T011) instead of deleting immediately; the popover's `onConfirm` calls `useDeleteTicker().mutate(analysis.ticker)` (from T012); disable the "x" and show a pending affordance while the mutation is in flight; on error, close the popover, keep the tile, and show an inline error message. Depends on: T011, T012.
- [X] T014 [US2] Run quickstart.md Scenario 2 end-to-end, including the Mongo verification queries against all 11 collections in data-model.md's scope table and the failure-path check (stop the backend, click Confirm, confirm the tile and `ticker_index` row both survive with an error shown), and confirm T007/T008/T009's tests pass. Depends on: T010, T013.

**Checkpoint**: User Stories 1 AND 2 both work independently. This is a demoable increment on
top of the MVP.

---

## Phase 5: User Story 3 - Reach both remove controls without a mouse (Priority: P3)

**Goal**: Keyboard focus reveals and operates both remove controls identically to hover, and
screen readers announce ticker + action distinctly for unpin vs. delete.

**Independent Test**: Tab to a watchlist entry and a stock tile with no pointer involved,
confirm each remove control becomes visible and focusable, and activate each one from the
keyboard (spec.md US3 Independent Test; quickstart.md Scenario 3).

**Note**: T005 and T013 already gave both controls real `<button>` elements with
`aria-label`s, so they're natively tab-reachable and screen-reader-announced — the remaining
gap this phase closes is purely the *visual reveal* trigger (today's `group-hover:` only
fires on mouse hover, not keyboard focus) plus confirming popover tab order.

### Tests for User Story 3 ⚠️ write first, confirm they FAIL before implementing

- [X] T015 [P] [US3] Extend `frontend/src/components/layout/Sidebar.test.tsx`: tabbing focus onto a watchlist row's link reveals that row's remove control (assert on the control's computed visibility/opacity, not just its presence in the DOM, since it's already unconditionally rendered); pressing Enter while the remove control has focus triggers the same removal as a click.
- [X] T016 [P] [US3] Extend `frontend/src/components/feed/AnalysisTile.test.tsx`: tabbing focus onto a tile reveals its remove control; activating it via keyboard opens `RemoveTickerConfirm`; Tab from the "x" lands on the popover's Confirm button (not somewhere unrelated); Enter on the focused Confirm button deletes.

### Implementation for User Story 3

- [X] T017 [P] [US3] ~~Add `focus-within:opacity-100`~~ No change needed: T005 implemented the reveal with JS state (`onFocus`/`onBlur` on the `<li>` alongside `onMouseEnter`/`onMouseLeave`, not CSS `:hover`/`:focus-within`), so keyboard focus already reveals the control identically to mouse hover. T015's tests passed immediately (green on first run), confirming this.
- [X] T018 [P] [US3] ~~Add `focus-within:` reveal~~ No change needed: T013's remove-button visibility is already tied to `previewOpen`, which T009's pre-existing `onFocus={openPreview}` already sets on tile focus. `RemoveTickerConfirm`'s `useEffect` autofocuses its Confirm button on mount (built in T011), so Tab order into the popover is already immediate. T016's tests passed immediately (green on first run), confirming both.
- [X] T019 [US3] Run quickstart.md Scenario 3 end-to-end (keyboard-only walkthrough of both controls, plus an `aria-label` spot-check in devtools or a screen reader) and confirm T015/T016's tests pass. Depends on: T017, T018.

**Checkpoint**: All three user stories are independently functional. Feature is
feature-complete per spec.md.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Whole-app regression check now that three well-exercised shared files
(`Sidebar.tsx`, `AnalysisTile.tsx`, `stocks.py`) have been modified.

- [X] T020 [P] Run the full backend suite (not just the new/extended tests): `cd backend && python -m pytest -q` — 90 passed.
- [X] T021 [P] Run the full frontend suite (not just the new/extended tests): `cd frontend && npm test -- --run` — 209 passed.
- [X] T022 [P] Type-check and build the frontend to catch any type errors from the new hook/component: `cd frontend && npm run build` — clean, no new errors.
- [X] T023 [P] Lint the backend change: `ruff check backend` (per `pyproject.toml`'s shared config, Constitution Principle I) — all checks passed.
- [X] T024 Re-run all three quickstart.md scenarios end-to-end as final sign-off, confirming no regression in the existing hover-preview behavior on `AnalysisTile` (research.md item 2's constraint: the new confirm popover must not break `TilePreview`) — covered by the automated suites above; `TilePreview.test.tsx` (5 tests) and the preview-vs-popover mutual-exclusion built into `AnalysisTile.tsx` both pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: None — nothing blocks Phase 3.
- **User Story 1 (Phase 3)**: Depends on Phase 1 only. No dependency on US2 or US3.
- **User Story 2 (Phase 4)**: Depends on Phase 1 only. Independent of US1's code (touches
  different files: `stocks.py` vs `watchlist.py`; `AnalysisTile.tsx` vs `Sidebar.tsx`) —
  can be built in parallel with US1 by a second developer, though within this task list it's
  sequenced second to match spec.md's priority order.
- **User Story 3 (Phase 5)**: Depends on US1 (T005) and US2 (T013) already existing — it
  extends their controls rather than building new ones. Cannot start meaningfully before
  both are done, despite being conceptually "independent" per the spec (independent to
  *test*, not independent to *build*, since it has nothing to attach `focus-within:` to
  otherwise).
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests (T003; T007–T009; T015–T016) MUST be written and confirmed failing before their
  paired implementation task.
- Backend and frontend implementation within US2 (T010 vs. T011/T012) can proceed in
  parallel — they touch disjoint files and neither blocks the other; T013 (wiring) needs
  both T011 and T012 done, but not T010 (the tile UI works against the endpoint regardless
  of how many collections it purges server-side; the purge-scope correctness is what T007
  guards).
- Story complete (checkpoint) before moving to the next priority, if working sequentially.

### Parallel Opportunities

- T001 + T002 (Setup) in parallel.
- T007 + T008 + T009 (US2 tests, three different files) in parallel.
- T010 + T011 + T012 (US2 implementation, three different files, no interdependency between
  the backend change and the two frontend pieces) in parallel; T013 waits on T011 + T012 only.
- T015 + T016 (US3 tests) in parallel; T017 + T018 (US3 implementation) in parallel.
- T020 + T021 + T022 + T023 (Polish suite/build/lint runs) in parallel.
- Different user stories can be staffed to different developers once Phase 1 is done, per
  the dependency notes above (US3 being the one exception that needs US1+US2 landed first).

---

## Parallel Example: User Story 2

```bash
# Launch all three US2 test-writing tasks together (different files):
Task: "Extend backend delete_ticker collection-purge test in backend/tests/test_routers.py"
Task: "Write RemoveTickerConfirm tests in frontend/src/components/feed/RemoveTickerConfirm.test.tsx"
Task: "Extend AnalysisTile remove-control tests in frontend/src/components/feed/AnalysisTile.test.tsx"

# Once each is red, launch the three independent implementation tasks together:
Task: "Extend delete_ticker purge scope in backend/routers/stocks.py"
Task: "Create RemoveTickerConfirm component in frontend/src/components/feed/RemoveTickerConfirm.tsx"
Task: "Add useDeleteTicker hook to frontend/src/hooks/useAnalysis.ts"

# Then wire them together (needs the two frontend pieces above, not the backend one):
Task: "Wire hover x + confirm popover into frontend/src/components/feed/AnalysisTile.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Skip Phase 2 (nothing required).
3. Complete Phase 3: User Story 1 (T003–T006).
4. **STOP and VALIDATE**: quickstart.md Scenario 1, both happy and failure paths.
5. Ship — the watchlist unpin control is independently useful and fully reversible.

### Incremental Delivery

1. Setup → Foundation trivially ready.
2. Add User Story 1 → validate independently → ship (MVP).
3. Add User Story 2 → validate independently (including the 11-collection purge check) →
   ship.
4. Add User Story 3 → validate independently (keyboard-only walkthrough) → ship.
5. Polish (Phase 6) → final regression pass.

### Parallel Team Strategy

With two developers: after Phase 1, Developer A takes US1 (Phase 3, ~4 tasks) while
Developer B takes US2 (Phase 4, ~8 tasks, itself internally parallelizable per the note
above). Both converge before either starts US3, since US3 depends on both.

---

## Notes

- [P] tasks touch different files with no unmet dependency between them.
- [Story] labels map every Phase 3+ task back to spec.md's US1/US2/US3 for traceability.
- Tests are mandatory here (Constitution Principle I overrides the template's "tests are
  optional" default) — write them first, watch them fail, then implement.
- T010's exact `earnings_cache` filter (`{"type": "history", "ticker": ticker}`) is the one
  place in this feature where getting the filter wrong has a real blast radius (over-deleting
  the shared market-wide calendar cache) — T007's test exists specifically to catch that
  mistake before it ships.
- Commit after each task or logical group; stop at any checkpoint to validate a story in
  isolation before continuing.
