# Tasks: Chat AI & News Platform Upgrade

**Input**: Design documents from `/specs/035-chat-and-news-upgrade/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and REQUIRED — constitution Principle I ("Test-First & Comprehensive Coverage") is non-negotiable for this repo; a task that adds behavior without a corresponding test is incomplete. Principle VI (amended v1.1.0 during planning) additionally requires the mirrored `news_articles` field-vocabulary tests in **both** services before that collection may be admitted to `query_guard.READABLE_COLLECTIONS`.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P1/P2/P2/P2/P3) so each story is independently implementable and testable. Two pre-existing bugs found while planning (research.md R2, R5) are fixed inside the story whose work would otherwise make them live or visible, not as separate cleanup — see Notes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task in this phase)
- **[Story]**: US1 / US2 / US3 / US4 / US5 / US6, mapping to spec.md's six user stories
- All paths are repo-relative

---

## Phase 1: Setup

**Purpose**: Establish a clean baseline before touching shared code.

- [X] T001 Record a passing baseline: run `pytest -q` in `backend/` and `agent-runner/`, and `npm test` in `frontend/` — no code changes in this task. This feature has no dedicated git branch of its own (tracked via `.specify/feature.json` on top of the existing working branch), so there is nothing to check out — just confirm the tree you're about to build on is green. **Baseline**: backend 366 passed, agent-runner 529 passed, frontend 425 passed (54 files).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `news_articles` collection plumbing and the pure ticker/citation-linkification module are both consumed by two or more later stories (data-model.md §1; research.md R5) — building them once, up front, keeps US2/US3/US4 from redefining the same constants or duplicating the same pure function.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `NEWS_ARTICLES = "news_articles"` to `backend/db.py` and, in `ensure_indexes()`, create the five indexes from data-model.md §1: unique `url`, descending `published_at`, multikey `tickers`, ascending `source_type`, and a text index on `(title, body_text)`.
- [X] T003 [P] Mirror T002 in `agent-runner/tools/db.py` — same constant name, same five indexes — per the hand-duplication precedent already used for `SCREENER`/`STRATEGY_SIGNALS` (constitution V/VI).
- [X] T004 [P] Create `backend/tests/test_linkify.py` covering `linkify_tickers(text, known_tickers)`: a recognized ticker becomes `[TICKER](/stock/TICKER)`; a lowercase word that collides with a ticker (`"it"`, `"all"`, `"on"`) is left alone (case-sensitive match, research.md R5); text already inside a markdown link (`[foo](/bar)`) is not rewritten; text inside a fenced or inline code span is not rewritten; a word not in `known_tickers` is never linked even if it looks like a ticker (FR-014). Also cover `linkify_citation(title, url)`: returns `[title](url)` markdown. Write these first — the module doesn't exist yet, so they must fail.
- [X] T005 Create `backend/semantic/linkify.py` implementing `linkify_tickers(text: str, known_tickers: set[str]) -> str` and `linkify_citation(title: str, url: str) -> str` per T004's cases — pure functions, no I/O, no model calls (constitution III). **14/14 tests pass.**

**Checkpoint**: `news_articles` indexes exist in both services' `ensure_indexes()`, and `linkify.py` passes its full test suite. User story implementation can now begin.

---

## Phase 3: User Story 1 - Reliable, Semantic-Grounded Answers (Priority: P1) 🎯 MVP

**Goal**: Every field in `SCREENER_SCHEMA` carries enough metadata (unit, closed value set, whether/how it aggregates) that the model can correctly build a `$group` pipeline, not just `$match`/`$sort`/`$limit` — directly addressing "I don't think it's always doing that" for aggregation-shaped questions.

**Independent Test**: Ask a simple lookup, an aggregation question ("average weekly change by sector"), and an out-of-scope question; confirm each is correctly translated and answered, and the aggregation one actually contains a `$group` stage.

### Tests for User Story 1 ⚠️ Write first, confirm they fail before implementing

- [X] T006 [P] [US1] Extend `backend/tests/test_screener_contract.py`: every field with an `aggregation` key has a `type` consistent with that aggregation kind (`"numeric"` ⇒ `type == "number"`; `"groupable"` ⇒ `type` in `{"string", "boolean"}`), and every field with an `enum` key has all of its listed values as non-empty strings. Keep the two existing assertions (field-name set, type+description present) — this test extends the file, it doesn't replace it.
- [X] T007 [P] [US1] Create `backend/tests/test_screener_query.py`: `build_system_prompt()`'s output contains a `$group` stage in its worked examples and mentions at least one accumulator (`$avg`, `$sum`, or `$count`); `generate_pipeline()` still calls `llm.generate_json()` with `QUERY_SCHEMA` unchanged (regression guard — this file didn't exist before, so this also closes the coverage gap).
- [X] T008 [P] [US1] Extend `backend/tests/test_chat_router.py` with an aggregation end-to-end case: mock the LLM call to return a pipeline containing `{"$group": {"_id": "$sector", "avg_change": {"$avg": "$weekly_change_pct"}}}`, `POST /chat`, and assert `generated_query.pipeline` contains that stage and `rows` reflects grouped (not per-ticker) documents.

### Implementation for User Story 1

- [X] T009 [US1] In `backend/semantic/schema.py::SCREENER_SCHEMA["fields"]`, add optional `unit`/`enum`/`aggregation` keys per data-model.md §3: `unit: "USD"` on `market_cap`/`free_cash_flow`/`total_debt`; `unit: "percent"` on `weekly_change_pct`/`monthly_change_pct`/`range_pct_20d`; `unit: "fraction"` on `revenue_growth_yoy`/`net_income_growth_yoy`/`net_profit_margin`; `enum` on `weekly_trend` (`up`/`down`/`flat`), `margin_trend`/`financials_trend` (`improving`/`flat`/`deteriorating`), and `liked_status` (`liked`/`disliked`/`null`); `aggregation: "numeric"` on every numeric field meaningfully averageable/summable; `aggregation: "groupable"` on `sector`, `industry`, `weekly_trend`, `margin_trend`, `financials_trend`, `is_tracked`, `fcf_exceeds_debt`, `liked_status`. Do not add, remove, or rename any field — only these three optional keys (constitution VI note in data-model.md §3).
- [X] T010 [US1] Extend `build_system_prompt()` in `backend/semantic/screener_query.py`: render each field's `unit`/`enum`/`aggregation` hints (when present) alongside its existing type/description line, and add a second worked example showing a `$group` pipeline (e.g. "average weekly change percent by sector") with explicit guidance: use `$group` with an accumulator when the question asks for an aggregate across stocks rather than a filtered list. **Extra fix found by T008's test**: `chat.py::answer_question()` unconditionally stripped `_id` from every row, which silently discards a `$group` result's group key (`_id` is the aggregation's category, not a Mongo document id, for a grouped pipeline) — now only stripped when the pipeline has no `$group` stage.

**Checkpoint**: User Story 1 is fully functional and independently testable — run `backend/tests/test_screener_contract.py`, `test_screener_query.py`, `test_chat_router.py`, and quickstart.md step 5. **Verified: 387 backend tests pass (was 366+14 baseline), 529 agent-runner tests unaffected.**

---

## Phase 4: User Story 2 - Company & Market News Captured for Search and Browsing (Priority: P1)

**Goal**: All three FMP feeds (general market, FMP editorial articles, stock-specific) are ingested into `news_articles` — deduped by URL, backfilled 30 days at launch, paced within the FMP budget guard — and the News tab shows them interleaved by recency with a type indicator.

**Independent Test**: Trigger a refresh, confirm all three `source_type` values are populated with title/date/publisher/body/link (and tickers where applicable); open the News tab and see them interleaved, not siloed.

### Tests for User Story 2 ⚠️ Write first, confirm they fail before implementing

- [X] T011 [P] [US2] Create `agent-runner/tests/test_news_pull.py` covering the per-feed mapping table in contracts/news-api.md: `news/general-latest` → `source_type: "general"`, `tickers: []`; `news/stock-latest` → `source_type: "stock"`, `tickers: [symbol]`; `fmp-articles` → `source_type: "fmp_article"`, `link`→`url`, `content`→`body_html` with `body_text` tag-stripped, and `"NYSE:EXR"`→`tickers: ["EXR"]`. Also cover: an article missing `title` or `url` is dropped; an unparseable `published_at` is dropped. Then cover backfill pacing (research.md R7): paging continues until an article older than the 30-day cutoff is reached; a `FmpBudgetExceededError` raised mid-page returns normally with whatever was ingested (does not propagate); a second run resumes from the `dataset_meta` checkpoint rather than re-paging from page 1; re-fetching an overlapping page upserts into no-ops (idempotent on `url`).
- [X] T012 [P] [US2] Create `agent-runner/tests/test_news_contract.py` asserting the normalizer's output field set (from T011's fixtures) equals the mirrored `NEWS_ARTICLE_FIELDS` table in contracts/news-collection.md, and that `source_type` only ever takes one of the three closed values.
- [X] T013 [P] [US2] Extend `agent-runner/tests/test_admin_jobs.py`: `admin_jobs.JOB_HANDLERS["market_news_pull"] is news_pull.run_market_news_pull`, `admin_jobs.STALE_MINUTES["market_news_pull"] == 20`, `admin_jobs.JOB_DATASETS["market_news_pull"] == "news_articles"`.
- [X] T014 [P] [US2] Create `backend/tests/test_news_router.py` covering `GET /news`: mixed-source recency ordering, `source_type` filter, `ticker` filter (composing with `source_type`), `limit` capped at 200, always-200 on an empty collection (`{"articles": [], "total": 0, "as_of": null}`); and `POST /news/refresh`: enqueues `market_news_pull`, returns `already_queued` when one is pending/running (mirror `test_market.py`'s `test_most_actives_refresh_dedupes_active_job`).

### Implementation for User Story 2

- [X] T015 [US2] Create `agent-runner/tools/news_pull.py`: per-feed normalizers per the mapping table (contracts/news-api.md), `_strip_html(html: str) -> str` via stdlib `html.parser`, `_parse_ticker_prefix("NYSE:EXR") -> "EXR"`, a paged fetch that reuses the stop-on-short-page/reached-cutoff/budget-exceeded pattern already proven in `agent-runner/tools/news.py::_fetch_window` (adapted for feed-level rather than ticker-level paging), and `run_market_news_pull(db) -> int` that upserts on `url` and checkpoints per-feed progress (oldest `published_at` reached) in `dataset_meta` so an interrupted backfill resumes.
- [X] T016 [US2] Register in `agent-runner/tools/admin_jobs.py`: add `"market_news_pull": news_pull.run_market_news_pull` to `JOB_HANDLERS`, `"market_news_pull": 20` to `STALE_MINUTES`, `"market_news_pull": "news_articles"` to `JOB_DATASETS`.
- [X] T017 [US2] Create `backend/routers/news.py` (`GET /news` with `limit`/`offset`/`source_type`/`ticker`, always returns 200; `POST /news/refresh` mirroring `market.py::refresh_most_actives`'s enqueue-or-dedupe shape exactly) and mount it in `backend/main.py`.
- [X] T018 [P] [US2] Add a `NewsArticle` interface to `frontend/src/api/types.ts` matching contracts/news-api.md's response shape. **Named `NewsFeedArticle`/`NewsFeedResponse` instead** — `NewsArticle` was already taken by the 021 per-ticker sentiment sub-report type; follows the same disambiguation precedent as `MarketNewsArticle` (022).
- [X] T019 [P] [US2] Add `rehype-raw` and `rehype-sanitize` to `frontend/package.json` dependencies (research.md R8 — scoped to the new `NewsBody` component only, never `AnswerText`).
- [X] T020 [US2] Create `frontend/src/hooks/useNews.ts`: `useNews(filters)` query (`queryKey: ["news", filters]`) and `useNewsRefresh()` mutation invalidating `["queue"]`, following `useMostActives.ts`'s existing pattern. Also added `["news"]` to `useQueueStatus()`'s post-drain invalidation list (`useQueue.ts`) so a completed `market_news_pull` refreshes the News tab automatically, matching every other admin job's existing treatment there.
- [X] T021 [US2] Create `frontend/src/components/news/NewsBody.tsx`: renders `body_html` through `rehype-raw` + `rehype-sanitize` when present, else renders `body_text` as plain text — a separate component and plugin set from `AnswerText` (research.md R8; 034 FR-004's no-`rehype-raw` guarantee on `AnswerText` must not regress).
- [X] T022 [US2] Create `frontend/src/components/feed/NewsFeed.tsx`: the mixed, recency-ordered stream with a per-item type badge (FR-006) and ticker chips linking to `/stock/:ticker` — **singular**, fixing the dead-link bug in `MarketNewsPanel.tsx:89` (research.md R5; logged in `KNOWN_ISSUES.md`) — using `NewsBody` for content.
- [X] T023 [US2] Update `frontend/src/pages/News.tsx` to render `NewsFeed` instead of `MarketNewsPanel`.
- [X] T024 [US2] Update `frontend/src/pages/News.test.tsx`: replace the `/market/news`-specific assertions (lines ~64-90 today) with `/news`-based ones — the page requests `/news`, renders items from more than one `source_type` when present, and still shows a graceful message (not an error page) on failure.

**Checkpoint**: User Story 2 is fully functional and independently testable — run the agent-runner and backend test suites above, then quickstart.md steps 1-3. **Verified: agent-runner 550 tests, backend 397 tests (387+10 router), frontend 426 tests, typecheck clean.**

---

## Phase 5: User Story 3 - Chat Answers Draw on Stored News (Priority: P2)

**Goal**: The existing single LLM query-generation call becomes multi-collection aware — the model can choose `news_articles` and get a correctly-scoped pipeline back, `query_guard` admits it safely, and `chat.py` actually executes against the collection it validated (fixing the dormant bug at `chat.py:143` — research.md R2).

**Independent Test**: Ask a ticker-scoped news question and a topical one; confirm the answer cites a real stored headline/date. Ask about a ticker with no stored news; confirm a plain "nothing found," not a fabrication.

**Depends on**: US2 (there is nothing to search until news is ingested — spec's own stated rationale) and Foundational's `linkify.linkify_citation()`.

### Tests for User Story 3 ⚠️ Write first, confirm they fail before implementing

- [X] T025 [P] [US3] Create `backend/tests/test_news_contract.py` (the backend half of the mirrored pair — contracts/news-collection.md) asserting `NEWS_SCHEMA["fields"]` name-set equals `NEWS_ARTICLE_FIELDS`, and every field has both `type` and `description` — mirrors `test_screener_contract.py`'s two assertions, now required by constitution Principle VI (v1.1.0).
- [X] T026 [P] [US3] Extend `backend/tests/test_query_guard.py`: `validate_pipeline(..., collection="news_articles")` is now accepted; a pipeline whose first stage is `{"$match": {"$text": {"$search": "..."}}}` is accepted; a pipeline with `$text` inside a later (non-first) stage is rejected (research.md R3).
- [X] T027 [P] [US3] Extend `backend/tests/test_chat_router.py`: a ticker-scoped news question yields `generated_query.collection == "news_articles"`, non-empty `citations`, and rows that are genuinely news documents (not screener documents — this is the direct regression test for the R2 bug: seed distinguishable data in both `screener` and `news_articles` and assert the response's rows came from the collection the model actually chose); a no-match news question returns an answer stating nothing was found and `citations == []`, never a fabricated headline (FR-009).

### Implementation for User Story 3

- [X] T028 [US3] Add `NEWS_SCHEMA` to `backend/semantic/schema.py` per data-model.md §3, including the tickers-array-vs-`$text` retrieval guidance from research.md R3 in its `description`.
- [X] T029 [US3] In `backend/semantic/query_guard.py`: extend `READABLE_COLLECTIONS` to `{"screener", "news_articles"}`; add validation that `$text` may appear only inside the pipeline's first stage and only within a `$match`.
- [X] T030 [US3] Extend `build_system_prompt()` in `backend/semantic/screener_query.py` to describe both `SCREENER_SCHEMA` and `NEWS_SCHEMA` and instruct the model to set `collection` to whichever one the question is actually about.
- [X] T031 [US3] In `backend/semantic/chat.py::answer_question()`: fix the R2 bug by executing `db[collection].aggregate(pipeline, ...)` using the validated, chosen `collection` instead of the hardcoded `db[SCREENER]`; when `collection == "news_articles"`, build a `citations` list (title, url, published_date, publisher) from the returned rows and adjust the answer-interpretation prompt to instruct citing specific stored stories and stating plainly when nothing relevant was found (FR-008, FR-009). **Extra fix found along the way**: the pre-existing `db[SCREENER].find_one() is None` emptiness gate ran *before* the collection was even known, so an empty `screener` would block a perfectly answerable news question — moved to after `collection` is resolved and made collection-aware (updated `test_empty_screener_degrades_gracefully` accordingly: 2 LLM calls now, not 1). Also made `_format_answer_prompt()`/`_fallback_answer()` collection-aware so their instructions/wording fit news rows (title/url) instead of always assuming screener rows (ticker).
- [X] T032 [US3] In `backend/semantic/chat.py`, apply `linkify.linkify_citation()` to rewrite each citation into the returned `answer` text before the response is returned. Implemented as a deterministic "Sources:" section appended after the model's prose (constitution III — the model isn't trusted to place links correctly, same reasoning as FR-014).

**Checkpoint**: User Story 3 is fully functional and independently testable — run `test_news_contract.py` (backend), `test_query_guard.py`, `test_chat_router.py`, and quickstart.md step 4; re-run US1's tests to confirm no regression in the plain screener flow. **Verified: 408 backend tests pass, 550 agent-runner tests unaffected.**

---

## Phase 6: User Story 4 - Clickable Tickers in Chat Answers (Priority: P2)

**Goal**: Any tracked ticker in a chat answer's prose renders as an in-app link; anything that merely looks like a ticker does not.

**Independent Test**: Ask a question whose answer mentions tickers; confirm each renders as a working link to its stock page and navigates without a full page reload, while a ticker-lookalike non-ticker word stays plain text.

**Depends on**: Foundational's `linkify.linkify_tickers()`. Sequenced after US3 since both touch `chat.py`'s response-assembly code.

### Tests for User Story 4 ⚠️ Write first, confirm they fail before implementing

- [X] T033 [P] [US4] Extend `backend/tests/test_chat_router.py`: a screener-match answer mentioning a tracked ticker contains `[TICKER](/stock/TICKER)` in the raw `answer` string; an answer containing a ticker-lookalike word that isn't in the tracked universe does not get linkified.
- [X] T034 [P] [US4] Extend `frontend/src/components/chat/AnswerText.test.tsx`: a root-relative link (`/stock/AAPL`) renders as in-app navigation (a react-router `Link`, not a plain anchor that would reload the page); an absolute URL still renders as a plain anchor with `target="_blank"` (the existing 034 behavior must be unchanged for external links).
- [X] T035 [P] [US4] Extend `frontend/src/pages/Chat.test.tsx`: a strategy-picks response's candidate ticker renders as a link to `/stock/{ticker}` (currently plain text at `Chat.tsx:106`).

### Implementation for User Story 4

- [X] T036 [US4] In `backend/semantic/chat.py::answer_question()`, apply `linkify.linkify_tickers()` (reading the known-ticker set from `db[SCREENER]`'s distinct tickers) to the final `answer` text on the screener-match and news-search return paths. Do not apply it to the strategy-picks path — those candidates are already structured data, linked directly in the frontend by T038.
- [X] T037 [US4] Update `AnswerText.tsx`'s `a` component: when `href` starts with `/`, render a react-router `Link`; otherwise keep the existing `target="_blank"` external-anchor behavior unchanged.
- [X] T038 [P] [US4] In `frontend/src/pages/Chat.tsx`, wrap each strategy-picks candidate's `{c.ticker}` (around line 106) in a `Link to={`/stock/${c.ticker}`}`. **Required adding a `MemoryRouter` wrapper to `Chat.test.tsx`'s `renderChat()` helper** — it had none, and both this change and `AnswerText`'s `Link` usage need router context to render at all now.

**Checkpoint**: User Story 4 is fully functional and independently testable — run `test_chat_router.py`, `AnswerText.test.tsx`, `Chat.test.tsx`, and quickstart.md step 6. **Verified: 410 backend tests, 429 frontend tests, typecheck clean.**

---

## Phase 7: User Story 5 - Persistent, Manageable Chat History (Priority: P2)

**Goal**: Conversations persist server-side across page reloads, are listed in a sidebar with an AI-summarized title and date, can be reopened or deleted, and a new chat can be started without losing access to prior ones.

**Independent Test**: Have a conversation, reload the page, find it in the sidebar with a title and date, reopen it, delete it, confirm it's gone and stays gone after another reload.

**Depends on**: US4 — the persisted `content` is the already-linkified answer (data-model.md §2), so history storage should land after linkification exists. Also supersedes 031's original stateless-history test in `Chat.test.tsx`.

### Tests for User Story 5 ⚠️ Write first, confirm they fail before implementing

- [X] T039 [P] [US5] Create `backend/tests/test_conversations.py` covering `semantic/conversations.py`: `create()` on a first exchange calls the title-generation LLM and stores its (≤6-word) result; on `llm.LLMError` it falls back to the first question truncated to 6 words rather than failing (research.md R6); `append()` on a later turn pushes both messages and updates `updated_at` without changing `title`; `list_conversations()` orders by `updated_at` descending; `get()` returns `None` for an unknown or malformed id; `delete()` returns `False` for an unknown id and removes the document on success.
- [X] T040 [P] [US5] Extend `backend/tests/test_chat_router.py`: `POST /chat` with no `conversation_id` creates one and returns `conversation_id` + non-null `conversation_title`; with a valid `conversation_id` it appends and returns `conversation_title: null`; with an unknown `conversation_id` it returns 404; when the conversation write itself fails (mock the DB call to raise), the answer is still returned with `conversation_id: null` (persistence must never cost the user their answer).
- [X] T041 [P] [US5] Create `backend/tests/test_chat_history_router.py` covering `GET /chat/conversations` (empty list on no data, most-recent-first ordering, `message_count` present), `GET /chat/conversations/{id}` (full messages on a known id, 404 on unknown/malformed id), and `DELETE /chat/conversations/{id}` (204 on success, 404 on a repeat delete).
- [X] T042 [P] [US5] Create `frontend/src/components/chat/ChatSidebar.test.tsx`: renders each conversation's title and date; clicking one calls the selection callback with its id; a delete control removes it from the rendered list and calls the delete mutation; a "new chat" control calls its callback.
- [X] T043 [P] [US5] Update `frontend/src/pages/Chat.test.tsx`: **remove** the existing `"the conversation does not persist across a remount (no history storage, FR-004)"` test (`Chat.test.tsx:245`) — FR-015 now requires the opposite — and add a case asserting a conversation's messages are still shown after a remount when a `conversation_id` is present, plus a case for selecting a different conversation from the sidebar and one for starting a new chat. **Replaced with**: conversation_id sent/adopted across turns, sidebar-select loads stored messages, and "New chat" clears the pane. Also had to mock `api.get`/`api.delete` (previously only `api.post` was mocked) since `ChatSidebar` now renders inside every test.

### Implementation for User Story 5

- [X] T044 [US5] Add `CHAT_CONVERSATIONS = "chat_conversations"` to `backend/db.py` and a descending `updated_at` index in `ensure_indexes()` (data-model.md §2). Backend-only — agent-runner never touches this collection.
- [X] T045 [US5] Create `backend/semantic/conversations.py`: `create(question, answer, db, *, client=None) -> dict`, `append(conversation_id, question, answer, db) -> None`, `list_conversations(db) -> list[dict]`, `get(conversation_id, db) -> dict | None`, `delete(conversation_id, db) -> bool` — title generation is one `llm.generate_text()` call constrained to ≤6 words, made only in `create()`, with the truncated-question fallback on `LLMError` (research.md R6).
- [X] T046 [US5] In `backend/semantic/chat.py::answer_question()`, accept an optional `conversation_id` parameter; after the (already-linkified) `answer_text` is produced, call `conversations.create()`/`conversations.append()`, catching any persistence error so the answer is still returned with `conversation_id: null`; add `conversation_id`, `conversation_title`, and `citations` to every response shape. **Refined during implementation**: refactored into a wrapper (`answer_question` now calls `_generate_answer` then `_attach_conversation`) so persistence covers the strategy-picks early-return path too, not just the free-form flow — and a **degraded** response (no_data/model_unavailable/out_of_scope/query_rejected) is deliberately *not* persisted (data-model.md's "at least one complete exchange" rule) so a non-answer doesn't cost an extra title-gen LLM call or clutter the sidebar. Updated `test_empty_screener_degrades_gracefully` and `test_ordinary_screener_question_is_unaffected_by_strategy_picks_dispatch`'s call-count assertions accordingly.
- [X] T047 [US5] Add `GET /chat/conversations`, `GET /chat/conversations/{id}`, and `DELETE /chat/conversations/{id}` to `backend/routers/chat.py`, mapping `conversations.get()`/`delete()` returning `None`/`False` to `404`; extend `POST /chat` to accept an optional `conversation_id` from the request body and pass it through to `chat_engine.answer_question()`. An unknown `conversation_id` is validated (404) in the router before calling into `chat_engine`, so a request that's going to fail doesn't spend an LLM call first.
- [X] T048 [P] [US5] Add `Conversation`, `ConversationSummary`, and `ConversationMessage` interfaces, plus the new `conversation_id`/`conversation_title`/`citations` response fields, to `frontend/src/api/types.ts` per contracts/chat-history-api.md.
- [X] T049 [P] [US5] Create `frontend/src/hooks/useConversations.ts`: `useConversations()` list query, `useConversation(id)` detail query, `useDeleteConversation()` mutation invalidating the list query. Also updated `useChat.ts` to send `conversation_id` and invalidate `["conversations"]` on success (sidebar's only refresh signal).
- [X] T050 [US5] Create `frontend/src/components/chat/ChatSidebar.tsx`: conversation list (title + date), a selection handler, a per-row delete control, and a "New chat" action.
- [X] T051 [US5] Rework `frontend/src/pages/Chat.tsx`: hold `conversationId` state; when a conversation is selected in `ChatSidebar`, load and render its stored messages; send `conversation_id` on every `POST /chat`; update local state from the response's `conversation_id`/`conversation_title`; render `ChatSidebar` alongside the existing exchange list. A reopened conversation's messages (role/content/timestamp only, no structured metadata) are rendered via a `stubResponse()` helper so the same JSX handles both live and reloaded exchanges.

**Checkpoint**: User Story 5 is fully functional and independently testable — run `test_conversations.py`, `test_chat_router.py`, `test_chat_history_router.py`, `ChatSidebar.test.tsx`, `Chat.test.tsx`, and quickstart.md step 7. **Verified: 436 backend tests, 437 frontend tests, typecheck clean.**

---

## Phase 8: User Story 6 - Watchlist and Top Traded Stocks Together in the Main Sidebar (Priority: P3)

**Goal**: The main app sidebar shows both Watchlist and Top Traded Stocks, each independently scrollable; Top Traded Stocks is removed from the Stocks page (a move, not a copy — FR-023).

**Independent Test**: Open any page with the main sidebar; confirm both sections are present and populated; confirm scrolling one list doesn't move the other or the page.

**Depends on**: Nothing else in this feature — frontend-only, fully independent of US1-US5.

### Tests for User Story 6 ⚠️ Write first, confirm they fail before implementing

- [X] T052 [P] [US6] Extend `frontend/src/components/layout/Sidebar.test.tsx`: a Top Traded Stocks section renders alongside Watchlist; each section's scroll container is a distinct element (not one shared scrolling region); an empty Top Traded Stocks list shows an empty-state message. Also had to switch the mock from an unconditional `api.get` response to URL-based routing (`/watchlist`, `/market/most-actives`, `/queue`), since the sidebar now calls all three.
- [X] T053 [P] [US6] Extend `frontend/src/pages/Stocks.test.tsx`: the Stocks page no longer renders Top Traded Stocks content (FR-023 — sidebar-exclusive).

### Implementation for User Story 6

- [X] T054 [US6] Create `frontend/src/components/layout/TopTradedList.tsx`: a compact ticker + change-percent list (via `useMostActives()`) sized for the sidebar's `w-56` width, with a small refresh control (via `useMostActivesRefresh()`) so the manual-refresh capability isn't lost in the move.
- [X] T055 [US6] Rework `frontend/src/components/layout/Sidebar.tsx` into a flex column with two `min-h-0 overflow-y-auto` sections — the existing Watchlist and the new `TopTradedList` — so each scrolls independently without scrolling the page (research.md R10; omitting `min-h-0` is the standard failure mode here). **Also required changing `<aside>` from `md:block` to `md:sticky md:top-0 md:flex md:h-screen`** — a flex-column child only has a bounded height to scroll within if the parent itself is height-bound; the old auto-height block-display sidebar had nothing for `overflow-y-auto` to clip against. Updated the one existing test that asserted `md:block` accordingly.
- [X] T056 [US6] Remove `MostActivesPanel` from `frontend/src/pages/Stocks.tsx`.
- [X] T057 [P] [US6] Delete `frontend/src/components/feed/MostActivesPanel.tsx` and `MostActivesPanel.test.tsx` — fully superseded by `TopTradedList`, no remaining call site (repo convention: delete unused code rather than leave it dead).

**Checkpoint**: All six user stories are independently functional — run `Sidebar.test.tsx`, `Stocks.test.tsx`, and quickstart.md step 8. **Verified: 433 frontend tests, typecheck clean.**

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide gates and final validation across all six stories.

- [X] T058 [P] Run `ruff check backend/` and `ruff check agent-runner/ scripts/` (constitution Development Workflow gate) and fix any findings introduced by this feature. One finding (unused local in `test_conversations.py`), fixed.
- [X] T059 [P] Run `npm run typecheck` and the full `npm test` suite in `frontend/`; fix any type errors or test failures across all touched components. Clean.
- [X] T060 Run all nine scenarios in `specs/035-chat-and-news-upgrade/quickstart.md` against a running Docker Compose stack and confirm every response/UI shape matches its documented expectation. **Rebuilt and ran the real stack** (backend/agent-runner/frontend images rebuilt from the new code; real MongoDB, real Ollama `qwen3:14b`, real FMP API): ingested 5,150 real articles across all three feeds with zero duplicate URLs and correct exchange-prefix ticker parsing; a real chat question about NVDA news correctly routed to `news_articles` (not `screener`), returned 10 real citations, and rendered `[NVDA](/stock/NVDA)`-linkified prose with an LLM-generated conversation title; a real aggregation question ("average weekly change by sector") produced an actual `$group` pipeline with the `_id` group key intact and a real per-sector narrative; the chat-history CRUD lifecycle (create → list → get → delete → 404 on re-delete) verified end-to-end against the live API. Total live FMP spend: 60 calls.
- [X] T061 [P] If quickstart validation (T060) surfaces any limitation or bug not already covered by a spec requirement, log it in `KNOWN_ISSUES.md` per this project's standing convention. **Found and fixed one real bug live**, not caught by any mocked unit test: `_pull_feed()`'s steady-state (single-page) check reused backfill mode's `for/else` logic, so a completed backfill silently reverted to "incomplete" whenever the steady-state page happened to come back full — which general/FMP-article "latest" feeds do on essentially every check, since they always have ≥100 recent items. Confirmed live (checkpoints oscillating `true`→`false`→`true`...), fixed by only letting the no-stopping-signal path revoke completeness in genuine backfill mode, covered by two new regression tests, verified fixed against the live stack. Logged in `KNOWN_ISSUES.md`'s Fixed section.
- [X] T062 [P] Move the two bugs logged in `KNOWN_ISSUES.md` during planning — the `MarketNewsPanel` dead ticker link (fixed by T022) and `chat.py`'s hardcoded-`SCREENER` execution bug (fixed by T031) — from the Open section to the Fixed section, now that both are resolved.
- [X] T063 [P] Update `specs/017-fmp-migration-admin/contracts/admin-jobs-api.md`'s job registry table to mark `market_news_pull` as implemented, closing the gap that table has recorded since 017. Documented the divergence from the original reservation (one feed → three, `market_news` → `news_articles`, `stale_minutes` 10 → 20, forward-only → 30-day backfill). Noted in passing: `GET /admin/jobs`/`ADMIN_JOBS` described later in that same contract was never actually built — pre-existing spec/implementation drift, out of scope here.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories. `news_articles` indexes (T002/T003) are needed by US2 (write) and US3 (read); `linkify.py` (T004/T005) is needed by US3 (citations) and US4 (tickers).
- **User Story 1 (Phase 3)**: Depends on Foundational only. Touches `schema.py`/`screener_query.py` exclusively — no dependency on or conflict with any other story.
- **User Story 2 (Phase 4)**: Depends on Foundational only (needs T002/T003's collection/indexes). Independent of US1.
- **User Story 3 (Phase 5)**: Depends on Foundational (`linkify.linkify_citation`, T005) **and** US2 (there is no news to search until it's ingested — spec's own stated rationale). Also the phase that fixes the R2 `chat.py` bug, since it's the one that makes the bug reachable.
- **User Story 4 (Phase 6)**: Depends on Foundational (`linkify.linkify_tickers`, T005). Sequenced after US3 since both edit `chat.py`'s response-assembly code — no logical conflict, just avoids rework.
- **User Story 5 (Phase 7)**: Depends on US4 — the message content persisted is the already-linkified answer (data-model.md §2). Also edits `chat.py` again, after US3/US4.
- **User Story 6 (Phase 8)**: Depends on Foundational only. Frontend-only, fully independent of US1-US5 — could be built in parallel with any of them by a second developer.
- **Polish (Phase 9)**: Depends on all six user stories being complete.

### Within Each User Story

- Tests are written and confirmed failing before implementation tasks in the same phase.
- Collection/schema changes before the modules that query them.
- New modules (`news_pull.py`, `conversations.py`, `linkify.py`) before the orchestration code that calls them.
- Backend response-shape changes before the frontend types/hooks that consume them.
- Frontend hooks before the components that use them; components before the pages that assemble them.

### Parallel Opportunities

- Phase 2 (Foundational): T002, T003, T004 touch three different files — parallelizable; T005 follows T004.
- Phase 3 (US1) tests: T006-T008 touch three different files — parallelizable.
- Phase 4 (US2) tests: T011-T014 touch four different files — parallelizable. Implementation: T018/T019 are independent of the backend tasks and of each other.
- Phase 5 (US3) tests: T025-T027 touch three different files — parallelizable.
- Phase 6 (US4) tests: T033-T035 touch three different files — parallelizable. T038 is independent of T036/T037 (different file).
- Phase 7 (US5) tests: T039-T043 touch five different files — parallelizable. Implementation: T048/T049 are independent of the backend tasks and of each other.
- Phase 8 (US6) tests: T052-T053 touch two different files — parallelizable. T057 is independent of T054-T056.
- Phase 9: T058, T059, T061, T062, T063 are independent of each other and of T060 (though T061 depends on T060 having run).
- **Cross-story**: US6 (Phase 8) has no dependency on US1-US5 and can be worked in parallel with any of them by a second developer, once Foundational is done.

---

## Parallel Example: User Story 2

```bash
# Tests (four different files, launch together):
Task: "Per-feed normalizer + backfill-pacing tests in agent-runner/tests/test_news_pull.py"
Task: "Mirrored field-vocabulary test in agent-runner/tests/test_news_contract.py"
Task: "market_news_pull registration assertions in agent-runner/tests/test_admin_jobs.py"
Task: "GET /news and POST /news/refresh tests in backend/tests/test_news_router.py"

