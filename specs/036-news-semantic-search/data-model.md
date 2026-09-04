# Phase 1 Data Model: News Semantic Search with Tag Prefiltering

**Feature**: `036-news-semantic-search` | **Date**: 2026-08-30

Referenced from [plan.md](plan.md). Contracts:
[news-collection-v2.md](contracts/news-collection-v2.md),
[chat-news-retrieval.md](contracts/chat-news-retrieval.md).

---

## 1. `news_articles` — six additive fields

Existing shape is unchanged (035 data-model.md §3). New fields, all written by
`agent-runner/tools/news_pull.py` via `news_enrich._enrich()`:

| Field | Type | Written when | Notes |
|---|---|---|---|
| `embedding` | array<double>, length 768 | enrichment | Unit vector from `ollama_embed_model` over `build_embed_text()`. Absent until enriched. **Internal** — not in `NEWS_SCHEMA`. |
| `embedding_model` | string | enrichment | e.g. `"nomic-embed-text"`. Equals `settings.ollama_embed_model` at write time. Drives the stale-vector filter (research.md R8). **Internal**. |
| `embedding_dim` | int | enrichment | `768`. Redundant with `len(embedding)`; stored for a cheap `$match` without `$expr`. **Internal**. |
| `embedded_at` | date (UTC) | enrichment | When the vector was produced. **Internal**. |
| `tags` | array<string> | enrichment | 3–6 normalized free-form topic labels (research.md R11). Possibly `[]` if the tag call failed but the embed succeeded. **In `NEWS_SCHEMA`**, `aggregation: "groupable"`. |
| `tags_generated_at` | date (UTC) | enrichment | When tags were produced. **Internal**. |

**Enrichment state** is derived, not stored: an article is "enriched for the current
method" iff `embedding` exists AND `embedding_model == settings.ollama_embed_model`.
`news_pull.py` and the backfill checkpoint both use that predicate.

**Validation rules**:
- `embedding` present ⇒ `len(embedding) == embedding_dim == 768` and the vector is
  L2-normalized (‖v‖ ≈ 1.0 ± 1e-3).
- `tags` entries satisfy `normalize_tags()` invariants: lowercase, no leading/trailing
  punctuation or whitespace, single spaces internally, 1–4 words, ≤ 40 chars, unique
  within the array.
- A partial enrichment (embed ok, tag call failed) is allowed: `embedding` set,
  `tags = []`, `tags_generated_at` set. The next backfill pass retries tags only when
  `tags == [] AND embedding exists` is *not* itself the retry trigger — retry trigger is
  `tags_generated_at` older than `embedded_at` is **not** used; instead a partial is
  re-attempted while `tags == []`. (Kept simple: `tags == []` ⇒ eligible for a tag
  retry, capped by `ENRICH_BATCH_PER_RUN`.)

**Indexes**: none added. Brute-force ranking reads a projected, capped candidate set;
the existing `published_at` and `tickers` indexes already serve the candidate filter's
`$match` + `sort`. A `tags` multikey index is **not** added now — the tag-filtered pool
is small and bounded by the same cap; add one only if profiling shows the candidate read
is slow (noted in quickstart).

---

## 2. `news_tags` — the in-use tag registry (NEW collection)

One document per distinct normalized tag. Written by
`agent-runner/tools/news_enrich.upsert_tag_registry()` during enrichment; read by
`backend/semantic/news_rank.match_question_tags()`.

| Field | Type | Notes |
|---|---|---|
| `_id` | string | The normalized tag itself (natural key). |
| `tag` | string | Same value as `_id`, kept as a named field for clarity in queries/exports. |
| `embedding` | array<double>, length 768 | Vector of the tag string under `ollama_embed_model`. |
| `embedding_model` | string | For the same stale-vector self-heal as articles. |
| `count` | int | Number of `news_articles` currently carrying this tag. Incremented on first attach per article; not strictly transactional (single-user, eventual is fine). |
| `first_seen` | date (UTC) | First time the tag was produced. |
| `last_seen` | date (UTC) | Most recent article that produced it. |

**Lifecycle**:
- On enrichment, for each normalized tag on the article: `upsert` the registry row
  (`$setOnInsert` embedding + `first_seen`; `$set` `last_seen`; `$inc` `count` by 1).
- If `embedding_model` on the row ≠ current, re-embed the tag string and overwrite
  (handled by the same backfill pass that re-enriches articles).
- No deletion in this feature. A future cleanup may drop `count == 0` or long-tail rows;
  `count` exists to make that safe.

**Not admitted to `query_guard.READABLE_COLLECTIONS`** — the chat never generates a
pipeline against it; `news_rank.py` reads it directly with a fixed projection.

**Indexes**: `_id` is the natural key (implicit unique). No secondary index —
`match_question_tags()` loads all rows' `{_id, embedding}` (low thousands) once per
semantic question and matches in NumPy, same brute-force rationale as R3. Revisit if the
registry ever exceeds ~50 k rows.

---

## 3. `NEWS_SCHEMA` change (semantic layer)

Add exactly one field entry to `NEWS_SCHEMA["fields"]` in `backend/semantic/schema.py`:

```python
{"name": "tags", "type": "array", "aggregation": "groupable",
 "description": (
     "Free-form topic labels assigned to this story at ingestion (e.g. "
     "\"monetary policy\", \"semiconductors\", \"oil prices\"). The chat engine "
     "matches a topic question to these automatically and pre-filters on them "
     "before ranking — you normally do NOT need to $match on tags yourself. "
     "Use them only for an explicit \"stories tagged X\" style request."
 )},
```

