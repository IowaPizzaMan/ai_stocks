"""semantic/schema.py::NEWS_SCHEMA -> news_articles field vocabulary — the
model's half of the mirrored pair required by constitution Principle VI
(amended v1.1.0). Spec: specs/035-chat-and-news-upgrade; specs/036-news-semantic-search;
contracts/news-collection.md; contracts/news-collection-v2.md.

Mirrored verbatim in agent-runner/tests/test_news_contract.py, which asserts
the same sets against what tools/news_pull.py + tools/news_enrich.py actually
produce.
"""
from semantic import schema

# Mirrored verbatim in agent-runner/tests/test_news_contract.py.
# 036 adds "tags" — the one model-legible enrichment field.
NEWS_ARTICLE_FIELDS = {
    "url", "source_type", "title", "published_at", "published_date",
    "publisher", "site", "author", "body_html", "body_text",
    "image_url", "tickers", "ingested_at",
    "tags",
}

# 036-news-semantic-search — written by the enrichment writer but DELIBERATELY
# absent from NEWS_SCHEMA: a raw 768-float vector (and its sidecars) must never
# enter a model-authored pipeline (contracts/news-collection-v2.md §2,
# research.md R9). The assertion below makes that exclusion provable, not
# accidental.
NEWS_ARTICLE_INTERNAL_FIELDS = {
    "embedding", "embedding_model", "embedding_dim", "embedded_at",
    "tags_generated_at",
}

# 036-news-semantic-search — the news_tags registry doc shape
# (contracts/news-collection-v2.md §3). Mirrored in agent-runner's test.
NEWS_TAG_FIELDS = {
    "_id", "tag", "embedding", "embedding_model", "count",
    "first_seen", "last_seen",
}


def test_schema_field_names_match_the_mirrored_contract_table():
    described = {field["name"] for field in schema.NEWS_SCHEMA["fields"]}
    assert described == NEWS_ARTICLE_FIELDS


def test_internal_enrichment_fields_are_provably_excluded_from_the_schema():
    described = {field["name"] for field in schema.NEWS_SCHEMA["fields"]}
    assert NEWS_ARTICLE_INTERNAL_FIELDS.isdisjoint(described)


def test_every_field_has_a_type_and_description():
    for field in schema.NEWS_SCHEMA["fields"]:
        assert field.get("type"), f"{field['name']} missing type"
        assert field.get("description"), f"{field['name']} missing description"


def test_schema_names_the_news_articles_collection():
    assert schema.NEWS_SCHEMA["collection"] == "news_articles"


def test_source_type_field_has_a_closed_enum_of_the_three_feeds():
    field = next(f for f in schema.NEWS_SCHEMA["fields"] if f["name"] == "source_type")
    assert set(field.get("enum") or []) == {"general", "stock", "fmp_article"}


def test_tags_field_is_groupable():
    field = next(f for f in schema.NEWS_SCHEMA["fields"] if f["name"] == "tags")
    assert field["aggregation"] == "groupable"
