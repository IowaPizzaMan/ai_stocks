"""GET /market/news — specs/022-market-news-feed.

Market-wide headlines for the Stocks page: cache-first, capped at 20, and
fail-soft. Nothing here may touch the analyses collection (FR-008).
"""
from datetime import datetime, timedelta, timezone

import requests

import fmp
from db import ANALYSES, MARKET_NEWS_CACHE
from routers import market as market_router


def raw(symbol="AAPL", published="2026-08-16 20:30:00", title="A headline", url=None, text="body"):
    """One article in FMP's news/stock-latest shape."""
    return {
        "symbol": symbol,
        "publishedDate": published,
        "publisher": "Seeking Alpha",
        "site": "seekingalpha.com",
        "title": title,
        "text": text,
        "image": "https://img",
        "url": url or f"https://example.com/{title.replace(' ', '-')}",
    }


def patch_fetch(monkeypatch, payload, calls=None):
    def fake(path, db):
        if calls is not None:
            calls.append(path)
        return payload

    monkeypatch.setattr(market_router, "fmp_get", fake)


# --- US1: shaping, ordering, cap --------------------------------------------


def test_returns_normalized_articles(client, db, monkeypatch):
    patch_fetch(monkeypatch, [raw(symbol="NBIS", title="Nebius momentum")])

    body = client.get("/market/news").json()

    assert body["stale"] is False
    assert body["as_of"] is not None
    a = body["articles"][0]
    assert a["ticker"] == "NBIS"
    assert a["headline"] == "Nebius momentum"
    assert a["source"] == "Seeking Alpha"
    assert a["date"] == "2026-08-16"
    assert a["datetime"] == "2026-08-16 20:30:00"
    assert a["url"].startswith("https://")
    assert a["text_excerpt"] == "body"


def test_sorted_newest_first_and_capped_at_twenty(client, db, monkeypatch):
    # 30 articles, oldest first on the wire — the cap must keep the NEWEST 20
    payload = [
        raw(published=f"2026-08-{str(1 + i).zfill(2)} 09:00:00", title=f"Story {i}")
        for i in range(30)
    ]
    patch_fetch(monkeypatch, payload)

    articles = client.get("/market/news").json()["articles"]

    assert len(articles) == 20
    assert articles[0]["headline"] == "Story 29"  # newest
    dates = [a["datetime"] for a in articles]
    assert dates == sorted(dates, reverse=True)
    assert "Story 0" not in [a["headline"] for a in articles]  # oldest dropped


def test_fewer_than_twenty_returns_all_without_padding(client, db, monkeypatch):
    patch_fetch(monkeypatch, [raw(title=f"S{i}") for i in range(7)])
    assert len(client.get("/market/news").json()["articles"]) == 7


def test_untagged_article_keeps_a_null_ticker(client, db, monkeypatch):
    patch_fetch(monkeypatch, [raw(symbol=None, title="Fed commentary")])
    assert client.get("/market/news").json()["articles"][0]["ticker"] is None


def test_rows_without_title_or_url_are_dropped(client, db, monkeypatch):
    patch_fetch(monkeypatch, [
        raw(title="Keeper"),
        {**raw(title="No url"), "url": ""},
        {**raw(title="x"), "title": ""},
    ])
    assert [a["headline"] for a in client.get("/market/news").json()["articles"]] == ["Keeper"]


def test_source_falls_back_to_site_then_unknown(client, db, monkeypatch):
    patch_fetch(monkeypatch, [
        {**raw(title="A"), "publisher": None},
        {**raw(title="B"), "publisher": None, "site": None},
    ])
    sources = {a["headline"]: a["source"] for a in client.get("/market/news").json()["articles"]}
    assert sources["A"] == "seekingalpha.com"
    assert sources["B"] == "unknown"


# --- US2: caching, no history ------------------------------------------------


