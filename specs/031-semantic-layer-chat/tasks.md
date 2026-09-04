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

- [X] T001 Add `ollama>=0.4` to `backend/requirements.txt`; add `depends_on: [ollama]` to the
      `backend` service block in `docker-compose.yml` (backend has no LLM capability today —
      research.md R10)
- [X] T002 [P] Add `SCREENER = "screener"` constant to `backend/db.py` and register its indexes
      in `ensure_indexes()`: `{ticker:1}` unique, `{range_pct_20d:1}`, `{zscore_20d:1}`,
      `{weekly_change_pct:1}`, `{financials_trend:1}`, `{fcf_exceeds_debt:1}`, `{sector:1}`,
      `{is_tracked:1}` — per data-model.md's Indexes section
- [X] T003 [P] Add the identical `SCREENER = "screener"` constant and matching
      `ensure_indexes()` entries to `agent-runner/tools/db.py` (Principle VI hand-sync)

**Checkpoint**: Both services agree the `screener` collection exists and is indexed identically.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Nothing in any user story is testable until signals can be computed and stored, the
model can be called safely, and generated queries can be validated. This phase delivers all
three.

**⚠️ CRITICAL**: No user story work may begin until this phase is complete.

- [X] T004 [P] Write exhaustive unit tests for `compute_signals()` in
      `agent-runner/tests/test_screener.py` covering: empty bars, exactly 24 vs. exactly 25 bars
      (the `insufficient_history` boundary), a flat price series (zero stdev → `zscore_20d`
      null), a zero-width 20-day range (`range_pct_20d` null), missing `financials`, a single
      annual financial period (trend fields null, need ≥2), `$numberLong` coercion on
      `freeCashFlow`/`totalDebt`, each `financials_trend`/`margin_trend` branch
      (improving/flat/deteriorating), and NaN/None values inside a bar. Tests must fail — the
      function doesn't exist yet.
- [X] T005 Implement `compute_signals(bars, financials, profile, *, ticker, is_tracked) -> dict`
      as a pure function in `agent-runner/tools/screener.py`, satisfying every case in T004 and
      every field in data-model.md's field table (no I/O, no `datetime.now()` inside — inject
      the timestamp)
- [X] T006 Implement `refresh_all(db)` in `agent-runner/tools/screener.py`: read
      `price_history`, `financials_cache`, `company_info`, `ticker_index`; call
      `compute_signals()` per ticker; `db[SCREENER].replace_one({"ticker": t}, doc,
      upsert=True)` (single writer — safe here per research.md R11, unlike `price_history`).
      Also added `refresh_one(ticker, db)` for the per-ticker trigger (T008).
- [X] T007 [P] Register a `screener_refresh` admin job handler in
      `agent-runner/tools/admin_jobs.py`, following the existing `JOB_HANDLERS` registry pattern,
      calling `refresh_all()`
- [X] T008 [P] Trigger `screener` refresh for a ticker immediately after its per-ticker prefetch
      completes (wherever `agent-runner/crew.py` or `agent-runner/queue_worker.py` finishes
      writing `price_history`/`financials_cache` for that ticker), so signals never lag their
      inputs by a cycle
- [X] T009 [P] Write `backend/tests/test_screener_contract.py` asserting the semantic-layer
      field description (from T013) contains exactly the same field names as
      `compute_signals()`'s output keys — the mirrored-table enforcement described in
      contracts/screener-collection.md. Must fail until T013 exists.
- [X] T010 Port `agent-runner/llm.py` to `backend/llm.py`: same `ollama.Client` /
      `client.chat(...)` shape, but add an **explicit `timeout`** on both the client and the
      call (fixes the gap logged in `KNOWN_ISSUES.md` for this new call site — agent-runner's
      own client is unchanged and remains a separately tracked issue), a long `keep_alive` so
      the model stays resident (research.md R2), and support for `format=<JSON Schema dict>`
      constrained decoding (research.md R10) for query generation. Also added explicit `think`
      control (default off) — qwen3 is a reasoning model, not something agent-runner's llm.py
      needed to handle.
