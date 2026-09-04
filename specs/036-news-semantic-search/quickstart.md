# Quickstart: News Semantic Search with Tag Prefiltering

**Feature**: `036-news-semantic-search`. Validation guide — proves the feature works
end to end. Design detail lives in [plan.md](plan.md), [data-model.md](data-model.md),
and [contracts/](contracts/).

## Prerequisites

- The Docker Compose stack up (`docker compose up -d`), or backend + agent-runner +
  mongo + ollama reachable locally.
- The embedding model pulled into Ollama:
  ```bash
  docker compose exec ollama ollama pull nomic-embed-text
  ```
- `qwen3:14b` already present (unchanged from 031/035).
- Some `news_articles` already ingested (035's `market_news_pull` has run at least
  once).

## 1. One-time setup

1. `pip install -r backend/requirements.txt` (picks up the explicit `numpy` line).
2. Confirm settings resolve (`.env` overrides optional — all have defaults):
   `ollama_embed_model=nomic-embed-text`, `news_rank_half_life_days=14`,
   `news_rank_max_candidates=5000`, `news_tag_match_threshold=0.72`,
   `news_rank_min_similarity=0.25`, `news_enrich_batch_per_run=200`.
3. Mongo index bootstrap runs on backend + agent-runner start; confirm `news_tags`
   exists after first enrichment run.

## 2. Enrich the archive (paced backfill)

Enqueue `market_news_pull` repeatedly (its normal trigger) — each run enriches up to
`news_enrich_batch_per_run` un-enriched articles in addition to pulling new ones.

```bash
# enqueue via the admin path used for other jobs, then watch the worker log
docker compose logs -f agent-runner | grep -i "enrich\|news_pull"
```

**Expected**: per run, "enriched N articles (M tags upserted)"; `dataset_meta`
`news_enrich` checkpoint advances; after ~⌈archive / 200⌉ runs every article has
`embedding` + `embedding_model == "nomic-embed-text"`.

**Check**:
```js
// mongosh
db.news_articles.countDocuments({ embedding: { $exists: false } })      // → trends to 0
db.news_articles.countDocuments({ embedding_model: "nomic-embed-text" }) // → trends to total
db.news_tags.find().sort({ count: -1 }).limit(20)                        // broad topics, not headlines
```

## 3. Unit-level validation (no LLM, no clock)

```bash
cd backend && pytest tests/test_news_rank.py -q
cd ../agent-runner && pytest tests/test_news_enrich.py -q
```

Covers: `normalize_tags` invariants; `recency_decay` at 0 / half-life / 2× half-life;
`cosine_rank` on orthogonal / identical / opposite vectors; `match_question_tags`
exact + near-miss (fixture: "interest rates" vs "monetary policy" vectors above/below
threshold) + no-match; `build_candidate_filter` for all four R4 rows including the
thin-ticker fallback; `score_articles` drops a wrong-length vector.

## 4. End-to-end scenarios

Run against a seeded corpus (`tests/fixtures/news_semantic_corpus.json` — a handful of
articles with known topics, tickers, and dates, pre-embedded via a recorded fixture or
a live `nomic-embed-text` call in the integration test).

| # | Ask | Expect | Spec |
|---|---|---|---|
| 1 | "any recent news about trade restrictions on chips" (corpus uses "semiconductor export controls", no "tariff"/"chip") | answer cites the export-controls articles; keyword `$text` for the same words returns them **not** at all | US1 AS1, SC-002 |
| 2 | topic question where corpus has one on-topic + one incidental-keyword article | on-topic article ranked first / cited; incidental one not cited | US1 AS2 |
| 3 | topic question with no matching corpus content | "no relevant news found" — no weak citation | US1 AS3 |
| 4 | "what did the Fed signal about rate cuts" with corpus ~8% tagged `monetary policy` | only `monetary policy`-tagged articles scored (assert via the logged candidate count / filter) | US2 AS1 |
| 5 | question mapping to two tags | ranked pool = union of both tag sets | US2 AS2 |
| 6 | question mapping to no known tag | still answered from the recency-window pool | US2 AS3, FR-006 |
| 7 | "why did NVDA drop today" — corpus has 2 NVDA explainers + 5 routine NVDA items same day | answer grounded in the 2 explainers | US3 AS1, SC-008 |
| 8 | "NVDA news about export restrictions" — NVDA articles across topics | only export-restriction NVDA articles cited, recency-blended | US3 AS2 |
| 9 | "latest NVDA news" | unchanged: most recent NVDA articles by date; `mode == "recency"`; no ranking invoked | US3 AS3, US4 AS1 |
| 10 | a screener question ("stocks near 20-day lows") | byte-identical to pre-feature behavior | US4 AS2, SC-004 |
| 11 | stop Ollama mid-test, ask a topic question | HTTP 200, keyword-fallback answer + "(semantic search was unavailable)" note | FR-011, SC-007 |
| 12 | ticker with 0–2 enriched articles, ask "why did X move" | falls back to plain recency for X; no crash | US4 behavior, R4 |

```bash
cd backend && pytest tests/test_chat_news_semantic.py -q
```

## 5. Latency check (SC-003 / FR-014)

With ≥ 25 000 enriched articles (or a synthetic fill), time a topic question and a
ticker-reason question end to end:

```bash
cd backend && pytest tests/test_chat_news_semantic.py -q -k latency   # asserts < existing chat target
```

The candidate read + NumPy rank should be < 200 ms of the total; if it is not, add a
`tags` multikey index (data-model.md §1) and/or lower `news_rank_max_candidates`.

## 6. Contract / consistency

```bash
cd backend && pytest tests/test_news_contract.py tests/test_screener_query.py -q
cd ../agent-runner && pytest tests/test_news_contract.py tests/test_news_pull.py -q
```

Asserts: writer produces `NEWS_ARTICLE_FIELDS ∪ NEWS_ARTICLE_INTERNAL_FIELDS`;
`NEWS_SCHEMA` describes exactly `NEWS_ARTICLE_FIELDS` (internal fields provably
excluded); `news_tags` doc matches `NEWS_TAG_FIELDS`; `news_search` object shape.

## 7. Full gate

```bash
ruff check backend/ agent-runner/
cd backend && pytest -q
cd ../agent-runner && pytest -q
```

## Rollback

Feature is off the request path unless the model emits `news_search.mode == "semantic"`.
To disable without a revert: set `news_rank_max_candidates=0` (forces every semantic
rank to an empty pool → "no relevant news found") — or restore the pre-036
`build_system_prompt()` so the model never emits `mode: semantic`. Enrichment fields
and `news_tags` are additive and harmless if left in place.
