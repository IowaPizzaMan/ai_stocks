"""Daily economics refresh scheduling — the pulls themselves are tools/economics.py's."""
from datetime import datetime, timezone

import mongomock
import pytest

import economics_worker
from settings import settings
from tools.db import ECONOMICS_META

HOUR = settings.economics_refresh_hour_utc


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


def at(day, hour):
    return datetime(2026, 8, day, hour, tzinfo=timezone.utc)


def test_runs_once_after_the_refresh_hour(db):
    calls = []

    def refresh(db=None):
        calls.append(1)
        return 15

    assert economics_worker.run_daily_economics_if_due(at(4, HOUR), db=db, refresh=refresh) is True
    # already ran today
    assert economics_worker.run_daily_economics_if_due(at(4, HOUR + 1), db=db, refresh=refresh) is False
    # new day
    assert economics_worker.run_daily_economics_if_due(at(5, HOUR), db=db, refresh=refresh) is True
    assert len(calls) == 2


def test_skips_before_the_refresh_hour(db):
    ran = economics_worker.run_daily_economics_if_due(
        at(4, HOUR - 1), db=db, refresh=lambda db=None: pytest.fail("too early"))
    assert ran is False


def test_hard_crash_leaves_timestamp_unset_so_the_next_tick_retries(db):
    def boom(db=None):
        raise RuntimeError("fmp down")

    assert economics_worker.run_daily_economics_if_due(at(4, HOUR), db=db, refresh=boom) is False
    assert db[ECONOMICS_META].find_one({"key": "last_run_at"}) is None

    assert economics_worker.run_daily_economics_if_due(
        at(4, HOUR), db=db, refresh=lambda db=None: 15) is True


def test_handles_naive_timestamps_from_mongo(db):
    db[ECONOMICS_META].insert_one({"key": "last_run_at", "value": datetime(2026, 8, 4, HOUR)})
    assert economics_worker.run_daily_economics_if_due(
        at(4, min(HOUR + 2, 23)), db=db, refresh=lambda db=None: pytest.fail("same day")) is False