- [X] T011 [P] Write `backend/tests/test_query_guard.py` — adversarial cases: `$out`, `$merge`,
      `$function`, `$accumulator`, `$where`, `$graphLookup`, an unrecognized `$`-prefixed stage,
      a pipeline targeting a collection other than `screener`, a pipeline with no `$limit`, and
      a pipeline whose `$limit` exceeds the hard cap. Every case must be rejected. Must fail —
      the guard doesn't exist yet.
- [X] T012 Implement `backend/semantic/query_guard.py`: a read-stage **allowlist**
      (`$match, $project, $addFields, $set, $group, $sort, $limit, $skip, $count, $unwind,
      $lookup, $facet, $sample, $sortByCount, $replaceRoot`), collection-target restriction to
      `screener`, `$limit` injection when absent (default 50, hard cap 200), and `maxTimeMS`
      injection (default 5000ms) — satisfying every case in T011
- [X] T013 [P] Implement `backend/semantic/schema.py`: the semantic layer description (field
      names, types, plain-language meaning) fed to the model, generated from or asserted against
      the same field table `compute_signals()` produces — satisfying T009
- [X] T014 Add an Ollama pre-warm call (a throwaway `chat()` invocation with `keep_alive` set) to
      `backend/main.py`'s lifespan startup, so the first real question isn't the one that pays
      the ~10s model-load cost (research.md R2 — SC-001 is warm-only). Runs in a daemon thread
      (fire-and-forget) so a slow/unreachable Ollama never delays backend startup.

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

- [X] T015 [P] [US1] Contract test in `backend/tests/test_chat_router.py`: `POST /chat` with the
      flagship question returns `200`, non-empty `answer`, `criteria` naming the four filters,
      `match_count > 0`, `generated_query.collection == "screener"`, and `rows` — seed
      `screener` with the fixture values from research.md R4 (AAPL etc.). Also added: empty-
      screener degrades to `note: "no_data"` without calling the model at all, and Ollama being
      unreachable degrades to `200`/`model_unavailable` rather than `503` (see the contract
      refinement noted below).
- [X] T016 [P] [US1] Contract test in `backend/tests/test_chat_router.py`: an out-of-scope
      question (e.g. "what is the CEO's favorite color?") returns `200`, `note: "out_of_scope"`,
      `generated_query: null`, and an `answer` that plainly declines (FR-007, SC-005)
- [X] T017 [P] [US1] Contract test in `backend/tests/test_chat_router.py`: when the query guard
      rejects a generated pipeline, the endpoint returns `200` with `note: "query_rejected"` and
      an explanatory `answer` — never a `500` (FR-015). Also asserts the DB is untouched (the
      actual FR-012/SC-007 guarantee).
- [X] T018 [P] [US1] Frontend test in `frontend/src/pages/Chat.test.tsx` (mock `api.post` per
      the repo's `vi.mock("../api/client", ...)` convention): submitting a question renders the
      answer, the criteria list, and the match count without any user action to reveal them.
      Note: this repo doesn't use `@testing-library/jest-dom` — assertions use `.toBeDefined()`/
      `.toBeNull()` per the existing `Sidebar.test.tsx` convention, not `.toBeInTheDocument()`.

### Implementation for User Story 1

- [X] T019 [US1] Implement `backend/semantic/chat.py`: build the query-generation prompt from
      `schema.py` + the question, call `llm.py` with `format=<schema>`, `temperature=0`,
      `think=false`; validate the result through `query_guard`; execute against `screener`;
      call `llm.py` again (`temperature=0.2`) to turn the rows into prose; assemble the full
      response shape from contracts/chat-api.md. The system prompt includes a worked example
      pipeline with `$`-prefixed stage names — an early live test against real Ollama showed
      the model sometimes omits the `$` without one; the guard caught it safely (as designed)
      but the example fixed the underlying reliability issue.
- [X] T020 [US1] Implement `GET /chat/schema` in `backend/routers/chat.py`, returning
      `schema.py`'s description plus `document_count` and `signals_as_of` from `screener`
- [X] T021 [US1] Implement `POST /chat` in `backend/routers/chat.py`: `422` on empty/oversized
      `question`, delegates to `chat.py`, `db=Depends(db_dependency)` per the repo's router
      convention. **Deviates from the original contract**: Ollama unreachable/timeout does NOT
      return `503` — it degrades to `200`/`degraded:true`/`note:"model_unavailable"`, matching
      this codebase's established fail-soft convention (`market.py`: "Always 200 — an empty
      result is a valid state, not an error"). contracts/chat-api.md updated to record this.
- [X] T022 [US1] Register `chat.router` in `backend/main.py`'s router-import block (satisfies
      T015–T017)
