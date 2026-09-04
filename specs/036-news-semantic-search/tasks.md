---
description: "Task list for 036-news-semantic-search implementation"
---

# Tasks: News Semantic Search with Tag Prefiltering

**Input**: Design documents from `/specs/036-news-semantic-search/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — constitution Principle I (Test-First & Comprehensive Coverage) is a
gating requirement for this feature, and plan.md / quickstart.md name the exact test
files. Every pure function gets an exhaustive suite; integration covers the quickstart
scenario table.

**Organization**: Grouped by user story. Phases are ordered by priority
(US1 P1 → US3 P1 → US2 P2 → US4 P3). Each story is independently testable at its
checkpoint.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 (Setup, Foundational, Polish carry no story label)

## Path Conventions

Web application, three services at repo root. This feature touches `backend/` and
`agent-runner/` only; `frontend/` is untouched (spec FR-016).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, model, and tunable settings in place before any code depends on them.

- [X] T001 [P] Add an explicit `numpy` line to `backend/requirements.txt` (currently only transitive via `pandas`; plan.md "Primary Dependencies")
- [X] T002 [P] Pull the embedding model into the Ollama service and record it in `docker-compose.yml` (or the ollama init step) and `specs/036-news-semantic-search/quickstart.md` §Prerequisites: `ollama pull nomic-embed-text`
- [X] T003 [P] Add ranking tunables to `backend/settings.py`: `ollama_embed_model="nomic-embed-text"`, `news_embed_max_chars=2000`, `news_rank_half_life_days=14`, `news_rank_max_candidates=5000`, `news_rank_fallback_days=30`, `news_tag_match_threshold=0.72`, `news_rank_min_ticker_pool=3`, `news_rank_top_n=10` (data-model.md §6)
- [X] T004 [P] Add enrichment tunables to `agent-runner/settings.py`: `ollama_embed_model="nomic-embed-text"`, `news_embed_max_chars=2000`, `news_enrich_batch_per_run=200` (mirrors backend where shared; data-model.md §6)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-service constants, the `embed()` wrappers, the full enrichment pipeline
(embeddings + tags + `news_tags` registry), the constitution-VI contract split, and the
pure ranking core. Every semantic user story depends on all of this.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Cross-service constants, indexes, and the embed wrapper

- [X] T005 [P] Add `NEWS_TAGS = "news_tags"` constant and its index bootstrap (`_id` natural key only) to `backend/db.py` (contracts/news-collection-v2.md §3)
- [X] T006 [P] Add the mirrored `NEWS_TAGS = "news_tags"` constant and index bootstrap to `agent-runner/tools/db.py`
- [X] T007 [P] Add `embed(texts: str | list[str]) -> list[list[float]]` to `backend/llm.py`: wraps `client.embed`, passes `keep_alive` + timeout, L2-normalizes each vector, raises `LLMError` on failure (plan.md; contracts/chat-news-retrieval.md §4)
- [X] T008 [P] Add the mirrored `embed()` wrapper to `agent-runner/llm.py` (same signature and normalization as T007)

### Enrichment — pure module, wiring, backfill (FR-001, FR-002, FR-002a, FR-002b, FR-003)

- [X] T009 [P] Create `agent-runner/tools/news_enrich.py` with the pure functions: `build_embed_text(article) -> str` (title + `\n\n` + `body_text[:news_embed_max_chars]`, deterministic head truncation, research.md R10); `normalize_tag(str) -> str` and `normalize_tags(list[str]) -> list[str]` (lowercase, strip punctuation, collapse whitespace, ≤4 words, ≤40 chars, drop empties, dedupe — research.md R11); module constants `TAG_SYSTEM_PROMPT` and `TAG_SCHEMA` (`{"tags": {"type": "array", "items": {"type": "string"}}}`)
- [X] T010 Implement `_enrich(article, *, client) -> dict` in `agent-runner/tools/news_enrich.py`: one `llm.embed()` over `build_embed_text`, one `llm.generate_json()` tag call at `temperature=0`, returns the six fields (`embedding`, `embedding_model`, `embedding_dim`, `embedded_at`, `tags`, `tags_generated_at`); on tag-call failure returns a partial (`embedding` set, `tags=[]`, `tags_generated_at` set) per data-model.md §1
- [X] T011 Implement `upsert_tag_registry(db, tags, *, client, now) -> int` in `agent-runner/tools/news_enrich.py`: for each normalized tag `upsert` a `news_tags` row — `$setOnInsert` `embedding` (from `llm.embed(tag)`) + `first_seen`, `$set` `last_seen`, `$inc` `count` by 1; re-embed the row when its `embedding_model` ≠ current (data-model.md §2)
- [X] T012 [P] Unit tests in `agent-runner/tests/test_news_enrich.py`: `normalize_tags` invariants (case, punctuation, whitespace, word/char caps, dedupe); `build_embed_text` truncation is deterministic at the boundary; `upsert_tag_registry` insert vs increment vs stale-model re-embed; `_enrich` partial-failure path (tags `[]`, embedding kept)
- [X] T013 Wire enrichment into `agent-runner/tools/news_pull.py`: before upserting a new or stale-model article call `news_enrich._enrich()` and merge the six fields into the document; call `news_enrich.upsert_tag_registry()` with the produced tags (research.md R7)
- [X] T014 Add the paced backfill loop to `agent-runner/tools/news_pull.py`: a `dataset_meta["news_enrich"]` checkpoint driving up to `settings.news_enrich_batch_per_run` articles per job run where `embedding` missing OR `embedding_model != settings.ollama_embed_model` OR `tags == []`; fail-soft to "enriched N this run" (research.md R7, R8)
- [X] T015 Extend `agent-runner/tests/test_news_pull.py`: enrichment invoked for a newly ingested article; backfill respects `news_enrich_batch_per_run` and advances the `news_enrich` checkpoint; a failing enrich call does not abort the job

### Constitution VI — schema + mirrored contract (FR-015)

- [X] T016 [P] Add exactly one field entry to `NEWS_SCHEMA["fields"]` in `backend/semantic/schema.py`: `{"name": "tags", "type": "array", "aggregation": "groupable", "description": ...}` with the "chat pre-filters on tags automatically, rarely `$match` yourself" wording from data-model.md §3
- [X] T017 [P] Extend `backend/tests/test_news_contract.py`: `NEWS_ARTICLE_FIELDS` gains `"tags"`; add `NEWS_ARTICLE_INTERNAL_FIELDS = {embedding, embedding_model, embedding_dim, embedded_at, tags_generated_at}`; assert `NEWS_SCHEMA` field names == `NEWS_ARTICLE_FIELDS` exactly (internal set provably excluded); add `NEWS_TAG_FIELDS` set (contracts/news-collection-v2.md §1–3)
- [X] T018 [P] Extend `agent-runner/tests/test_news_contract.py` to mirror T017: the document `news_pull.py` upserts produces `NEWS_ARTICLE_FIELDS ∪ NEWS_ARTICLE_INTERNAL_FIELDS`; `upsert_tag_registry()` writes exactly `NEWS_TAG_FIELDS`

### Pure ranking core — shared by US1 / US2 / US3

- [X] T019 [P] Create `backend/semantic/news_rank.py` with the pure functions: `build_embed_text(article)` (hand-copied from T009, constitution V); `cosine_rank(q_vec, matrix) -> np.ndarray` (normalized dot product, guards row length); `recency_decay(published_at, now, half_life_days) -> float` (`0.5 ** (age_days / half_life_days)`); `score_articles(q_vec, rows, now, half_life_days) -> list[(row, score)]` (`cosine * decay`, drops rows whose vector length ≠ 768, sorted desc) — research.md R3, R6
- [X] T020 Add `match_question_tags(candidate_tags, registry_rows, q_tag_vecs, threshold) -> list[str]` (cosine ≥ threshold → union of matched registry tag names, current-model rows only) and `build_candidate_filter(news_search, matched_tags, now, *, ticker_pool_size) -> dict` (the full R4 table: ticker hard-filter ± tag `$in`; tag `$in`; recency-window fallback; thin-ticker sentinel — all cases also require `embedding` present and `embedding_model == current`) to `backend/semantic/news_rank.py` — research.md R4, R5
- [X] T021 [P] Unit tests in `backend/tests/test_news_rank.py`: `recency_decay` at age 0 / one half-life / two half-lives; `cosine_rank` on identical / orthogonal / opposite vectors; `score_articles` drops a wrong-length vector and orders by blended score; `match_question_tags` exact match, near-miss above/below threshold (fixture "interest rates" vs "monetary policy"), no-match → `[]`; `build_candidate_filter` for all four R4 rows including the thin-ticker fallback — fixed vectors, fixed `now`, no Ollama

**Checkpoint**: Ingestion produces embeddings, tags, and a populated `news_tags` registry;
the mirrored contract tests pass; every pure ranking function is covered. No request-path
behavior has changed yet.

---

## Phase 3: User Story 1 - Topic questions return news that is actually about the topic (Priority: P1) 🎯 MVP

**Goal**: A non-ticker topic question is embedded, ranked against a recency-bounded
candidate pool by cosine × recency-decay, and the answer is grounded in the top matches —
including reworded questions that share no keywords with the relevant stories.

**Independent Test**: Run the golden topic-question set (including deliberately reworded
variants) against the seeded corpus; confirm cited articles are on-topic and include the
reworded-case matches the current `$text` path misses; a no-match question yields
"no relevant news found", not a weak citation.

### Tests for User Story 1

- [X] T022 [P] [US1] Add `news_search` object assertions to `backend/tests/test_screener_query.py`: shape (`mode`, `ticker`, `query_text`, `candidate_tags`), field validation rules from contracts/chat-news-retrieval.md §1, and topic-question routing → `mode: "semantic"`, `ticker: null`
- [X] T023 [P] [US1] Create fixture `backend/tests/fixtures/news_semantic_corpus.json`: a handful of articles with known topics, tickers, and dates, pre-embedded (recorded fixture or a live `nomic-embed-text` call in the integration test) — quickstart.md §4
- [X] T024 [US1] Integration tests in `backend/tests/test_chat_news_semantic.py` for quickstart scenarios 1–3: reworded topic ("trade restrictions on chips" vs corpus "semiconductor export controls") cites the right articles where `$text` returns none (SC-002); on-topic article outranks an incidental-keyword article; no-match topic → "no relevant news found"

### Implementation for User Story 1

- [X] T025 [US1] Add the `news_search` object to `QUERY_SCHEMA` in `backend/semantic/screener_query.py` as an optional object (treated as `{"mode": "recency"}` when absent), with the per-field constraints in contracts/chat-news-retrieval.md §1
- [X] T026 [US1] Add topic-mode guidance and worked examples to `build_system_prompt()` in `backend/semantic/screener_query.py`: "news about tariffs" / "anything on rate cuts" → `mode: semantic`, `ticker: null`, populated `query_text` + `candidate_tags` (contracts/chat-news-retrieval.md §2)
- [X] T027 [US1] Implement `rank_articles(db, news_search, *, client, now, limit) -> list[dict]` in `backend/semantic/news_rank.py`: embed `query_text`; call `build_candidate_filter` with `matched_tags=[]` (recency-window fallback branch); read candidates with `sort(published_at desc).limit(news_rank_max_candidates)` and projection `{_id, url, title, published_at, tickers, embedding}`; `score_articles`; return the top `limit` full documents; raise `LLMError` if `embed()` fails
- [X] T028 [US1] Add the semantic branch to the news path in `backend/semantic/chat.py`: when `news_search.mode == "semantic"` call `news_rank.rank_articles()` and feed the results to the existing answer-interpretation + citation step unchanged; `mode == "recency"` runs the generated pipeline exactly as today (research.md R2)

**Checkpoint**: Topic semantic search works end to end against the recency-window pool.
US1 is independently demoable as the MVP.

---

## Phase 4: User Story 3 - "Why did this stock move" questions (Priority: P1)

**Goal**: A ticker-reason question ("why did NVDA drop today", "NVDA news on export bans")
is hard-filtered to that ticker's articles, then ranked by cosine × recency-decay, so the
answer is grounded in the articles that actually discuss the move or the angle.

**Independent Test**: With a corpus that has, for one ticker, both price-move explainers
and unrelated same-ticker articles from the same days, ask "why did <ticker> move" and
confirm the explanatory articles are the ones cited; a plain "latest <ticker> news"
request is unchanged.

### Tests for User Story 3

- [X] T029 [P] [US3] Add ticker-reason routing assertions to `backend/tests/test_screener_query.py`: "why did NVDA drop today" / "NVDA news about export bans" → `mode: "semantic"`, `ticker: "NVDA"`; "latest NVDA news" stays `mode: "recency"`
- [X] T030 [US3] Integration tests in `backend/tests/test_chat_news_semantic.py` for quickstart scenarios 7, 8, 12: 2 NVDA explainers + 5 routine same-day items → answer grounded in the 2 explainers (SC-008); "NVDA news about export restrictions" cites only the export-restriction NVDA articles, recency-blended; a ticker with 0–2 enriched articles falls back to plain recency without crashing

### Implementation for User Story 3

- [X] T031 [US3] Add ticker-reason worked examples to `build_system_prompt()` in `backend/semantic/screener_query.py`: "why did NVDA drop today" / "what's behind the TSLA move" → `mode: semantic` with `ticker` set (contracts/chat-news-retrieval.md §2)
- [X] T032 [US3] Extend `rank_articles()` in `backend/semantic/news_rank.py` to pass `news_search.ticker` and a computed `ticker_pool_size` into `build_candidate_filter` (ticker hard-filter branch); when the enriched pool for that ticker is `< settings.news_rank_min_ticker_pool`, return the plain-recency result for that ticker and skip ranking (spec US4 fallback; contracts/chat-news-retrieval.md §3)
- [X] T033 [US3] Handle the ticker-reason path in `backend/semantic/chat.py`: pass `ticker` through to `rank_articles`; the thin-ticker fallback result flows into the same citation step

**Checkpoint**: Ticker-reason answers are grounded in explanatory articles; thin/empty
ticker pools degrade to recency. US1 and US3 both work independently.

---

## Phase 5: User Story 2 - Tag prefiltering keeps topic search fast and focused (Priority: P2)

**Goal**: When a question maps to one or more in-use tags, the candidate pool is narrowed
to articles carrying those tags before ranking; unmapped questions fall back to the
recency-window pool.

**Independent Test**: With a tagged corpus, ask questions that map cleanly to a single tag
and assert (via the logged candidate filter/count) that only tagged articles were scored,
answer quality matches or beats scoring the whole pool, and end-to-end time stays within
the chat latency target; a two-tag question scores the union; an unmapped question still
answers from the recency pool.

### Tests for User Story 2

- [X] T034 [US2] Integration tests in `backend/tests/test_chat_news_semantic.py` for quickstart scenarios 4–6: ~8% `monetary policy` corpus → only tagged articles scored (assert via logged candidate filter/count); question mapping to two tags → ranked pool is the union; question mapping to no known tag → answered from the recency-window pool (FR-006)

### Implementation for User Story 2

- [X] T035 [US2] Wire tag matching into `rank_articles()` in `backend/semantic/news_rank.py`: `embed()` the `candidate_tags` entries in the same call as `query_text`; load `news_tags` with projection `{_id, embedding, embedding_model}`; `match_question_tags()` → `matched_tags`; pass `matched_tags` into `build_candidate_filter` so the tag `$in` branch (and ticker+tag combination) fires (contracts/chat-news-retrieval.md §3 steps 1–3)
- [X] T036 [US2] Emit a structured log line in `rank_articles()` recording the chosen filter shape and candidate count, so the prefilter can be asserted in tests and inspected per quickstart.md §4 scenario 4

**Checkpoint**: Tag-mapped questions score only the tagged pool; unmapped questions fall
back. All three semantic stories work independently.

---

## Phase 6: User Story 4 - Existing ticker news and other chat answers are unchanged (Priority: P3)

**Goal**: Plain ticker-recency news, screener questions, and the embedding-unavailable
path all behave exactly as before — a guardrail, not new value.

**Independent Test**: Run the existing news and screener chat golden-question suites
unchanged and confirm no regression; stop Ollama and confirm a topic question still
returns HTTP 200 with a degradation note.

### Implementation for User Story 4

- [X] T037 [US4] Add the degradation path to `backend/semantic/chat.py`: catch `LLMError` from `news_rank.rank_articles()`, execute the model's already-generated pipeline instead, and append the note `"(Ranked by keyword match — semantic search was unavailable.)"` — never a 500 (FR-011; contracts/chat-news-retrieval.md §4)

### Tests for User Story 4

- [X] T038 [P] [US4] Regression tests in `backend/tests/test_chat_news_semantic.py` for quickstart scenarios 9 & 11: "latest NVDA news" → `mode == "recency"`, `news_rank` not invoked, most-recent-by-date output unchanged; Ollama stopped mid-request → HTTP 200 + the degradation note (SC-007)
- [X] T039 [P] [US4] Run `backend/tests/test_screener_query.py` and the existing chat golden suites unchanged; assert screener answers and cited data are byte-identical to pre-feature behavior (quickstart scenario 10, SC-004)

**Checkpoint**: No regression in plain ticker recency, screener, or the offline path.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T040 [P] Add a latency test to `backend/tests/test_chat_news_semantic.py` (`-k latency`): with ≥ 25 000 enriched articles (or a synthetic fill) a topic and a ticker-reason question complete within the existing chat target, and the candidate read + NumPy rank is < 200 ms (SC-003, FR-014, quickstart.md §5)
- [ ] T041 [P] (DEFERRED — needs live `nomic-embed-text` + a labelled golden set; `news_rank_min_similarity` added as FR-006a, starting values recorded in data-model.md §6 and KNOWN_ISSUES.md) Calibrate `news_tag_match_threshold` and `news_rank_half_life_days` against the golden set; record the final values and the SC-001 / SC-008 baseline measurements in `specs/036-news-semantic-search/data-model.md` §6 and spec.md Success Criteria
- [X] T042 [P] Run `ruff check backend/ agent-runner/` and the full `pytest -q` in both services (quickstart.md §7 full gate)
- [ ] T043 (DEFERRED — needs the running Docker stack + pulled model; automated equivalents pass: test_chat_news_semantic.py covers all 12 scenario rows, full pytest + ruff green) Execute `specs/036-news-semantic-search/quickstart.md` end to end: paced backfill to zero un-enriched, the mongosh checks, and all 12 scenario-table rows
- [X] T044 [P] Log any bug or limitation found during T043 in `KNOWN_ISSUES.md` per the project convention

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup. **Blocks every user story.**
- **US1 (Phase 3)**: depends on Foundational. MVP.
- **US3 (Phase 4)**: depends on Foundational; extends `news_rank.rank_articles` and
  `screener_query.build_system_prompt` from US1 (T032 builds on T027, T031 on T026) — run
  after US1 for least churn, though the `build_candidate_filter` ticker branch itself
  already exists from T020.
- **US2 (Phase 5)**: depends on Foundational; T035 extends the `rank_articles` from US1.
  The pure `match_question_tags` / tag branch already exist from T020.
- **US4 (Phase 6)**: depends on US1 (T037 wraps the T028 call site); regression tests can
  run once each prior story lands.
- **Polish (Phase 7)**: after all desired stories.

### Story Independence

Each story is independently *testable* at its checkpoint. US2 and US3 layer additional
branches onto `rank_articles` but neither breaks US1's topic path — the recency-window
fallback remains the behavior when no ticker and no tag match.

### Within Each Story

- Tests for the routing/schema change ([P], different file) can be written first.
- `news_rank.py` changes precede the `chat.py` wiring that calls them.
- `screener_query.py` prompt/schema changes precede the integration tests that depend on
  the model emitting the new shape.

### Parallel Opportunities

- **Phase 1**: T001, T002, T003, T004 all parallel.
- **Phase 2**: T005/T006/T007/T008 parallel; T009 parallel with those; T012 parallel with
  T016/T017/T018; T019 parallel with T021 and with the contract tasks; the enrichment
  chain T010→T011→T013→T014 is sequential (same file / dependency), T020 depends on T019.
- **Phase 3**: T022 and T023 parallel; implementation T025→T026 (same file) then
  T027→T028.
- **Phase 4**: T029 parallel with T031; T032 then T033.
- **Phase 6**: T038 and T039 parallel after T037.
- **Phase 7**: T040, T041, T042, T044 parallel; T043 after T042.

---

## Parallel Example: Phase 2 Foundational

```bash
# Cross-service scaffolding together:
Task: "Add NEWS_TAGS const + index to backend/db.py"                 # T005
Task: "Add NEWS_TAGS const + index to agent-runner/tools/db.py"      # T006
Task: "Add embed() wrapper to backend/llm.py"                        # T007
Task: "Add embed() wrapper to agent-runner/llm.py"                   # T008
Task: "Create agent-runner/tools/news_enrich.py pure functions"      # T009

