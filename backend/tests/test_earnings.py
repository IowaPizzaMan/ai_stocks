"""Earnings router tests — fetch layer faked, mongomock via conftest client."""
from datetime import datetime, timezone

from db import EARNINGS_SCANS, TICKER_INDEX, WORK_QUEUE
from fmp import FmpBudgetExceededError
from routers import earnings as earnings_router

CALENDAR_PAYLOAD = {
    "entries": [
        {"ticker": "BIG", "company": "Big Co", "report_date": "2026-08-15",
         "eps_estimate": 1.0, "eps_actual": None, "revenue_estimate": 1e9,
         "revenue_actual": None, "eps_surprise_pct": None, "revenue_surprise_pct": None,
         "beat": None, "reporting_state": "upcoming", "market_cap": 50e9,
         "sector": "Technology", "last_updated": "2026-08-17"},
        {"ticker": "MID", "company": "Mid Co", "report_date": "2026-08-16",
         "eps_estimate": 0.5, "eps_actual": None, "revenue_estimate": 5e8,
         "revenue_actual": None, "eps_surprise_pct": None, "revenue_surprise_pct": None,
         "beat": None, "reporting_state": "upcoming", "market_cap": 5e9,
         "sector": "Energy", "last_updated": "2026-08-17"},
    ],
    "total_before_screen": 2,
    "stale": False,
    "fetched_at": datetime.now(timezone.utc).isoformat(),
}


# --- GET /earnings/calendar -----------------------------------------------------

def test_calendar_is_read_only(client, db, monkeypatch):
    """Deliberate deviation from the spec's auto-ingest: pulling the calendar
    must never register tickers or feed the work queue (peak weeks hold
    hundreds of names — the user queues individual rows instead)."""
    monkeypatch.setattr(earnings_router.earnings_data, "get_earnings_calendar",
                        lambda start, end, db: CALENDAR_PAYLOAD)

    r = client.get("/earnings/calendar?from=2026-08-15&to=2026-08-19")
    assert r.status_code == 200
    body = r.json()
    assert [e["ticker"] for e in body["entries"]] == ["BIG", "MID"]
    assert body["total_before_screen"] == 2
    assert body["stale"] is False

    assert db[WORK_QUEUE].count_documents({}) == 0
    assert db[TICKER_INDEX].count_documents({}) == 0


def test_calendar_serves_from_shared_cache(client, monkeypatch):
    """The router must pass through whatever earnings_data returns, including
    the cached-window path — the real caching/dedupe/ordering behavior is
    covered directly in test_earnings_data.py."""
    monkeypatch.setattr(earnings_router.earnings_data, "get_earnings_calendar",
                        lambda start, end, db: CALENDAR_PAYLOAD)

    r = client.get("/earnings/calendar?from=2026-08-15&to=2026-08-19")
    assert [e["ticker"] for e in r.json()["entries"]] == ["BIG", "MID"]


def test_calendar_rejects_inverted_range(client):
    r = client.get("/earnings/calendar?from=2026-08-19&to=2026-08-15")
    assert r.status_code == 422


def test_calendar_rejects_span_over_90_days(client):
    r = client.get("/earnings/calendar?from=2026-01-01&to=2026-12-31")
    assert r.status_code == 422


def test_calendar_budget_exceeded_returns_503(client, monkeypatch):
    def _raise(start, end, db):
        raise FmpBudgetExceededError("cap")

    monkeypatch.setattr(earnings_router.earnings_data, "get_earnings_calendar", _raise)
    r = client.get("/earnings/calendar?from=2026-08-15&to=2026-08-19")
    assert r.status_code == 503


def test_calendar_provider_unavailable_returns_502(client, monkeypatch):
    def _raise(start, end, db):
        raise earnings_router.earnings_data.CalendarUnavailableError("down")

    monkeypatch.setattr(earnings_router.earnings_data, "get_earnings_calendar", _raise)
    r = client.get("/earnings/calendar?from=2026-08-15&to=2026-08-19")
    assert r.status_code == 502


def test_calendar_universe_unavailable_returns_502(client, monkeypatch):
    def _raise(start, end, db):
        raise earnings_router.earnings_data.UniverseUnavailableError("down")

    monkeypatch.setattr(earnings_router.earnings_data, "get_earnings_calendar", _raise)
    r = client.get("/earnings/calendar?from=2026-08-15&to=2026-08-19")
    assert r.status_code == 502


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
