"""Router tests against mongomock via dependency override."""
from datetime import datetime, timedelta, timezone

from db import ANALYSES, FINANCIALS_CACHE, TICKER_INDEX, WATCHLIST, WORK_QUEUE


def analysis_doc(ticker, ts, signal="bullish", conviction="high", sector=None):
    return {
        "ticker": ticker, "timestamp": ts, "signal": signal, "conviction": conviction,
        "summary": f"{ticker} looks {signal}", "key_trends": [], "flags": [],
        "sector": sector,
        "position_management": {"stair_step_stops": [1.0]},
        "sub_reports": {"technical": {"overall_technical_signal": signal}},
    }


NOW = datetime.now(timezone.utc)


# --- analysis ----------------------------------------------------------------

def test_feed_pagination_and_projection(client, db):
    for i in range(25):
        db[ANALYSES].insert_one(analysis_doc(f"T{i:02d}", NOW - timedelta(hours=i)))

    r = client.get("/analysis/feed").json()
    assert r["total"] == 25
    assert len(r["items"]) == 20
    assert r["items"][0]["ticker"] == "T00"  # newest first
    assert "sub_reports" not in r["items"][0]

    page2 = client.get("/analysis/feed?page=2").json()
    assert len(page2["items"]) == 5


def test_feed_filters(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAA", NOW, signal="bullish"))
    db[ANALYSES].insert_one(analysis_doc("BBB", NOW, signal="bearish"))

    items = client.get("/analysis/feed?signal=bearish").json()["items"]
    assert [i["ticker"] for i in items] == ["BBB"]


def test_feed_ticker_filter_substring_case_insensitive(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("APP", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))

    items = client.get("/analysis/feed?ticker=ap").json()["items"]
    assert sorted(i["ticker"] for i in items) == ["AAPL", "APP"]

    # regex metacharacters in input must be escaped, not interpreted
    assert client.get("/analysis/feed?ticker=A.P").json()["items"] == []


def test_ticker_history(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=1)))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))

    r = client.get("/analysis/aapl").json()
    assert len(r) == 2
    assert r[0]["sub_reports"]  # full docs include sub_reports


def test_sector_endpoint_latest_per_ticker(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=2), signal="bearish", sector="Technology"))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish", sector="Technology"))

    r = client.get("/analysis/sector/Technology").json()
    assert len(r) == 1
    assert r[0]["signal"] == "bullish"


# --- queue -------------------------------------------------------------------

def test_enqueue_registers_and_creates_job(client, db):
    r = client.post("/queue/nvda").json()
    assert r["status"] == "enqueued"
    assert db[WORK_QUEUE].find_one({"ticker": "NVDA"})["status"] == "pending"
    reg = db[TICKER_INDEX].find_one({"ticker": "NVDA"})
    assert reg["status"] == "active" and "manual" in reg["sources"]


def test_enqueue_idempotent(client, db):
    first = client.post("/queue/NVDA").json()
    second = client.post("/queue/NVDA").json()
    assert second["status"] == "already_queued"
    assert second["job_id"] == first["job_id"]
    assert db[WORK_QUEUE].count_documents({"ticker": "NVDA"}) == 1


def test_enqueue_reactivates_removed_ticker(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "GONE", "status": "removed_from_market",
                                 "delisted_at": NOW, "delisted_reason": "x", "sources": []})
    client.post("/queue/GONE")
    reg = db[TICKER_INDEX].find_one({"ticker": "GONE"})
    assert reg["status"] == "active"
    assert "delisted_at" not in reg


def test_run_all_sweeps_active_only(client, db):
    for t, status in [("AAA", "active"), ("BBB", "active"), ("CCC", "disabled"),
                      ("DDD", "removed_from_market")]:
        db[TICKER_INDEX].insert_one({"ticker": t, "status": status, "sources": []})
    db[WORK_QUEUE].insert_one({"ticker": "BBB", "status": "pending", "created_at": NOW,
                               "updated_at": NOW})

    r = client.post("/queue/all").json()
    assert r["enqueued"] == ["AAA"]
    assert r["already_queued"] == ["BBB"]
    assert r["universe_size"] == 2


