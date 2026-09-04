"""Cross-service contract for the `stock_events` collection.
Spec: specs/037-stocks-conviction-and-activity; contracts/stock-events-api.md.

Mirrored verbatim in agent-runner/tests/test_stock_events.py — that
duplication IS the cross-service consistency check (constitution Principle
VI), the same pattern test_db_constants.py already uses for STRATEGY_SIGNALS:
two independently-maintained assertions of the same literal, rather than one
service importing the other's code (the two share no Python package by
design). If either service's field set or index set drifts from the other,
either a document the reader expects silently isn't there, or a document the
writer produces is invisible to a query the reader relies on.
"""
import mongomock

import db as dbmod

# Mirrored verbatim in agent-runner/tests/test_stock_events.py's
# STOCK_EVENT_FIELDS.
STOCK_EVENT_FIELDS = {"ticker", "event_type", "occurred_at", "changed", "changes",
                      "reason", "source"}

# Mirrored verbatim in agent-runner/tools/db.py::ensure_indexes()'s stock_events
# block.
STOCK_EVENTS_INDEX_KEYS = {
    (("occurred_at", -1),),
    (("ticker", 1), ("occurred_at", -1)),
    (("ticker", 1), ("event_type", 1)),
}


def test_stock_events_constant_pinned():
    assert dbmod.STOCK_EVENTS == "stock_events"


def test_declared_indexes_match_the_documented_set():
    db = mongomock.MongoClient()["stock_events_contract_test"]
    dbmod.ensure_indexes(db)
    declared = {
        tuple(tuple(pair) for pair in spec["key"])
        for name, spec in db[dbmod.STOCK_EVENTS].index_information().items()
        if name != "_id_"
    }
    assert declared == STOCK_EVENTS_INDEX_KEYS


def test_router_field_vocabulary_matches_the_writer(client, db):
    """The field set GET /events actually returns (source excluded by design)
    plus the excluded `source` field together reconstruct the full writer
    vocabulary asserted in agent-runner/tests/test_stock_events.py."""
    db[dbmod.STOCK_EVENTS].insert_one({
        "ticker": "AVB", "event_type": "added", "occurred_at": None,
        "changed": False, "changes": None, "reason": None, "source": "agent_runner",
    })
    item = client.get("/events").json()["items"][0]
    exposed_fields = set(item.keys())
    assert exposed_fields == STOCK_EVENT_FIELDS - {"source"}
    assert exposed_fields | {"source"} == STOCK_EVENT_FIELDS