No other schema change. The five internal enrichment fields are **deliberately absent** —
see [contracts/news-collection-v2.md](contracts/news-collection-v2.md) and research.md R9.

---

## 4. `news_search` object (chat query-generation output)

Emitted by `generate_pipeline()` only when `collection == "news_articles"`. Full shape
and semantics in [contracts/chat-news-retrieval.md](contracts/chat-news-retrieval.md).

| Field | Type | Meaning |
|---|---|---|
| `mode` | `"recency"` \| `"semantic"` | `recency` → run the generated pipeline as today. `semantic` → `news_rank.py`. |
| `ticker` | string \| null | Set when the question names one specific ticker. With `mode: semantic` this is a **hard** pre-filter (spec FR-004 ticker-reason). |
| `query_text` | string | The cleaned natural-language intent to embed (e.g. "why nvidia stock fell today"). |
| `candidate_tags` | array<string> | 0–4 topic guesses to match against `news_tags` (research.md R5). |

Routing (FR-010a), decided by the model in the one call:

| Question shape | `mode` | `ticker` | Path |
|---|---|---|---|
| "latest NVDA news", "any news on TSLA" | `recency` | NVDA/TSLA | existing pipeline (`$match tickers`, sort by date) |
| "why did NVDA drop today", "NVDA news on export bans" | `semantic` | NVDA | ticker-hard-filter → cosine+decay rank |
| "news about tariffs", "what's happening with rate cuts" | `semantic` | null | tag prefilter (or recency fallback) → cosine+decay rank |
| screener questions | n/a (`collection == "screener"`) | — | unchanged |

---

## 5. Ranking model (`backend/semantic/news_rank.py`, all pure except `rank_articles`)

| Function | Signature | Pure? | Responsibility |
|---|---|---|---|
| `build_embed_text` | `(article: dict) -> str` | ✅ | title + `\n\n` + `body_text[:NEWS_EMBED_MAX_CHARS]` (shared with agent-runner via copy, constitution V) |
| `normalize_tag` / `normalize_tags` | `(str) -> str` / `(list[str]) -> list[str]` | ✅ | R11 normalization invariants |
| `match_question_tags` | `(candidate_tags, registry_rows, q_vecs, threshold) -> list[str]` | ✅ | cosine ≥ threshold → union of matched registry tag names |
| `build_candidate_filter` | `(news_search, matched_tags, now, *, ticker_pool_size) -> dict` | ✅ | the R4 table → a Mongo filter dict |
| `cosine_rank` | `(q_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray` | ✅ | normalized dot product; assumes rows already unit vectors, guards length |
| `recency_decay` | `(published_at, now, half_life_days) -> float` | ✅ | `0.5 ** (age_days / half_life_days)` |
| `score_articles` | `(q_vec, rows, now, half_life_days) -> list[(row, score)]` | ✅ | `cosine * decay`, sorted desc, drops dim-mismatch rows |
| `rank_articles` | `(db, news_search, *, client, now, limit) -> list[dict]` | ❌ (IO) | embed `query_text` + `candidate_tags`; load registry; match tags; build filter; read capped projected candidates; `score_articles`; return top `limit` full docs |

`rank_articles` raises `llm.LLMError` if the question/tag embedding call fails — `chat.py`
catches it and falls back (R8).

---

## 6. Settings (both services' `settings.py` unless noted)

| Setting | Default | Where | Purpose |
|---|---|---|---|
| `ollama_embed_model` | `"nomic-embed-text"` | both | embedding model name (FR-013 swap point) |
| `news_embed_max_chars` | `2000` | agent-runner (+ backend for `build_embed_text`) | R10 truncation |
| `news_enrich_batch_per_run` | `200` | agent-runner | R7 backfill pacing |
| `news_rank_half_life_days` | `14` | backend | R6 recency decay (FR-004a) |
| `news_rank_max_candidates` | `5000` | backend | R3/R4 brute-force pool cap |
| `news_rank_fallback_days` | `30` | backend | R4 no-tag-match recency window |
| `news_tag_match_threshold` | `0.72` | backend | R5 question→tag cosine cutoff |
| `news_rank_min_ticker_pool` | `3` | backend | R4 ticker-reason → recency fallback threshold |
| `news_rank_top_n` | `10` | backend | grounding cap (spec FR-008) |
| `news_rank_min_similarity` | `0.25` | backend | min raw cosine (pre-decay) for an article to ground an answer — implements spec US1 AS3 ("no relevant news found" instead of a weak citation); `0` disables. Added during implementation (constitution II); calibrate in T041. |

---

## 7. Cross-service constants (hand-duplicated, constitution V)

| Constant | Value | Files |
|---|---|---|
| `NEWS_TAGS` | `"news_tags"` | `backend/db.py`, `agent-runner/tools/db.py` |
| `NEWS_ARTICLE_FIELDS` | existing 13 + `"tags"` | both `test_news_contract.py` |
| `NEWS_ARTICLE_INTERNAL_FIELDS` | `{embedding, embedding_model, embedding_dim, embedded_at, tags_generated_at}` | both `test_news_contract.py` |
| `NEWS_TAG_FIELDS` | `{_id, tag, embedding, embedding_model, count, first_seen, last_seen}` | both `test_news_contract.py` (new assertion) |