def test_queue_status(client, db):
    db[WORK_QUEUE].insert_one({"ticker": "AAA", "status": "pending", "created_at": NOW, "updated_at": NOW})
    db[WORK_QUEUE].insert_one({"ticker": "BBB", "status": "running", "created_at": NOW, "updated_at": NOW})
    db[WORK_QUEUE].insert_one({"ticker": "CCC", "status": "done", "created_at": NOW, "updated_at": NOW})

    r = client.get("/queue").json()
    assert r["pending_count"] == 1 and r["running_count"] == 1
    assert r["pending"][0]["ticker"] == "AAA"


# --- watchlist ---------------------------------------------------------------

def test_watchlist_add_get_remove(client, db):
    added = client.post("/watchlist/aapl", json={"name": "Apple", "sector": "Technology"}).json()
    assert added["ticker"] == "AAPL"

    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    listed = client.get("/watchlist").json()
    assert listed["count"] == 1
    assert listed["items"][0]["last_signal"] == "bullish"
    assert db[TICKER_INDEX].find_one({"ticker": "AAPL"})["sources"] == ["watchlist"]

    assert client.post("/watchlist/AAPL").status_code == 409
    assert client.delete("/watchlist/AAPL").json() == {"removed": "AAPL"}
    assert client.delete("/watchlist/AAPL").status_code == 404


# --- stocks / tickers --------------------------------------------------------

def test_search_enriches_with_latest_signal(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "name": "Apple Inc.", "status": "active"})
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))

    r = client.get("/stocks/search?q=aa").json()
    assert r[0]["ticker"] == "AAPL"
    assert r[0]["signal"] == "bullish"


def test_get_ticker_record_and_404(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "name": "Apple Inc.", "status": "active"})
    assert client.get("/stocks/AAPL").json()["name"] == "Apple Inc."
    assert client.get("/stocks/ZZZZ").status_code == 404


def test_financials_endpoint(client, db):
    db[FINANCIALS_CACHE].insert_one({"ticker": "AAPL", "data": {"income_annual": [{"revenue": 1}]},
                                     "fetched_at": NOW})
    assert client.get("/stocks/AAPL/financials").json()["income_annual"] == [{"revenue": 1}]
    assert client.get("/stocks/MSFT/financials").status_code == 404


def test_signals_endpoint(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    r = client.get("/stocks/AAPL/signals").json()
    assert r["ticker"] == "AAPL"
    assert r["technical"]["overall_technical_signal"] == "bullish"
    assert client.get("/stocks/MSFT/signals").status_code == 404


def test_tickers_admin_list_patch_delete(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})
    db[TICKER_INDEX].insert_one({"ticker": "MSFT", "status": "disabled"})
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[WATCHLIST].insert_one({"ticker": "AAPL"})

    listed = client.get("/tickers").json()
    assert listed["total"] == 2 and listed["active_count"] == 1 and listed["disabled_count"] == 1

    patched = client.patch("/tickers/AAPL", json={"status": "disabled"}).json()
    assert patched["status"] == "disabled"

    deleted = client.delete("/tickers/AAPL").json()
    assert deleted == {"deleted": "AAPL"}
    assert db[ANALYSES].count_documents({"ticker": "AAPL"}) == 0
    assert db[WATCHLIST].count_documents({"ticker": "AAPL"}) == 0
    assert client.delete("/tickers/AAPL").status_code == 404


def test_bulk_add(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "disabled", "sources": []})
    r = client.post("/tickers/bulk", json={"tickers": "aapl msft,nvda\n123bad aapl"}).json()

    assert r["added"] == ["MSFT", "NVDA"]
    assert r["already_existed"] == ["AAPL"]
    assert r["invalid"] == ["123BAD"]
    assert db[TICKER_INDEX].find_one({"ticker": "AAPL"})["status"] == "active"