# Two independent frontend implementation tasks (launch together):
Task: "NewsArticle type in frontend/src/api/types.ts"
Task: "rehype-raw + rehype-sanitize in frontend/package.json"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1) — this alone fixes the reported aggregation-query reliability problem, with no new collections or frontend changes.
3. **STOP and VALIDATE**: run T006-T008's tests plus quickstart.md step 5.
4. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational → `news_articles` indexes and `linkify.py` ready.
2. Add User Story 1 → test independently → deploy/demo (MVP — aggregation questions work).
3. Add User Story 2 → test independently → deploy/demo (news is ingested and browsable, three source types mixed on the News tab).
4. Add User Story 3 → test independently → deploy/demo (chat can search that news; the dormant `chat.py` collection bug is fixed here).
5. Add User Story 4 → test independently → deploy/demo (tickers and citations are clickable).
6. Add User Story 5 → test independently → deploy/demo (conversations persist, sidebar with delete).
7. Add User Story 6 → test independently → deploy/demo (sidebar consolidation — could also land any time after Foundational, in parallel with 3-6).
8. Polish → lint, typecheck, full quickstart pass, known-issues log.

### Parallel Team Strategy

With multiple developers, after Foundational:

- Developer A: US1 → US3 → US4 → US5 (the chat/semantic-layer thread — each depends on the last)
- Developer B: US2 (news ingestion) in parallel with Developer A's US1, then hands off data for Developer A's US3
- Developer C: US6 (sidebar) — fully independent, can start immediately after Foundational and finish any time

---

## Notes

- [P] tasks touch different files with no dependency on an incomplete task in the same phase.
- Constitution Principle I is non-negotiable here — every implementation task above has a corresponding test task earlier in its phase.
- Constitution Principle VI was amended (v1.0.1 → v1.1.0) during `/speckit-plan` for this feature: any collection admitted to `query_guard.READABLE_COLLECTIONS` now requires the mirrored field-vocabulary test pair in both services. T012 (agent-runner) and T025 (backend) together satisfy that requirement for `news_articles` before T029 admits it.
- Two pre-existing bugs, found while reading the code during planning and logged in `KNOWN_ISSUES.md`, are fixed as part of the story that would otherwise make them live: the `MarketNewsPanel.tsx` singular/plural route mismatch (T022, US2) and `chat.py`'s hardcoded-`SCREENER` execution despite validating a chosen `collection` (T031, US3). T062 moves both to the Fixed section once done.
- T043 deliberately **removes** a pre-existing test (`Chat.test.tsx:245`) rather than extending it — FR-015 inverts 031's original stateless-history guarantee (FR-004), so the old test asserting non-persistence is now asserting the wrong behavior, not a regression to preserve.
- Commit after each task or logical group; verify tests fail before implementing, per repo convention.
