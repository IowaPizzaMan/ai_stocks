"""GET /market/* — read-only views over what the agent-runner cached."""
from datetime import datetime, timedelta, timezone

from db import (
    BREADTH_CACHE,
    BREADTH_DIVERGENCES,
    BREADTH_META,
    MACRO_ANALYSIS_CACHE,
    MARKET_FLOW_EVENTS,
    MARKET_MOVERS,
    WORK_QUEUE,
)

NOW = datetime.now(timezone.utc)


def mover_row(ticker, rank, category="actives", date="2026-08-22", **overrides):
    row = {
        "date": date, "category": category, "ticker": ticker, "rank": rank,
        "company": f"{ticker} Inc", "price": 10.0, "change": 0.5,
        "change_pct": 3.35196, "exchange": "NASDAQ", "volume": None,
        "source": "fmp", "collected_at": NOW,
    }
    row.update(overrides)
    return row


# --- most-actives (specs/028-dashboard-tweaks-batch US6) ----------------------

def test_most_actives_returns_latest_date_ordered_by_rank(client, db):
    db[MARKET_MOVERS].insert_many([
        mover_row("ZWQ", rank=1),
        mover_row("LUCY", rank=0),
    ])

    r = client.get("/market/most-actives").json()
    assert r["date"] == "2026-08-22"
    assert [i["ticker"] for i in r["items"]] == ["LUCY", "ZWQ"]


def test_most_actives_only_the_latest_date_is_served(client, db):
    db[MARKET_MOVERS].insert_many([
        mover_row("OLD", rank=0, date="2026-08-21"),
        mover_row("NEW", rank=0, date="2026-08-22"),
    ])

    r = client.get("/market/most-actives").json()
    assert [i["ticker"] for i in r["items"]] == ["NEW"]


def test_most_actives_limit_is_honoured(client, db):
    db[MARKET_MOVERS].insert_many([mover_row(f"T{i}", rank=i) for i in range(5)])
    r = client.get("/market/most-actives?limit=2").json()
    assert len(r["items"]) == 2
    assert [i["ticker"] for i in r["items"]] == ["T0", "T1"]


def test_most_actives_omits_volume_from_the_response(client, db):
    """R9 — the provider supplies none; never send a fabricated 0/null column."""
    db[MARKET_MOVERS].insert_one(mover_row("LUCY", rank=0))
    r = client.get("/market/most-actives").json()
    assert "volume" not in r["items"][0]


def test_most_actives_empty_collection_returns_empty_list_and_null_date(client, db):
    r = client.get("/market/most-actives").json()
    assert r == {"items": [], "as_of": None, "date": None}


def test_most_actives_refresh_enqueues_job(client, db):
    r = client.post("/market/most-actives/refresh").json()
    assert r["status"] == "enqueued"
    job = db[WORK_QUEUE].find_one({"job_type": "market_movers_pull"})
    assert job["status"] == "pending"


def test_most_actives_refresh_dedupes_active_job(client, db):
    first = client.post("/market/most-actives/refresh").json()
    second = client.post("/market/most-actives/refresh").json()
    assert second["status"] == "already_queued"
    assert second["job_id"] == first["job_id"]
    assert db[WORK_QUEUE].count_documents({"job_type": "market_movers_pull"}) == 1


def breadth_row(exchange, date, mcclellan, spy_close=None):
    row = {"exchange": exchange, "date": date, "mcclellan": mcclellan}
    if spy_close is not None:
        row["spy_close"] = spy_close
    return row


def test_breadth_returns_aligned_series_oldest_first(client, db):
    db[BREADTH_CACHE].insert_many([
        breadth_row("nyse", "2026-08-03", -20.0, 630.0),
        breadth_row("nyse", "2026-08-04", -35.5, 625.5),
        breadth_row("nasdaq", "2026-08-03", -12.0),
        breadth_row("nasdaq", "2026-08-04", -18.0),
    ])

    r = client.get("/market/breadth").json()
    assert [p["date"] for p in r["nymo"]] == ["2026-08-03", "2026-08-04"]
    assert [p["value"] for p in r["nymo"]] == [-20.0, -35.5]
    assert [p["value"] for p in r["namo"]] == [-12.0, -18.0]
    assert r["spy"] == [{"date": "2026-08-03", "close": 630.0},
                        {"date": "2026-08-04", "close": 625.5}]
    assert r["as_of"] == "2026-08-04"


def test_breadth_omits_rows_without_spy_close(client, db):
    db[BREADTH_CACHE].insert_many([
        breadth_row("nyse", "2026-08-03", -20.0),           # pre-dates SPY caching
        breadth_row("nyse", "2026-08-04", -35.5, 625.5),
    ])

    r = client.get("/market/breadth").json()
    assert len(r["nymo"]) == 2  # the oscillator still has both days
    assert [p["date"] for p in r["spy"]] == ["2026-08-04"]


