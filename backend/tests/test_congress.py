"""GET/POST /congress/* — read-only over congress_trades (US4) plus refresh.
Spec: specs/028-dashboard-tweaks-batch US4.
Contract: specs/028-dashboard-tweaks-batch/contracts/congress-api.md
"""
from datetime import datetime, timedelta, timezone

from db import CONGRESS_TRADES, WORK_QUEUE

NOW = datetime.now(timezone.utc)


def trade_doc(
    trade_id, ticker="AAPL", politician="Jane Doe", person_id="D1", chamber="senate",
    transaction_type="Purchase", amount_range="$1,001 - $15,000",
    disclosure_date=None, transaction_date=None,
):
    return {
        "trade_id": trade_id, "chamber": chamber, "person_id": person_id,
        "politician": politician, "district": "AR", "owner": "Self",
        "ticker": ticker, "asset_description": f"{ticker} Inc" if ticker else "Some Fund",
        "asset_type": "Stock" if ticker else "Fund",
        "transaction_type": transaction_type, "amount_range": amount_range,
        "transaction_date": transaction_date or "2026-01-01",
        "disclosure_date": disclosure_date or (NOW - timedelta(days=5)).date().isoformat(),
        "link": None, "source": "fmp", "collected_at": NOW,
    }


# --- GET /congress/trades ------------------------------------------------------

def test_trades_lists_newest_disclosure_first(client, db):
    db[CONGRESS_TRADES].insert_many([
        trade_doc("t1", ticker="AAPL", disclosure_date="2026-08-01"),
        trade_doc("t2", ticker="MSFT", disclosure_date="2026-08-15"),
    ])
    r = client.get("/congress/trades").json()
    assert [i["ticker"] for i in r["items"]] == ["MSFT", "AAPL"]
    assert r["total"] == 2


def test_trades_ticker_filter_is_substring_case_insensitive(client, db):
    db[CONGRESS_TRADES].insert_many([
        trade_doc("t1", ticker="AAPL"), trade_doc("t2", ticker="MSFT"),
    ])
    items = client.get("/congress/trades?ticker=aa").json()["items"]
    assert [i["ticker"] for i in items] == ["AAPL"]


def test_trades_politician_filter_is_substring_case_insensitive(client, db):
    db[CONGRESS_TRADES].insert_many([
        trade_doc("t1", politician="Jane Doe"), trade_doc("t2", politician="John Smith"),
    ])
    items = client.get("/congress/trades?politician=jane").json()["items"]
    assert [i["politician"] for i in items] == ["Jane Doe"]


def test_trades_politician_filter_matches_exact_person_id(client, db):
    """R7 — person_id is stable per member; an exact-looking id should match
    on identity rather than falling only to substring-on-name."""
    db[CONGRESS_TRADES].insert_many([
        trade_doc("t1", politician="Jane Doe", person_id="D000001"),
        trade_doc("t2", politician="Jane Doeling", person_id="D000002"),
    ])
    items = client.get("/congress/trades?politician=D000001").json()["items"]
    assert [i["person_id"] for i in items] == ["D000001"]


def test_trades_both_filters_combine(client, db):
    db[CONGRESS_TRADES].insert_many([
        trade_doc("t1", ticker="AAPL", politician="Jane Doe"),
        trade_doc("t2", ticker="AAPL", politician="John Smith"),
        trade_doc("t3", ticker="MSFT", politician="Jane Doe"),
    ])
    items = client.get("/congress/trades?ticker=AAPL&politician=Jane").json()["items"]
    assert len(items) == 1 and items[0]["politician"] == "Jane Doe"


def test_trades_chamber_filter(client, db):
    db[CONGRESS_TRADES].insert_many([
        trade_doc("t1", chamber="senate"), trade_doc("t2", chamber="house"),
    ])
    items = client.get("/congress/trades?chamber=house").json()["items"]
    assert [i["chamber"] for i in items] == ["house"]


def test_trades_limit_cap(client, db):
    db[CONGRESS_TRADES].insert_many([trade_doc(f"t{i}") for i in range(10)])
    assert len(client.get("/congress/trades?limit=3").json()["items"]) == 3


def test_trades_empty_collection_returns_200_empty_list(client, db):
    r = client.get("/congress/trades").json()
    assert r == {"items": [], "total": 0, "as_of": None}


def test_trades_null_ticker_row_included(client, db):
    db[CONGRESS_TRADES].insert_one(trade_doc("t1", ticker=None))
    items = client.get("/congress/trades").json()["items"]
    assert items[0]["ticker"] is None


# --- GET /congress/summary ------------------------------------------------------

def test_summary_ranks_most_bought_by_count(client, db):
    recent = (NOW - timedelta(days=5)).date().isoformat()
    db[CONGRESS_TRADES].insert_many([
        trade_doc("t1", ticker="AAPL", disclosure_date=recent, transaction_type="Purchase"),
        trade_doc("t2", ticker="AAPL", disclosure_date=recent, transaction_type="Purchase"),
        trade_doc("t3", ticker="NVDA", disclosure_date=recent, transaction_type="Purchase"),
    ])
    r = client.get("/congress/summary").json()
    assert r["most_bought"][0] == {"ticker": "AAPL", "buy_count": 2}
    assert r["window_days"] == 90


def test_summary_high_dollar_shows_bracket_text_not_a_number(client, db):
    recent = (NOW - timedelta(days=5)).date().isoformat()
    db[CONGRESS_TRADES].insert_one(
        trade_doc("t1", disclosure_date=recent, amount_range="$250,001 - $500,000")
    )
    r = client.get("/congress/summary").json()
    assert r["high_dollar"][0]["amount_range"] == "$250,001 - $500,000"
    assert r["high_dollar_threshold"] == "$100,001"


def test_summary_empty_collection_returns_empty_lists_not_error(client, db):
    r = client.get("/congress/summary").json()
    assert r["most_bought"] == []
    assert r["high_dollar"] == []


# --- POST /congress/refresh -----------------------------------------------------

def test_refresh_enqueues_job(client, db):
    r = client.post("/congress/refresh").json()
    assert r["status"] == "enqueued"
    assert db[WORK_QUEUE].find_one({"job_type": "congress_trades_pull"})["status"] == "pending"


def test_refresh_dedupes_active_job(client, db):
    first = client.post("/congress/refresh").json()
    second = client.post("/congress/refresh").json()
    assert second["status"] == "already_queued"
    assert second["job_id"] == first["job_id"]
