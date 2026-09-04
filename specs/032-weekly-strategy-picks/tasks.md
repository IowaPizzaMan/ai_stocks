---

description: "Task list for Weekly Strategy Buy/Short Picks in AI Chat"

---

# Tasks: Weekly Strategy Buy/Short Picks in AI Chat

**Input**: Design documents from `/specs/032-weekly-strategy-picks/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/strategy-picks-api.md, quickstart.md

**Tests**: Included — Constitution Principle I is NON-NEGOTIABLE for this repo ("Every feature MUST ship with tests before it is considered done"; rule-engine skills and backend routers/agent-runner tools MUST have pytest coverage).

**Organization**: Tasks are grouped by user story (spec.md: US1 = buy picks P1, US2 = short picks P2, US3 = follow-up refinement P3) so each can be delivered and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete sibling task)
- **[Story]**: Which user story this task belongs to (US1/US2/US3) — omitted for Setup, Foundational, and Polish

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Register the new collection consistently across both services, per Constitution Principle VI.

- [X] T001 [P] Add `STRATEGY_SIGNALS = "strategy_signals"` constant to `agent-runner/tools/db.py`, in the same style/section as the existing `SCREENER` constant
- [X] T002 [P] Add `STRATEGY_SIGNALS = "strategy_signals"` constant to `backend/db.py`, matching `agent-runner/tools/db.py`
- [X] T003 Add `strategy_signals` indexes to `backend/db.py::ensure_indexes()` — `{ticker: 1}` unique, `{"the_strat.direction": 1, "the_strat.strength": -1}`, `{"gap_analysis.direction": 1, "gap_analysis.score": -1}` per data-model.md (depends on T002)
- [X] T004 [P] Extend `backend/tests/test_db_constants.py` to assert `STRATEGY_SIGNALS` matches between `backend/db.py` and `agent-runner/tools/db.py` (depends on T001, T002)

**Checkpoint**: Collection registered and indexed identically in both services.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Precompute the per-ticker strategy signals, build the Market Flow filter, and wire chat dispatch — every user story needs all of this in place.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Add a `reversal_level` field to each gap dict returned by `agent-runner/skills/gap_analysis.py::run()` — `prev_low` (`df["Low"].iloc[i-1]`) for a down gap, `prev_high` (`df["High"].iloc[i-1]`) for an up gap; both already computed locally inside the existing loop, per data-model.md's Gap Analysis derivation
- [X] T006 [P] Add test cases for the new `reversal_level` field (both gap directions) in `agent-runner/tests/test_gap_analysis.py` (depends on T005)
- [X] T007 Create `agent-runner/tools/strategy_signals.py` mirroring `agent-runner/tools/screener.py`'s shape: pure `compute_signals(ticker, price_data) -> dict` producing the `the_strat` block (direction from `tfc.status`, `strength` = count of aligned actionable timeframes, `pattern`/`timeframe`/`entry_price` preferring weekly with monthly→quarterly→yearly fallback, forced `null` direction when no pattern backs an aligned TFC) and the `gap_analysis` block (direction from `latest_gap.direction` + `score >= 3`, `entry_price` from `reversal_level`, `score`/`bias` passed through) exactly as specified in data-model.md; plus `refresh_all(db)`, `refresh_one(ticker, db)`, `run_strategy_signals_refresh(db)` entry point (depends on T005)
- [X] T008 [P] Exhaustive pytest coverage for `compute_signals()` in `agent-runner/tests/test_strategy_signals.py`: full-bullish/full-bearish/conflict TFC, weekly-pattern-present vs. fallback timeframes, aligned-TFC-but-no-pattern (direction forced `null`), insufficient price history, gap score ≥3 vs. <3 in both directions, no gap in the lookback window (depends on T007)
- [X] T009 Register `"strategy_signals_refresh": run_strategy_signals_refresh` in `agent-runner/tools/admin_jobs.py::JOB_HANDLERS`, following the exact pattern `"screener_refresh": run_screener_refresh` already uses (depends on T007)
- [X] T010 [P] Create `backend/semantic/market_flow_filter.py`: pure `classify_level(nymo_value) -> str` (small port of `skills/market_flow.py::classify_level`'s thresholds — hand-duplication precedent, not imported), `get_market_condition(db) -> dict` (one read of the latest `breadth_cache` row), and `apply_filter(candidates, direction, condition) -> dict` applying the buy/short inclusion table from data-model.md (exclude buy candidates when overbought >60, exclude short candidates when oversold <-60), returning kept candidates, excluded candidates with reasons, and a market-condition note (FR-017/FR-018)
- [X] T011 [P] Tests in `backend/tests/test_market_flow_filter.py`: boundary values (60, 60.01, -60, -60.01), missing/`null` breadth data, both buy and short directions (depends on T010)
- [X] T012 Create `backend/semantic/strategy_picks.py`: `detect(question, history) -> dict` (one `llm.generate_json()` call, `temperature: 0`, schema from contracts/strategy-picks-api.md, with `history` included in the prompt so a later follow-up can be understood in context); `compute_picks(direction, count, db) -> dict` (deterministic queries against `strategy_signals` per strategy — `.find({"the_strat.direction": ...}).sort([("the_strat.strength", -1), ("ticker", 1)]).limit(count)` and the Gap Analysis equivalent — wrapping each strategy's query/derivation in try/except so one failure doesn't sink the other (FR-015), then applying `market_flow_filter.apply_filter()`); `narrate(question, structured_result) -> str` (one `llm.generate_text()` call instructed to narrate the given lists verbatim, never alter them, and close with the FR-010 disclaimer); `answer_strategy_picks(question, history, db) -> dict` orchestrating all three into the response shape from contracts/strategy-picks-api.md, including FR-013/FR-019 special-casing for unrecognized/market_flow-named requests (depends on T007, T010). 21 tests in `backend/tests/test_strategy_picks.py` cover count resolution, ranking/tie-breaks, entry-price presence, no-padding, zero-candidate notes, FR-015 partial failure, Market Flow integration, intent parsing, narration fallback, and full orchestration.
- [X] T013 Wire dispatch into `backend/semantic/chat.py::answer_question()`: call `strategy_picks.detect()` first (behind a cheap `looks_like_strategy_picks()` keyword pre-filter so an ordinary screener question doesn't pay for the extra Ollama call — added during implementation to protect 031's SC-001 latency target); when `is_strategy_picks` is true, delegate to `strategy_picks.answer_strategy_picks()` and return its result; otherwise fall through unchanged into the existing free-form pipeline-generation flow (FR-011). Also added `"strategy_picks": None` to `_empty_response()` and the main success-path dict so every response shape is consistent (depends on T012)
- [X] T014 [P] Regression tests in `backend/tests/test_chat_router.py`: an ordinary screener question returns `strategy_picks: null` with `rows`/`criteria`/`generated_query` populated exactly as before, and makes exactly 2 Ollama calls (no extra intent-detection call); a question containing a strategy keyword but where `detect()` says no still falls through to the free-form flow (depends on T013)
- [X] T015 [P] Extend `frontend/src/api/types.ts` with `StrategyPicks`, `StrategyList`, `StrategyCandidate` types matching the response shape in contracts/strategy-picks-api.md, added as an optional field on the existing `ChatResponse` type

**Checkpoint**: `strategy_signals` precomputable and populated, Market Flow filter working, chat dispatch wired end-to-end, existing screener chat provably unaffected. User story work can now begin.

---

## Phase 3: User Story 1 - Weekly buy picks per strategy (Priority: P1) 🎯 MVP

**Goal**: A user asks a buy-picks question and gets one ranked list per strategy with specific prices, in the same reply.

**Independent Test**: Ask the buy-picks question from spec.md in the chat; verify the response has a distinct list per strategy, each ≤10 (or requested count) tickers, every ticker has a price, and a disclaimer is present.

- [X] T016 [US1] End-to-end buy-direction tests in `backend/tests/test_strategy_picks.py`: full lists returned for `direction: "buy"`; FR-006 lists aren't padded when fewer than the requested count qualify; FR-007 a strategy with zero qualifying buy candidates states so via its `note` field; FR-004/FR-012 every returned candidate carries a specific `entry_price` and a candidate without a defensible price is excluded; FR-010 the narrated `answer` includes a disclaimer sentence; FR-016 a requested count like "top 5" is honored and an invalid/unreasonable count falls back to 10 — written alongside T012 (depends on T012)
- [X] T017 [US1] FR-013 test + any needed fix: asking for a strategy name the system doesn't recognize returns `strategy_picks: null` and an `answer` listing the supported strategies, in `backend/tests/test_strategy_picks.py` — written alongside T012 (depends on T012)
- [X] T018 [US1] FR-015 test: simulate one strategy's derivation raising inside `compute_picks()` and confirm the other strategy's list still returns normally with a `note`-bearing entry for the failed one, in `backend/tests/test_strategy_picks.py` — written alongside T012 (depends on T012)
- [X] T019 [US1] FR-019 test + any needed fix: asking "what are my Market Flow picks" returns `strategy_picks: null` and an `answer` explaining Market Flow is a filter applied across the other two strategies, not its own list, in `backend/tests/test_strategy_picks.py` — written alongside T012 (depends on T012)
- [X] T020 [US1] Render `strategy_picks` buy lists in `frontend/src/pages/Chat.tsx`: one section per strategy, each candidate's ticker + entry price, a strategy's empty-list `note`, and any `excluded_by_market_flow` entries with their reason — reusing the existing chat message layout and "thinking…" indicator unchanged (depends on T015)
- [X] T021 [US1] [P] Rendering tests for the buy-picks response shape (multi-list, empty-list note, excluded-candidate note) in `frontend/src/pages/Chat.test.tsx` (depends on T020). Also verified: `npx tsc --noEmit` clean, full frontend suite (409 tests) and full backend suite (336 tests) both pass.

**Checkpoint**: User Story 1 is fully functional and independently testable/demoable.

---

## Phase 4: User Story 2 - Weekly short picks per strategy (Priority: P2)

**Goal**: The same capability as US1, mirrored for short-sell candidates.

**Independent Test**: Ask the short-picks question from spec.md; verify the response format matches US1's structure with `direction: "short"`, independent of whether a buy question was asked first.

- [X] T022 [US2] End-to-end short-direction tests in `backend/tests/test_strategy_picks.py`, mirroring T016's coverage with `direction: "short"` (full lists across both strategies, no padding, no long-candidate leakage, entry prices present) (depends on T012, T016)
- [X] T023 [US2] FR-003 edge case test: a strategy with no qualifying short-side signal for the week states so plainly via its `note` field, in `backend/tests/test_strategy_picks.py` (depends on T012)
- [X] T024 [US2] Market Flow short-side exclusion test: an oversold NYMO reading excludes an otherwise-qualifying short candidate with the correct reason text, in `backend/tests/test_market_flow_filter.py` and `backend/tests/test_strategy_picks.py` (depends on T010, T012)
- [X] T025 [US2] [P] Short-direction label rendering ("Short at $X" vs. "Buy at $X") in `frontend/src/pages/Chat.tsx`, plus a test case in `frontend/src/pages/Chat.test.tsx` — built alongside T020/T021 since the component already branches on `direction` (depends on T020)

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Follow-up refinement in the same conversation (Priority: P3)

**Goal**: A follow-up question in the same chat narrows or explains a prior strategy-picks answer without the user restating the original question.

**Independent Test**: Ask a full picks question, then a narrowing follow-up ("just show me the Gap Analysis ones"); confirm the response reflects only that strategy's list from the same underlying computation.

- [X] T026 [US3] Confirm/extend `strategy_picks.detect()`'s prompt so a follow-up question can infer `direction` from the replayed `history` when the user doesn't restate it, in `backend/semantic/strategy_picks.py` — already built in T012 (`_format_history()` prepends history to the prompt; the system prompt explicitly instructs using it to resolve a follow-up), confirmed by `test_detect_includes_history_in_the_prompt` (depends on T012)
- [X] T027 [US3] When `named_strategy` is set on a follow-up (e.g., "just show me the Gap Analysis ones"), filter the response's `lists[]` (and `excluded_by_market_flow[]`) to only that strategy's entries in `backend/semantic/strategy_picks.py::answer_strategy_picks()` (depends on T012, T026)
- [X] T028 [US3] End-to-end follow-up narrowing test (ask full picks, then narrow by strategy name, confirm consistent results) in `backend/tests/test_strategy_picks.py` (depends on T026, T027)

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T029 [P] Run `ruff check agent-runner/ backend/` and fix any findings (Constitution: Development Workflow & Quality Gates) — found and fixed 3 unused-import findings in `backend/tests/test_strategy_picks.py`; both services now clean
- [X] T030 Run quickstart.md's 6 manual validation scenarios end-to-end against a running Docker Compose stack — rebuilt backend+agent-runner images, enqueued `strategy_signals_refresh` via `work_queue` (real queue_worker pickup, wrote 560 real docs, 126 with a real The Strat direction / 73 with a real Gap Analysis direction), then hit the live `/chat` endpoint with real Ollama (qwen3:14b) for all 6 scenarios plus the US3 follow-up — all passed with correct, non-fabricated prose grounded in the real ranked data; zero errors/warnings in either service's logs throughout
- [X] T031 [P] Log any limitations or deviations discovered during implementation in `KNOWN_ISSUES.md` — added two entries under "Design limitations": the keyword pre-filter's follow-up-recognition gap, and the short-picks latency being close to the ≤15s ceiling
- [X] T032 Verify the plan's ≤15s-warm performance goal against a real Ollama-backed strategy-picks request; note any shortfall in `KNOWN_ISSUES.md` — measured live: buy picks 11.2s, short picks 14.1s (both within budget; short is close to the ceiling — logged as a watch-item), Market Flow/unrecognized-strategy special cases ~1.5-2s (single call, no ranking), count-limited and follow-up-narrowing requests ~5s, existing screener regression ~5.3s (unchanged from before this feature, confirming the keyword pre-filter avoids the extra call)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion (T003 needs T002) — BLOCKS all user stories.
- **User Stories (Phase 3-5)**: All depend on Foundational (Phase 2) completion.
  - US1 (P1) has no dependency on US2/US3.
  - US2 (P2) reuses US1's pipeline (same `compute_picks()`/`narrate()`, direction-parameterized) — independently testable, but T022 borrows T016's test patterns for consistency.
  - US3 (P3) extends `strategy_picks.detect()`/`compute_picks()` built in Foundational and exercised by US1/US2.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### Within Each Phase

- Foundational: T005 → T006/T007; T007 → T008/T009; T010 → T011; (T007, T010) → T012 → T013 → T014; T015 is independent of the backend chain.
- US1: T016-T019 (backend, parallelizable across different FRs but same file — run sequentially within the file) → T020 → T021.
- US2: T022-T024 (backend) → T025 (frontend).
- US3: T026 → T027 → T028.

### Parallel Opportunities

- Setup: T001, T002 in parallel; T004 after both.
- Foundational: T005/T010/T015 can start in parallel (different files, no shared dependency); T006 after T005; T008/T009 after T007; T011 after T010; T012 after both T007 and T010; T013 after T012; T014 after T013.
- US1: T021 after T020; T016-T019 touch the same test file so run sequentially even though conceptually independent.
- US2: T025 can run in parallel with T022-T024 once T020 (from US1) is done.
- Polish: T029 and T031 can run in parallel with each other and with T030/T032.

---

## Parallel Example: Foundational Phase

```bash
# Launch independent Foundational tasks together:
Task: "Add reversal_level field to agent-runner/skills/gap_analysis.py::run()"
Task: "Create backend/semantic/market_flow_filter.py"
Task: "Extend frontend/src/api/types.ts with StrategyPicks types"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1 (buy picks).
4. **STOP and VALIDATE**: run quickstart.md scenarios 1, 2, 4, 5, 6 against a live stack.
5. Deploy/demo if ready — buy picks alone already deliver the primary value requested.

### Incremental Delivery

1. Setup + Foundational → precomputation and dispatch working, existing chat unaffected.
2. Add US1 → buy picks work end-to-end → validate → demo (MVP).
3. Add US2 → short picks work end-to-end (mostly test/UI-copy work, since the pipeline is already direction-agnostic) → validate → demo.
4. Add US3 → conversational narrowing → validate → demo.
5. Polish → lint, full quickstart pass, performance check.

---

## Notes

- [P] tasks touch different files and have no dependency on an incomplete sibling task.
- US2's backend tasks are lighter than US1's by design (research.md/plan.md): `compute_picks()` and `narrate()` are built once, direction-parameterized, in Foundational — US2 mainly proves the short side and its specific copy/edge cases.
- Constitution Principle III is fully satisfied, not just mitigated: no task gives the LLM a role in selecting or ranking tickers — `detect()` only extracts parameters, `narrate()` only composes prose from an already-final structured result.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
