"""Tests for /institutional endpoints — mongomock via conftest client."""
from datetime import datetime, timedelta, timezone

from db import INSTITUTIONAL_FLOW, INSTITUTIONAL_FLOW_META

NOW = datetime(2026, 8, 2, 4, 0, tzinfo=timezone.utc)


def event(**overrides):
    base = {
        "ticker": "GOOGL", "fund": "Pershing Square", "action": "new_position",
        "shares": 1_200_000, "value_usd": 220_000_000.0, "pct_of_portfolio": 8.4,
        "pct_change": None, "headline": "Pershing Square opened a new $220M position in GOOGL",
        "notability_score": 91, "source": "13F",
        "filed_at": NOW - timedelta(days=2), "scanned_at": NOW,
    }
    return {**base, **overrides}


def seed(db, *events):
    db[INSTITUTIONAL_FLOW].insert_many([dict(e) for e in events])


def test_flow_empty(client):
    r = client.get("/institutional/flow")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_flow_sorted_and_paginated(client, db):
    seed(db,
         event(ticker="OLD", filed_at=NOW - timedelta(days=5)),
         event(ticker="NEW", filed_at=NOW - timedelta(days=1)),
         event(ticker="MID", filed_at=NOW - timedelta(days=3)))

    r = client.get("/institutional/flow", params={"page_size": 2})
    body = r.json()
    assert body["total"] == 3
    assert [i["ticker"] for i in body["items"]] == ["NEW", "MID"]

    r2 = client.get("/institutional/flow", params={"page_size": 2, "page": 2})
    assert [i["ticker"] for i in r2.json()["items"]] == ["OLD"]


def test_flow_filters(client, db):
    seed(db,
         event(),
         event(ticker="OXY", fund="Berkshire Hathaway", action="add",
               notability_score=60, source="dataroma"),
         event(ticker="AAPL", fund="Vanguard Group", action="trim", notability_score=12))

    r = client.get("/institutional/flow", params={"action": "add"})
    assert [i["ticker"] for i in r.json()["items"]] == ["OXY"]

    r = client.get("/institutional/flow", params={"fund": "berkshire"})
    assert [i["fund"] for i in r.json()["items"]] == ["Berkshire Hathaway"]

    r = client.get("/institutional/flow", params={"ticker": "googl"})
    assert [i["ticker"] for i in r.json()["items"]] == ["GOOGL"]

    r = client.get("/institutional/flow", params={"min_notability": 50})
    assert {i["ticker"] for i in r.json()["items"]} == {"GOOGL", "OXY"}


def test_flow_date_range(client, db):
    seed(db,
         event(ticker="OLD", filed_at=NOW - timedelta(days=30)),
         event(ticker="NEW", filed_at=NOW - timedelta(days=1)))

    r = client.get("/institutional/flow",
                   params={"from_date": (NOW - timedelta(days=7)).isoformat()})
    assert [i["ticker"] for i in r.json()["items"]] == ["NEW"]

    r = client.get("/institutional/flow",
                   params={"to_date": (NOW - timedelta(days=7)).isoformat()})
    assert [i["ticker"] for i in r.json()["items"]] == ["OLD"]


def test_ticker_flow_history(client, db):
    seed(db,
         event(filed_at=NOW - timedelta(days=10)),
         event(action="add", filed_at=NOW - timedelta(days=1)),
         event(ticker="OXY"))

    r = client.get("/institutional/flow/googl")
    assert r.status_code == 200
    body = r.json()
    assert [e["action"] for e in body] == ["add", "new_position"]
    assert all(e["ticker"] == "GOOGL" for e in body)


def test_scan_trigger_sets_flag(client, db):
    r = client.post("/institutional/scan")
    assert r.status_code == 200
    assert r.json()["status"] == "queued"

    flag = db[INSTITUTIONAL_FLOW_META].find_one({"key": "manual_scan_requested"})
    assert flag["value"] is True
    assert "requested_at" in flag
