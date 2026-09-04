# Contract: `news_articles` v2 Field Vocabulary + `news_tags`

**Feature**: `036-news-semantic-search` | Constitution Principle VI (v1.1.0).

Extends [specs/035-chat-and-news-upgrade/contracts/news-collection.md](../../035-chat-and-news-upgrade/contracts/news-collection.md).
`news_articles` is **written by agent-runner** (`tools/news_pull.py`, now via
`tools/news_enrich.py`) and **read by backend** (`routers/news.py`, and chat via
`semantic/schema.py`'s `NEWS_SCHEMA` + `semantic/news_rank.py`). No shared package —
consistency is a mirrored test.

## 1. The mirrored table — model-legible fields

```python
NEWS_ARTICLE_FIELDS = {
    "url", "source_type", "title", "published_at", "published_date",
    "publisher", "site", "author", "body_html", "body_text",
    "image_url", "tickers", "ingested_at",
    "tags",                          # NEW in 036
}
```

Asserted **verbatim in both**:

- `backend/tests/test_news_contract.py` — equals `{f["name"] for f in NEWS_SCHEMA["fields"]}`
- `agent-runner/tests/test_news_contract.py` — equals the model-legible keys of the doc
  `tools/news_pull.py` upserts

## 2. The internal set — written but deliberately NOT in the schema

```python
NEWS_ARTICLE_INTERNAL_FIELDS = {
    "embedding",            # array<double>[768], L2-normalized
    "embedding_model",      # str, == settings.ollama_embed_model at write time
    "embedding_dim",        # int, 768
    "embedded_at",          # date (UTC)
    "tags_generated_at",    # date (UTC)
}
```

Asserted in both `test_news_contract.py`:

- the writer produces **`NEWS_ARTICLE_FIELDS ∪ NEWS_ARTICLE_INTERNAL_FIELDS`**
- `NEWS_SCHEMA` describes **exactly `NEWS_ARTICLE_FIELDS`** — i.e.
  `NEWS_ARTICLE_INTERNAL_FIELDS ∩ schema field names == ∅`

### Why the split (constitution VI intent)

Principle VI exists so a writer-produced field is never *accidentally* invisible to the
chat model. `embedding` is a field the model must **never** reference in a generated
pipeline — advertising a 768-float array invites `$sort`/`$project`/`$match` misuse, and
`query_guard` would then need a special case to strip it. The internal set makes the
exclusion **explicit and tested**: add a sixth internal field and forget to register it
here, and the mirrored `writer == FIELDS ∪ INTERNAL` assertion fails. `tags` is the one
new field that is genuinely a groupable category, so it is described normally.

## 3. `news_tags` (new collection) field set

```python
NEWS_TAG_FIELDS = {
    "_id",              # str — the normalized tag (natural key)
    "tag",              # str — same value, named for query/export clarity
    "embedding",        # array<double>[768]
    "embedding_model",  # str
    "count",            # int — articles currently carrying this tag
    "first_seen",       # date (UTC)
    "last_seen",        # date (UTC)
}
```

Asserted in both `test_news_contract.py` against the doc
`news_enrich.upsert_tag_registry()` writes. **Not** admitted to
`query_guard.READABLE_COLLECTIONS` — chat never queries it; `news_rank.py` reads it
directly with a fixed `{_id: 1, embedding: 1, embedding_model: 1}` projection.

`NEWS_TAGS = "news_tags"` constant is hand-duplicated in `backend/db.py` and
`agent-runner/tools/db.py` (existing precedent for collection-name constants).

## 4. Closed value sets

Unchanged: `source_type ∈ {"general", "fmp_article", "stock"}`.

`tags` is an **open** set by design (spec FR-002) — no enum assertion. Its normalized
form is constrained instead: `normalize_tags()` guarantees lowercase, punctuation-
trimmed, single-spaced, 1–4 words, ≤ 40 chars, unique-within-array. Both services'
tests assert those invariants on a sample of produced tags.

## 5. Change procedure

Adding / renaming / removing a `news_articles` or `news_tags` field requires, in one
change:

1. `agent-runner/tools/news_enrich.py` (and/or `news_pull.py`) — the writer
2. Decide model-legible vs internal:
   - model-legible → `backend/semantic/schema.py` `NEWS_SCHEMA["fields"]` **and**
     `NEWS_ARTICLE_FIELDS`
   - internal → `NEWS_ARTICLE_INTERNAL_FIELDS` only (never the schema)
3. Both `test_news_contract.py` files — the sets above
4. `backend/routers/news.py` — only if the field becomes user-facing in the API
   (`tags` is **not**, per spec FR-016)
5. This document

Skipping step 2/3 is what the mirrored assertion exists to make impossible.
