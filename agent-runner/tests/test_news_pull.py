"""Unit tests for tools/news_pull.py — network fully faked.
Spec: specs/035-chat-and-news-upgrade US2 (FR-001..FR-004, FR-024);
contracts/news-api.md (field mapping table); research.md R7 (backfill
pacing), R9 (url dedup).
"""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest
import requests

import llm
from tools import news_pull
from tools.db import DATASET_META, NEWS_ARTICLES, NEWS_TAGS
from tools.fmp_client import FmpBudgetExceededError


@pytest.fixture
def db():
    return mongomock.MongoClient()["news_pull_test"]


@pytest.fixture(autouse=True)
def fake_ollama(monkeypatch):
    """036 — run_market_news_pull now runs a paced enrichment batch after the
    pull. Default every test to a fast, offline embed/tag stub so the existing
    pull-mechanics tests never touch Ollama; the enrichment-specific tests
    below override these as needed."""
    def fake_embed(texts, client=None):
        n = 1 if isinstance(texts, str) else len(texts)
        return [[1.0, 0.0, 0.0]] * n

    monkeypatch.setattr(llm, "embed", fake_embed)
    monkeypatch.setattr(llm, "generate_json", lambda **kw: {"tags": ["markets"]})


def _dt(days_ago: float) -> str:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return when.strftime("%Y-%m-%d %H:%M:%S")


def general_row(**overrides) -> dict:
    row = {
        "symbol": None, "publishedDate": _dt(0.1), "publisher": "CNBC",
        "title": "Ukraine is targeting Russia's retail giants",
        "image": "https://images.example.com/a.jpg", "site": "cnbc.com",
        "text": "Ukraine's drone campaign is expanding...",
        "url": "https://www.cnbc.com/2026/08/25/ukraine-war-russia",
    }
    row.update(overrides)
    return row


def stock_row(**overrides) -> dict:
    row = {
        "symbol": "CC", "publishedDate": _dt(0.1), "publisher": "PRNewsWire",
        "title": "Chemours Publishes 2025 Sustainability Report",
        "image": "https://images.example.com/cc.jpg", "site": "prnewswire.com",
        "text": "WILMINGTON, Del., Aug. 25, 2026 /PRNewswire/ -- The Chemours Company...",
        "url": "https://www.prnewswire.com/news-releases/chemours",
    }
    row.update(overrides)
    return row


def fmp_article_row(**overrides) -> dict:
    row = {
        "title": "Extra Space Storage (NYSE:EXR): Analyst Ratings, Price Targets",
        "date": _dt(0.1),
        "content": "<ul> <li>Most analysts maintain a <strong>Hold</strong> rating</li> </ul>",
        "tickers": "NYSE:EXR",
        "image": "https://portal.example.com/exr.jpeg",
        "link": "https://financialmodelingprep.com/market-news/extra-space-storage-exr",
        "author": "Tony Dante",
        "site": "Financial Modeling Prep",
    }
    row.update(overrides)
    return row


# --- per-feed field mapping (contracts/news-api.md) -------------------------

def test_general_feed_maps_to_stored_shape_with_no_tickers():
    article = news_pull._normalize(general_row(), "general")
    assert article["source_type"] == "general"
    assert article["url"] == "https://www.cnbc.com/2026/08/25/ukraine-war-russia"
    assert article["publisher"] == "CNBC"
    assert article["tickers"] == []
    assert article["body_html"] is None
    assert article["body_text"] == "Ukraine's drone campaign is expanding..."


def test_stock_feed_maps_symbol_into_a_single_element_tickers_list():
    article = news_pull._normalize(stock_row(), "stock")
    assert article["source_type"] == "stock"
    assert article["tickers"] == ["CC"]
    assert article["publisher"] == "PRNewsWire"


def test_fmp_article_feed_maps_link_to_url():
    article = news_pull._normalize(fmp_article_row(), "fmp_article")
    assert article["url"] == "https://financialmodelingprep.com/market-news/extra-space-storage-exr"


def test_fmp_article_feed_strips_html_content_into_body_text():
    article = news_pull._normalize(fmp_article_row(), "fmp_article")
    assert article["body_html"] == "<ul> <li>Most analysts maintain a <strong>Hold</strong> rating</li> </ul>"
    assert article["body_text"] == "Most analysts maintain a Hold rating"


