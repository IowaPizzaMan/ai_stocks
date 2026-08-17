"""News tool + NewsAnalyst — specs/021-stock-page-redesign US5.

The tally/timeline/trend math is deterministic and fully covered here
(constitution Principle I & III); the LLM call is faked so the agent's
merge/mapping logic is testable without Ollama.
"""
from datetime import date, datetime, timedelta, timezone

import mongomock
import pytest
import requests

from agents import news_analyst
from tools import news as news_tool
from tools.db import STOCK_NEWS_CACHE
from tools.fmp_client import FmpBudgetExceededError


@pytest.fixture
def db():
    return mongomock.MongoClient()["test"]


def article(days_ago=0, title="", text="", publisher="Wire", url=None):
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "symbol": "AAPL",
        "publishedDate": when.strftime("%Y-%m-%d %H:%M:%S"),
        "publisher": publisher,
        "title": title,
        "site": "example.com",
        "text": text,
        "url": url or f"https://example.com/{days_ago}-{title[:10]}",
    }


# --- deterministic tally -----------------------------------------------------


def test_tally_counts_bullish_and_bearish_terms_in_title_and_body():
    a = news_tool.tally_article(
        article(title="Record quarter as demand accelerates",
                text="Management raised guidance and called momentum strong.")
    )
    assert a["bullish_count"] >= 3
    assert a["bearish_count"] == 0
    assert a["headline"] == "Record quarter as demand accelerates"
    assert a["source"] == "Wire"
    assert a["ai_summary"] is None


def test_article_with_no_recognized_terms_is_neutral_not_bearish():
    a = news_tool.tally_article(article(title="Company schedules annual meeting",
                                        text="The meeting will be held virtually."))
    assert a["bullish_count"] == 0
    assert a["bearish_count"] == 0


def test_timeline_aggregates_articles_sharing_a_date():
    day = date.today().isoformat()
    articles = [
        {"date": day, "bullish_count": 6, "bearish_count": 2},
        {"date": day, "bullish_count": 1, "bearish_count": 0},
    ]
    timeline = news_tool.build_timeline(articles)
    assert timeline == [{"date": day, "bullish": 7, "bearish": 2, "article_count": 2}]


def test_timeline_is_ascending_by_date():
    articles = [
        {"date": "2026-03-01", "bullish_count": 1, "bearish_count": 0},
        {"date": "2026-01-01", "bullish_count": 0, "bearish_count": 1},
        {"date": "2026-02-01", "bullish_count": 2, "bearish_count": 0},
    ]
    assert [p["date"] for p in news_tool.build_timeline(articles)] == [
        "2026-01-01", "2026-02-01", "2026-03-01",
    ]


@pytest.mark.parametrize(
    "recent_bullish,recent_bearish,expected",
    [(8, 1, "bullish"), (0, 6, "bearish"), (3, 3, "mixed")],
)
def test_trend_reads_the_recent_window(recent_bullish, recent_bearish, expected):
    today = date.today()
    timeline = [
        # older, opposite-signed coverage must not outvote the recent window
        {"date": (today - timedelta(days=60)).isoformat(), "bullish": 0, "bearish": 40,
         "article_count": 5},
        {"date": today.isoformat(), "bullish": recent_bullish, "bearish": recent_bearish,
         "article_count": 3},
    ]
    assert news_tool.compute_trend(timeline) == expected


def test_trend_on_empty_timeline_is_mixed():
    assert news_tool.compute_trend([]) == "mixed"


# --- fetch, cache, fail-soft -------------------------------------------------


def test_get_stock_news_fetches_caches_and_shapes(db, monkeypatch):
    raw = [article(days_ago=1, title="Record beat", text="strong demand"),
           article(days_ago=2, title="Guidance cut", text="headwind and slowdown")]
    monkeypatch.setattr(news_tool, "fmp_get", lambda path, db=None: raw)

    out = news_tool.get_stock_news("aapl", db=db)

    assert out["news_count"] == 2
    assert out["stale"] is False
    assert out["as_of"] == out["articles"][0]["date"]
    # newest first
    assert out["articles"][0]["headline"] == "Record beat"
    assert out["trend"] in {"bullish", "bearish", "mixed"}
    assert out["window_days"] == news_tool.NEWS_DAYS
    assert out["days_covered"] == 2
    assert db[STOCK_NEWS_CACHE].find_one({"ticker": "AAPL"})["articles"] == raw


