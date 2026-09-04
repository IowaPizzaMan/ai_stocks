# Contract: `news_articles` Collection Field Vocabulary

**Feature**: `035-chat-and-news-upgrade` | Constitution Principle VI (v1.1.0).

> Principle VI was amended on 2026-08-25 to extend cross-layer consistency to the
> semantic layer. The mirrored pair specified below is no longer a convention
> borrowed from `screener` — it is **required** for any collection admitted to
> `query_guard.READABLE_COLLECTIONS`, which this feature does for
> `news_articles`.

`news_articles` is **written by agent-runner** (`tools/news_pull.py`) and **read
by backend** (`routers/news.py`, and chat-generated aggregation pipelines via
`semantic/schema.py`'s `NEWS_SCHEMA`). The two services share no Python package,
so this vocabulary is kept consistent by a mirrored test rather than by imports —
the same mechanism `screener` uses (`specs/031-semantic-layer-chat/contracts/screener-collection.md`).

## The mirrored table

```python
NEWS_ARTICLE_FIELDS = {
    "url", "source_type", "title", "published_at", "published_date",
    "publisher", "site", "author", "body_html", "body_text",
    "image_url", "tickers", "ingested_at",
}
```

Asserted **verbatim in both**:

- `backend/tests/test_news_contract.py` — against `NEWS_SCHEMA["fields"]`
- `agent-runner/tests/test_news_contract.py` — against the document
  `tools/news_pull.py`'s normalizer actually produces

## Why this test exists

The two failure modes it catches, both silent:

- A field the writer produces but `NEWS_SCHEMA` does not describe is **invisible
  to the model** — chat can never query it.
- A field `NEWS_SCHEMA` describes but the writer never produces yields pipelines
  that **match nothing**, which reads to the user as "no news found" rather than
  as a bug.

Neither surfaces as an exception. Both surface as bad chat answers, days later.
That is precisely the gap `screener`'s equivalent test was written to close, and
the reasoning is recorded verbatim at the top of `backend/semantic/schema.py`.

## Closed value sets

`source_type` ∈ `{"general", "fmp_article", "stock"}`.

This set is also asserted in both services' tests. It is closed because
`NEWS_SCHEMA` advertises it to the model as an `enum` (data-model.md §3) — a
fourth feed added to the writer without updating the schema would be
unqueryable, and a value advertised but never written produces empty results.

## Change procedure

Adding, renaming, or removing a field in `news_articles` requires, in one change:

1. `agent-runner/tools/news_pull.py` — the normalizer that writes it
2. `backend/semantic/schema.py` — `NEWS_SCHEMA["fields"]`, with a `description`
   good enough for the model to use the field correctly
3. Both `test_news_contract.py` files — the mirrored table above
4. `backend/routers/news.py` — only if the field is user-facing in the API
5. This document

Skipping step 2 or 3 is what the mirrored assertion exists to make impossible.
