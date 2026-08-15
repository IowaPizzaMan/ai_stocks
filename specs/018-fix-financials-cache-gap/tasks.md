# Tasks: Fix Stale Empty Financials Cache

**Input**: Design documents from `/specs/018-fix-financials-cache-gap/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/financials-cache.md, quickstart.md

**Tests**: Included — constitution Principle I (Test-First & Comprehensive Coverage) is non-negotiable for this repo: behavior lands with tests, tests are written first and must fail before implementation.

**Organization**: Tasks are grouped by user story. US1 (retry on warm cache hit) is a self-sufficient MVP — via the legacy empty-key rule it fixes the reported BSX bug even before US2 exists. US2 (outcome recording) adds the confirmed-vs-unavailable precision that stops retrying genuinely-empty statement types.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Include exact file paths in descriptions

## Path Conventions

Existing two-service layout — no new directories. All behavior change is in `agent-runner/tools/financials.py` + `agent-runner/tests/test_financials.py`; backend and specs files are touched only for regression/docs.

---

## Phase 1: Setup (Baseline)

**Purpose**: Confirm a green starting point so failures during implementation are attributable to this feature.

- [X] T001 Run the existing suite and linter to confirm baseline green: `python -m pytest tests/test_financials.py -v` and `ruff check .` from `agent-runner/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None required. No new dependencies, collections, or infrastructure — the change is confined to one existing function and its tests (plan.md Structure Decision). Proceed directly to Phase 3.

**Checkpoint**: Baseline green from T001 = foundation ready.

---

## Phase 3: User Story 1 - Financial statements appear when the provider has data (Priority: P1) 🎯 MVP

**Goal**: A warm cache hit no longer blindly returns cached `data` — statement types that are retry-eligible get re-fetched on that run, merged into the doc, and served. With the legacy rule (doc has no `outcomes` field → empty value = retry-eligible), this alone self-heals the BSX case with no migration.

**Independent Test**: Seed a mongomock cache doc (no `outcomes` field) with all-empty statement lists and a recent `fetched_at`; call `get_financials`; assert the empty keys were re-fetched and the merged result is returned. Live: re-run BSX analysis and see financials populate (quickstart.md step 2).

### Tests for User Story 1 (write first — must fail against current code) ⚠️

- [X] T002 [US1] Add failing tests for warm-hit retry to `agent-runner/tests/test_financials.py`: (a) legacy doc (no `outcomes`, all keys empty, fresh `fetched_at`) → all 7 keys re-fetched, merged data returned and persisted; (b) legacy doc with mixed keys (some populated, some empty) → only empty keys re-fetched, populated keys untouched and served with zero calls for them; (c) partial retry preserves the doc's original `fetched_at` (research D4); (d) retry that hits 402 again fail-softs — key stays `[]`, no exception escapes `get_financials` (FR-004)
- [X] T003 [US1] Add failing regression guard to `agent-runner/tests/test_financials.py`: warm doc with all keys populated → zero FMP calls and data returned as-is (protects FR-003 / SC-002; adapts the existing `test_warm_cache_makes_no_fmp_calls` seeding to the new lookup path)

### Implementation for User Story 1

- [X] T004 [US1] Implement warm-hit retry in `get_financials` in `agent-runner/tools/financials.py`: on a cache hit within 90 days, compute retry-eligible keys (legacy rule for docs without `outcomes`: empty value → eligible), re-fetch only those via `fmp_get` with the existing 402/403 and `FmpBudgetExceededError` degrade-to-`[]` handling, merge into `data`, persist with `$set` on `data` only (do NOT touch `fetched_at`), and return the merged dict
- [X] T005 [US1] Run `python -m pytest tests/test_financials.py -v` and `ruff check .` from `agent-runner/` — T002/T003 tests now pass, all pre-existing tests still pass

**Checkpoint**: US1 fully functional — the reported bug is fixed (BSX self-heals on next analysis run). Only imprecision remaining: a genuinely-empty statement type on a legacy doc is retried every run instead of once.

---

## Phase 4: User Story 2 - Distinguish "confirmed no data" from "temporarily unavailable" (Priority: P2)

**Goal**: Fetches record a per-key `outcomes` map (`confirmed` = HTTP 200 even if empty; `unavailable` = 402/403/budget), and the retry logic consumes it — so confirmed-empty keys are settled for the window (FR-002/FR-003) and only genuinely-unavailable keys keep retrying (FR-001).

**Independent Test**: Simulate a full fetch where one key 402s and another returns 200-empty; assert the doc's `outcomes` marks them `unavailable`/`confirmed` respectively, and that a second call retries only the 402'd key.

### Tests for User Story 2 (write first — must fail against US1-only code) ⚠️

