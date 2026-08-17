"""macro_analyst.run()'s per-sector cache — no network, mongomock db."""
from datetime import datetime, timedelta, timezone

import mongomock

from agents import macro_analyst
from tests.test_phase5_agents import SchemaFakeLLM, macro_context
from tools.db import MACRO_ANALYSIS_CACHE


def make_db():
    return mongomock.MongoClient()["macro_cache_test"]


def test_no_db_never_caches():
    client = SchemaFakeLLM()
    macro_analyst.run("Technology", macro_context(), client=client)
    macro_analyst.run("Technology", macro_context(), client=client)
    assert len(client.calls) == 2  # each call is fresh with no db passed


def test_second_call_same_sector_hits_cache():
    db = make_db()
    client = SchemaFakeLLM()

    macro_analyst.run("Technology", macro_context(), client=client, db=db)
    macro_analyst.run("Technology", macro_context(), client=client, db=db)  # same sector

    assert len(client.calls) == 1
    assert db[MACRO_ANALYSIS_CACHE].count_documents({}) == 1


def test_different_sector_recomputes():
    db = make_db()
    client = SchemaFakeLLM()

    macro_analyst.run("Technology", macro_context(), client=client, db=db)
    macro_analyst.run("Financials", macro_context(), client=client, db=db)

    assert len(client.calls) == 2
    assert db[MACRO_ANALYSIS_CACHE].count_documents({}) == 2


def test_stale_cache_recomputes():
    db = make_db()
    client = SchemaFakeLLM()

    stale = datetime.now(timezone.utc) - timedelta(days=8)
    db[MACRO_ANALYSIS_CACHE].insert_one(
        {"sector": "Technology", "result": {"stale": True}, "computed_at": stale}
    )

    out = macro_analyst.run("Technology", macro_context(), client=client, db=db)
    assert len(client.calls) == 1
    assert "stale" not in out


def test_unknown_sector_falls_back_to_shared_bucket():
    db = make_db()
    client = SchemaFakeLLM()

    macro_analyst.run(None, macro_context(), client=client, db=db)
    macro_analyst.run(None, macro_context(), client=client, db=db)

    assert len(client.calls) == 1
    assert db[MACRO_ANALYSIS_CACHE].find_one({"sector": "unknown"}) is not None
