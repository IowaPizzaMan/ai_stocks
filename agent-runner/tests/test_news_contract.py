"""tools/news_pull.py + tools/news_enrich.py -> news_articles / news_tags field
vocabulary — the writer's half of the mirrored pair required by constitution
Principle VI (amended v1.1.0). Spec: specs/035-chat-and-news-upgrade;
specs/036-news-semantic-search; contracts/news-collection.md;
contracts/news-collection-v2.md.

Mirrored verbatim in backend/tests/test_news_contract.py, which asserts the
same sets against `NEWS_SCHEMA["fields"]` — the model's view of this
collection. Together they catch the two silent failure modes named in
contracts/news-collection-v2.md: a writer-produced field the schema doesn't
describe (invisible to chat), or one the schema describes but the writer never
produces (pipelines that match nothing) — plus, for 036, that the five
internal enrichment fields are written but provably kept out of the schema.
"""
import mongomock

import llm
from tools import news_enrich, news_pull

# Mirrored verbatim in backend/tests/test_news_contract.py.
NEWS_ARTICLE_FIELDS = {
    "url", "source_type", "title", "published_at", "published_date",
    "publisher", "site", "author", "body_html", "body_text",
    "image_url", "tickers", "ingested_at",
    "tags",
}

NEWS_ARTICLE_INTERNAL_FIELDS = {
    "embedding", "embedding_model", "embedding_dim", "embedded_at",
    "tags_generated_at",
}

NEWS_TAG_FIELDS = {
    "_id", "tag", "embedding", "embedding_model", "count",
    "first_seen", "last_seen",
}

_SAMPLE_ROWS = {
    "general": {
        "symbol": None, "publishedDate": "2026-08-25 06:20:17", "publisher": "CNBC",
        "title": "headline", "image": "https://x/a.jpg", "site": "cnbc.com",
        "text": "body", "url": "https://x/general",
    },
    "stock": {
        "symbol": "CC", "publishedDate": "2026-08-25 06:20:17", "publisher": "PRNewsWire",
        "title": "headline", "image": "https://x/b.jpg", "site": "prnewswire.com",
        "text": "body", "url": "https://x/stock",
    },
    "fmp_article": {
        "title": "headline", "date": "2026-08-25 06:20:17", "content": "<p>body</p>",
        "tickers": "NYSE:EXR", "image": "https://x/c.jpg",
        "link": "https://x/fmp-article", "author": "Author", "site": "Financial Modeling Prep",
    },
}


def test_stored_article_field_set_is_the_model_legible_plus_internal_union():
    for source_type, raw in _SAMPLE_ROWS.items():
        article = news_pull._normalize(raw, source_type)
        # _normalize produces the model-legible fields except ingested_at
        # (stamped by _upsert); _enrich adds `tags` + the five internal fields.
        enrichment = {
            "embedding": [0.1], "embedding_model": "m", "embedding_dim": 1,
            "embedded_at": None, "tags": [], "tags_generated_at": None,
        }
        produced = set(article) | {"ingested_at"} | set(enrichment)
        assert produced == NEWS_ARTICLE_FIELDS | NEWS_ARTICLE_INTERNAL_FIELDS, (
            f"{source_type} stored-doc field set drifted from the contract"
        )


def test_enrich_produces_exactly_tags_plus_the_five_internal_fields(monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda texts, client=None: [[0.1, 0.2]])
    monkeypatch.setattr(llm, "generate_json", lambda **kw: {"tags": ["markets"]})

    produced = set(news_enrich._enrich({"title": "t", "body_text": "b"}, client=None))
    assert produced == {"tags"} | NEWS_ARTICLE_INTERNAL_FIELDS


def test_upsert_tag_registry_writes_exactly_the_news_tag_fields(monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda texts, client=None: [[0.1, 0.2]] * len(texts))
    db = mongomock.MongoClient()["news_contract_test"]
    from datetime import datetime, timezone

    news_enrich.upsert_tag_registry(db, ["monetary policy"], client=None,
                                    now=datetime.now(timezone.utc))

    row = db[news_enrich.NEWS_TAGS].find_one({"_id": "monetary policy"})
    assert set(row) == NEWS_TAG_FIELDS


def test_source_type_is_one_of_the_three_closed_values():
    assert {f["source_type"] for f in [
        news_pull._normalize(raw, source_type) for source_type, raw in _SAMPLE_ROWS.items()
    ]} == {"general", "stock", "fmp_article"}