# Then the two independent test-heavy tracks in parallel:
Task: "Unit tests backend/tests/test_news_rank.py"                   # T021
Task: "Contract tests backend + agent-runner test_news_contract.py" # T017, T018
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Phase 1 Setup.
2. Phase 2 Foundational — the whole enrichment pipeline and pure ranking core.
3. Phase 3 US1 — topic semantic search against the recency-window pool.
4. **STOP and VALIDATE**: quickstart scenarios 1–3; confirm reworded-topic recall the
   `$text` path lacks.
5. Demo.

### Incremental Delivery

1. Setup + Foundational → ingestion enriches, registry fills, contracts green.
2. US1 → topic semantic search (MVP).
3. US3 → "why did it move" ticker-reason grounding.
4. US2 → tag prefilter narrows the pool and keeps it fast at scale.
5. US4 → prove plain recency, screener, and the offline path never regressed.
6. Polish → latency at 25k, threshold calibration, full gate, quickstart walkthrough.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- Constitution V: `build_embed_text` is hand-copied into `backend/semantic/news_rank.py`
  and `agent-runner/tools/news_enrich.py` — no shared package; the duplication is covered
  by both services' tests.
- `news_tags` is **not** added to `query_guard.READABLE_COLLECTIONS`; `news_rank.py` reads
  it directly with a fixed projection.
- The five internal enrichment fields must stay out of `NEWS_SCHEMA` — T017/T018 make that
  a tested invariant.
- Commit after each task or logical group; stop at any checkpoint to validate.
