"""Unit tests for queue_worker.py — mongomock + fake crew; no network."""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

import queue_worker
from crew import TickerDelistedError
from tools.db import ANALYSES, TICKER_INDEX, WATCHLIST, WORK_QUEUE


@pytest.fixture
def db():
    return mongomock.MongoClient()["queue_test"]


@pytest.fixture(autouse=True)
def reset_startup():
    queue_worker._started = False
    yield
    queue_worker._started = False


class FakeCrew:
    def __init__(self, result=None, error=None):
        self.result = result or {"ticker": "AAPL", "signal": "bullish", "conviction": "high"}
        self.error = error
        self.ran = []

    def run(self, ticker):
        self.ran.append(ticker)
        if self.error:
            raise self.error
        return dict(self.result)


def enqueue(db, ticker, created_at=None, status="pending"):
    db[WORK_QUEUE].insert_one({
        "ticker": ticker, "status": status,
        "created_at": created_at or datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })


def test_empty_queue_returns_false(db):
    assert queue_worker.claim_and_run_next(db=db, crew=FakeCrew()) is False


def test_successful_job_writes_analysis_and_marks_done(db):
    enqueue(db, "AAPL")
    crew = FakeCrew()

    assert queue_worker.claim_and_run_next(db=db, crew=crew) is True
    assert crew.ran == ["AAPL"]

    job = db[WORK_QUEUE].find_one({"ticker": "AAPL"})
    assert job["status"] == "done"
    assert "completed_at" in job
    assert db[ANALYSES].count_documents({"ticker": "AAPL"}) == 1


def test_fifo_order(db):
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    enqueue(db, "NEWER")
    enqueue(db, "OLDER", created_at=old)
    crew = FakeCrew()

    queue_worker.claim_and_run_next(db=db, crew=crew)
    assert crew.ran == ["OLDER"]


def test_generic_failure_marks_failed_not_delisted(db):
    enqueue(db, "AAPL")
    crew = FakeCrew(error=RuntimeError("network blip"))

    assert queue_worker.claim_and_run_next(db=db, crew=crew) is True
    job = db[WORK_QUEUE].find_one({"ticker": "AAPL"})
    assert job["status"] == "failed"
    assert job["delisted"] is False
    assert "network blip" in job["error"]
    assert db[ANALYSES].count_documents({}) == 0


def test_delisted_marks_registry_and_watchlist(db):
    db[TICKER_INDEX].insert_one({"ticker": "GONE", "status": "active"})
    db[WATCHLIST].insert_one({"ticker": "GONE", "status": "active"})
    enqueue(db, "GONE")
    crew = FakeCrew(error=TickerDelistedError("GONE"))

    queue_worker.claim_and_run_next(db=db, crew=crew)

    job = db[WORK_QUEUE].find_one({"ticker": "GONE"})
    assert job["status"] == "failed"
    assert job["delisted"] is True
    assert db[TICKER_INDEX].find_one({"ticker": "GONE"})["status"] == "removed_from_market"
    assert db[WATCHLIST].find_one({"ticker": "GONE"})["status"] == "removed_from_market"


def test_stale_running_jobs_recovered_on_startup(db):
    stale = datetime.now(timezone.utc) - timedelta(minutes=45)
    db[WORK_QUEUE].insert_one({
        "ticker": "STUCK", "status": "running", "started_at": stale,
        "created_at": stale, "updated_at": stale,
    })
    crew = FakeCrew()

    # startup recovery flips it to pending, then it gets claimed and run
    assert queue_worker.claim_and_run_next(db=db, crew=crew) is True
    assert crew.ran == ["STUCK"]


def test_fresh_running_job_not_recovered(db):
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    db[WORK_QUEUE].insert_one({
        "ticker": "BUSY", "status": "running", "started_at": recent,
        "created_at": recent, "updated_at": recent,
    })
    assert queue_worker.claim_and_run_next(db=db, crew=FakeCrew()) is False
    assert db[WORK_QUEUE].find_one({"ticker": "BUSY"})["status"] == "running"
