---

description: "Task list for Remove Stock Page Horizontal Overflow"
---

# Tasks: Remove Stock Page Horizontal Overflow

**Input**: Design documents from `/specs/030-stock-page-overflow/`

**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required for user stories), [research.md](research.md), [data-model.md](data-model.md) (N/A — no entities), [quickstart.md](quickstart.md)

**Tests**: Included. Constitution Principle I requires Vitest + RTL coverage for
user-facing frontend logic, and `plan.md`/`research.md` §4 already commit to specific
structural (class-presence) assertions as the automated regression guard for this CSS fix,
alongside manual in-browser verification (jsdom has no real layout engine — see
research.md §4).

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)

## Path Conventions

Web app structure already in place (`backend/`, `frontend/`). This feature touches
`frontend/src/` only — see plan.md's Project Structure section.

---

## Phase 1: Setup

**Purpose**: Establish a clean baseline before making changes

- [ ] T001 Run `cd frontend && npm run test && npm run typecheck` to confirm both pass
      before any changes, so later failures can be attributed to this feature's edits

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fix the shared app-shell layout bug (documented in `KNOWN_ISSUES.md`) that
both user stories depend on — neither story's independent test can pass until the shell
itself stops forcing page width.

**⚠️ CRITICAL**: No user story work can be verified until this phase is complete

- [ ] T002 [P] In `frontend/src/App.tsx`, add `min-w-0` to the `<main>` element's
      className (currently `"flex-1 p-6"` at App.tsx:21) so the main content area can
      shrink to fit the viewport instead of being forced wide by its content's intrinsic
      width (research.md §1)
- [ ] T003 [P] In `frontend/src/components/layout/Sidebar.tsx`, add a responsive hide
      class (`hidden md:block`) to the `<aside>` element's className (currently
      `"w-56 shrink-0 border-r border-zinc-800 p-4 text-sm text-zinc-400"` at
      Sidebar.tsx:77) so the fixed-width Watchlist sidebar no longer forces page width
      below the `md` (768px) breakpoint (research.md §2)
- [ ] T004 [P] Update `frontend/src/App.test.tsx` to assert the `<main>` element carries
      `min-w-0` alongside `flex-1` (depends on T002)
- [ ] T005 [P] Update `frontend/src/components/layout/Sidebar.test.tsx` to assert the
      `<aside>` element carries the `hidden md:block` responsive-hide class alongside its
      existing classes (depends on T003)

**Checkpoint**: The shared shell no longer forces page width at narrow viewports —
foundation ready for stock-page-specific work.

---

## Phase 3: User Story 1 - No page-wide horizontal scroll on narrow screens (Priority: P1) 🎯 MVP

**Goal**: `/stock/:ticker` shows no horizontal scrollbar at phone widths (320px–390px),
with every header control reachable and long company names wrapping/truncating instead of
forcing overflow.

**Independent Test**: Load `/stock/:ticker` at a 390px-wide viewport and confirm there is
no horizontal scrollbar and no content is clipped or pushed off the right edge.

### Implementation for User Story 1

- [ ] T006 [US1] In `frontend/src/pages/StockDetail.tsx`, add `min-w-0` and `truncate` (or
      `break-words`) to the ticker `<h1>{symbol}</h1>` and the `record?.name` span inside
      the header's `flex items-center gap-4` container (StockDetail.tsx:78-85), so a long
      company name wraps/truncates instead of forcing the header row wider than the
      viewport (research.md §3)
- [ ] T007 [US1] Update `frontend/src/pages/StockDetail.test.tsx` to assert the ticker and
      company-name header elements carry `min-w-0` and `truncate` (or `break-words`)
      classes (depends on T006)

### Manual Verification for User Story 1

- [ ] T008 [US1] Per `quickstart.md` step 2: with `npm run dev` running, open
      `/stock/:ticker` in a browser and confirm no horizontal scrollbar at 320px and 390px
      viewport widths, and that all header controls (back link, Pull/Refresh/Watchlist
      buttons) remain reachable without side-scrolling (spec.md SC-001, SC-002)
- [ ] T009 [US1] Per `quickstart.md` step 3: open a ticker with an unusually long company
      name at a narrow viewport and confirm the header wraps/truncates instead of
      widening the page (spec.md Edge Cases)

**Checkpoint**: User Story 1 is independently functional — the stock page has no
horizontal overflow at phone widths. This is the MVP.

---

## Phase 4: User Story 2 - Layout reflows smoothly across window sizes (Priority: P2)

