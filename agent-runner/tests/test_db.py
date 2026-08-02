"""Unit tests for tools/db.py against mongomock (no live Mongo needed)."""
from datetime import datetime, timezone

import mongomock
import pytest

from tools import db as dbmod


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


def test_write_then_query_roundtrip(db):
    dbmod.write_db(dbmod.WATCHLIST, {"ticker": "AAPL", "note": "core"}, db=db)
    rows = dbmod.query_db(dbmod.WATCHLIST, {"ticker": "AAPL"}, db=db)
    assert rows == [{"ticker": "AAPL", "note": "core"}]


def test_write_db_upsert_replaces(db):
    dbmod.write_db(dbmod.WATCHLIST, {"ticker": "AAPL", "note": "old"}, upsert_key="ticker", db=db)
    dbmod.write_db(dbmod.WATCHLIST, {"ticker": "AAPL", "note": "new"}, upsert_key="ticker", db=db)
    rows = dbmod.query_db(dbmod.WATCHLIST, {"ticker": "AAPL"}, db=db)
    assert rows == [{"ticker": "AAPL", "note": "new"}]


def test_get_latest_analysis_sorts_by_timestamp(db):
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new = datetime(2026, 6, 1, tzinfo=timezone.utc)
    db[dbmod.ANALYSES].insert_many([
        {"ticker": "MSFT", "timestamp": old, "signal": "hold"},
        {"ticker": "MSFT", "timestamp": new, "signal": "buy"},
        {"ticker": "AAPL", "timestamp": new, "signal": "sell"},
    ])
    latest = dbmod.get_latest_analysis("MSFT", db=db)
    assert latest["signal"] == "buy"
    assert "_id" not in latest


def test_get_latest_analysis_missing_ticker(db):
    assert dbmod.get_latest_analysis("ZZZZ", db=db) is None


def test_register_ticker_insert_and_merge(db):
    dbmod.register_ticker("nvda", "watchlist", name="NVIDIA", db=db)
    dbmod.register_ticker("NVDA", "13f", sector="Technology", db=db)

    doc = db[dbmod.TICKER_INDEX].find_one({"ticker": "NVDA"})
    assert doc["status"] == "active"
    assert sorted(doc["sources"]) == ["13f", "watchlist"]
    assert doc["name"] == "NVIDIA"
    assert doc["sector"] == "Technology"
    assert db[dbmod.TICKER_INDEX].count_documents({}) == 1


def test_mark_ticker_removed_updates_registry_and_watchlist(db):
    dbmod.register_ticker("BBBY", "watchlist", db=db)
    db[dbmod.WATCHLIST].insert_one({"ticker": "BBBY", "status": "active"})

    dbmod.mark_ticker_removed("BBBY", "delisted", db=db)

    reg = db[dbmod.TICKER_INDEX].find_one({"ticker": "BBBY"})
    assert reg["status"] == "removed_from_market"
    assert reg["delisted_reason"] == "delisted"
    watch = db[dbmod.WATCHLIST].find_one({"ticker": "BBBY"})
    assert watch["status"] == "removed_from_market"


def test_track_fmp_call_increments(db):
    assert dbmod.track_fmp_call(db=db) == 1
    assert dbmod.track_fmp_call(db=db) == 2
    assert dbmod.track_fmp_call(db=db) == 3


def test_ensure_indexes_idempotent(db):
    dbmod.ensure_indexes(db=db)
    dbmod.ensure_indexes(db=db)
    names = db[dbmod.TICKER_INDEX].index_information()
    assert any("ticker" in str(k) for k in names)
