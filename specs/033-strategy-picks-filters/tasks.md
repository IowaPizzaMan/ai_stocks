# Tasks: Combined Strategy Picks & Screener Filters in AI Chat

**Input**: Design documents from `/specs/033-strategy-picks-filters/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/strategy-picks-filters-api.md](./contracts/strategy-picks-filters-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included and REQUIRED — constitution Principle I ("Test-First & Comprehensive Coverage") is non-negotiable for this repo; a task that adds behavior without a corresponding test is incomplete.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) so each story is independently implementable and testable. Every 032-era file this feature touches already exists — no new service, collection, or route.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task in this phase)
- **[Story]**: US1 / US2 / US3, mapping to spec.md's three user stories
- All paths are repo-relative

---

## Phase 1: Setup

**Purpose**: Establish a clean baseline before touching shared code.

- [X] T001 Confirm branch `033-strategy-picks-filters` is checked out and record a passing baseline by running `python -m pytest tests/test_screener.py tests/test_strategy_signals.py -q` in `agent-runner/` and `python -m pytest tests/test_screener_contract.py tests/test_chat_router.py tests/test_strategy_picks.py -q` in `backend/` — no code changes in this task.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extract the query-generation code both `chat.py`'s existing free-form flow and this feature's new condition-translation path must share (research.md R3) — a pure refactor, zero behavior change, but every user story below builds on it.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Extract `QUERY_SCHEMA`, `build_system_prompt()` (from `_build_system_prompt`), `criteria_from_pipeline()` (from `_criteria_from_pipeline`), and a new `generate_pipeline(prompt_text, *, client=None)` wrapper into new module `backend/semantic/screener_query.py`; update `backend/semantic/chat.py` to import and call these instead of its local copies — behavior of the existing free-form flow must be unchanged (data-model.md "New shared module").
- [X] T003 Run `python -m pytest tests/test_chat_router.py tests/test_strategy_picks.py -q` in `backend/` after T002 and confirm all pre-existing tests still pass unmodified — regression guard for FR-009 before any new behavior is added.

**Checkpoint**: Foundation ready — `screener_query.py` exists and `chat.py`'s free-form flow is verified unchanged; user story implementation can now begin.

---

## Phase 3: User Story 1 - Narrowing strategy picks with an extra condition (Priority: P1) 🎯 MVP

**Goal**: A strategy-picks question that also names one or more extra conditions (liked/disliked, sector, financial trend, etc.) is recognized, translated into a `screener` query via the shared mechanism from Phase 2, and used to narrow each strategy's candidate universe *before* ranking — with plain zero-match and unrecognized-condition messaging.

**Independent Test**: Ask a strategy-picks question (containing a strategy-related keyword, so it passes the still-unmodified intent gate) with one extra condition; verify returned picks are a subset meeting that condition. Ask one combining two conditions (liked + sector); verify results meet both. Ask one with a condition matching zero candidates; verify a plain explanation, not an empty unexplained list or unfiltered results.

### Tests for User Story 1 ⚠️ Write first, confirm they fail before implementing

- [X] T004 [P] [US1] Add `liked_status` derivation cases to `agent-runner/tests/test_screener.py::compute_signals()` tests: `"liked"`, `"disliked"`, and `None` (no `ticker_index` document, or one with `sentiment: null`) — mirrors data-model.md's validation rules.
- [X] T005 [P] [US1] Add `"liked_status"` to the mirrored `SCREENER_FIELDS` set in `backend/tests/test_screener_contract.py` (constitution Principle VI — this assertion must fail until T010 lands).
- [X] T006 [P] [US1] Create `backend/tests/test_condition_filter.py` covering `condition_filter.translate_conditions()`: a single condition applied successfully, two conditions AND'd into one pipeline, a legitimate zero-match ticker set (`applied: True`, `tickers: set()`), `in_scope: false` → `applied: False`, `llm.LLMError` → `applied: False`, `query_guard.QueryRejected` → `applied: False`, and that any `$sort`/`$limit`/`$project` stage the model emits is stripped before execution so the ticker set is never truncated (research.md R4).
- [X] T007 [P] [US1] Extend `backend/tests/test_strategy_picks.py` with `_rank_strategy()`/`compute_picks()` cases: a `ticker_filter` excludes non-matching tickers from the Mongo predicate *before* sort/limit (a filtered-out stock never occupies a slot a qualifying one should get), and a strategy's empty result under a narrowing `ticker_filter` produces a `note` naming the condition.
- [X] T008 [P] [US1] Extend `backend/tests/test_chat_router.py` with an end-to-end `POST /chat` case for a combined liked+sector question, asserting `strategy_picks.condition_requested`, `condition_applied`, `condition_note`, and the repurposed top-level `criteria` field match `contracts/strategy-picks-filters-api.md`'s example.

### Implementation for User Story 1

- [X] T009 [P] [US1] In `agent-runner/tools/screener.py`, add a `liked_status: str | None` parameter to `compute_signals()` and populate it in `refresh_all()`/`refresh_one()` by reading `sentiment` from the same `ticker_index` lookup already used for `is_tracked` (data-model.md).
- [X] T010 [P] [US1] Add the `liked_status` field description to `backend/semantic/schema.py::SCREENER_SCHEMA["fields"]` (data-model.md's exact wording).
- [X] T011 [P] [US1] Add `db[SCREENER].create_index([("liked_status", ASCENDING)])` to `backend/db.py::ensure_indexes()`, alongside `screener`'s existing single-field indexes.
- [X] T012 [P] [US1] In `backend/semantic/strategy_picks.py`, extend `INTENT_SCHEMA` with `"extra_conditions": {"type": ["array", "null"], "items": {"type": "string"}}` (added to `required`), and extend `_build_intent_system_prompt()` to instruct extraction of every additional filtering condition as free-text phrases, explicitly naming liked/disliked preference as one recognized kind (data-model.md).
- [X] T013 [P] [US1] Create `backend/semantic/condition_filter.py::translate_conditions(conditions: list[str], db, *, client=None) -> dict`: join `conditions` into one prompt, call `screener_query.generate_pipeline()`, map `in_scope=false` / `llm.LLMError` / `query_guard.QueryRejected` to `applied=False`, otherwise strip `$sort`/`$limit`/`$project` from the validated pipeline, append `{"$project": {"_id": 0, "ticker": 1}}`, execute unlimited against `db[SCREENER]`, and return `{"applied", "tickers", "criteria", "note"}` per data-model.md's `ConditionFilterResult`.
- [X] T014 [US1] In `backend/semantic/strategy_picks.py`, extend `_rank_strategy()` to accept `ticker_filter: set[str] | None` and add `{"ticker": {"$in": sorted(ticker_filter)}}` to its Mongo predicate when present; extend `compute_picks()` to accept and thread through `ticker_filter` / `condition_label`, naming the condition in a strategy's empty-result `note` when the emptiness is caused by the filter.
- [X] T015 [US1] In `backend/semantic/strategy_picks.py::answer_strategy_picks()`, call `condition_filter.translate_conditions()` when `intent["extra_conditions"]` is non-empty, pass its ticker set into `compute_picks()`, and populate the new `condition_requested` / `condition_applied` / `condition_note` fields plus the top-level `criteria` field (from `ConditionFilterResult.criteria`) on the response.
- [X] T016 [US1] Extend `_format_narration_prompt()` and `_fallback_narration()` in `backend/semantic/strategy_picks.py` to include the condition's criteria or failure note, so `narrate()`'s prose states what was applied or why a condition couldn't be (FR-007 baseline case).

**Checkpoint**: User Story 1 is fully functional and independently testable — run `backend/tests/test_condition_filter.py`, `test_strategy_picks.py`, `test_screener_contract.py`, and `agent-runner/tests/test_screener.py`.

---

## Phase 4: User Story 2 - Reliable recognition of a strategy-picks question, any phrasing (Priority: P2)

**Goal**: A strategy-picks-shaped question is recognized even with no trigger keyword present, without changing how an ordinary screener question is answered.

**Independent Test**: Ask several strategy-picks questions phrased without "strategy"/"The Strat"/"Gap Analysis"/"Market Flow"; verify each is recognized and answered as strategy-picks. Ask an ordinary screener question; verify its response is unaffected.

### Tests for User Story 2 ⚠️ Write first, confirm they fail before implementing

- [X] T017 [P] [US2] Extend `backend/tests/test_strategy_picks.py::detect()` tests with no-keyword phrasings ("give me 10 stocks to buy and 10 to short", "what should I add to my portfolio this week") expecting `is_strategy_picks: true`, plus an ordinary screener question expecting `false` (regression guard for FR-009).
- [X] T018 [P] [US2] Extend `backend/tests/test_chat_router.py` to assert `chat.answer_question()` now invokes `strategy_picks.detect()` unconditionally (e.g. via a spy/mock) even for a question with none of the old trigger keywords, and that a plain screener question's full response body is unchanged from pre-033 behavior.

### Implementation for User Story 2

- [X] T019 [US2] Remove `strategy_picks.looks_like_strategy_picks()` and `_INTENT_HINT_KEYWORDS` from `backend/semantic/strategy_picks.py`.
- [X] T020 [US2] Update `backend/semantic/chat.py::answer_question()` to call `strategy_picks.detect()` unconditionally, removing the `looks_like_strategy_picks()` guard while keeping the existing `llm.LLMError` → `is_strategy_picks: False` fallback (FR-001).
- [X] T021 [US2] Broaden `_build_intent_system_prompt()` in `backend/semantic/strategy_picks.py` with phrasing-agnostic `is_strategy_picks` recognition guidance (asking what to buy/short "this week" per an approach, with or without naming it), including the positive/negative examples from data-model.md.

**Checkpoint**: User Stories 1 and 2 both work independently and together — a no-keyword question carrying a liked/sector condition is recognized and correctly filtered.

---

## Phase 5: User Story 3 - Graceful handling when a condition has no matching data (Priority: P3)

**Goal**: A condition with no corresponding data field, or an ambiguous condition with a reasonable stand-in interpretation, is handled transparently rather than fabricated or crashed on.

**Independent Test**: Ask a compound question using a condition with no reasonable corresponding field (e.g. "most popular"); verify the response explains the limitation and still answers the rest. Ask one with an ambiguous but resolvable condition (e.g. "large cap"); verify the response discloses the interpretation used.

### Tests for User Story 3 ⚠️ Write first, confirm they fail before implementing

- [X] T022 [P] [US3] Extend `backend/tests/test_condition_filter.py` with the "most popular in consumer staples" case: `in_scope: false` from the translation call yields `applied: False` and a `note` naming what couldn't be applied (US3 AS1).
- [X] T023 [P] [US3] Extend `backend/tests/test_strategy_picks.py` with an ambiguous-condition case (e.g. "large cap") where translation succeeds but the resolved predicate isn't the literal phrase — asserting `condition_applied: true` with a non-null `condition_note` stating the interpretation used (FR-008).
- [X] T024 [P] [US3] Extend `backend/tests/test_chat_router.py` with an end-to-end case mirroring `contracts/strategy-picks-filters-api.md`'s "condition couldn't be applied" example, asserting the strategy-picks answer is still returned, unfiltered, alongside the explanatory `condition_note`.

### Implementation for User Story 3

- [X] T025 [US3] Refine `condition_filter.translate_conditions()`'s `note` text for the `in_scope: false` / `llm.LLMError` / `QueryRejected` paths to state plainly, per-condition, what couldn't be applied (data-model.md's `ConditionFilterResult`), in `backend/semantic/condition_filter.py`.
- [X] T026 [US3] Add an explicit instruction to the condition-translation prompt built in `backend/semantic/condition_filter.py` (not the shared `screener_query.build_system_prompt()`, which must stay behavior-identical for the free-form flow per FR-009) to disclose rather than silently substitute an ambiguous interpretation, and to never fabricate a match for a concept with no corresponding field.

**Checkpoint**: All three user stories are independently functional; US3 hardens the disclosure/failure messaging US1 already wired end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide gates and final validation across all three stories.

- [X] T027 [P] Run `ruff check backend/` and `ruff check agent-runner/ scripts/` (constitution Development Workflow gate) and fix any findings introduced by this feature.
- [X] T028 Run all six scenarios in `specs/033-strategy-picks-filters/quickstart.md` against a running Docker Compose stack and confirm every response shape matches its documented expectation.
- [X] T029 [P] If quickstart validation (T028) surfaces any limitation or bug not already covered by a spec requirement, log it in `KNOWN_ISSUES.md` per this project's standing convention.
- [X] T030 [P] Add `condition_requested: string | null`, `condition_applied: boolean`, and `condition_note: string | null` to the `StrategyPicks` interface in `frontend/src/api/types.ts` for type accuracy — no rendering change required (`Chat.tsx` doesn't reference these fields; see Notes).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (US1's `condition_filter.py` imports `screener_query.py`).
- **User Story 1 (Phase 3)**: Depends on Foundational only. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational only. Independent of US1 — testable on its own with a keyword-free question that has no extra condition. Touches `strategy_picks.py`'s intent-detection code that US1 also extended (T012); apply after US1 in this ordering to avoid rework, though the two changes don't conflict logically.
- **User Story 3 (Phase 5)**: Depends on Foundational and on US1's `condition_filter.py` existing (T013) — it refines that module's messaging rather than replacing it.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests are written and confirmed failing before implementation tasks in the same phase.
- Data/schema changes (screener field, index) before the modules that query them.
- New modules (`condition_filter.py`) before the orchestration code that calls them.
- Ranking/filtering logic before the response-shape wiring that surfaces it.
- Narration/prompt refinements last, since they consume the already-final structured result.

### Parallel Opportunities

- Phase 3 (US1) tests: T004–T008 touch five different files — all parallelizable.
- Phase 3 (US1) implementation: T009–T013 touch five different files (`agent-runner/tools/screener.py`, `backend/semantic/schema.py`, `backend/db.py`, `backend/semantic/strategy_picks.py`, `backend/semantic/condition_filter.py`) — parallelizable; T014–T016 then apply sequentially since they build on T013 and share `strategy_picks.py` with T012.
- Phase 4 (US2) tests: T017–T018 touch two different files — parallelizable.
- Phase 5 (US3) tests: T022–T024 touch three different files — parallelizable.
- Phase 6: T027 and T029 are independent of each other and of T028.

---

## Parallel Example: User Story 1

```bash
# Tests (five different files, launch together):
Task: "liked_status derivation cases in agent-runner/tests/test_screener.py"
Task: "liked_status mirrored field-name assertion in backend/tests/test_screener_contract.py"
Task: "condition_filter.translate_conditions() cases in backend/tests/test_condition_filter.py"
Task: "ticker_filter cases in backend/tests/test_strategy_picks.py"
Task: "combined-condition end-to-end case in backend/tests/test_chat_router.py"

