"""Unit tests for scripts/dedupe_analyses.py against mongomock."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from dedupe_analyses import dedupe  # noqa: E402
from tools.db import ANALYSES  # noqa: E402


@pytest.fixture
def db():
    return mongomock.MongoClient()["dedupe_test"]


NOW = datetime.now(timezone.utc)


def analysis_doc(ticker, ts, **extra):
    doc = {"ticker": ticker, "signal": "bullish", "conviction": "high", "summary": "x"}
    if ts is not None:
        doc["timestamp"] = ts
    doc.update(extra)
    return doc


def test_dedupe_collapses_to_latest_per_ticker(db):
    for i in range(5):
        db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=i), summary=f"run {i}"))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW, summary="only run"))

    removed = dedupe(db)

    assert removed == 4
    aapl_docs = list(db[ANALYSES].find({"ticker": "AAPL"}))
    assert len(aapl_docs) == 1
    assert aapl_docs[0]["summary"] == "run 0"  # NOW - 0 days == most recent
    msft_docs = list(db[ANALYSES].find({"ticker": "MSFT"}))
    assert len(msft_docs) == 1
    assert msft_docs[0]["summary"] == "only run"


def test_dedupe_is_idempotent(db):
    for i in range(3):
        db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=i)))

    dedupe(db)
    before = list(db[ANALYSES].find({}))

    second_run_removed = dedupe(db)

    assert second_run_removed == 0
    assert list(db[ANALYSES].find({})) == before


def test_dedupe_enables_unique_index(db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=1)))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))

    dedupe(db)

    info = db[ANALYSES].index_information()
    assert any(
        spec.get("unique") and spec.get("key") == [("ticker", 1)] for spec in info.values()
    )


def test_dedupe_treats_missing_timestamp_as_oldest(db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", None, summary="no timestamp"))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, summary="has timestamp"))

    dedupe(db)

    docs = list(db[ANALYSES].find({"ticker": "AAPL"}))
    assert len(docs) == 1
    assert docs[0]["summary"] == "has timestamp"


def test_dedupe_survives_simulated_interruption(db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=1)))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW - timedelta(days=1)))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))

    # simulate a crash after AAPL's group was cleaned up but before the run
    # reached MSFT's group (and before ensure_indexes ever ran, so the
    # not-yet-processed MSFT duplicates don't violate any index)
    stale_aapl = db[ANALYSES].find_one({"ticker": "AAPL", "timestamp": NOW - timedelta(days=1)})
    db[ANALYSES].delete_one({"_id": stale_aapl["_id"]})
    assert db[ANALYSES].count_documents({"ticker": "MSFT"}) == 2  # still un-deduped

    dedupe(db)  # resuming run must finish the job without erroring

    assert db[ANALYSES].count_documents({"ticker": "AAPL"}) == 1
    assert db[ANALYSES].count_documents({"ticker": "MSFT"}) == 1
