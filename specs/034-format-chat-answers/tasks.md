---

description: "Task list for Format Chat Answers"
---

# Tasks: Format Chat Answers

**Input**: Design documents from `/specs/034-format-chat-answers/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/answer-text-component.md, quickstart.md

**Tests**: Included — plan.md's Constitution Check (Principle I) requires Vitest + RTL coverage for `AnswerText`, and `Chat.test.tsx` already follows this pattern.

**Organization**: Tasks are grouped by user story (US1/US2/US3 from spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Web application layout already in use by this repo: `frontend/src/...` (this feature touches only `frontend/`; `backend/` and `agent-runner/` are untouched per FR-008).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new rendering dependencies and scaffold the new component directory before any story-specific work begins.

- [X] T001 Add `react-markdown` and `remark-breaks` to `frontend/package.json` dependencies and install (`cd frontend && npm install react-markdown remark-breaks`)
- [X] T002 Create `frontend/src/components/chat/` directory (new per-page component directory, matching the convention of `components/congress/`, `components/earnings/`, `components/stock/`)

**Checkpoint**: Dependencies installed, directory exists — component work can begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the single shared component (`AnswerText`) that every user story's acceptance criteria render through. All three user stories exercise the same component, so its core implementation is foundational rather than story-specific — but per the contract (`contracts/answer-text-component.md`) it is one component with no per-story variants, so it is built once here and each story phase below adds/validates its own behavior and tests against it.

**⚠️ CRITICAL**: No user story test can pass until this phase is complete.

- [X] T003 Create `AnswerText` component in `frontend/src/components/chat/AnswerText.tsx` per `contracts/answer-text-component.md`: accepts `{ text: string }` prop, renders via `ReactMarkdown` with the `remark-breaks` plugin (research.md D1/D2), no `rehype-raw` (keeps embedded HTML/script inert per FR-004), and a `components` prop mapping `p`, `ul`, `ol`, `li`, `strong`, `em`, `h1`-`h6`, `a`, `code`, `blockquote` to Tailwind-styled JSX wrappers using the existing dark palette (`text-zinc-100`/`text-zinc-300`/`text-zinc-500`, `text-sky-500` for links, `border-zinc-800` for blockquote rule) per research.md D3; `ul`/`ol` overrides use `pl-*` left-padding classes so nested sub-lists indent automatically via DOM nesting (research.md D4); `a` override sets `target="_blank" rel="noopener noreferrer"` with `href` taken as-is with no scheme validation (research.md D5/FR-010); wrap the rendered output in a container with wrapping/overflow classes (e.g. `break-words`, no fixed-width overflow) to satisfy FR-005
- [X] T004 Swap `<p className="text-sm text-zinc-100">{exchange.response.answer}</p>` at `frontend/src/pages/Chat.tsx:80` for `<AnswerText text={exchange.response.answer} />`, importing `AnswerText` from `../components/chat/AnswerText` (contracts/answer-text-component.md Caller contract; applies inside the exchange-history loop so it covers every exchange per FR-007)

**Checkpoint**: `AnswerText` exists and is wired into `Chat.tsx`. User story test/validation phases below can now run against real rendering.

---

## Phase 3: User Story 1 - Scan a multi-point answer at a glance (Priority: P1) 🎯 MVP

**Goal**: Multi-paragraph and list-structured assistant answers render as visually distinct paragraphs/list items instead of one run-on block (FR-001, FR-002).

**Independent Test**: Ask a question that produces a multi-sentence, multi-point answer (e.g. one comparing several tickers) and confirm the response renders as separated paragraphs/list items rather than one continuous line of text.

### Tests for User Story 1

- [X] T005 [P] [US1] Add `frontend/src/components/chat/AnswerText.test.tsx` with cases: plain single-sentence text renders as one `<p>` (FR-006 baseline), text with a blank line between two lines renders as two separate `<p>` blocks (FR-001), `- item`/`1. item` lines render as a `<ul>`/`<ol>` with distinct `<li>` entries (FR-002), and an indented nested list item renders as a nested `<ul>`/`<ol>` inside its parent `<li>` (FR-002 nested-list clarification)
- [X] T006 [P] [US1] Update `frontend/src/pages/Chat.test.tsx`: add/adjust a case asserting a multi-paragraph or list-formatted fixture answer renders as multiple distinct elements (query by role/substring per research.md D6, not a full raw-string match), confirming the `AnswerText` swap at Chat.tsx:80 is wired correctly end-to-end

### Implementation for User Story 1

- [X] T007 [US1] Run `cd frontend && npm test -- AnswerText.test.tsx Chat.test.tsx` and fix any paragraph/list styling or `components` map gaps in `frontend/src/components/chat/AnswerText.tsx` (from T003) until all US1 cases in T005/T006 pass

**Checkpoint**: User Story 1 is fully functional and testable independently — paragraphs and (including nested) lists render correctly.

---

## Phase 4: User Story 2 - Spot key details within the answer (Priority: P2)

**Goal**: Emphasized text, headers, inline code spans, blockquotes, and links render as styled/functional output with no literal markup characters visible (FR-003, FR-010).

**Independent Test**: Ask a question whose answer includes emphasized terms and confirm those terms render as visually styled text with no stray formatting characters visible.

### Tests for User Story 2

- [X] T008 [P] [US2] Extend `frontend/src/components/chat/AnswerText.test.tsx` with cases: `**bold**`/`*italic*` render as `<strong>`/`<em>` with no literal `*` characters, `# Header`..`###### Header` render as `<h1>`-`<h6>`, `` `code` `` renders as `<code>` with no literal backticks, `> quote` renders as `<blockquote>` with no literal `>`, and `[text](url)` renders as a clickable `<a href="url">` including a non-http(s) scheme URL (e.g. `javascript:` or `data:`) with no scheme restriction applied (FR-010, spec.md edge case) and with `target="_blank"`/`rel="noopener noreferrer"` attributes present
- [X] T009 [P] [US2] Extend `frontend/src/components/chat/AnswerText.test.tsx` with an embedded-HTML/script edge case: an answer containing literal `<script>alert(1)</script>` text renders as inert visible text (not executed, no script element mounted in the DOM) — FR-004