def test_fmp_article_feed_parses_exchange_prefixed_tickers():
    article = news_pull._normalize(fmp_article_row(tickers="NYSE:EXR,NASDAQ:AAPL"), "fmp_article")
    assert article["tickers"] == ["EXR", "AAPL"]


def test_fmp_article_feed_uses_author_as_publisher():
    article = news_pull._normalize(fmp_article_row(), "fmp_article")
    assert article["publisher"] == "Tony Dante"
    assert article["author"] == "Tony Dante"


# --- drop rules (data-model.md validation rules) ----------------------------

def test_article_missing_title_is_dropped():
    assert news_pull._normalize(general_row(title=""), "general") is None


def test_article_missing_url_is_dropped():
    assert news_pull._normalize(general_row(url=""), "general") is None


def test_article_with_unparseable_published_date_is_dropped():
    assert news_pull._normalize(general_row(publishedDate="not-a-date"), "general") is None


def test_article_with_missing_published_date_is_dropped():
    assert news_pull._normalize(general_row(publishedDate=None), "general") is None


# --- run_market_news_pull: single-page steady state -------------------------

def test_run_ingests_all_three_feeds(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        if path.startswith("news/general-latest"):
            return [general_row()]
        if path.startswith("news/stock-latest"):
            return [stock_row()]
        if path.startswith("fmp-articles"):
            return [fmp_article_row()]
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(news_pull, "fmp_get", fake_fmp_get)
    count = news_pull.run_market_news_pull(db)

    assert count == 3
    stored_types = {doc["source_type"] for doc in db[NEWS_ARTICLES].find()}
    assert stored_types == {"general", "stock", "fmp_article"}


def test_rerun_upserts_on_url_without_duplicating(db, monkeypatch):
    monkeypatch.setattr(news_pull, "fmp_get", lambda path, db=None: [general_row()])
    news_pull._pull_feed(db, "general", "news/general-latest")
    news_pull._pull_feed(db, "general", "news/general-latest")

    assert db[NEWS_ARTICLES].count_documents({}) == 1


# --- backfill pacing (research.md R7) ---------------------------------------

def test_backfill_pages_backward_until_the_cutoff_is_reached(db, monkeypatch):
    # Page 0: a full, recent page (not short, so paging continues). Page 1:
    # straddles the 30-day cutoff (one fresh, one stale) — paging should stop
    # here, the stale one dropped, not stored.
    page0 = [general_row(url=f"https://x/p0-{i}", publishedDate=_dt(1)) for i in range(news_pull.PAGE_SIZE)]
    page1 = [
        general_row(url="https://x/b", publishedDate=_dt(29)),
        general_row(url="https://x/c", publishedDate=_dt(31)),
    ]

    def fake_fmp_get(path, db=None):
        if "page=0" in path:
            return page0
        if "page=1" in path:
            return page1
        raise AssertionError(f"paging should have stopped before {path}")

    monkeypatch.setattr(news_pull, "fmp_get", fake_fmp_get)
    count = news_pull._pull_feed(db, "general", "news/general-latest")

    assert count == news_pull.PAGE_SIZE + 1  # all of page0 + "b" from page1 — "c" is past the cutoff
    stored_urls = {doc["url"] for doc in db[NEWS_ARTICLES].find()}
    assert "https://x/b" in stored_urls
    assert "https://x/c" not in stored_urls
    checkpoint = db[DATASET_META].find_one({"dataset": "news_general"})
    assert checkpoint["backfill_complete"] is True


def test_a_short_page_also_marks_backfill_complete(db, monkeypatch):
    monkeypatch.setattr(news_pull, "fmp_get", lambda path, db=None: [general_row()])
    news_pull._pull_feed(db, "general", "news/general-latest")

    checkpoint = db[DATASET_META].find_one({"dataset": "news_general"})
    assert checkpoint["backfill_complete"] is True


def test_steady_state_check_with_a_full_page_does_not_revoke_completeness(db, monkeypatch):
    """Found live against real FMP data (research.md R7's assumption didn't
    hold): general-latest/fmp-articles always return a full page of "latest"
    items, so a naive steady-state single-page check would see a full,
    non-cutoff page every time and (incorrectly) conclude the backfill was
    never finished — re-entering 20-page backfill mode on every future run
    against a feed that never runs dry, and never converging."""
    db[DATASET_META].insert_one({
        "dataset": "news_general", "backfill_complete": True, "next_page": 0,
        "oldest_published_at": None,
    })
    # Steady-state check sees a FULL page (>= PAGE_SIZE, none past cutoff) —
    # exactly the shape that flips the old buggy logic back to "incomplete".
    full_page = [general_row(url=f"https://x/{i}") for i in range(news_pull.PAGE_SIZE)]
    monkeypatch.setattr(news_pull, "fmp_get", lambda path, db=None: full_page)

    news_pull._pull_feed(db, "general", "news/general-latest")

    checkpoint = db[DATASET_META].find_one({"dataset": "news_general"})
    assert checkpoint["backfill_complete"] is True


def test_backfill_mode_still_correctly_stays_incomplete_when_the_page_cap_is_exhausted(db, monkeypatch):
    """Companion to the steady-state case above: when genuinely still
    backfilling (not yet complete), exhausting the per-run page cap without
    a stopping signal must still resume next run, not flip to complete."""
    full_page = [general_row(url=f"https://x/{i}") for i in range(news_pull.PAGE_SIZE)]
    monkeypatch.setattr(news_pull, "fmp_get", lambda path, db=None: full_page)

    news_pull._pull_feed(db, "general", "news/general-latest")

    checkpoint = db[DATASET_META].find_one({"dataset": "news_general"})
    assert checkpoint["backfill_complete"] is False
    assert checkpoint["next_page"] == news_pull.MAX_PAGES_PER_RUN


# --- budget guard (constitution IV) -----------------------------------------

def test_budget_exceeded_mid_pull_returns_partial_count_without_raising(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        if "page=0" in path:
            return [general_row(url=f"https://x/p0-{i}") for i in range(news_pull.PAGE_SIZE)]
        raise FmpBudgetExceededError("daily cap exceeded")

    monkeypatch.setattr(news_pull, "fmp_get", fake_fmp_get)
    # No exception — a blown budget is an expected daily condition, not a job failure.
    count = news_pull._pull_feed(db, "general", "news/general-latest")

    assert count == news_pull.PAGE_SIZE  # page 0 landed in full before the budget hit
    checkpoint = db[DATASET_META].find_one({"dataset": "news_general"})
    assert checkpoint["backfill_complete"] is False
    assert checkpoint["next_page"] == 1


def test_run_market_news_pull_never_raises_when_one_feed_is_budget_exhausted(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        if path.startswith("news/general-latest"):
            raise FmpBudgetExceededError("cap")
        if path.startswith("news/stock-latest"):
            return [stock_row()]
        if path.startswith("fmp-articles"):
            return [fmp_article_row()]
        raise AssertionError(path)

    monkeypatch.setattr(news_pull, "fmp_get", fake_fmp_get)
    count = news_pull.run_market_news_pull(db)  # must not raise

    assert count == 2  # stock + fmp_article landed; general contributed 0


def test_a_network_failure_mid_pull_is_caught_like_a_budget_exceeded(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(news_pull, "fmp_get", fake_fmp_get)
    count = news_pull._pull_feed(db, "general", "news/general-latest")

    assert count == 0
    checkpoint = db[DATASET_META].find_one({"dataset": "news_general"})
    assert checkpoint["backfill_complete"] is False


# --- resumability (research.md R7) ------------------------------------------

def test_a_second_run_resumes_from_the_checkpoint_rather_than_re_paging_from_page_zero(db, monkeypatch):
    requested_pages: list[int] = []

    def fake_fmp_get(path, db=None):
        page = int(path.split("page=")[1].split("&")[0])
        requested_pages.append(page)
        if page == 0:
            return [general_row(url="https://x/a") for _ in range(news_pull.PAGE_SIZE)]
        raise FmpBudgetExceededError("cap")  # every subsequent page hits budget in this test

    monkeypatch.setattr(news_pull, "fmp_get", fake_fmp_get)
    news_pull._pull_feed(db, "general", "news/general-latest")  # first run: page 0 ok, page 1 hits budget

    assert requested_pages == [0, 1]

    news_pull._pull_feed(db, "general", "news/general-latest")  # second run

    # The second run's first request must be page 1 (the checkpoint), not
    # page 0 again — re-paging from the start would waste budget re-fetching
    # content already ingested on every single run.
    assert requested_pages[2] == 1


# --- 036 enrichment pass (research.md R7; data-model.md §1/§2) -------------

def test_enrichment_runs_for_a_newly_ingested_article(db, monkeypatch):
    monkeypatch.setattr(news_pull, "fmp_get", lambda path, db=None: [general_row(url="https://x/new")])

    news_pull.run_market_news_pull(db)

    doc = db[NEWS_ARTICLES].find_one({"url": "https://x/new"})
    assert doc["embedding"] == [1.0, 0.0, 0.0]
    assert doc["embedding_model"] == news_pull.settings.ollama_embed_model
    assert doc["embedding_dim"] == 3
    assert doc["tags"] == ["markets"]
    # tag fed into the registry
    assert db[NEWS_TAGS].find_one({"_id": "markets"})["count"] == 1
    # checkpoint written
    assert db[DATASET_META].find_one({"dataset": news_pull.ENRICH_CHECKPOINT})["remaining"] == 0


def test_enrich_pending_respects_the_per_run_batch_and_reports_remaining(db, monkeypatch):
    monkeypatch.setattr(news_pull.settings, "news_enrich_batch_per_run", 2)
    now = datetime.now(timezone.utc)
    db[NEWS_ARTICLES].insert_many([
        {"url": f"https://x/{i}", "title": f"t{i}", "body_text": "b",
         "published_at": now - timedelta(hours=i), "tags": []}
        for i in range(5)
    ])

    enriched = news_pull.enrich_pending(db)

    assert enriched == 2
    assert db[NEWS_ARTICLES].count_documents({"embedding": {"$exists": True}}) == 2
    checkpoint = db[DATASET_META].find_one({"dataset": news_pull.ENRICH_CHECKPOINT})
    assert checkpoint["enriched_last_run"] == 2
    assert checkpoint["remaining"] == 3
    # newest-first: the two most recent (i=0, i=1) were the ones enriched
    assert db[NEWS_ARTICLES].find_one({"url": "https://x/0"}).get("embedding") is not None
    assert db[NEWS_ARTICLES].find_one({"url": "https://x/4"}).get("embedding") is None


def test_enrich_pending_reprocesses_stale_model_articles(db, monkeypatch):
    now = datetime.now(timezone.utc)
    db[NEWS_ARTICLES].insert_one({
        "url": "https://x/stale", "title": "t", "body_text": "b", "published_at": now,
        "embedding": [0.0], "embedding_model": "old-model", "tags": ["old"],
    })

    news_pull.enrich_pending(db)

    doc = db[NEWS_ARTICLES].find_one({"url": "https://x/stale"})
    assert doc["embedding_model"] == news_pull.settings.ollama_embed_model
    assert doc["embedding"] == [1.0, 0.0, 0.0]


def test_a_failing_enrich_call_does_not_abort_the_pull(db, monkeypatch):
    def fake_fmp_get(path, db=None):
        if path.startswith("news/general-latest"):
            return [general_row(url="https://x/new")]
        return []

    monkeypatch.setattr(news_pull, "fmp_get", fake_fmp_get)

    def boom(texts, client=None):
        raise llm.LLMError("ollama down")

    monkeypatch.setattr(llm, "embed", boom)

    # Must not raise — the pull is still a successful job.
    count = news_pull.run_market_news_pull(db)

    assert count == 1
    doc = db[NEWS_ARTICLES].find_one({"url": "https://x/new"})
    assert "embedding" not in doc  # enrichment was skipped, article still stored
    checkpoint = db[DATASET_META].find_one({"dataset": news_pull.ENRICH_CHECKPOINT})
    assert checkpoint["enriched_last_run"] == 0
    assert checkpoint["remaining"] == 1