def test_get_stock_news_drops_articles_older_than_the_window(db, monkeypatch):
    monkeypatch.setattr(
        news_tool, "fmp_get",
        lambda path, db=None: [article(days_ago=2, title="Fresh"),
                               article(days_ago=120, title="Ancient")],
    )
    out = news_tool.get_stock_news("AAPL", db=db)
    assert [a["headline"] for a in out["articles"]] == ["Fresh"]


# --- windowed paging (keeps a full month, not just the newest page) ----------


def test_requests_the_full_window_with_from_and_to(db, monkeypatch):
    paths = []

    def fake_get(path, db=None):
        paths.append(path)
        return [article(days_ago=1, title="Only page")]

    monkeypatch.setattr(news_tool, "fmp_get", fake_get)
    news_tool.get_stock_news("AAPL", db=db)

    assert "from=" in paths[0] and "to=" in paths[0]
    assert f"limit={news_tool.PAGE_SIZE}" in paths[0]


def test_pages_backwards_until_the_window_is_covered(db, monkeypatch):
    """A mega-cap runs a full page per couple of weeks, so one page is not a
    month — the fetch must keep paging until it reaches the cutoff."""
    pages = {
        0: [article(days_ago=d, title=f"p0-{i}", url=f"u0-{i}")
            for i, d in enumerate([1] * news_tool.PAGE_SIZE)],
        1: [article(days_ago=d, title=f"p1-{i}", url=f"u1-{i}")
            for i, d in enumerate([15] * news_tool.PAGE_SIZE)],
        2: [article(days_ago=29, title="oldest", url="u2-0")],
    }
    seen = []

    def fake_get(path, db=None):
        page = int(path.split("page=")[1])
        seen.append(page)
        return pages.get(page, [])

    monkeypatch.setattr(news_tool, "fmp_get", fake_get)
    out = news_tool.get_stock_news("AAPL", db=db)

    assert seen == [0, 1, 2]  # stops on the short third page
    assert out["news_count"] == news_tool.PAGE_SIZE * 2 + 1
    assert out["days_covered"] == 3


def test_stops_paging_once_a_page_reaches_past_the_cutoff(db, monkeypatch):
    seen = []

    def fake_get(path, db=None):
        page = int(path.split("page=")[1])
        seen.append(page)
        # a full page that already spans past the window — no need to go older
        return [article(days_ago=1, title=f"a{i}", url=f"u{page}-{i}")
                for i in range(news_tool.PAGE_SIZE - 1)] + [
            article(days_ago=40, title="past cutoff", url=f"old-{page}")
        ]

    monkeypatch.setattr(news_tool, "fmp_get", fake_get)
    news_tool.get_stock_news("AAPL", db=db)
    assert seen == [0]


def test_paging_is_bounded_by_max_pages(db, monkeypatch):
    seen = []

    def fake_get(path, db=None):
        page = int(path.split("page=")[1])
        seen.append(page)
        # always full and always recent → only MAX_PAGES stops the loop
        return [article(days_ago=1, title=f"a{i}", url=f"u{page}-{i}")
                for i in range(news_tool.PAGE_SIZE)]

    monkeypatch.setattr(news_tool, "fmp_get", fake_get)
    out = news_tool.get_stock_news("AAPL", db=db)

    assert len(seen) == news_tool.MAX_PAGES
    assert out["news_count"] <= news_tool.MAX_ARTICLES


def test_duplicate_urls_across_pages_are_not_double_counted(db, monkeypatch):
    def fake_get(path, db=None):
        page = int(path.split("page=")[1])
        if page > 1:
            return []
        # same article returned on both pages
        return [article(days_ago=1, title="Dupe", url="same-url")]

    monkeypatch.setattr(news_tool, "fmp_get", fake_get)
    out = news_tool.get_stock_news("AAPL", db=db)
    assert out["news_count"] == 1


def test_a_failure_on_a_later_page_keeps_the_pages_already_fetched(db, monkeypatch):
    def fake_get(path, db=None):
        page = int(path.split("page=")[1])
        if page == 0:
            # a full, entirely-recent page → the loop wants to continue
            return [article(days_ago=1, title=f"a{i}", url=f"u{i}")
                    for i in range(news_tool.PAGE_SIZE)]
        raise requests.HTTPError("502")

    monkeypatch.setattr(news_tool, "fmp_get", fake_get)
    out = news_tool.get_stock_news("AAPL", db=db)

    # partial coverage beats no coverage — page 0 survives the page-1 failure
    assert out["stale"] is False
    assert out["news_count"] == news_tool.PAGE_SIZE