**Goal**: Continuously resizing the browser between desktop and 320px never shows a
horizontal scrollbar at any intermediate width, and other pages sharing the app shell
don't regress.

**Independent Test**: Load the stock detail page at a wide desktop width, then
progressively shrink the browser window down to 320px, confirming no horizontal
scrollbar appears at any point.

### Manual Verification for User Story 2

- [ ] T010 [US2] Per `quickstart.md` step 2: with the stock detail page open, drag the
      browser window slowly from a wide desktop width down to 320px and confirm no
      horizontal scrollbar appears at any intermediate width, then widen it back to
      desktop and confirm the layout returns to normal with no leftover clipping
      (spec.md SC-003)
- [ ] T011 [US2] Per `quickstart.md` step 3: at 390px width, open the main feed page (`/`)
      and confirm it also has no horizontal scrollbar, verifying the Phase 2 shell fix
      doesn't regress other pages that share it (spec.md FR-006, SC-005)
- [ ] T012 [US2] Per `quickstart.md` step 3: at a narrow width, open a tab with a wide
      data table (e.g. the Institutional tab) and confirm it still scrolls within its own
      container rather than causing page-level horizontal scroll (spec.md FR-004, SC-004)

**Checkpoint**: Both user stories are functional — the full `quickstart.md` checklist
passes.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and closing the loop on the known-issue record

- [ ] T013 [P] Run `cd frontend && npm run test` and confirm the full suite passes,
      including the assertions added in T004, T005, and T007
- [ ] T014 [P] Run `cd frontend && npm run typecheck` and confirm no type errors
- [ ] T015 Update `KNOWN_ISSUES.md`: move the "App shell causes horizontal page scroll at
      phone widths (~390px)" bullet (currently under "Design limitations (accepted for
      now)") into the "Fixed" section, following the existing `~~struck-through~~ — fixed
      via specs/030-stock-page-overflow/...` format used by the other entries there

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS both user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) completion
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) completion; its manual
  checks (T010) are most meaningful once US1's header fix (T006) is also in place, so do
  Phase 3 before Phase 4 even though there's no file-level conflict
- **Polish (Phase 5)**: Depends on Phases 3 and 4 both being complete

### Within Each Phase

- T002 and T003 touch different files and have no dependency on each other — parallelizable
- T004 depends on T002 (same behavior, different file); T005 depends on T003 — both test
  tasks are parallelizable with each other
- T006 before T007 (implementation before its test assertion)
- T008/T009 depend on T006 being in place (they verify its effect in-browser)
- T010–T012 depend on both Phase 2 and Phase 3 being complete (they verify the combined
  effect)
- T015 should be last — it records the fix only once everything above is verified

### Parallel Opportunities

- T002 and T003 (Foundational implementation, different files)
- T004 and T005 (Foundational tests, different files)
- T013 and T014 (Polish validation commands, independent)

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch both shell fixes together (different files, no shared dependency):
Task: "Add min-w-0 to <main> in frontend/src/App.tsx"
Task: "Add hidden md:block to <aside> in frontend/src/components/layout/Sidebar.tsx"

# Then their tests, also in parallel:
Task: "Assert min-w-0 on <main> in frontend/src/App.test.tsx"
Task: "Assert hidden md:block on <aside> in frontend/src/components/layout/Sidebar.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (fixes the shared shell bug)
3. Complete Phase 3: User Story 1 (stock page header fix + narrow-width verification)
4. **STOP and VALIDATE**: Confirm T008/T009 pass — the core complaint ("remove the
   overflow from the stock page") is resolved
5. This alone is a shippable fix

### Incremental Delivery

1. Setup + Foundational → shell no longer forces width
2. Add User Story 1 → verify independently → MVP complete
3. Add User Story 2 → verify continuous resize + no regressions elsewhere
4. Phase 5 → full test suite green, typecheck clean, `KNOWN_ISSUES.md` updated

---

## Notes

- No `[P]` tasks exist within Phase 3 or Phase 4 — the implementation task (T006) and its
  test (T007) are sequential by nature (test asserts the implementation's classes), and
  the manual verification tasks are inherently sequential checks against a running dev
  server, not independent file edits.
- Commit after each phase (or after each task, if preferred) rather than as one large diff,
  consistent with this being a small, easily-reviewable layout fix.
- This feature adds no new dependencies, files, components, or entities — total surface
  area is 3 source files + their 3 existing test files + `KNOWN_ISSUES.md`.