def test_breadth_serves_stored_divergence_and_resolved_history(client, db):
    db[BREADTH_META].insert_one({
        "key": "last_divergence",
        "value": {"type": "bearish", "description": "SPY higher high vs NYMO lower high",
                  "price_points": [{"date": "2026-07-28", "value": 648.3},
                                   {"date": "2026-08-07", "value": 652.1}],
                  "osc_points": [{"date": "2026-07-28", "value": 31.2},
                                 {"date": "2026-08-07", "value": 18.4}]},
    })
    db[BREADTH_DIVERGENCES].insert_many([
        {"type": "bullish", "detected_on": "2026-06-02", "resolved": "2026-06-12",
         "anchor_dates": [], "spy_change_5d": 2.1, "spy_change_10d": 3.4},
        {"type": "bearish", "detected_on": "2026-07-01", "resolved": "2026-07-09",
         "anchor_dates": [], "spy_change_5d": None, "spy_change_10d": None},
        {"type": "bearish", "detected_on": "2026-08-07", "resolved": None,  # still open
         "anchor_dates": [], "spy_change_5d": None, "spy_change_10d": None},
    ])

    r = client.get("/market/breadth").json()
    assert r["divergence"]["type"] == "bearish"
    assert len(r["divergence"]["price_points"]) == 2
    # resolved only, oldest first — the chart plots markers left to right
    assert [h["resolved"] for h in r["divergence_history"]] == ["2026-06-12", "2026-07-09"]


def test_breadth_empty_cache_is_not_an_error(client, db):
    r = client.get("/market/breadth").json()
    assert r["nymo"] == [] and r["spy"] == []
    assert r["divergence"]["type"] == "none"
    assert r["as_of"] is None


def test_breadth_lookback_caps_returned_days(client, db):
    db[BREADTH_CACHE].insert_many([
        breadth_row("nyse", f"2026-08-{day:02d}", float(day), 600.0 + day)
        for day in range(1, 21)
    ])

    r = client.get("/market/breadth", params={"lookback_days": 10}).json()
    assert len(r["nymo"]) == 10
    assert r["nymo"][0]["date"] == "2026-08-11"  # the most recent 10, chronological


def test_flow_events_newest_first(client, db):
    db[MARKET_FLOW_EVENTS].insert_many([
        {"event_id": "a", "category": "market_flow", "kind": "breadth_divergence",
         "divergence_type": "bullish", "headline": "older", "body": "",
         "created_at": NOW - timedelta(days=3)},
        {"event_id": "b", "category": "market_flow", "kind": "breadth_divergence",
         "divergence_type": "bearish", "headline": "newer", "body": "",
         "created_at": NOW},
    ])

    r = client.get("/market/flow-events").json()
    assert [e["headline"] for e in r] == ["newer", "older"]


def test_flow_events_respects_limit(client, db):
    db[MARKET_FLOW_EVENTS].insert_many([
        {"event_id": str(i), "headline": f"e{i}", "created_at": NOW - timedelta(days=i)}
        for i in range(5)
    ])

    assert len(client.get("/market/flow-events", params={"limit": 2}).json()) == 2


def macro_result(**overrides):
    result = {
        "inflation_impact": {"trend": "stable", "impact_on_sector": "neutral", "cpi_latest": 330.1},
        "rate_impact": {"direction": "holding", "impact_on_valuation": "neutral", "fed_funds_rate": 4.25},
        "growth_backdrop": {"recession_signal": "mild", "commentary": "cooling",
                            "yield_curve_spread": 0.4, "curve_inverted": False},
        "consumer_backdrop": "resilient",
        "sector_rotation_signal": "neutral",
        "overall_macro_signal": "neutral",
        "confidence": "medium",
    }
    result.update(overrides)
    return result


def test_macro_empty_collection_is_not_an_error(client, db):
    r = client.get("/market/macro").json()
    assert r == {"sectors": [], "as_of": None}


def test_macro_returns_sectors_newest_first(client, db):
    db[MACRO_ANALYSIS_CACHE].insert_many([
        {"sector": "Technology", "result": macro_result(overall_macro_signal="bullish"),
         "computed_at": NOW - timedelta(days=1)},
        {"sector": "Financials", "result": macro_result(overall_macro_signal="bearish"),
         "computed_at": NOW},
    ])

    r = client.get("/market/macro").json()
    assert [s["sector"] for s in r["sectors"]] == ["Financials", "Technology"]
    assert "_id" not in r["sectors"][0]
    financials = r["sectors"][0]
    assert financials["overall_macro_signal"] == "bearish"
    assert financials["inflation_impact"]["cpi_latest"] == 330.1
    assert financials["rate_impact"]["fed_funds_rate"] == 4.25
    assert financials["confidence"] == "medium"
    assert r["as_of"] == financials["computed_at"]