# Implementation (five different files, launch together):
Task: "liked_status derivation in agent-runner/tools/screener.py"
Task: "liked_status field description in backend/semantic/schema.py"
Task: "liked_status index in backend/db.py"
Task: "INTENT_SCHEMA extra_conditions in backend/semantic/strategy_picks.py"
Task: "condition_filter.py translate_conditions() in backend/semantic/condition_filter.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1) — this alone delivers the exact capability the spec's Input
   section was written to fix ("only use the stocks I have liked").
3. **STOP and VALIDATE**: run T004–T008's tests plus quickstart.md scenarios 1, 2, and 4.
4. Deploy/demo if ready — User Story 1 works with the existing keyword gate still in place.

### Incremental Delivery

1. Setup + Foundational → shared query-generation module ready.
2. Add User Story 1 → test independently → deploy/demo (MVP).
3. Add User Story 2 → test independently → deploy/demo (now keyword-free phrasing is recognized).
4. Add User Story 3 → test independently → deploy/demo (unanswerable/ambiguous conditions are now disclosed, not fabricated or crashed on).
5. Polish → lint, full quickstart pass, known-issues log.

---

## Notes

- [P] tasks touch different files with no dependency on an incomplete task in the same phase.
- Constitution Principle I is non-negotiable here — every implementation task above has a
  corresponding test task earlier in its phase.
- No frontend *rendering* task exists — the spec's Assumptions explicitly rule out new
  user-facing controls, and `frontend/src/pages/Chat.tsx` already surfaces the condition
  disclosure through the narrated `answer` text. T030 only keeps `frontend/src/api/types.ts`
  accurate for the three new additive fields; it does not change any component.
- Commit after each task or logical group; verify tests fail before implementing, per repo convention.
