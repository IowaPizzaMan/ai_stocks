# Contract: Chat News Retrieval — `news_search` object + mode routing

**Feature**: `036-news-semantic-search`. Extends
[specs/031-semantic-layer-chat/contracts/chat-api.md](../../031-semantic-layer-chat/contracts/chat-api.md)
and 035's multi-collection query generation. No HTTP surface change — `POST /chat`
request/response shapes are unchanged. This contract governs the **internal** output of
`semantic/screener_query.generate_pipeline()` and the branch in `semantic/chat.py`.

## 1. `generate_pipeline()` output — additive field

Unchanged when `collection == "screener"`. When `collection == "news_articles"`, the
JSON the model returns MUST additionally contain:

```json
{
  "collection": "news_articles",
  "pipeline": [ ... ],
  "in_scope": true,
  "news_search": {
    "mode": "recency" | "semantic",
    "ticker": "NVDA" | null,
    "query_text": "why nvidia stock fell today",
    "candidate_tags": ["chip export restrictions", "us china trade"]
  }
}
```

`QUERY_SCHEMA` gains `news_search` as an optional object (required in practice for
`news_articles`; a missing/`null` `news_search` is treated as
`{"mode": "recency"}` for backward safety). Field rules:

| Field | Constraint | On violation |
|---|---|---|
| `mode` | one of `"recency"`, `"semantic"` | unknown/missing → treated as `"recency"` |
| `ticker` | uppercase symbol in the known-ticker universe, or `null` | unknown symbol → treated as `null` (topic path) |
| `query_text` | non-empty string ≤ 400 chars | empty → fall back to the raw user question text |
| `candidate_tags` | array of 0–4 strings, each ≤ 60 chars | over-long entries trimmed; > 4 → first 4 kept |

The `pipeline` is still generated and still returned on the response's
`generated_query` (031 FR-013 transparency). It is **executed only when
`mode == "recency"`** or as the degradation fallback (§4).

## 2. Mode routing (spec FR-010a)

| Model sees a question like | `mode` | `ticker` | Effect |
|---|---|---|---|
| "latest NVDA news", "recent TSLA headlines" | `recency` | `NVDA` | run generated pipeline (`$match {tickers}`, `$sort published_at desc`, `$limit`) — **unchanged from today** |
| "why did NVDA drop today", "what's behind the TSLA move", "NVDA news about export bans" | `semantic` | `NVDA` | `news_rank`: hard pre-filter `{tickers: "NVDA"}`, then cosine × recency-decay rank |
| "news about tariffs", "anything on rate cuts", "consumer spending slowdown" | `semantic` | `null` | `news_rank`: tag pre-filter if `candidate_tags` match `news_tags`, else recency-window fallback; then rank |

The system prompt in `screener_query.build_system_prompt()` gains worked examples for
each row (mirroring how 035 added `$group` few-shots).

## 3. `news_rank.rank_articles()` behavior

Input: the `news_search` object, `db`, an llm `client`, `now`, `limit`
(`settings.news_rank_top_n`).

1. Embed `query_text` → `q_vec`; embed each `candidate_tags` entry → `q_tag_vecs`.
   (One `llm.embed()` call with a list input.)
2. Load `news_tags` `{_id, embedding, embedding_model}`; `match_question_tags()` →
   `matched_tags` (cosine ≥ `news_tag_match_threshold`, current-model rows only).
3. `build_candidate_filter(news_search, matched_tags, now, ticker_pool_size=…)`:
   - `ticker` set → `{"tickers": ticker, "embedding": {"$exists": true},
     "embedding_model": <current>}`; if that ticker has `< news_rank_min_ticker_pool`
     enriched articles, return the **recency** result for that ticker instead (spec
     US4 fallback) and skip ranking.
   - else `matched_tags` non-empty → `{"tags": {"$in": matched_tags}, "embedding": …}`
   - else → `{"published_at": {"$gte": now - news_rank_fallback_days},
     "embedding": …}` (spec FR-006)
4. Read candidates: the filter, `sort(published_at desc)`,
   `limit(news_rank_max_candidates)`, projection
   `{_id, url, title, published_at, tickers, embedding}`.
5. `score_articles(q_vec, rows, now, news_rank_half_life_days)` — drops any row whose
   vector length ≠ 768; `score = cosine × 0.5 ** (age_days / half_life)`; sort desc.
6. Return the top `limit` **full** documents (re-read or carried) for the existing
   answer-interpretation + citation step in `chat.py`.

Deterministic pieces (`match_question_tags`, `build_candidate_filter`, `cosine_rank`,
`recency_decay`, `score_articles`) are unit-tested with fixed vectors and a fixed
`now` — no Ollama, no wall clock.

## 4. Degradation (spec FR-011 / FR-012 / FR-013)

| Condition | Behavior |
|---|---|
| `llm.embed()` raises `LLMError` (Ollama down/timeout) | `chat.py` catches it, executes the model's generated `$text`/`$match` pipeline instead, appends note: *"(Ranked by keyword match — semantic search was unavailable.)"*. HTTP 200. |
| Candidate article missing `embedding` or wrong `embedding_model` | excluded by the filter; still reachable via `recency` mode and `routers/news.py`. |
| Loaded vector length ≠ question vector length | dropped in `score_articles` before the matmul (belt-and-braces over the filter). |
| `mode == "semantic"` but **zero** candidates after filtering | same "no relevant news found" answer as today (031 empty-result path); not an error. |
| `news_search` absent from model output | treated as `{"mode": "recency"}`. |

## 5. Latency budget (spec FR-014 / SC-003)

No new LLM call on the routing decision (rides the existing `generate_pipeline()`
call). The semantic path adds: one `embed()` call for `query_text` + tags (~50–300 ms
resident), one small `news_tags` read + NumPy match (low ms), one projected capped
candidate read (~50–120 ms at 5 000 docs), one NumPy matmul + sort (few ms). Total
added ≈ 0.1–0.5 s, inside the 031 SC-001 ~10 s end-to-end target with margin.
