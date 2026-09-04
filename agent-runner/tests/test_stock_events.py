"""Tests for the stock_events writer path: register_ticker's "added" event
and queue_worker's "updated" event. Spec: specs/037-stocks-conviction-and-activity;
data-model.md §2; contracts/stock-events-api.md.

The field vocabulary asserted in test_stock_events_fields_match_the_documented_shape
is mirrored verbatim in backend/tests/test_stock_events_contract.py — the two
services share no Python package, so this pair IS the cross-service
consistency check (constitution Principle VI).
"""
from datetime import datetime, timezone

import mongomock
import pytest

import queue_worker
from tools import db as dbmod

STOCK_EVENT_FIELDS = {"ticker", "event_type", "occurred_at", "changed", "changes",
                      "reason", "source"}


@pytest.fixture
def db():
    return mongomock.MongoClient()["stock_events_test"]


@pytest.fixture(autouse=True)
def reset_startup():
    queue_worker._started = False
    yield
    queue_worker._started = False


# --- register_ticker() emits "added" -----------------------------------------

def test_register_ticker_emits_exactly_one_added_event(db):
    dbmod.register_ticker("AVB", "watchlist", db=db)
    events = list(db[dbmod.STOCK_EVENTS].find({"ticker": "AVB"}))
    assert len(events) == 1
    assert events[0]["event_type"] == "added"
    assert events[0]["changed"] is False
    assert events[0]["changes"] is None
    assert events[0]["reason"] is None


def test_register_ticker_called_again_does_not_duplicate_added(db):
    dbmod.register_ticker("AVB", "watchlist", db=db)
    dbmod.register_ticker("AVB", "13f", db=db)  # existing ticker, new source
    events = list(db[dbmod.STOCK_EVENTS].find({"ticker": "AVB", "event_type": "added"}))
    assert len(events) == 1


def test_register_ticker_new_tickers_each_get_their_own_added_event(db):
    dbmod.register_ticker("AVB", "watchlist", db=db)
    dbmod.register_ticker("MSFT", "watchlist", db=db)
    assert db[dbmod.STOCK_EVENTS].count_documents({"event_type": "added"}) == 2


def test_stock_events_fields_match_the_documented_shape(db):
    dbmod.register_ticker("AVB", "watchlist", db=db)
    event = db[dbmod.STOCK_EVENTS].find_one({"ticker": "AVB"}, {"_id": 0})
    assert set(event.keys()) == STOCK_EVENT_FIELDS


# --- queue_worker's persist path emits "updated" -----------------------------

class FakeCrew:
    def __init__(self, result):
        self.result = result

    def run(self, ticker, parallel_prefetch=False, mode="delta"):
        return dict(self.result)


def _enqueue(db, ticker="AVB"):
    db[dbmod.WORK_QUEUE].insert_one({
        "ticker": ticker, "status": "pending", "created_at": datetime.now(timezone.utc),
    })


def test_updated_event_unchanged_reanalysis_has_no_changes_or_reason(db):
    _enqueue(db)
    crew = FakeCrew({
        "ticker": "AVB", "signal": "bullish", "conviction": "medium", "conviction_rank": 2,
        "conviction_detail": {"level": "medium", "conditions": {}},
        "changes_since_last": {
            "signal": {"from": "bullish", "to": "bullish", "changed": False},
            "conviction": {"from": "medium", "to": "medium", "changed": False},
            "flags_added": [], "flags_removed": [],
        },
    })
    queue_worker.claim_and_run_next(db=db, crew=crew)

    event = db[dbmod.STOCK_EVENTS].find_one({"ticker": "AVB", "event_type": "updated"})
    assert event is not None
    assert event["changed"] is False
    assert event["changes"] is None
    assert event["reason"] is None


def test_updated_event_first_ever_pull_is_unchanged():
    """crew.py's changes_since_last is None on a first-ever pull (nothing to
    compare against) — must not be treated as a change."""
    db = mongomock.MongoClient()["stock_events_test_first_pull"]
    _enqueue(db)
    crew = FakeCrew({"ticker": "AVB", "signal": "bullish", "conviction": "high",
                     "changes_since_last": None})
    queue_worker.claim_and_run_next(db=db, crew=crew)

    event = db[dbmod.STOCK_EVENTS].find_one({"ticker": "AVB", "event_type": "updated"})
    assert event["changed"] is False


def test_updated_event_conviction_change_is_flagged_with_a_rule_derived_reason(db):
    _enqueue(db)
    # Seed a "previous" analysis with an old conviction_detail so
    # describe_transition() has something to diff against.
    old_detail = {
        "level": "medium",
        "conditions": {
            "strategies": {"pass": False}, "zscore": {"pass": True}, "revenue": {"pass": True},
        },
        "blockers": ["strategies not aligned: gap_analysis not calling buy"],
    }
    db[dbmod.ANALYSES].insert_one({
        "ticker": "AVB", "timestamp": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "signal": "neutral", "conviction": "medium", "conviction_detail": old_detail,
    })
    new_detail = {
        "level": "high",
        "conditions": {
            "strategies": {"pass": True}, "zscore": {"pass": True}, "revenue": {"pass": True},
        },
        "blockers": [],
    }
    crew = FakeCrew({
        "ticker": "AVB", "signal": "bullish", "conviction": "high", "conviction_rank": 3,
        "conviction_detail": new_detail,
        "changes_since_last": {
            "signal": {"from": "neutral", "to": "bullish", "changed": True},
            "conviction": {"from": "medium", "to": "high", "changed": True},
            "flags_added": [], "flags_removed": [],
        },
    })
    queue_worker.claim_and_run_next(db=db, crew=crew)

    event = db[dbmod.STOCK_EVENTS].find_one({"ticker": "AVB", "event_type": "updated"})
    assert event["changed"] is True
    assert event["changes"] == {
        "signal": {"from": "neutral", "to": "bullish", "changed": True},
        "conviction": {"from": "medium", "to": "high", "changed": True},
    }
    assert event["reason"]  # non-empty, rule-derived (not LLM prose)
    assert "strategy alignment" in event["reason"]


def test_updated_event_signal_only_change_has_changes_but_no_conviction_key(db):
    _enqueue(db)
    crew = FakeCrew({
        "ticker": "AVB", "signal": "bearish", "conviction": "low",
        "changes_since_last": {
            "signal": {"from": "neutral", "to": "bearish", "changed": True},
            "conviction": {"from": "low", "to": "low", "changed": False},
            "flags_added": [], "flags_removed": [],
        },
    })
    queue_worker.claim_and_run_next(db=db, crew=crew)

    event = db[dbmod.STOCK_EVENTS].find_one({"ticker": "AVB", "event_type": "updated"})
    assert event["changed"] is True
    assert "signal" in event["changes"]
    assert "conviction" not in event["changes"]
    assert event["reason"] is None  # only conviction changes get a rule-derived reason
