"""Daily breadth refresh scheduling — the compute itself is tools/breadth.py's."""
from datetime import datetime, timezone

import mongomock
import pytest

import breadth_worker
from settings import settings
from tools.db import BREADTH_META

HOUR = settings.breadth_refresh_hour_utc
RESULT = {"nymo": {"current": -42.0}, "divergence": {"type": "none"}}


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


def at(day, hour):
    return datetime(2026, 8, day, hour, tzinfo=timezone.utc)


def test_runs_once_after_the_refresh_hour(db):
    calls = []

    def refresh(db=None):
        calls.append(1)
        return RESULT

    assert breadth_worker.run_daily_breadth_if_due(at(4, HOUR), db=db, refresh=refresh) is True
    # already ran today
    assert breadth_worker.run_daily_breadth_if_due(at(4, HOUR + 1), db=db, refresh=refresh) is False
    # new day
    assert breadth_worker.run_daily_breadth_if_due(at(5, HOUR), db=db, refresh=refresh) is True
    assert len(calls) == 2


def test_skips_before_the_refresh_hour(db):
    ran = breadth_worker.run_daily_breadth_if_due(
        at(4, HOUR - 1), db=db, refresh=lambda db=None: pytest.fail("too early"))
    assert ran is False


def test_failure_leaves_timestamp_unset_so_the_next_tick_retries(db):
    def boom(db=None):
        raise RuntimeError("yahoo down")

    assert breadth_worker.run_daily_breadth_if_due(at(4, HOUR), db=db, refresh=boom) is False
    assert db[BREADTH_META].find_one({"key": "last_run_at"}) is None

    assert breadth_worker.run_daily_breadth_if_due(
        at(4, HOUR), db=db, refresh=lambda db=None: RESULT) is True


def test_handles_naive_timestamps_from_mongo(db):
    db[BREADTH_META].insert_one({"key": "last_run_at", "value": datetime(2026, 8, 4, HOUR)})
    assert breadth_worker.run_daily_breadth_if_due(
        at(4, HOUR + 2), db=db, refresh=lambda db=None: pytest.fail("same day")) is False