- [ ] T006 [US2] Add failing outcome-recording tests to `agent-runner/tests/test_financials.py`: (a) full fetch with one key 402ing → doc's `outcomes` = `unavailable` for that key, `confirmed` for the rest (extend `test_restricted_symbol_402_degrades_to_empty`); (b) full fetch under `FmpBudgetExceededError` → all keys `unavailable` (extend `test_budget_exceeded_degrades_to_empty`); (c) full fetch returning 200 with empty payload for a key → `confirmed`, and a subsequent warm call does NOT re-fetch it (AC US2-2); (d) warm-hit retry that succeeds promotes the key `unavailable` → `confirmed` and a third call makes zero fetches (state-transition table in data-model.md)
- [ ] T007 [US2] Add failing invariant test to `agent-runner/tests/test_financials.py`: whenever a doc is written, `outcomes` and `data` cover exactly `set(ENDPOINTS)` and every `unavailable` key has `data[key] == []` (data-model.md validation rules)

### Implementation for User Story 2

- [ ] T008 [US2] Record and consume outcomes in `agent-runner/tools/financials.py`: full fetch writes `outcomes[key] = "confirmed" | "unavailable"` per the contract's outcome-recording table (contracts/financials-cache.md); warm-hit retry-eligibility switches from the legacy empty-value rule to `outcomes[key] == "unavailable"` when the field is present (legacy rule kept as fallback for docs without it); successful retries update both `data[key]` and `outcomes[key]` in the same `$set`
- [ ] T009 [US2] Run `python -m pytest tests/test_financials.py -v` and `ruff check .` from `agent-runner/` — full suite green
- [ ] T010 [US2] Run backend consumer regression from `backend/`: `python -m pytest tests/test_routers.py -v` — `GET /stocks/{ticker}/financials` response shape unchanged (`outcomes` must NOT leak into the response; contract's HTTP section)

**Checkpoint**: Both stories complete — retry is precise, confirmed results are settled for the window, consumers unchanged.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Spec sync (constitution II), issue-log hygiene, and end-to-end validation.

- [ ] T011 [P] Rewrite the "Caching logic" section of `specs/component-specs/agent-runner/tools/financials.md` to describe the `outcomes` map, per-key warm-hit retry, legacy-doc derivation, and `fetched_at` preservation (sync obligation in contracts/financials-cache.md)
- [ ] T012 [P] Move the "Empty financials from a temporary FMP condition are cached as settled for 90 days" entry in `KNOWN_ISSUES.md` from Open bugs to the fixed section (strikethrough style used by existing entries), noting the fix shipped via `specs/018-fix-financials-cache-gap/`
- [ ] T013 Live validation per `specs/018-fix-financials-cache-gap/quickstart.md` step 2: rebuild/restart agent-runner (`docker compose up -d --build agent-runner`), trigger a BSX analysis run, confirm via mongosh that the BSX doc's keys populate with `confirmed` outcomes and original `fetched_at`, and that `GET http://localhost:8000/stocks/BSX/financials` + the Stock Detail page show financial data (SC-001)
- [ ] T014 Final gate: full `python -m pytest` + `ruff check .` in `agent-runner/`, and `python -m pytest` in `backend/` (constitution Development Workflow gate)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run immediately
- **Foundational (Phase 2)**: Empty — no blocker beyond T001
- **US1 (Phase 3)**: Depends on T001 only
- **US2 (Phase 4)**: Depends on US1's implementation (T004) — it refines the retry-eligibility rule T004 introduces. Still independently *testable* (T006/T007 assert outcome behavior directly)
- **Polish (Phase 5)**: T011/T012 after US2 lands; T013/T014 last

### Task Dependencies

```text
T001 → T002, T003 → T004 → T005 → T006, T007 → T008 → T009, T010 → T011, T012 (parallel) → T013 → T014
```

### Parallel Opportunities

Limited by design — nearly everything lives in two files (`financials.py`, `test_financials.py`), so most tasks are sequential. Genuine parallelism:

- T009 and T010 (different services' test runs)
- T011 and T012 (different documentation files)

## Parallel Example: Phase 5

```bash
# After T010, launch both doc-sync tasks together:
Task: "Rewrite Caching logic section in specs/component-specs/agent-runner/tools/financials.md"
Task: "Move fixed entry in KNOWN_ISSUES.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 baseline → T002–T005
2. **STOP and VALIDATE**: BSX self-heals live (quickstart step 2 works at this point — the legacy rule retries its empty keys)
3. This alone resolves the reported bug; US2 is precision, not the fix

### Incremental Delivery

1. US1 → validate live → the user-visible bug is gone (MVP)
2. US2 → validate → confirmed-empty keys stop burning a retry call per run (SC-004 fully met)
3. Polish → component spec + KNOWN_ISSUES sync, final gates

---

## Notes

- Tests first, watch them fail, then implement (constitution I)
- `income_quarterly` uses `limit=4` on the stable API (`limit=8` 402s) — don't "fix" that while editing (component spec note, verified 2026-08-02)
- The separate `analyst-estimates` 400 bug logged in KNOWN_ISSUES.md is explicitly OUT of scope for this feature — don't fold it into these tasks
- Commit after each task or logical group