- [X] T023 [P] [US1] Add `ChatRequest`/`ChatResponse`/`ChatCriterion` types to
      `frontend/src/api/types.ts` per contracts/chat-api.md
- [X] T024 [P] [US1] Implement `useChat` in `frontend/src/hooks/useChat.ts` as a `useMutation`
      (no polling, per the repo's global `refetchInterval: false` convention) posting to `/chat`
- [X] T025 [US1] Implement `frontend/src/pages/Chat.tsx`: question input, loading state, answer
      display, criteria list **always visible**, match count, raw query behind a toggle
      (FR-013/014), `degraded`/`note` handling — satisfying T018
- [X] T026 [US1] Add `{ to: "/chat", label: "Chat" }` to the `links` array in
      `frontend/src/components/layout/Navbar.tsx`
- [X] T027 [US1] Add the import and `<Route path="/chat" element={<Chat />} />` to
      `frontend/src/App.tsx`

**US1 verified end-to-end against real infrastructure, not just mocks**: populated the real
`screener` collection (557 docs) via `agent-runner`'s `refresh_all()`, confirmed AAPL's computed
signals match research.md R4's reference values exactly, then called `chat.answer_question()`
directly against live MongoDB + live `qwen3:14b`. The flagship question correctly returned 0
matches (verified independently via direct aggregation — real fundamentals data makes the
4-criteria filter genuinely this narrow), and a relaxed price-only version of the question
returned the exact same 13-ticker set as research.md R4 (VRSK, SCSC, ROL, HST, AAPL, IDXX, EBAY,
TPR, TROW, ACGL, MO, VTRS, F) — reproduced identically through a real running `uvicorn` process
over HTTP, not just in-process. The out-of-scope and query-rejected paths were also exercised
live. `npm run build` (tsc + vite) is clean; 274 backend tests and 405 frontend tests pass.

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

- [X] T028 [P] [US2] Contract test in `backend/tests/test_chat_router.py`: `POST /chat` with a
      `history` array containing the flagship Q&A, followed by a question referencing "those,"
      returns an answer scoped to the prior result set rather than re-screening everything.
      Also added a truncation test (long history → only the most recent 6 turns reach the model,
      research.md R9).
- [X] T029 [P] [US2] Frontend test in `frontend/src/pages/Chat.test.tsx`: a second question is
      sent with the accumulated `history`; simulating a remount (fresh component mount) shows an
      empty conversation (FR-004 — no persistence). Both were already written as part of T018's
      test file ("a follow-up question sends the prior exchange as history" and "the
      conversation does not persist across a remount").

### Implementation for User Story 2

- [X] T030 [US2] Extend `POST /chat` in `backend/routers/chat.py` to accept optional `history`
      (default `[]`), truncating server-side to the last ~6 turns before use (research.md R9).
      Implemented as part of T019/T021 (US1) since generation and history-handling were designed
      together from the start — `chat.py`'s `_format_history()` already applies
      `MAX_HISTORY_TURNS = 6`.
- [X] T031 [US2] Extend `backend/semantic/chat.py` to fold `history` into both the
      query-generation and interpretation prompts so references like "those" resolve. Already
      present in `_format_history()` + `answer_question()`'s prompt construction (T019).
- [X] T032 [US2] Add in-memory conversation state (array of turns, component state only — no
      `localStorage`, no server call to persist) to `frontend/src/pages/Chat.tsx`, replayed as
      `history` on every request — satisfying T029. Already present as the `turns` state array
      (T025).

**US2 verified live against real Ollama**: asked the flagship-adjacent question, then a
follow-up ("which of those has the highest market cap?") passing the first answer back as
history. The model correctly resolved "those" to the 13-ticker set from the prior turn and
correctly identified AAPL ($4.54T) as the answer — genuinely correct, not just well-formed.

**Checkpoint**: US1 and US2 both function independently; a follow-up conversation works and
nothing survives a refresh.

---

## Phase 5: User Story 3 - Trustworthy, complete underlying data (Priority: P3)

**Goal**: Signals are provably correct, and the one genuinely orphaned collection is gone.

**Independent Test**: quickstart.md steps 3 and 7 — the screener-driven ~13-ticker set matches a
direct aggregation; `portfolio_digest_cache` is gone; `transcripts_cache` and `fmp_entitlements`
remain; both Python test suites still pass.

### Tests for User Story 3

- [X] T033 [P] [US3] Add a regression test in `agent-runner/tests/test_screener.py` asserting
      `compute_signals()` reproduces the reference AAPL values measured in research.md R4
      (`range_pct_20d ≈ 0.21`, `zscore_20d ≈ −0.42`, `weekly_change_pct ≈ 1.12`,
      `fcf_exceeds_debt == False`) from fixed input fixtures
- [X] T034 [P] [US3] Add a test (`backend/tests/test_db_constants.py`) asserting
      `FUND_HOLDINGS`, `SECTOR_PERFORMANCE`, `STOCK_NEWS`, `MARKET_NEWS` are no longer defined in
      `backend/db.py` or `agent-runner/tools/db.py`, and that `TRANSCRIPTS_CACHE`/
      `FMP_ENTITLEMENTS` are NOT removed by the same pass.

### Implementation for User Story 3

- [X] T035 [P] [US3] Remove the dead constants `FUND_HOLDINGS`, `SECTOR_PERFORMANCE`,
      `STOCK_NEWS`, `MARKET_NEWS` from `backend/db.py`. **Do not touch** the
      `"sector_performance"` / `"fund_holdings"` string literals in
      `agent-runner/tools/fmp_client.py:148,153` — those are unrelated FMP probe-family keys.
      Verified via grep before removal: zero other references in either service.
- [X] T036 [P] [US3] Remove the same four dead constants from `agent-runner/tools/db.py`
- [X] T037 [US3] Add a one-off, explicitly-confirmed script `scripts/drop_portfolio_digest_cache.py`
      that drops `portfolio_digest_cache` (1 doc, zero code references — orphaned when
      `agent-runner/tools/portfolio.py` was deleted, research.md R7). Not run automatically by
      any test or CI step; requires an explicit `--yes` flag. Dry-run verified against the live
      database (correctly reports 1 document, does not drop without `--yes`) — **not executed
      with `--yes`**, per operating principle: dropping a collection is irreversible and is the
      user's call, not mine to make unilaterally.
- [X] T038 [P] [US3] Add `{ticker: 1}` unique index for `institutional_cache` to both
      `backend/db.py` and `agent-runner/tools/db.py`'s `ensure_indexes()` (pre-existing gap,
      research.md R8 — it's queried by ticker but has no index beyond `_id`). Verified no
      duplicate tickers exist in the live collection first (would have broken a unique index),
      then applied to the live database via `ensure_indexes()`.
- [X] T039 [P] [US3] Add a short comment in both `db.py` files next to `TRANSCRIPTS_CACHE` and
      `FMP_ENTITLEMENTS` noting they are intentionally retained despite 0 live documents
      (reserved for `specs/007-earnings-transcripts/`; actively written respectively) — so a
      future cleanup pass doesn't re-flag them

**US3 verified**: full backend (278) and agent-runner (501) suites pass after both removals and
the new index. `db.py` imports cleanly in both services.

**Checkpoint**: Data layer is accurate and pruned; `SC-003` and the US3 acceptance scenarios
hold.

---

## Phase 6: User Story 4 - Platform scales to a much larger dataset (Priority: P4)

**Goal**: Confirm, not assume, that chat and the data layer hold up at ~15x volume.

**Independent Test**: quickstart.md step 8 — seed a 15x-sized `screener`, confirm chat latency
and correctness are unaffected, confirm no per-document size or query-time limits are hit.

### Tests / Implementation for User Story 4

- [X] T040 [P] [US4] Write `scripts/seed_15x_screener.py` generating ~8,340 synthetic `screener`
      documents (realistic field distributions, not all-identical values) for a scale dry-run.
      Seeds a separate `stockai_scale_test` database — never touches production data — and
      supports `--cleanup` to drop it afterward.
- [X] T041 [US4] Run the 15x dry-run per quickstart.md step 8 against the seeded data; confirm
      chat query execution stays in the low milliseconds and the flagship question still returns
      a sensible result set; record the measured numbers in research.md's R5 section. **Real
      measurement corrected the earlier estimate**: 8,340 docs came to 5.12 MB data / 0.77 MB
      indexes (vs. the ~17 MB originally estimated from an assumed 2 KB/doc — actual average is
      ~644 bytes/doc), and a flagship-style 4-predicate `$match` against the full collection
      returned in 3.6ms. research.md R5 updated with the measured numbers.
- [X] T042 [P] [US4] Add a test in `backend/tests/test_query_guard.py` confirming the `$limit` /
      `maxTimeMS` bounds actually constrain execution against a large seeded collection (not
      just against the small dev dataset) — one test proves the injected `$limit` actually caps
      a 2,000-document match to 50 results, another confirms an over-cap pipeline is rejected
      before `.aggregate()` is ever reached.

**US4 verified with real measurements, not assumptions** — the explicit goal of this user story
(spec: "confirm response times and correctness stay within acceptable bounds," not "assume they
will").

**Checkpoint**: All four user stories are independently functional; SC-004 is verified with
real numbers, not assumed.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T043 Run the full quickstart.md success checklist end-to-end, in order. Corrected three
      inaccuracies found while doing so: step 2 assumed a generic `/admin/jobs/screener_refresh`
      HTTP endpoint that doesn't exist (this app enqueues admin jobs into `work_queue` directly,
      no generic trigger route) — replaced with the direct `refresh_all()` invocation actually
      used throughout implementation; step 7 rewritten to reference the real
      `scripts/drop_portfolio_digest_cache.py`; step 8 rewritten to reference the real
      `scripts/seed_15x_screener.py` instead of hypothetical mongosh math against production data.
- [X] T044 [P] `ruff check backend/` and `ruff check agent-runner/ scripts/` — fix any
      violations (constitution's mandatory quality gate). Found and fixed one violation
      (E741 ambiguous variable name `l` in `screener.py`'s `_price_signals`).
- [X] T045 Run `pytest` in `backend/` and `agent-runner/`, and `npm test` in `frontend/` —
      confirm all green, including the pre-existing `transcripts_cache` cleanup test
      (`backend/tests/test_routers.py`) which must still pass after T035–T039. Final counts:
      **280 backend, 501 agent-runner, 405 frontend — all passing.**
- [X] T046 [P] Review `KNOWN_ISSUES.md`'s two entries added during planning (Ollama timeout,
      MongoDB auth posture) and update wording if implementation revealed anything beyond what
      was recorded. Updated both: the Ollama-timeout entry now notes `backend/llm.py` got an
      explicit timeout while `agent-runner/llm.py` remains unfixed (a separate, still-open
      issue); the MongoDB-auth entry now names `backend/semantic/query_guard.py` as the concrete
      case the entry had anticipated, rather than leaving it a forward-looking prediction.

**Feature complete.** All 46 tasks done. Final verification: 280 + 501 + 405 = 986 tests passing
across all three services, `ruff` clean on both Python services, `npm run build` (tsc + vite)
clean, and the core chat flow (including a real follow-up conversation) verified live against
production MongoDB data and the actual `qwen3:14b` model — not just mocks. One deliberately
unexecuted step remains: `scripts/drop_portfolio_digest_cache.py --yes`, held for the user's
explicit go-ahead per the spec's own non-reversibility note.

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
