"""GET /analysis/feed ordering contract. Spec: specs/037-stocks-conviction-and-activity;
contracts/feed-ordering.md.

(conviction_rank desc, ticker asc) is a *total* order because `analyses`
carries a unique index on `ticker` — these tests are the regression net for
"Load more" never reflowing already-rendered tiles (FR-003).
"""
from datetime import datetime, timezone

from db import ANALYSES, TICKER_INDEX

NOW = datetime.now(timezone.utc)


def analysis_doc(ticker, conviction="high", conviction_rank=3, signal="bullish", sector=None):
    doc = {
        "ticker": ticker, "timestamp": NOW, "signal": signal, "conviction": conviction,
        "summary": f"{ticker} looks {signal}", "key_trends": [], "flags": [],
        "sector": sector, "position_management": {"stair_step_stops": [1.0]},
        "sub_reports": {"technical": {"overall_technical_signal": signal}},
    }
    if conviction_rank is not None:
        doc["conviction_rank"] = conviction_rank
    return doc


# --- test 1: rank-descending order -------------------------------------------

def test_items_come_back_conviction_rank_descending(client, db):
    db[ANALYSES].insert_one(analysis_doc("LOWX", conviction="low", conviction_rank=1))
    db[ANALYSES].insert_one(analysis_doc("HIGHX", conviction="high", conviction_rank=3))
    db[ANALYSES].insert_one(analysis_doc("MEDX", conviction="medium", conviction_rank=2))

    items = client.get("/analysis/feed").json()["items"]
    assert [i["ticker"] for i in items] == ["HIGHX", "MEDX", "LOWX"]


# --- test 2: ticker-ascending among a shared rank ----------------------------

def test_same_rank_tickers_sort_ticker_ascending(client, db):
    for t in ("MSFT", "AVB", "GOOG", "AAPL"):
        db[ANALYSES].insert_one(analysis_doc(t, conviction="high", conviction_rank=3))

    items = client.get("/analysis/feed").json()["items"]
    assert [i["ticker"] for i in items] == ["AAPL", "AVB", "GOOG", "MSFT"]


# --- test 3: missing conviction_rank sorts last ------------------------------

def test_missing_conviction_rank_sorts_after_all_ranked_documents(client, db):
    db[ANALYSES].insert_one(analysis_doc("LEGACY", conviction="high", conviction_rank=None))
    db[ANALYSES].insert_one(analysis_doc("LOWX", conviction="low", conviction_rank=1))

    items = client.get("/analysis/feed").json()["items"]
    assert [i["ticker"] for i in items] == ["LOWX", "LEGACY"]


# --- test 4: page boundary never reflows -------------------------------------

def test_page_boundary_never_reflows_a_previously_shown_item(client, db):
    # 25 tickers, ranks spread across high/medium/low so ties don't mask a
    # real page-boundary regression.
    ranks = {"high": 3, "medium": 2, "low": 1}
    for i in range(25):
        level = ("high", "medium", "low")[i % 3]
        db[ANALYSES].insert_one(analysis_doc(f"T{i:02d}", conviction=level, conviction_rank=ranks[level]))

    page1 = client.get("/analysis/feed?page=1&page_size=10").json()["items"]
    page2 = client.get("/analysis/feed?page=2&page_size=10").json()["items"]

    last_page1 = (page1[-1]["conviction"], page1[-1]["ticker"])
    for item in page2:
        # every page-2 item's rank must be <= the last page-1 item's rank,
        # and if equal rank, its ticker must sort at-or-after the boundary
        assert ranks[item["conviction"]] <= ranks[last_page1[0]]
        if ranks[item["conviction"]] == ranks[last_page1[0]]:
            assert item["ticker"] > last_page1[1]

    # and re-fetching page 1 with a larger page size never moves an item that
    # was already on page 1 out of the first 10 positions
    combined = client.get("/analysis/feed?page=1&page_size=20").json()["items"]
    assert [i["ticker"] for i in page1] == [i["ticker"] for i in combined[:10]]


# --- test 5: ordering survives every existing filter -------------------------

def test_ordering_survives_sector_filter(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "MSFT", "status": "active", "sector": "Tech"})
    db[TICKER_INDEX].insert_one({"ticker": "AVB", "status": "active", "sector": "Tech"})
    db[TICKER_INDEX].insert_one({"ticker": "XOM", "status": "active", "sector": "Energy"})
    db[ANALYSES].insert_one(analysis_doc("MSFT", conviction="low", conviction_rank=1))
    db[ANALYSES].insert_one(analysis_doc("AVB", conviction="high", conviction_rank=3))
    db[ANALYSES].insert_one(analysis_doc("XOM", conviction="high", conviction_rank=3))

    items = client.get("/analysis/feed?sector=Tech").json()["items"]
    assert [i["ticker"] for i in items] == ["AVB", "MSFT"]


def test_ordering_survives_signal_filter(client, db):
    db[ANALYSES].insert_one(analysis_doc("LOWX", signal="bearish", conviction="low", conviction_rank=1))
    db[ANALYSES].insert_one(analysis_doc("HIGHX", signal="bearish", conviction="high", conviction_rank=3))
    db[ANALYSES].insert_one(analysis_doc("SKIP", signal="bullish", conviction="high", conviction_rank=3))

    items = client.get("/analysis/feed?signal=bearish").json()["items"]
    assert [i["ticker"] for i in items] == ["HIGHX", "LOWX"]


# --- test 6: conviction filter stays ticker-ascending ------------------------

def test_conviction_filter_keeps_ticker_ascending_order(client, db):
    for t in ("ZETA", "ALPHA", "MU"):
        db[ANALYSES].insert_one(analysis_doc(t, conviction="high", conviction_rank=3))
    db[ANALYSES].insert_one(analysis_doc("SKIP", conviction="medium", conviction_rank=2))

    items = client.get("/analysis/feed?conviction=high").json()["items"]
    assert [i["ticker"] for i in items] == ["ALPHA", "MU", "ZETA"]
