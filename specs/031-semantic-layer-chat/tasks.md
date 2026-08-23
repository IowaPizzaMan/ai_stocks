# Tasks: Semantic Layer Chat Assistant

**Input**: Design documents from `specs/031-semantic-layer-chat/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and required, not optional — constitution Principle I is NON-NEGOTIABLE for
this repo, and `compute_signals()` is exactly the pure, deterministic, high-value surface the
principle exists for. Test tasks are ordered before their implementation per Principle I's
"tests before it is considered done."

**Architecture note**: `/speckit-clarify` raised whether to replace model-generated raw queries
with a parameterized screening tool (would have eliminated the Principle III deviation
entirely). The user chose to keep the current plan (raw query generation, clarification Q1 =
option B) rather than rewrite. Tasks below implement the plan as designed in `plan.md`,
including its recorded, justified deviation.

**Organization**: Tasks are grouped by user story (P1–P4 from spec.md) so each is independently
implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps task to US1–US4 from spec.md
- File paths are exact, per plan.md's Project Structure

---

## Phase 1: Setup

**Purpose**: Register the new collection everywhere both services need to agree on it, before
any signal computation or query logic is written.

- [ ] T001 Add `ollama>=0.4` to `backend/requirements.txt`; add `depends_on: [ollama]` to the
      `backend` service block in `docker-compose.yml` (backend has no LLM capability today —
      research.md R10)
- [ ] T002 [P] Add `SCREENER = "screener"` constant to `backend/db.py` and register its indexes
      in `ensure_indexes()`: `{ticker:1}` unique, `{range_pct_20d:1}`, `{zscore_20d:1}`,
      `{weekly_change_pct:1}`, `{financials_trend:1}`, `{fcf_exceeds_debt:1}`, `{sector:1}`,
      `{is_tracked:1}` — per data-model.md's Indexes section
- [ ] T003 [P] Add the identical `SCREENER = "screener"` constant and matching
      `ensure_indexes()` entries to `agent-runner/tools/db.py` (Principle VI hand-sync)

**Checkpoint**: Both services agree the `screener` collection exists and is indexed identically.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Nothing in any user story is testable until signals can be computed and stored, the
model can be called safely, and generated queries can be validated. This phase delivers all
three.

**⚠️ CRITICAL**: No user story work may begin until this phase is complete.

- [ ] T004 [P] Write exhaustive unit tests for `compute_signals()` in
      `agent-runner/tests/test_screener.py` covering: empty bars, exactly 24 vs. exactly 25 bars
      (the `insufficient_history` boundary), a flat price series (zero stdev → `zscore_20d`
      null), a zero-width 20-day range (`range_pct_20d` null), missing `financials`, a single
      annual financial period (trend fields null, need ≥2), `$numberLong` coercion on
      `freeCashFlow`/`totalDebt`, each `financials_trend`/`margin_trend` branch
      (improving/flat/deteriorating), and NaN/None values inside a bar. Tests must fail — the
      function doesn't exist yet.
- [ ] T005 Implement `compute_signals(bars, financials, profile, *, ticker, is_tracked) -> dict`
      as a pure function in `agent-runner/tools/screener.py`, satisfying every case in T004 and
      every field in data-model.md's field table (no I/O, no `datetime.now()` inside — inject
      the timestamp)
- [ ] T006 Implement `refresh_all(db)` in `agent-runner/tools/screener.py`: read
      `price_history`, `financials_cache`, `company_info`, `ticker_index`; call
      `compute_signals()` per ticker; `db[SCREENER].replace_one({"ticker": t}, doc,
      upsert=True)` (single writer — safe here per research.md R11, unlike `price_history`)
- [ ] T007 [P] Register a `screener_refresh` admin job handler in
      `agent-runner/tools/admin_jobs.py`, following the existing `JOB_HANDLERS` registry pattern,
      calling `refresh_all()`
- [ ] T008 [P] Trigger `screener` refresh for a ticker immediately after its per-ticker prefetch
      completes (wherever `agent-runner/crew.py` or `agent-runner/queue_worker.py` finishes
      writing `price_history`/`financials_cache` for that ticker), so signals never lag their
      inputs by a cycle
- [ ] T009 [P] Write `backend/tests/test_screener_contract.py` asserting the semantic-layer
      field description (from T013) contains exactly the same field names as
      `compute_signals()`'s output keys — the mirrored-table enforcement described in
      contracts/screener-collection.md. Must fail until T013 exists.
- [ ] T010 Port `agent-runner/llm.py` to `backend/llm.py`: same `ollama.Client` /
      `client.chat(...)` shape, but add an **explicit `timeout`** on both the client and the
      call (fixes the gap logged in `KNOWN_ISSUES.md` for this new call site — agent-runner's
      own client is unchanged and remains a separately tracked issue), a long `keep_alive` so
      the model stays resident (research.md R2), and support for `format=<JSON Schema dict>`
      constrained decoding (research.md R10) for query generation
- [ ] T011 [P] Write `backend/tests/test_query_guard.py` — adversarial cases: `$out`, `$merge`,
      `$function`, `$accumulator`, `$where`, `$graphLookup`, an unrecognized `$`-prefixed stage,
      a pipeline targeting a collection other than `screener`, a pipeline with no `$limit`, and
      a pipeline whose `$limit` exceeds the hard cap. Every case must be rejected. Must fail —
      the guard doesn't exist yet.
- [ ] T012 Implement `backend/semantic/query_guard.py`: a read-stage **allowlist**
      (`$match, $project, $addFields, $set, $group, $sort, $limit, $skip, $count, $unwind,
      $lookup, $facet, $sample, $sortByCount, $replaceRoot`), collection-target restriction to
      `screener`, `$limit` injection when absent (default 50, hard cap 200), and `maxTimeMS`
      injection (default 5000ms) — satisfying every case in T011
- [ ] T013 [P] Implement `backend/semantic/schema.py`: the semantic layer description (field
      names, types, plain-language meaning) fed to the model, generated from or asserted against
      the same field table `compute_signals()` produces — satisfying T009
- [ ] T014 Add an Ollama pre-warm call (a throwaway `chat()` invocation with `keep_alive` set) to
      `backend/main.py`'s lifespan startup, so the first real question isn't the one that pays
      the ~10s model-load cost (research.md R2 — SC-001 is warm-only)

**Checkpoint**: `screener` can be populated and inspected; a hand-written pipeline can be
validated and rejected correctly; the backend can call Ollama safely. No user-facing behavior
yet — that starts in Phase 3.

---

## Phase 3: User Story 1 - Ask a research question in plain English (Priority: P1) 🎯 MVP

**Goal**: A user opens the Chat tab, asks a data-grounded question, and gets a real answer
naming actual tickers, back by a real query.

**Independent Test**: quickstart.md steps 2–4 — populate `screener`, submit the flagship
question, confirm the ~13-ticker set and that criteria/match-count/raw-query are all present.

### Tests for User Story 1

- [ ] T015 [P] [US1] Contract test in `backend/tests/test_chat_router.py`: `POST /chat` with the
      flagship question returns `200`, non-empty `answer`, `criteria` naming the four filters,
      `match_count > 0`, `generated_query.collection == "screener"`, and `rows` — seed
      `screener` with the fixture values from research.md R4 (AAPL etc.)
- [ ] T016 [P] [US1] Contract test in `backend/tests/test_chat_router.py`: an out-of-scope
      question (e.g. "what is the CEO's favorite color?") returns `200`, `note: "out_of_scope"`,
      `generated_query: null`, and an `answer` that plainly declines (FR-007, SC-005)
- [ ] T017 [P] [US1] Contract test in `backend/tests/test_chat_router.py`: when the query guard
      rejects a generated pipeline, the endpoint returns `200` with `note: "query_rejected"` and
      an explanatory `answer` — never a `500` (FR-015)
- [ ] T018 [P] [US1] Frontend test in `frontend/src/pages/Chat.test.tsx` (mock `api.post` per
      the repo's `vi.mock("../api/client", ...)` convention): submitting a question renders the
      answer, the criteria list, and the match count without any user action to reveal them

### Implementation for User Story 1

- [ ] T019 [US1] Implement `backend/semantic/chat.py`: build the query-generation prompt from
      `schema.py` + the question, call `llm.py` with `format=<schema>`, `temperature=0`,
      `think=false`; validate the result through `query_guard`; execute against `screener`;
      call `llm.py` again (`temperature=0.2`) to turn the rows into prose; assemble the full
      response shape from contracts/chat-api.md
- [ ] T020 [US1] Implement `GET /chat/schema` in `backend/routers/chat.py`, returning
      `schema.py`'s description plus `document_count` and `signals_as_of` from `screener`
- [ ] T021 [US1] Implement `POST /chat` in `backend/routers/chat.py`: `422` on empty/oversized
      `question`, `503` on Ollama unreachable/timeout, delegates to `chat.py`, `db=Depends(db_dependency)`
      per the repo's router convention
- [ ] T022 [US1] Register `chat.router` in `backend/main.py`'s router-import block (satisfies
      T015–T017)
- [ ] T023 [P] [US1] Add `ChatRequest`/`ChatResponse`/`ChatCriterion` types to
      `frontend/src/api/types.ts` per contracts/chat-api.md
- [ ] T024 [P] [US1] Implement `useChat` in `frontend/src/hooks/useChat.ts` as a `useMutation`
      (no polling, per the repo's global `refetchInterval: false` convention) posting to `/chat`
- [ ] T025 [US1] Implement `frontend/src/pages/Chat.tsx`: question input, loading state, answer
      display, criteria list **always visible**, match count, raw query behind a toggle
      (FR-013/014), `degraded`/`note` handling — satisfying T018
- [ ] T026 [US1] Add `{ to: "/chat", label: "Chat" }` to the `links` array in
      `frontend/src/components/layout/Navbar.tsx`
- [ ] T027 [US1] Add the import and `<Route path="/chat" element={<Chat />} />` to
      `frontend/src/App.tsx`

**Checkpoint**: User Story 1 is fully functional and independently testable — quickstart.md
steps 2–4 and 6 (nav/route parts) pass.

---

## Phase 4: User Story 2 - Ask a follow-up question (Priority: P2)

**Goal**: A follow-up question resolves against the prior exchange without repeating context,
and nothing is persisted server-side.

**Independent Test**: quickstart.md's follow-up example — ask the flagship question, then "which
of those has the largest market cap?" — and confirm the reference resolves; confirm a page
refresh clears the conversation.

### Tests for User Story 2

- [ ] T028 [P] [US2] Contract test in `backend/tests/test_chat_router.py`: `POST /chat` with a
      `history` array containing the flagship Q&A, followed by a question referencing "those,"
      returns an answer scoped to the prior result set rather than re-screening everything
- [ ] T029 [P] [US2] Frontend test in `frontend/src/pages/Chat.test.tsx`: a second question is
      sent with the accumulated `history`; simulating a remount (fresh component mount) shows an
      empty conversation (FR-004 — no persistence)

### Implementation for User Story 2

- [ ] T030 [US2] Extend `POST /chat` in `backend/routers/chat.py` to accept optional `history`
      (default `[]`), truncating server-side to the last ~6 turns before use (research.md R9)
- [ ] T031 [US2] Extend `backend/semantic/chat.py` to fold `history` into both the
      query-generation and interpretation prompts so references like "those" resolve
- [ ] T032 [US2] Add in-memory conversation state (array of turns, component state only — no
      `localStorage`, no server call to persist) to `frontend/src/pages/Chat.tsx`, replayed as
      `history` on every request — satisfying T029

**Checkpoint**: US1 and US2 both function independently; a follow-up conversation works and
nothing survives a refresh.

---

## Phase 5: User Story 3 - Trustworthy, complete underlying data (Priority: P3)

**Goal**: Signals are provably correct, and the one genuinely orphaned collection is gone.

**Independent Test**: quickstart.md steps 3 and 7 — the screener-driven ~13-ticker set matches a
direct aggregation; `portfolio_digest_cache` is gone; `transcripts_cache` and `fmp_entitlements`
remain; both Python test suites still pass.

### Tests for User Story 3

- [ ] T033 [P] [US3] Add a regression test in `agent-runner/tests/test_screener.py` asserting
      `compute_signals()` reproduces the reference AAPL values measured in research.md R4
      (`range_pct_20d ≈ 0.21`, `zscore_20d ≈ −0.42`, `weekly_change_pct ≈ 1.12`,
      `fcf_exceeds_debt == False`) from fixed input fixtures
- [ ] T034 [P] [US3] Add a test (in `backend/tests/test_db_constants.py` or similar) asserting
      `FUND_HOLDINGS`, `SECTOR_PERFORMANCE`, `STOCK_NEWS`, `MARKET_NEWS` are no longer defined in
      `backend/db.py` or `agent-runner/tools/db.py`

### Implementation for User Story 3

- [ ] T035 [P] [US3] Remove the dead constants `FUND_HOLDINGS`, `SECTOR_PERFORMANCE`,
      `STOCK_NEWS`, `MARKET_NEWS` from `backend/db.py`. **Do not touch** the
      `"sector_performance"` / `"fund_holdings"` string literals in
      `agent-runner/tools/fmp_client.py:148,153` — those are unrelated FMP probe-family keys.
- [ ] T036 [P] [US3] Remove the same four dead constants from `agent-runner/tools/db.py`
- [ ] T037 [US3] Add a one-off, explicitly-confirmed script `scripts/drop_portfolio_digest_cache.py`
      that drops `portfolio_digest_cache` (1 doc, zero code references — orphaned when
      `agent-runner/tools/portfolio.py` was deleted, research.md R7). Not run automatically by
      any test or CI step — run manually per quickstart.md step 7, after the user confirms.
- [ ] T038 [P] [US3] Add `{ticker: 1}` unique index for `institutional_cache` to both
      `backend/db.py` and `agent-runner/tools/db.py`'s `ensure_indexes()` (pre-existing gap,
      research.md R8 — it's queried by ticker but has no index beyond `_id`)
- [ ] T039 [P] [US3] Add a short comment in both `db.py` files next to `TRANSCRIPTS_CACHE` and
      `FMP_ENTITLEMENTS` noting they are intentionally retained despite 0 live documents
      (reserved for `specs/007-earnings-transcripts/`; actively written respectively) — so a
      future cleanup pass doesn't re-flag them

**Checkpoint**: Data layer is accurate and pruned; `SC-003` and the US3 acceptance scenarios
hold.

---

## Phase 6: User Story 4 - Platform scales to a much larger dataset (Priority: P4)

**Goal**: Confirm, not assume, that chat and the data layer hold up at ~15x volume.

**Independent Test**: quickstart.md step 8 — seed a 15x-sized `screener`, confirm chat latency
and correctness are unaffected, confirm no per-document size or query-time limits are hit.

### Tests / Implementation for User Story 4

- [ ] T040 [P] [US4] Write `scripts/seed_15x_screener.py` generating ~8,340 synthetic `screener`
      documents (realistic field distributions, not all-identical values) for a scale dry-run
- [ ] T041 [US4] Run the 15x dry-run per quickstart.md step 8 against the seeded data; confirm
      chat query execution stays in the low milliseconds and the flagship question still returns
      a sensible result set; record the measured numbers in research.md's R5 section
- [ ] T042 [P] [US4] Add a test in `backend/tests/test_query_guard.py` confirming the `$limit` /
      `maxTimeMS` bounds actually constrain execution against the 15x-scale seeded collection
      (not just against the small dev dataset)

**Checkpoint**: All four user stories are independently functional; SC-004 is verified with
real numbers, not assumed.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T043 Run the full quickstart.md success checklist end-to-end, in order
- [ ] T044 [P] `ruff check backend/` and `ruff check agent-runner/ scripts/` — fix any
      violations (constitution's mandatory quality gate)
- [ ] T045 Run `pytest` in `backend/` and `agent-runner/`, and `npm test` in `frontend/` —
      confirm all green, including the pre-existing `transcripts_cache` cleanup test
      (`backend/tests/test_routers.py:460`) which must still pass after T035–T039
- [ ] T046 [P] Review `KNOWN_ISSUES.md`'s two entries added during planning (Ollama timeout,
      MongoDB auth posture) and update wording if implementation revealed anything beyond what
      was recorded — e.g., if T010's backend-side timeout fix should be cross-referenced

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup (needs the `SCREENER` constant to exist) —
  **blocks all user stories**
- **User Story 1 (Phase 3)**: depends on Foundational only
- **User Story 2 (Phase 4)**: depends on Foundational **and** US1 (extends the same endpoint and
  page built in Phase 3) — not independent of US1 the way US3/US4 are
- **User Story 3 (Phase 5)**: depends on Foundational only; independent of US1/US2
- **User Story 4 (Phase 6)**: depends on Foundational and the `screener` collection shape from
  Phase 2; independent of US1/US2/US3 in implementation, though its test is most meaningful
  once US1 exists to exercise
- **Polish (Phase 7)**: depends on all delivered stories

### Parallel Opportunities

- T002, T003 in parallel (different files)
- T004, T009, T011, T013 in parallel once T002/T003 land (different test/impl files, no
  cross-dependency until integration)
- Within US1: T015–T018 in parallel; T023, T024 in parallel
- Within US3: T033–T039 are almost entirely `[P]` — different files, no shared state
- US3 (Phase 5) and US4 (Phase 6) can run in parallel with each other, and with US2 (Phase 4),
  once Foundational is done — only US2's dependency on US1's files (`routers/chat.py`,
  `semantic/chat.py`, `Chat.tsx`) makes it sequential after Phase 3

---

## Parallel Example: Foundational Phase

```bash
# After T002/T003 land, these have no interdependency:
Task: "Write exhaustive unit tests for compute_signals() in agent-runner/tests/test_screener.py"
Task: "Write backend/tests/test_query_guard.py adversarial cases"
Task: "Implement backend/semantic/schema.py"
```

## Parallel Example: User Story 3

```bash
Task: "Remove dead constants from backend/db.py"
Task: "Remove dead constants from agent-runner/tools/db.py"
Task: "Add institutional_cache ticker index to both db.py files"
Task: "Add regression test for AAPL reference signal values"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1)
2. **STOP and VALIDATE**: run quickstart.md steps 2–4 and 6
3. This is a demoable chat feature even before follow-ups, cleanup, or the 15x dry-run exist

### Incremental Delivery

1. Setup + Foundational → foundation ready (screener populated, guard proven, LLM callable)
2. + US1 → demoable chat (MVP)
3. + US2 → conversational follow-ups
4. + US3 → data provably accurate, `portfolio_digest_cache` gone
5. + US4 → 15x headroom measured, not assumed
6. Polish → full quickstart pass, lint, full test suites green

### Notes on this feature specifically

- T010 and T012 are the two tasks implementing the Constitution Complexity Tracking mitigations
  (constrained decoding, read-only allowlist) — do not treat them as generic plumbing; they are
  the load-bearing safety mechanisms for the recorded Principle III deviation.
- T037 (`drop_portfolio_digest_cache.py`) is the only genuinely destructive task in this list.
  Confirm with the user before running it, per the spec's own non-reversibility note.
- T041's numbers matter more than its passing/failing status — the point of US4 is an honest
  measurement, not a checkbox.
