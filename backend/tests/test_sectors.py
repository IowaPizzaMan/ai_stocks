"""Sector rollup endpoints, against mongomock via the shared client fixture."""
from datetime import datetime, timedelta, timezone

from db import ANALYSES
from tests.test_routers import analysis_doc

NOW = datetime.now(timezone.utc)


def test_sectors_rollup_counts_and_top_ticker(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish", conviction="medium", sector="Technology"))
    db[ANALYSES].insert_one(analysis_doc("NVDA", NOW, signal="bullish", conviction="high", sector="Technology"))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW, signal="bearish", conviction="high", sector="Technology"))
    db[ANALYSES].insert_one(analysis_doc("JPM", NOW, signal="neutral", conviction="low", sector="Financials"))
    db[ANALYSES].insert_one(analysis_doc("XYZ", NOW))  # sector=None — excluded

    r = client.get("/sectors").json()
    assert [s["sector"] for s in r] == ["Financials", "Technology"]

    tech = next(s for s in r if s["sector"] == "Technology")
    assert tech["bullish_count"] == 2
    assert tech["bearish_count"] == 1
    assert tech["neutral_count"] == 0
    assert tech["ticker_count"] == 3
    assert tech["top_ticker"] == "NVDA"  # bullish + high conviction beats bullish/medium

    fin = next(s for s in r if s["sector"] == "Financials")
    assert fin["ticker_count"] == 1
    assert fin["top_ticker"] == "JPM"


def test_sectors_uses_latest_analysis_per_ticker(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=2), signal="bearish", sector="Technology"))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish", sector="Technology"))

    r = client.get("/sectors").json()
    assert len(r) == 1
    assert r[0]["bullish_count"] == 1
    assert r[0]["bearish_count"] == 0


def test_sector_detail_aliases_analysis_sector(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish", sector="Technology"))

    r = client.get("/sectors/Technology").json()
    assert len(r) == 1
    assert r[0]["ticker"] == "AAPL"
    assert "sub_reports" not in r[0]


def test_sectors_empty(client, db):
    assert client.get("/sectors").json() == []
