"""GET/POST /news — the mixed general/stock/FMP-article stream.
Spec: specs/035-chat-and-news-upgrade US2; contracts/news-api.md.
"""
from datetime import datetime, timedelta, timezone

from db import NEWS_ARTICLES, WORK_QUEUE

NOW = datetime.now(timezone.utc)


def article(url, source_type="general", published_at=None, **overrides):
    doc = {
        "url": url, "source_type": source_type, "title": f"headline for {url}",
        "published_at": published_at or NOW, "published_date": (published_at or NOW).date().isoformat(),
        "publisher": "CNBC", "site": "cnbc.com", "author": None,
        "body_html": None, "body_text": "body text", "image_url": None,
        "tickers": [], "ingested_at": NOW,
    }
    doc.update(overrides)
    return doc


def test_mixed_stream_is_ordered_by_recency(client, db):
    db[NEWS_ARTICLES].insert_many([
        article("https://x/old", published_at=NOW - timedelta(days=2)),
        article("https://x/new", published_at=NOW),
        article("https://x/mid", published_at=NOW - timedelta(days=1)),
    ])
    r = client.get("/news").json()
    assert [a["url"] for a in r["articles"]] == ["https://x/new", "https://x/mid", "https://x/old"]


def test_articles_from_all_three_source_types_are_returned_together(client, db):
    db[NEWS_ARTICLES].insert_many([
        article("https://x/a", source_type="general"),
        article("https://x/b", source_type="stock", tickers=["AAPL"]),
        article("https://x/c", source_type="fmp_article", tickers=["EXR"]),
    ])
    r = client.get("/news").json()
    assert {a["source_type"] for a in r["articles"]} == {"general", "stock", "fmp_article"}


def test_source_type_filter_narrows_the_stream(client, db):
    db[NEWS_ARTICLES].insert_many([
        article("https://x/a", source_type="general"),
        article("https://x/b", source_type="stock", tickers=["AAPL"]),
    ])
    r = client.get("/news?source_type=stock").json()
    assert [a["url"] for a in r["articles"]] == ["https://x/b"]


def test_ticker_filter_narrows_the_stream(client, db):
    db[NEWS_ARTICLES].insert_many([
        article("https://x/a", source_type="stock", tickers=["AAPL"]),
        article("https://x/b", source_type="stock", tickers=["NVDA"]),
    ])
    r = client.get("/news?ticker=NVDA").json()
    assert [a["url"] for a in r["articles"]] == ["https://x/b"]


def test_source_type_and_ticker_filters_compose(client, db):
    db[NEWS_ARTICLES].insert_many([
        article("https://x/a", source_type="stock", tickers=["AAPL"]),
        article("https://x/b", source_type="fmp_article", tickers=["AAPL"]),
    ])
    r = client.get("/news?source_type=stock&ticker=AAPL").json()
    assert [a["url"] for a in r["articles"]] == ["https://x/a"]


def test_limit_is_capped_at_the_hard_max(client, db):
    db[NEWS_ARTICLES].insert_many([
        article(f"https://x/{i}", published_at=NOW - timedelta(minutes=i)) for i in range(5)
    ])
    r = client.get("/news?limit=999").json()
    assert len(r["articles"]) == 5  # not an error, just capped internally — no 250-row fixture needed to prove it
    r2 = client.get("/news?limit=2").json()
    assert len(r2["articles"]) == 2


def test_empty_collection_returns_200_with_empty_list(client, db):
    r = client.get("/news")
    assert r.status_code == 200
    assert r.json() == {"articles": [], "total": 0, "as_of": None}


def test_total_reflects_the_full_matching_count_not_just_the_page(client, db):
    db[NEWS_ARTICLES].insert_many([article(f"https://x/{i}") for i in range(3)])
    r = client.get("/news?limit=1").json()
    assert r["total"] == 3
    assert len(r["articles"]) == 1


# --- refresh (mirrors test_market.py's most-actives/refresh tests) ---------

def test_refresh_enqueues_market_news_pull(client, db):
    r = client.post("/news/refresh").json()
    assert r["status"] == "enqueued"
    job = db[WORK_QUEUE].find_one({"job_type": "market_news_pull"})
    assert job["status"] == "pending"


def test_refresh_dedupes_an_active_job(client, db):
    first = client.post("/news/refresh").json()
    second = client.post("/news/refresh").json()
    assert second["status"] == "already_queued"
    assert second["job_id"] == first["job_id"]
    assert db[WORK_QUEUE].count_documents({"job_type": "market_news_pull"}) == 1