### Implementation for User Story 2

- [X] T010 [US2] Run `cd frontend && npm test -- AnswerText.test.tsx` and fix any emphasis/header/code/blockquote/link styling or `rel`/`target` attribute gaps in `frontend/src/components/chat/AnswerText.tsx` until all US2 cases in T008/T009 pass

**Checkpoint**: User Stories 1 AND 2 both work independently — structure and inline styling are both correct.

---

## Phase 5: User Story 3 - Answer stays readable on any device (Priority: P3)

**Goal**: Long or densely formatted answers remain fully readable at narrow viewport widths with no horizontal overflow (FR-005, SC-004).

**Independent Test**: Resize the Chat page to a narrow viewport, ask a question with a long answer, and confirm the text wraps within the visible width with no horizontal scrollbar.

### Tests for User Story 3

- [X] T011 [P] [US3] Extend `frontend/src/components/chat/AnswerText.test.tsx` with a case asserting the rendered container carries word-wrap/overflow-safe classes (e.g. `break-words`, no `whitespace-nowrap`/fixed width) for a long unbroken-content fixture (a long word or URL with no natural break points), covering FR-005

### Implementation for User Story 3

- [X] T012 [US3] Run `cd frontend && npm test -- AnswerText.test.tsx` and adjust wrapping/overflow Tailwind classes on `AnswerText`'s container (`frontend/src/components/chat/AnswerText.tsx`) until the T011 case passes; manually verify at a 375px viewport per `quickstart.md` step 5

