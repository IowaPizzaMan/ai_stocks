"""Like/dislike (stock sentiment). Spec: specs/028-dashboard-tweaks-batch US3.
Contract: specs/028-dashboard-tweaks-batch/contracts/stock-sentiment-api.md
"""
from datetime import datetime, timezone

from db import TICKER_INDEX

NOW = datetime.now(timezone.utc)


def test_set_liked(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})

    r = client.put("/stocks/AAPL/sentiment", json={"sentiment": "liked"})
    assert r.status_code == 200
    assert r.json() == {"ticker": "AAPL", "sentiment": "liked"}
    doc = db[TICKER_INDEX].find_one({"ticker": "AAPL"})
    assert doc["sentiment"] == "liked"
    assert doc["sentiment_at"] is not None


def test_setting_disliked_over_liked_replaces_it(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})
    client.put("/stocks/AAPL/sentiment", json={"sentiment": "liked"})

    r = client.put("/stocks/AAPL/sentiment", json={"sentiment": "disliked"})
    assert r.json() == {"ticker": "AAPL", "sentiment": "disliked"}
    assert db[TICKER_INDEX].find_one({"ticker": "AAPL"})["sentiment"] == "disliked"


def test_resending_the_stored_value_clears_it_toggle_off(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})
    client.put("/stocks/AAPL/sentiment", json={"sentiment": "liked"})

    r = client.put("/stocks/AAPL/sentiment", json={"sentiment": "liked"})
    assert r.status_code == 200
    assert r.json() == {"ticker": "AAPL", "sentiment": None}
    doc = db[TICKER_INDEX].find_one({"ticker": "AAPL"})
    assert doc["sentiment"] is None
    assert doc["sentiment_at"] is None


def test_delete_clears_unconditionally(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "sentiment": "disliked"})

    r = client.delete("/stocks/AAPL/sentiment")
    assert r.status_code == 200
    assert r.json() == {"ticker": "AAPL", "sentiment": None}
    assert db[TICKER_INDEX].find_one({"ticker": "AAPL"})["sentiment"] is None


def test_put_404_for_untracked_ticker(client, db):
    """FR-006a enforced at the API, not just hidden in the UI."""
    r = client.put("/stocks/ZZZZ/sentiment", json={"sentiment": "liked"})
    assert r.status_code == 404
    assert db[TICKER_INDEX].find_one({"ticker": "ZZZZ"}) is None


def test_delete_404_for_untracked_ticker(client, db):
    assert client.delete("/stocks/ZZZZ/sentiment").status_code == 404


def test_put_422_for_invalid_value(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})
    r = client.put("/stocks/AAPL/sentiment", json={"sentiment": "meh"})
    assert r.status_code == 422
    assert db[TICKER_INDEX].find_one({"ticker": "AAPL"}).get("sentiment") is None


def test_get_ticker_record_includes_sentiment(client, db):
    """One request answers both 'is it tracked' and 'what is its tag' (R11)."""
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "sentiment": "liked"})
    r = client.get("/stocks/AAPL").json()
    assert r["sentiment"] == "liked"


def test_ticker_is_upper_cased(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})
    r = client.put("/stocks/aapl/sentiment", json={"sentiment": "liked"})
    assert r.json()["ticker"] == "AAPL"
