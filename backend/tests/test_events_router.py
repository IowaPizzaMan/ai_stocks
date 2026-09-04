"""GET /events and GET /events/{ticker}. Spec: specs/037-stocks-conviction-and-activity;
contracts/stock-events-api.md.
"""
from datetime import datetime, timedelta, timezone

from db import STOCK_EVENTS

NOW = datetime.now(timezone.utc)


def event(ticker, event_type="added", *, occurred_at=None, changed=False,
         changes=None, reason=None, source="agent_runner"):
    return {
        "ticker": ticker, "event_type": event_type,
        "occurred_at": occurred_at or NOW,
        "changed": changed, "changes": changes, "reason": reason, "source": source,
    }


# --- test 1: newest-first ordering -------------------------------------------

def test_activity_feed_returns_events_newest_first(client, db):
    db[STOCK_EVENTS].insert_one(event("AAA", occurred_at=NOW - timedelta(hours=2)))
    db[STOCK_EVENTS].insert_one(event("BBB", occurred_at=NOW))
    db[STOCK_EVENTS].insert_one(event("CCC", occurred_at=NOW - timedelta(hours=1)))

    items = client.get("/events").json()["items"]
    assert [i["ticker"] for i in items] == ["BBB", "CCC", "AAA"]


# --- test 2: 100-event cap + page-boundary behavior --------------------------

def test_activity_feed_caps_total_at_100_and_empties_past_the_window(client, db):
    for i in range(150):
        db[STOCK_EVENTS].insert_one(event(f"T{i:03d}", occurred_at=NOW - timedelta(minutes=i)))

    r = client.get("/events?page=1&page_size=20").json()
    assert r["total"] == 100
    assert r["window"] == 100

    # page 6 (offset 100) is past the 100-event window -> empty, not an error
    past_window = client.get("/events?page=6&page_size=20").json()
    assert past_window["items"] == []

    # page 5 (offset 80-99) is the last full page within the window
    last_page = client.get("/events?page=5&page_size=20").json()
    assert len(last_page["items"]) == 20


def test_activity_feed_partial_page_at_the_window_boundary(client, db):
    for i in range(105):
        db[STOCK_EVENTS].insert_one(event(f"T{i:03d}", occurred_at=NOW - timedelta(minutes=i)))

    # page_size=30: pages are [0-29][30-59][60-89][90-119] but window=100, so
    # the 4th page must be truncated to 10 items (90..99), not 30.
    r = client.get("/events?page=4&page_size=30").json()
    assert len(r["items"]) == 10


# --- test 3: empty collection --------------------------------------------------

def test_activity_feed_empty_collection_returns_200_not_404(client, db):
    r = client.get("/events")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "page_size": 20, "window": 100}


# --- test 4: per-ticker history filters to added + changed only -------------

def test_ticker_history_excludes_unchanged_updates(client, db):
    db[STOCK_EVENTS].insert_one(event("AVB", "added", occurred_at=NOW - timedelta(days=2)))
    db[STOCK_EVENTS].insert_one(event("AVB", "updated", occurred_at=NOW - timedelta(days=1),
                                      changed=False))
    db[STOCK_EVENTS].insert_one(event("AVB", "updated", occurred_at=NOW, changed=True,
                                      changes={"conviction": {"from": "medium", "to": "high"}},
                                      reason="strategy alignment changed"))

    r = client.get("/events/AVB").json()
    assert r["total"] == 2
    assert [i["event_type"] for i in r["items"]] == ["updated", "added"]  # newest first
    assert r["items"][0]["changed"] is True


# --- test 5: unknown ticker returns empty, not 404 ---------------------------

def test_ticker_history_unknown_ticker_returns_empty_not_404(client, db):
    r = client.get("/events/ZZZZ")
    assert r.status_code == 200
    assert r.json() == {"ticker": "ZZZZ", "items": [], "total": 0, "limit": 20}


def test_ticker_history_uppercases_the_ticker(client, db):
    db[STOCK_EVENTS].insert_one(event("AVB", "added"))
    r = client.get("/events/avb").json()
    assert r["ticker"] == "AVB"
    assert r["total"] == 1


# --- test 6: source is never exposed -----------------------------------------

def test_source_field_is_never_exposed(client, db):
    db[STOCK_EVENTS].insert_one(event("AAA", source="backfill"))
    db[STOCK_EVENTS].insert_one(event("AAA", "updated"))

    feed_item = client.get("/events").json()["items"][0]
    assert "source" not in feed_item
    history_item = client.get("/events/AAA").json()["items"][0]
    assert "source" not in history_item


# --- test 7: limit range enforcement -----------------------------------------

def test_ticker_history_limit_is_clamped_to_the_declared_range(client, db):
    assert client.get("/events/AVB?limit=0").status_code == 422
    assert client.get("/events/AVB?limit=51").status_code == 422
    assert client.get("/events/AVB?limit=50").status_code == 200


def test_activity_feed_page_size_is_clamped_to_the_declared_range(client, db):
    assert client.get("/events?page_size=0").status_code == 422
    assert client.get("/events?page_size=101").status_code == 422
    assert client.get("/events?page=0").status_code == 422