**Checkpoint**: All three user stories are independently functional — structure, inline styling, and responsive wrapping are all correct.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Requirements that span all three stories — malformed input safety, multi-exchange consistency, and full quickstart validation.

- [X] T013 [P] Add a malformed-markdown edge case to `frontend/src/components/chat/AnswerText.test.tsx`: an answer with an unclosed emphasis marker (e.g. `"This *is bold"`) still renders fully and readably with no thrown error and no missing text (spec.md Edge Cases)
- [X] T014 [P] Add a multi-exchange consistency case to `frontend/src/pages/Chat.test.tsx`: a conversation with two exchanges, each with differently-formatted answers (e.g. one plain, one with a list), asserts both render through `AnswerText` correctly, not just the most recent one (FR-007)
- [X] T015 Run `cd frontend && npm run typecheck` and fix any type errors introduced by the `AnswerText` component or its call site
- [X] T016 Run the full `quickstart.md` automated validation (`cd frontend && npm run typecheck && npm test -- Chat.test.tsx AnswerText.test.tsx`) and confirm every FR/SC listed in quickstart.md's "Expected" section passes
- [X] T017 Perform `quickstart.md`'s manual validation against the live Chat page (ask a multi-point question, confirm paragraphs/lists/bold/links render, resize to ~375px and confirm no horizontal scroll, ask a second question and confirm both exchanges render consistently)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion (T001's installed deps) — BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion (T003/T004)
  - US1, US2, US3 all extend the same `AnswerText.test.tsx` file, so within-file edits are sequential in practice even though they test independent behavior; each story's assertions are independently verifiable
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — no dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — independently testable; does not require US1's tests to exist first, though both land in the same test file
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) — independently testable

### Within Each User Story

- Tests written before the implementation/fix task that makes them pass
- Story complete before moving to next priority (recommended; not a hard technical dependency since all stories share one component)

### Parallel Opportunities

- T005 and T006 (US1 tests, different files) can run in parallel
- T008 and T009 (US2 tests, same file — sequential in practice) are logically independent but not file-parallel
- T013 and T014 (Polish tests, different files) can run in parallel
- Once Phase 2 completes, US1/US2/US3 test-writing (T005/T006, T008/T009, T011) can be drafted in parallel by different contributors before running the shared `npm test` fix pass

---

## Parallel Example: User Story 1

```bash
# Launch both US1 test-writing tasks together (different files):
Task: "Add AnswerText.test.tsx paragraph/list cases in frontend/src/components/chat/AnswerText.test.tsx"
Task: "Update Chat.test.tsx multi-paragraph/list assertion in frontend/src/pages/Chat.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T004) — CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T005-T007)
4. **STOP and VALIDATE**: Multi-paragraph/list answers render correctly, independently of US2/US3
5. Deploy/demo if ready — this alone resolves the core "read nicely" complaint

### Incremental Delivery

1. Setup + Foundational → `AnswerText` exists and is wired in
2. Add User Story 1 → paragraphs/lists render → validate → demo (MVP!)
3. Add User Story 2 → emphasis/headers/code/blockquotes/links render → validate → demo
4. Add User Story 3 → confirmed responsive at narrow widths → validate → demo
5. Polish → malformed-input safety, multi-exchange consistency, full quickstart pass

### Parallel Team Strategy

With multiple developers, after Phase 2 (Foundational) completes:
- Developer A: User Story 1 (T005-T007)
- Developer B: User Story 2 (T008-T010)
- Developer C: User Story 3 (T011-T012)

All three extend the same `AnswerText.tsx`/`AnswerText.test.tsx` files, so coordinate merges (small, additive diffs — new test cases and `components` map entries — low conflict risk).

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- This feature has exactly one shared component (`AnswerText`) serving all three stories — "Foundational" here means "the component that makes any story testable," not unrelated shared infrastructure
- No backend/API/database work — `backend/` and `agent-runner/` are untouched (FR-008)
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
