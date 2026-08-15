---

description: "Task list for Feed Checkerboard Grid implementation"

---

# Tasks: Feed Checkerboard Grid

**Input**: Design documents from `/specs/019-feed-checkerboard-grid/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/feed-grid-ui.md](./contracts/feed-grid-ui.md), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution Principle I requires Vitest + React Testing Library coverage for frontend user-facing logic (filtering, pagination, mutations); this feature's core logic — signal/conviction rendering and the grouping helper — is exactly that surface.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) so each can be implemented and validated independently. All paths are relative to the repository root; every file under `frontend/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, mapping to spec.md's user stories
- Frontend-only feature — no `backend/` or `agent-runner/` paths appear below

---

## Phase 1: Setup

**Purpose**: No new tooling, dependencies, or scaffolding is required (research R1–R10: zero new packages). This phase confirms the working environment is ready.

- [X] T001 Confirm frontend toolchain is ready: `cd frontend && npm install && npm run typecheck && npm test` all succeed on the unmodified branch (baseline before any edits)

**Checkpoint**: Baseline green. No infrastructure changes needed before Foundational work begins.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure grouping helper, the widened page size, and the skeleton placeholder are consumed by every user story's grid rendering — they must exist first.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Write `groupBySignal` test suite in `frontend/src/lib/groupFeed.test.ts` — fixed group order (bullish → neutral → bearish → unknown), newest-first within group, unknown/missing-signal bucket, empty input, empty groups omitted, and regrouping is stable when re-run on a larger merged array (page-merge behavior per FR-014). Tests MUST fail (module doesn't exist yet).
- [X] T003 Implement `groupBySignal(items: AnalysisFeedItem[])` pure helper and `GroupedFeed` type in `frontend/src/lib/groupFeed.ts` per [data-model.md](./data-model.md), making T002 pass
- [X] T004 [P] Bump feed page size from 20 to 60 in `frontend/src/hooks/useAnalysis.ts` (`useFeed`'s `page_size` param) per research R2
- [X] T005 [P] Create `SkeletonTile` loading placeholder in `frontend/src/components/feed/SkeletonTile.tsx` (tile-shaped shimmer; do not modify the shared `frontend/src/components/shared/SkeletonCard.tsx`, which InstitutionalFlow still uses)

**Checkpoint**: `groupFeed.test.ts` passes; `useFeed` requests 60 items/page; `SkeletonTile` renders. User story implementation can now begin.

---

## Phase 3: User Story 1 - Scan many stocks at a glance (Priority: P1) 🎯 MVP

**Goal**: Feed renders a dense, signal-grouped grid of compact tiles — ticker + signal-colored fill + 1–3 conviction dots, nothing else on the tile face — showing ≥30 tiles on a typical desktop screen without scrolling.

**Independent Test**: Load the Feed with 30+ analyzed stocks; confirm a full desktop screen shows dozens of tiles grouped bullish → neutral → bearish, each showing only a ticker, a signal-colored fill, and the correct dot count.

### Tests for User Story 1

> Write these tests FIRST; confirm they fail before implementing T008–T009.

- [X] T006 [P] [US1] Write `AnalysisTile.test.tsx` in `frontend/src/components/feed/AnalysisTile.test.tsx` — fill/border/text classes per signal (bullish/bearish/neutral), dashed fallback style for an unrecognized/missing signal, dot count 3/2/1 for high/medium/low conviction, zero dots for missing conviction, ticker is the only visible text, `aria-label` contains ticker + signal + conviction + recency (research R8), long tickers (GOOGL, BRK.B) render without ambiguous truncation
- [X] T007 [P] [US1] Write Feed page-composition tests in `frontend/src/pages/Feed.test.tsx` — renders a CSS grid of tiles grouped under labeled dividers (Bullish/Neutral/Bearish) in that order, shows a board of `SkeletonTile` placeholders during initial load only, preserves the existing error message on fetch failure, preserves the existing "No analyses yet" empty state

### Implementation for User Story 1

- [X] T008 [US1] Implement `AnalysisTile` component in `frontend/src/components/feed/AnalysisTile.tsx` — ticker text, signal-mapped fill/border/text classes with dashed fallback for unknown signal, own compact 3-dot row (neutral-colored, `aria-hidden`, 0 filled when conviction missing), computed `aria-label` per [contracts/feed-grid-ui.md](./contracts/feed-grid-ui.md); makes T006 pass
- [X] T009 [US1] Rewrite `frontend/src/pages/Feed.tsx` to render `groupBySignal(allItems)` as a responsive CSS Grid (`grid-cols-[repeat(auto-fill,minmax(...,1fr))]`, per research R7) of `AnalysisTile`s under labeled group-divider rows, replacing the single-column `AnalysisCard` list; widen the page container from `max-w-3xl` to `max-w-7xl`; render a ~30-tile `SkeletonTile` board during initial load instead of 6 `SkeletonCard`s; preserve existing error/empty states; makes T007 pass
- [X] T010 [US1] Delete `frontend/src/components/feed/AnalysisCard.tsx` (Feed is its only consumer, confirmed by grep in research R6 — no other page imports it)
- [X] T011 [P] [US1] Rewrite `specs/component-specs/frontend/pages/Feed.md` to document the grouped tile-grid layout, and add `specs/component-specs/frontend/components/feed/AnalysisTile.md` describing the tile's face contract (ticker + fill + dots only); note in `specs/component-specs/frontend/components/feed/AnalysisCard.md` that it was replaced by `AnalysisTile` in feature 019

**Checkpoint**: Feed page independently shows a dense, signal-grouped, conviction-dotted tile grid. US1 is demoable on its own (tiles are not yet clickable/hoverable beyond default browser behavior — that's US2).

---

## Phase 4: User Story 2 - Drill into a stock from a tile (Priority: P2)

**Goal**: Clicking/tapping a tile navigates to that stock's detail page; hovering or focusing a tile reveals a rich preview (signal label, conviction with label, recency, summary snippet, add-to-watchlist) without navigating.

**Independent Test**: Click any tile and verify navigation to `/stock/{ticker}`; hover a tile and verify the preview shows signal/conviction/recency/summary and a working watchlist button that does not navigate.

### Tests for User Story 2

> Write these tests FIRST; confirm they fail before implementing T013–T014.

- [X] T012 [P] [US2] Write `TilePreview.test.tsx` in `frontend/src/components/feed/TilePreview.test.tsx` — renders `SignalBadge`, `ConvictionMeter` with label, relative time (+ "data as of" date when available), line-clamped summary, and a "+ Watchlist" button; clicking the watchlist button calls the `useAddToWatchlist` mutation and does not trigger navigation (`stopPropagation`)

### Implementation for User Story 2

- [X] T013 [US2] Implement `TilePreview` component in `frontend/src/components/feed/TilePreview.tsx` reusing `SignalBadge` and `ConvictionMeter` (shared components, unchanged) plus `useAddToWatchlist`, per [contracts/feed-grid-ui.md](./contracts/feed-grid-ui.md); makes T012 pass
- [X] T014 [US2] Wire `AnalysisTile` (`frontend/src/components/feed/AnalysisTile.tsx`) to: navigate to `/stock/{ticker}` on click or Enter-when-focused; show `TilePreview` on `mouseenter`/`focus-within` and hide on `mouseleave`/`blur`; flip the preview's placement near grid edges so it's never clipped (research R3); ensure the tile itself remains focusable (`tabIndex`/role)
- [X] T015 [US2] Add navigation and hover/focus-preview test cases to `frontend/src/pages/Feed.test.tsx` — clicking a rendered tile navigates via router, focusing a tile surfaces its preview
- [X] T016 [P] [US2] Update `specs/component-specs/frontend/components/feed/AnalysisTile.md` with the `TilePreview` contract (hover/focus trigger, content, watchlist action, click-through navigation)

**Checkpoint**: US1 + US2 together deliver the full "scan, then drill in" workflow — grid is browsable and every tile is actionable.

---

## Phase 5: User Story 3 - Filter the grid (Priority: P3)

**Goal**: Existing Feed filters (ticker, signal, sector, conviction) continue to narrow which tiles appear in the grid; pinned market-flow events remain visible above the grid only when unfiltered.

**Independent Test**: Apply each existing filter and confirm the grid shows only matching tiles; clear filters and confirm the full board returns; confirm market-flow event cards hide while filtered and reappear when cleared.

### Tests for User Story 3

> Write these tests FIRST; confirm they fail before implementing T018.

- [X] T017 [P] [US3] Add filter-narrowing and market-flow-pin test cases to `frontend/src/pages/Feed.test.tsx` — grid narrows to matching tiles when `signal`/`sector`/`conviction`/`ticker` URL params are set, full board returns when params are cleared, pinned `MarketFlowCard`s render above the grid only when no filters are active and hide once any filter is applied

### Implementation for User Story 3

- [X] T018 [US3] In `frontend/src/pages/Feed.tsx`, confirm/adjust the existing filter-read-from-`useSearchParams` wiring and the `pinnedEvents` (unfiltered + ≤14-day) logic still function correctly against the new grid layout — render `MarketFlowCard`s as a full-width row above the tile grid (research R9); `FilterBar` itself is unchanged; makes T017 pass (verified passing with no code changes required — T009's grid rewrite preserved this logic unmodified)

**Checkpoint**: All three user stories work together — dense grouped grid, click-through with rich preview, and full filter parity with the old feed.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across the whole feature.

- [X] T019 [P] Verify responsive reflow (FR-008): at phone-width viewports the grid drops to fewer columns, tiles stay legible/tappable, and the page never scrolls horizontally — adjust `frontend/src/pages/Feed.tsx` grid classes if needed. Verified via Playwright against the live stack: the grid's own `auto-fill`/`minmax` columns always fit their container at every width tested (390px–1920px), no changes needed. A horizontal-scroll bug *does* exist at 390px, but it originates in the pre-existing App shell (fixed-width sidebar + `FilterBar` inputs without `min-w-0`), not in the tile grid — logged in `KNOWN_ISSUES.md` rather than fixed here (out of scope for this frontend-only Feed feature).
- [X] T020 Run `cd frontend && npm run typecheck && npm test` and fix any regressions across the full suite (confirm no remaining references to the deleted `AnalysisCard`) — 72/72 tests pass, typecheck clean, zero references to `AnalysisCard` remain
- [X] T021 Execute the manual validation steps in [quickstart.md](./quickstart.md) against a running `docker compose` stack and record results — validated live via Playwright against the rebuilt `docker compose` stack with real seeded data (24 analyses): grid density/grouping/colors/dots (steps 1–3) ✓, one-click navigation to `/stock/MSFT` (step 4) ✓, hover preview with signal/conviction/recency/summary/watchlist button (step 5) ✓, responsive reflow at 1920px/390px with no grid-caused overflow (step 9) ✓. Infinite-scroll-merge (step 6) and full filter sweep (step 7) already covered by the automated `Feed.test.tsx` suite (US3 tests) rather than re-driven manually.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run first.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories (`groupBySignal`, page size, `SkeletonTile` are consumed by every story's rendering).
- **User Story 1 (Phase 3)**: Depends on Foundational only. Delivers the MVP grid on its own.
- **User Story 2 (Phase 4)**: Depends on Foundational + US1 (needs `AnalysisTile` to exist before wiring click/hover onto it).
- **User Story 3 (Phase 5)**: Depends on Foundational + US1 (needs the new `Feed.tsx` grid to exist before verifying filters against it); independent of US2.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories — the true MVP slice.
- **US2 (P2)**: Builds on US1's `AnalysisTile` (adds interactivity to an existing component) but is independently testable once wired.
- **US3 (P3)**: Builds on US1's `Feed.tsx` grid (verifies existing filter logic against it); independent of US2 — could be done before US2 if reprioritized.

### Within Each User Story

- Tests written and failing before implementation (T006/T007 before T008–T010; T012 before T013–T015; T017 before T018).
- Component implementation before page wiring (`AnalysisTile`/`TilePreview` before `Feed.tsx` integration).
- Component-spec doc updates ([P]) can run alongside their story's code tasks.

### Parallel Opportunities

- T002, T004, T005 (Foundational) touch different files — run in parallel.
- T006 and T007 (US1 tests) touch different files — run in parallel.
- T011 (US1 doc update) can run in parallel with T008–T010 (different files).
- T012 (US2 test) can start in parallel with US1's later tasks once `AnalysisTile` exists, but T013–T015 must wait for T008.
- T016 (US2 doc update) parallel with T013–T015.
- T017 (US3 test) can be drafted in parallel with US2 work once T009 (Feed.tsx grid) lands, since US3 doesn't depend on US2.

---

## Parallel Example: Foundational Phase

```bash
# After T001 (baseline check), launch together:
Task: "Write groupBySignal test suite in frontend/src/lib/groupFeed.test.ts"
Task: "Bump feed page size from 20 to 60 in frontend/src/hooks/useAnalysis.ts"
Task: "Create SkeletonTile loading placeholder in frontend/src/components/feed/SkeletonTile.tsx"
```

## Parallel Example: User Story 1

```bash
# Tests first, together:
Task: "Write AnalysisTile.test.tsx covering signal fills, dot counts, aria-label"
Task: "Write Feed page-composition tests covering grouped grid and skeleton board"

# Then, once T008 lands, doc update runs alongside T009-T010:
Task: "Rewrite Feed.md and add AnalysisTile.md component specs"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T005) — CRITICAL, blocks everything
3. Complete Phase 3: User Story 1 (T006–T011)
4. **STOP and VALIDATE**: Confirm the grid renders ≥30 grouped tiles with correct colors/dots per [quickstart.md](./quickstart.md) steps 1–3
5. Demo the dense board even before click-through or filters are wired

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add US1 → validate independently → demo the MVP grid
3. Add US2 → validate independently → demo click-through + hover preview
4. Add US3 → validate independently → demo full filter parity
5. Polish (T019–T021) → final responsive check, full test run, manual quickstart pass

---

## Notes

- [P] tasks touch different files with no unmet dependency.
- [Story] labels map every user-story-phase task to spec.md's US1/US2/US3 for traceability.
- No `backend/` or `agent-runner/` changes anywhere in this feature — confirmed frontend-only in plan.md.
- `frontend/src/components/shared/SkeletonCard.tsx`, `ConvictionMeter.tsx`, and `SignalBadge.tsx` are reused unmodified — do not edit them as part of this feature.
- Commit after each task or logical group; stop at each phase checkpoint to validate independently before continuing.
