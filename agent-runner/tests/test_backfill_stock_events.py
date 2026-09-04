"""Unit tests for scripts/backfill_stock_events.py against mongomock.
Spec: specs/037-stocks-conviction-and-activity; contracts/stock-events-api.md
tests #17-20.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from backfill_stock_events import backfill  # noqa: E402
from tools.db import STOCK_EVENTS, TICKER_INDEX  # noqa: E402

FIRST_SEEN = datetime(2026, 1, 15, tzinfo=timezone.utc)


@pytest.fixture
def db():
    return mongomock.MongoClient()["backfill_stock_events_test"]


def test_one_added_event_per_existing_ticker_dated_from_first_seen(db):
    db[TICKER_INDEX].insert_many([
        {"ticker": "AVB", "first_seen_at": FIRST_SEEN, "status": "active"},
        {"ticker": "MSFT", "first_seen_at": FIRST_SEEN, "status": "active"},
    ])

    count = backfill(db=db)

    assert count == 2
    events = list(db[STOCK_EVENTS].find({"event_type": "added"}))
    assert len(events) == 2
    avb = next(e for e in events if e["ticker"] == "AVB")
    assert avb["occurred_at"].replace(tzinfo=timezone.utc) == FIRST_SEEN  # mongomock strips tzinfo
    assert avb["source"] == "backfill"
    assert avb["changed"] is False


def test_running_twice_creates_no_duplicates(db):
    db[TICKER_INDEX].insert_one({"ticker": "AVB", "first_seen_at": FIRST_SEEN, "status": "active"})

    first_count = backfill(db=db)
    second_count = backfill(db=db)

    assert first_count == 1
    assert second_count == 0
    assert db[STOCK_EVENTS].count_documents({"ticker": "AVB", "event_type": "added"}) == 1


def test_ticker_with_a_live_added_event_is_not_duplicated(db):
    db[TICKER_INDEX].insert_one({"ticker": "AVB", "first_seen_at": FIRST_SEEN, "status": "active"})
    # simulates register_ticker() already having written a live "added" event
    # (e.g. the ticker was added after the app upgraded but before the
    # back-fill script ran)
    db[STOCK_EVENTS].insert_one({
        "ticker": "AVB", "event_type": "added", "occurred_at": FIRST_SEEN,
        "changed": False, "changes": None, "reason": None, "source": "agent_runner",
    })

    count = backfill(db=db)

    assert count == 0
    assert db[STOCK_EVENTS].count_documents({"ticker": "AVB", "event_type": "added"}) == 1


def test_no_updated_events_are_ever_created(db):
    db[TICKER_INDEX].insert_one({"ticker": "AVB", "first_seen_at": FIRST_SEEN, "status": "active"})

    backfill(db=db)

    assert db[STOCK_EVENTS].count_documents({"event_type": "updated"}) == 0


def test_empty_ticker_index_backfills_nothing(db):
    assert backfill(db=db) == 0
    assert db[STOCK_EVENTS].count_documents({}) == 0
