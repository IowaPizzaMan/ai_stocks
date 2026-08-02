"""Earnings router tests — fetch layer faked, mongomock via conftest client."""
from datetime import datetime, timedelta, timezone

from db import EARNINGS_CACHE, EARNINGS_SCANS, TICKER_INDEX, WORK_QUEUE
from routers import earnings as earnings_router

CALENDAR = [
    {"ticker": "BIG", "company": "Big Co", "report_date": "2026-08-04",
     "report_time": "bmo", "eps_estimate": 1.0, "revenue_estimate": 1e9,
     "market_cap": 50e9, "sector": "Technology"},
    {"ticker": "MID", "company": "Mid Co", "report_date": "2026-08-05",
     "report_time": "amc", "eps_estimate": 0.5, "revenue_estimate": 5e8,
     "market_cap": 5e9, "sector": "Energy"},
]


# --- GET /earnings/calendar -----------------------------------------------------

def test_calendar_returns_registers_and_enqueues(client, db, monkeypatch):
    monkeypatch.setattr(earnings_router.earnings_data, "get_earnings_calendar",
                        lambda days_ahead, db: CALENDAR)

    r = client.get("/earnings/calendar?days=5")
    assert r.status_code == 200
    assert [e["ticker"] for e in r.json()] == ["BIG", "MID"]

    big = db[TICKER_INDEX].find_one({"ticker": "BIG"})
    assert big["status"] == "active"
    assert big["name"] == "Big Co" and big["sector"] == "Technology"
    assert "earnings_calendar" in big["sources"]
    assert db[WORK_QUEUE].count_documents({"status": "pending"}) == 2

    # repeat call: no duplicate jobs
    client.get("/earnings/calendar?days=5")
    assert db[WORK_QUEUE].count_documents({"status": "pending"}) == 2


def test_calendar_skips_delisted_tickers(client, db, monkeypatch):
    monkeypatch.setattr(earnings_router.earnings_data, "get_earnings_calendar",
                        lambda days_ahead, db: CALENDAR)
    db[TICKER_INDEX].insert_one({"ticker": "BIG", "status": "removed_from_market"})

    client.get("/earnings/calendar")

    assert db[WORK_QUEUE].find_one({"ticker": "BIG"}) is None
    assert db[TICKER_INDEX].find_one({"ticker": "BIG"})["status"] == "removed_from_market"
    assert db[WORK_QUEUE].find_one({"ticker": "MID"}) is not None


def test_calendar_serves_from_shared_cache(client, db, monkeypatch):
    """The real fetch layer must honor a cache doc written by the agent-runner."""
    db[EARNINGS_CACHE].insert_one({
        "type": "calendar", "days": 7, "data": CALENDAR,
        "fetched_at": datetime.now(timezone.utc) - timedelta(hours=1),
    })
    monkeypatch.setattr(earnings_router.earnings_data, "_finnhub_get",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should be cached")))

    r = client.get("/earnings/calendar")
    assert [e["ticker"] for e in r.json()] == ["BIG", "MID"]


# --- scan lifecycle ---------------------------------------------------------------

def test_scan_trigger_and_poll(client, db):
    r = client.post("/earnings/scan", json={"days_ahead": 3}).json()
    scan_id = r["scan_id"]
    assert r["status"] == "pending"

    doc = db[EARNINGS_SCANS].find_one({"scan_id": scan_id})
    assert doc["days_ahead"] == 3 and doc["status"] == "pending"

    # simulate the agent-runner completing it
    db[EARNINGS_SCANS].update_one(
        {"scan_id": scan_id},
        {"$set": {"status": "complete", "candidates": [{"ticker": "MID", "score": 92}],
                  "total_screened": 2}})

    polled = client.get(f"/earnings/scan/{scan_id}").json()
    assert polled["status"] == "complete"
    assert polled["candidates"][0]["ticker"] == "MID"


def test_scan_default_days_and_missing_scan_404(client, db):
    r = client.post("/earnings/scan").json()
    assert db[EARNINGS_SCANS].find_one({"scan_id": r["scan_id"]})["days_ahead"] == 7
    assert client.get("/earnings/scan/nope").status_code == 404


def test_scan_rejects_out_of_range_days(client):
    assert client.post("/earnings/scan", json={"days_ahead": 60}).status_code == 422


# --- POST /earnings/analyze ---------------------------------------------------------

def test_analyze_enqueues_with_parallel_prefetch(client, db):
    r = client.post("/earnings/analyze", json={"tickers": ["mid", "BIG"]}).json()
    assert r["enqueued"] == ["MID", "BIG"]

    job = db[WORK_QUEUE].find_one({"ticker": "MID"})
    assert job["source"] == "earnings_scanner"
    assert job["parallel_prefetch"] is True
    assert "earnings_scanner" in db[TICKER_INDEX].find_one({"ticker": "MID"})["sources"]


def test_analyze_skips_already_queued(client, db):
    db[WORK_QUEUE].insert_one({"ticker": "MID", "status": "running"})
    r = client.post("/earnings/analyze", json={"tickers": ["MID"]}).json()
    assert r["enqueued"] == []
    assert db[WORK_QUEUE].count_documents({"ticker": "MID"}) == 1


# --- GET /earnings/history/{ticker} ---------------------------------------------------

def test_history_passthrough(client, monkeypatch):
    fake = {"ticker": "NVDA", "quarters": [], "avg_abs_move_pct": 0,
            "beat_rate": 0, "num_quarters": 0}
    monkeypatch.setattr(earnings_router.earnings_data, "get_earnings_history",
                        lambda ticker, db: fake)
    assert client.get("/earnings/history/nvda").json() == fake