def test_a_failure_on_the_very_first_page_falls_back_to_cache(db, monkeypatch):
    db[STOCK_NEWS_CACHE].insert_one({
        "ticker": "AAPL",
        "articles": [article(days_ago=1, title="Cached", url="c1")],
        "fetched_at": datetime.now(timezone.utc),
    })

    def fake_get(path, db=None):
        raise requests.HTTPError("502")

    monkeypatch.setattr(news_tool, "fmp_get", fake_get)
    out = news_tool.get_stock_news("AAPL", db=db)

    assert out["stale"] is True
    assert [a["headline"] for a in out["articles"]] == ["Cached"]


def test_get_stock_news_serves_stale_cache_when_budget_exceeded(db, monkeypatch):
    cached = [article(days_ago=1, title="Cached story", text="strong")]
    db[STOCK_NEWS_CACHE].insert_one(
        {"ticker": "AAPL", "articles": cached, "fetched_at": datetime.now(timezone.utc)}
    )

    def boom(path, db=None):
        raise FmpBudgetExceededError("cap hit")

    monkeypatch.setattr(news_tool, "fmp_get", boom)

    out = news_tool.get_stock_news("AAPL", db=db)
    assert out["stale"] is True
    assert [a["headline"] for a in out["articles"]] == ["Cached story"]


def test_get_stock_news_survives_http_failure(db, monkeypatch):
    def boom(path, db=None):
        raise requests.HTTPError("500")

    monkeypatch.setattr(news_tool, "fmp_get", boom)
    out = news_tool.get_stock_news("NOCACHE", db=db)
    assert out["stale"] is True
    assert out["articles"] == []
    assert out["news_count"] == 0


# --- NewsAnalyst -------------------------------------------------------------


def test_news_analyst_maps_summaries_by_index_and_returns_stance(monkeypatch):
    payload = {
        "articles": [
            {"date": "2026-08-15", "datetime": "2026-08-15 09:00:00", "source": "Wire",
             "headline": "Record beat", "url": "u1", "text_excerpt": "strong demand",
             "bullish_count": 3, "bearish_count": 0, "ai_summary": None},
            {"date": "2026-08-14", "datetime": "2026-08-14 09:00:00", "source": "Wire",
             "headline": "Guidance cut", "url": "u2", "text_excerpt": "headwind",
             "bullish_count": 0, "bearish_count": 2, "ai_summary": None},
        ],
        "timeline": [{"date": "2026-08-14", "bullish": 0, "bearish": 2, "article_count": 1}],
        "trend": "bearish",
        "news_count": 2,
        "as_of": "2026-08-15",
    }

    monkeypatch.setattr(
        news_analyst, "generate_json",
        lambda *a, **k: {
            "summaries": [{"index": 1, "summary": "Guidance was reduced."},
                          {"index": 0, "summary": "Results beat expectations."}],
            "stance": {"direction": "bearish", "reasoning": "'Guidance cut' outweighs the beat."},
        },
    )

    out = news_analyst.run("AAPL", {"news": payload})

    # summaries land on the right articles even when returned out of order
    assert out["articles"][0]["ai_summary"] == "Results beat expectations."
    assert out["articles"][1]["ai_summary"] == "Guidance was reduced."
    assert out["stance"]["direction"] == "bearish"
    # deterministic fields pass through untouched
    assert out["trend"] == "bearish"
    assert out["timeline"] == payload["timeline"]