def test_fresh_cache_is_served_without_calling_the_provider(client, db, monkeypatch):
    calls = []
    patch_fetch(monkeypatch, [raw(title="Fresh")], calls)

    first = client.get("/market/news").json()
    second = client.get("/market/news").json()

    assert len(calls) == 1  # second request served from cache
    assert first["as_of"] == second["as_of"]
    assert second["stale"] is False


def test_cache_older_than_the_window_triggers_exactly_one_refresh(client, db, monkeypatch):
    calls = []
    patch_fetch(monkeypatch, [raw(title="Refreshed")], calls)

    client.get("/market/news")
    db[MARKET_NEWS_CACHE].update_one(
        {}, {"$set": {"fetched_at": datetime.now(timezone.utc) - timedelta(minutes=61)}}
    )
    body = client.get("/market/news").json()

    assert len(calls) == 2
    assert body["articles"][0]["headline"] == "Refreshed"
    fetched = db[MARKET_NEWS_CACHE].find_one({})["fetched_at"]
    assert datetime.now(timezone.utc) - fetched.replace(tzinfo=timezone.utc) < timedelta(minutes=1)


def test_cache_stays_a_single_document_across_refreshes(client, db, monkeypatch):
    patch_fetch(monkeypatch, [raw(title="One")])
    for _ in range(3):
        client.get("/market/news")
        db[MARKET_NEWS_CACHE].update_one(
            {}, {"$set": {"fetched_at": datetime.now(timezone.utc) - timedelta(hours=2)}}
        )
    assert db[MARKET_NEWS_CACHE].count_documents({}) == 1


def test_never_writes_to_the_analyses_collection(client, db, monkeypatch):
    patch_fetch(monkeypatch, [raw(title="Market wide")])
    db[ANALYSES].insert_one({"ticker": "AAPL", "summary": "untouched", "sub_reports": {}})

    client.get("/market/news")

    assert db[ANALYSES].count_documents({}) == 1
    doc = db[ANALYSES].find_one({"ticker": "AAPL"})
    assert doc["summary"] == "untouched"
    assert "news" not in doc.get("sub_reports", {})
    assert db[MARKET_NEWS_CACHE].count_documents({}) == 1


# --- US3: graceful degradation ----------------------------------------------


def test_provider_error_serves_the_previous_articles_as_stale(client, db, monkeypatch):
    patch_fetch(monkeypatch, [raw(title="Cached copy")])
    client.get("/market/news")  # warm the cache

    db[MARKET_NEWS_CACHE].update_one(
        {}, {"$set": {"fetched_at": datetime.now(timezone.utc) - timedelta(hours=2)}}
    )

    def boom(path, db):
        raise requests.HTTPError("502")

    monkeypatch.setattr(market_router, "fmp_get", boom)

    r = client.get("/market/news")
    assert r.status_code == 200
    body = r.json()
    assert body["stale"] is True
    assert body["articles"][0]["headline"] == "Cached copy"


def test_provider_error_with_no_cache_returns_empty_not_an_error(client, db, monkeypatch):
    def boom(path, db):
        raise requests.RequestException("dns")

    monkeypatch.setattr(market_router, "fmp_get", boom)

    r = client.get("/market/news")
    assert r.status_code == 200
    assert r.json() == {"articles": [], "as_of": None, "stale": True}


def test_budget_exceeded_degrades_like_a_provider_error(client, db, monkeypatch):
    patch_fetch(monkeypatch, [raw(title="Before the cap")])
    client.get("/market/news")
    db[MARKET_NEWS_CACHE].update_one(
        {}, {"$set": {"fetched_at": datetime.now(timezone.utc) - timedelta(hours=2)}}
    )

    attempts = []

    def capped(path, db):
        attempts.append(path)
        raise fmp.FmpBudgetExceededError("cap")

    monkeypatch.setattr(market_router, "fmp_get", capped)

    body = client.get("/market/news").json()

    assert body["stale"] is True
    assert body["articles"][0]["headline"] == "Before the cap"
    assert len(attempts) == 1  # no retry after the cap trips