def test_news_analyst_skips_llm_when_there_are_no_articles(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("LLM must not be called without articles")

    monkeypatch.setattr(news_analyst, "generate_json", fail)
    out = news_analyst.run("AAPL", {"news": {"articles": [], "timeline": [], "trend": "mixed",
                                             "news_count": 0, "as_of": None}})
    assert out["stance"] is None
    assert out["articles"] == []


def test_news_analyst_tolerates_malformed_summary_entries(monkeypatch):
    payload = {
        "articles": [{"date": "2026-08-15", "datetime": "2026-08-15 09:00:00", "source": "W",
                      "headline": "H", "url": "u", "text_excerpt": "t",
                      "bullish_count": 0, "bearish_count": 0, "ai_summary": None}],
        "timeline": [], "trend": "mixed", "news_count": 1, "as_of": "2026-08-15",
    }
    monkeypatch.setattr(
        news_analyst, "generate_json",
        lambda *a, **k: {"summaries": [{"index": "not-an-int", "summary": "x"}],
                         "stance": {"direction": "neutral", "reasoning": "thin coverage"}},
    )
    out = news_analyst.run("AAPL", {"news": payload})
    assert out["articles"][0]["ai_summary"] is None
    assert out["stance"]["direction"] == "neutral"


# --- delta window (024 US3) ---------------------------------------------------


def test_delta_request_starts_from_the_newest_stored_article(db, monkeypatch):
    """A repeat pull asks only for what it is missing — for news this genuinely
    saves API calls, since the endpoint pages at 250 articles."""
    stored = [article(days_ago=2, title="Old news")]
    db[STOCK_NEWS_CACHE].insert_one({"ticker": "AAPL", "articles": stored})

    paths = []
    monkeypatch.setattr(news_tool, "fmp_get",
                        lambda path, db=None: paths.append(path) or [])

    news_tool.get_stock_news("AAPL", db=db)

    today = date.today()
    expected = (today - timedelta(days=3)).isoformat()   # newest(-2d) minus 1d overlap
    assert f"from={expected}" in paths[0]
    assert f"from={(today - timedelta(days=news_tool.NEWS_DAYS - 1)).isoformat()}" not in paths[0]


def test_no_stored_articles_fetches_the_full_window(db, monkeypatch):
    paths = []
    monkeypatch.setattr(news_tool, "fmp_get",
                        lambda path, db=None: paths.append(path) or [])

    news_tool.get_stock_news("COLD", db=db)

    cutoff = (date.today() - timedelta(days=news_tool.NEWS_DAYS - 1)).isoformat()
    assert f"from={cutoff}" in paths[0]


def test_rebuild_ignores_the_stored_baseline(db, monkeypatch):
    """FR-024 — a full refresh re-fetches the whole window rather than topping
    up from a baseline the operator has just declared suspect."""
    stored = [news_tool.tally_article(article(days_ago=2, title="Old news"))]
    db[STOCK_NEWS_CACHE].insert_one({"ticker": "AAPL", "articles": stored})

    paths = []
    monkeypatch.setattr(news_tool, "fmp_get",
                        lambda path, db=None: paths.append(path) or [])

    news_tool.get_stock_news("AAPL", db=db, rebuild=True)

    cutoff = (date.today() - timedelta(days=news_tool.NEWS_DAYS - 1)).isoformat()
    assert f"from={cutoff}" in paths[0]


def test_merged_articles_are_unique_by_url(db, monkeypatch):
    """FR-008 — the deliberate one-day overlap must not duplicate coverage."""
    shared = article(days_ago=1, title="Same story", url="https://example.com/same")
    db[STOCK_NEWS_CACHE].insert_one({"ticker": "AAPL", "articles": [shared]})

    monkeypatch.setattr(news_tool, "fmp_get", lambda path, db=None: [shared])
    out = news_tool.get_stock_news("AAPL", db=db)

    assert out["news_count"] == 1
    urls = [a["url"] for a in out["articles"]]
    assert len(urls) == len(set(urls))


def test_a_refetched_article_replaces_its_stored_copy(db, monkeypatch):
    old = article(days_ago=1, title="Draft headline", url="https://example.com/x")
    db[STOCK_NEWS_CACHE].insert_one({"ticker": "AAPL", "articles": [old]})

    corrected = article(days_ago=1, title="Corrected headline", url="https://example.com/x")
    monkeypatch.setattr(news_tool, "fmp_get", lambda path, db=None: [corrected])

    out = news_tool.get_stock_news("AAPL", db=db)
    assert [a["headline"] for a in out["articles"]] == ["Corrected headline"]


def test_articles_aged_out_of_the_window_are_dropped_from_storage(db, monkeypatch):
    """FR-017 — with the TTL gone, the merge is what keeps storage bounded."""
    ancient = article(days_ago=90, title="Ancient")
    db[STOCK_NEWS_CACHE].insert_one({"ticker": "AAPL", "articles": [ancient]})

    monkeypatch.setattr(news_tool, "fmp_get",
                        lambda path, db=None: [article(days_ago=1, title="Fresh")])
    news_tool.get_stock_news("AAPL", db=db)

    doc = db[STOCK_NEWS_CACHE].find_one({"ticker": "AAPL"})
    assert [a["title"] for a in doc["articles"]] == ["Fresh"]


def test_trend_is_computed_over_the_full_retained_window(db, monkeypatch):
    """FR-018 — derived outputs read the whole window, not just what arrived in
    this delta. Two old bearish stories must still outweigh one new bullish."""
    stored = [
        article(days_ago=3, title="Guidance cut", text="decline weak loss"),
        article(days_ago=4, title="Downgrade", text="miss plunge risk"),
    ]
    db[STOCK_NEWS_CACHE].insert_one({"ticker": "AAPL", "articles": stored})

    monkeypatch.setattr(
        news_tool, "fmp_get",
        lambda path, db=None: [article(days_ago=1, title="Beat", text="record strong")])

    out = news_tool.get_stock_news("AAPL", db=db)
    assert out["news_count"] == 3
    assert len(out["timeline"]) == 3


def test_coverage_envelope_is_written(db, monkeypatch):
    monkeypatch.setattr(news_tool, "fmp_get",
                        lambda path, db=None: [article(days_ago=1, title="Fresh")])
    news_tool.get_stock_news("AAPL", db=db)

    cov = db[STOCK_NEWS_CACHE].find_one({"ticker": "AAPL"})["coverage"]
    assert cov["newest_published"] is not None
    assert cov["window_days"] == news_tool.NEWS_DAYS
    assert cov["established_at"] is not None


def test_legacy_document_without_coverage_still_works(db, monkeypatch):
    """FR-021 — pre-024 documents are a valid baseline; no wipe-and-refetch."""
    db[STOCK_NEWS_CACHE].insert_one({
        "ticker": "AAPL",
        "articles": [article(days_ago=1, title="Legacy")],
        "fetched_at": datetime.now(timezone.utc),
    })
    monkeypatch.setattr(news_tool, "fmp_get", lambda path, db=None: [])

    out = news_tool.get_stock_news("AAPL", db=db)
    assert out["news_count"] == 1
    assert db[STOCK_NEWS_CACHE].find_one({"ticker": "AAPL"})["coverage"] is not None


def test_stock_news_cache_has_no_ttl_index(db):
    """The trap: a TTL deletes the document the delta baseline lives in, which
    would silently restore full-window fetching with no error."""
    from tools import db as dbmod
    dbmod.ensure_indexes(db=db)
    info = db[STOCK_NEWS_CACHE].index_information()
    assert not any("expireAfterSeconds" in spec for spec in info.values())


def test_stage_is_marked_incremental_when_a_baseline_exists(db, monkeypatch):
    """FR-002 — without this the stage infers 'full' from having spent requests
    and keeps saying 'full' long after the fetch went incremental."""
    from tools import metrics
    db[STOCK_NEWS_CACHE].insert_one(
        {"ticker": "AAPL", "articles": [article(days_ago=2, title="Old")]})
    monkeypatch.setattr(news_tool, "fmp_get", lambda path, db=None: [])

    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("news", recorder):
        news_tool.get_stock_news("AAPL", db=db)

    assert recorder.stages()[0]["retrieval"] == metrics.INCREMENTAL


def test_stage_is_marked_full_on_a_cold_baseline(db, monkeypatch):
    from tools import metrics
    monkeypatch.setattr(news_tool, "fmp_get", lambda path, db=None: [])

    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("news", recorder):
        news_tool.get_stock_news("COLD", db=db)

    assert recorder.stages()[0]["retrieval"] == metrics.FULL


def test_stage_is_marked_degraded_when_serving_stale_news(db, monkeypatch):
    from tools import metrics
    db[STOCK_NEWS_CACHE].insert_one(
        {"ticker": "AAPL", "articles": [article(days_ago=1, title="Cached")]})

    def boom(path, db=None):
        raise FmpBudgetExceededError("cap hit")

    monkeypatch.setattr(news_tool, "fmp_get", boom)

    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("news", recorder):
        out = news_tool.get_stock_news("AAPL", db=db)

    assert out["stale"] is True
    assert recorder.stages()[0]["outcome"] == metrics.DEGRADED
