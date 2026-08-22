"""Sector rollup endpoints, against mongomock via the shared client fixture."""
from datetime import datetime, timedelta, timezone

from db import ANALYSES, PRICE_HISTORY, TICKER_INDEX, WORK_QUEUE
from tests.test_routers import analysis_doc

NOW = datetime.now(timezone.utc)


def _register(db, ticker, sector=None):
    """029-company-profile-tweaks (FR-026): sector now lives on ticker_index
    (the company profile's value), not analyses.sector — nothing has ever
    written that field. Tests build state through the same path the real
    profile fetch writes to, per research R5."""
    doc = {"ticker": ticker, "status": "active"}
    if sector is not None:
        doc["sector"] = sector
    db[TICKER_INDEX].insert_one(doc)


def price_doc(ticker, bars):
    """bars: list of (date_str, close) — minimal OHLCV, only close matters here."""
    return {
        "ticker": ticker,
        "bars": [
            {"date": d, "open": c, "high": c, "low": c, "close": c, "volume": 100}
            for d, c in bars
        ],
        "coverage": {"first_date": bars[0][0], "last_date": bars[-1][0]},
    }


def test_sectors_rollup_counts_and_top_ticker(client, db):
    for t, sector in [("AAPL", "Technology"), ("NVDA", "Technology"), ("MSFT", "Technology"), ("JPM", "Financials"), ("XYZ", None)]:
        _register(db, t, sector)
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish", conviction="medium"))
    db[ANALYSES].insert_one(analysis_doc("NVDA", NOW, signal="bullish", conviction="high"))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW, signal="bearish", conviction="high"))
    db[ANALYSES].insert_one(analysis_doc("JPM", NOW, signal="neutral", conviction="low"))
    db[ANALYSES].insert_one(analysis_doc("XYZ", NOW))  # no profile sector — Unclassified

    r = client.get("/sectors").json()
    assert [s["sector"] for s in r] == ["Financials", "Technology", "Unclassified"]

    tech = next(s for s in r if s["sector"] == "Technology")
    assert tech["bullish_count"] == 2
    assert tech["bearish_count"] == 1
    assert tech["neutral_count"] == 0
    assert tech["ticker_count"] == 3
    assert tech["top_ticker"] == "NVDA"  # bullish + high conviction beats bullish/medium

    fin = next(s for s in r if s["sector"] == "Financials")
    assert fin["ticker_count"] == 1
    assert fin["top_ticker"] == "JPM"

    unclassified = next(s for s in r if s["sector"] == "Unclassified")
    assert unclassified["ticker_count"] == 1  # XYZ grouped, not dropped (FR-027)


def test_sectors_uses_latest_analysis_per_ticker(client, db):
    _register(db, "AAPL", "Technology")
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=2), signal="bearish"))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish"))

    r = client.get("/sectors").json()
    assert len(r) == 1
    assert r[0]["bullish_count"] == 1
    assert r[0]["bearish_count"] == 0


def test_sectors_reads_ticker_index_sector_not_analyses_sector(client, db):
    """A stray/legacy analyses.sector value must be ignored — ticker_index
    (the profile's value) is the single source of truth (FR-026)."""
    _register(db, "AAPL", "Financials")
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish", sector="Technology"))

    r = client.get("/sectors").json()
    assert [s["sector"] for s in r] == ["Financials"]


def test_unclassified_bucket_and_filtered_feed_agree_on_count(client, db):
    """Regression: found via live testing against real data — 'Unclassified'
    is a computed label, never a literal ticker_index.sector value, so a
    naive {"sector": "Unclassified"} feed filter resolved to zero tickers
    even though the rollup counted many (FR-026a)."""
    _register(db, "AAPL", "Technology")
    _register(db, "XYZ", None)  # no profile sector — Unclassified
    _register(db, "ABC", "")  # empty-string sector — also Unclassified
    for t in ("AAPL", "XYZ", "ABC"):
        db[ANALYSES].insert_one(analysis_doc(t, NOW))

    rollup = client.get("/sectors").json()
    unclassified = next(s for s in rollup if s["sector"] == "Unclassified")
    assert unclassified["ticker_count"] == 2

    feed = client.get("/analysis/feed", params={"sector": "Unclassified"}).json()
    assert feed["total"] == 2
    assert {i["ticker"] for i in feed["items"]} == {"XYZ", "ABC"}


def test_unclassified_sector_detail_matches_rollup(client, db):
    _register(db, "XYZ", None)
    db[ANALYSES].insert_one(analysis_doc("XYZ", NOW))

    r = client.get("/sectors/Unclassified").json()
    assert [d["ticker"] for d in r] == ["XYZ"]


def test_sector_rollup_and_filtered_feed_agree_on_count(client, db):
    """FR-026a: a sector's rollup count must equal the item count the feed's
    sector filter returns for the same sector — the two read the same join."""
    for t in ("AAPL", "NVDA", "MSFT"):
        _register(db, t, "Technology")
    _register(db, "JPM", "Financials")
    for t in ("AAPL", "NVDA", "MSFT", "JPM"):
        db[ANALYSES].insert_one(analysis_doc(t, NOW))

    rollup = client.get("/sectors").json()
    tech = next(s for s in rollup if s["sector"] == "Technology")

    feed = client.get("/analysis/feed", params={"sector": "Technology"}).json()
    assert feed["total"] == tech["ticker_count"] == 3


def test_sector_detail_uses_ticker_index_sector(client, db):
    _register(db, "AAPL", "Technology")
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish"))

    r = client.get("/sectors/Technology").json()
    assert len(r) == 1
    assert r[0]["ticker"] == "AAPL"
    assert "sub_reports" not in r[0]


def test_sector_detail_empty_for_unknown_sector(client, db):
    assert client.get("/sectors/NoSuchSector").json() == []


def test_sectors_empty(client, db):
    assert client.get("/sectors").json() == []


# --- sector ETF comparison chart (specs/028-dashboard-tweaks-batch US5) -------

SECTOR_ETFS = ["XLC", "XLY", "XLP", "XLE", "XLF", "XLI", "XLV", "XLB", "XLRE", "XLK", "XLU"]


def daily_bars(n, start=None, base_close=100.0):
    start = start or (NOW - timedelta(days=n)).date()
    return [((start + timedelta(days=i)).isoformat(), base_close + i) for i in range(n)]


def test_etf_series_returns_one_entry_per_tracked_etf_even_with_no_data(client, db):
    r = client.get("/sectors/etf-series?window=6m").json()
    assert {s["ticker"] for s in r["series"]} == set(SECTOR_ETFS)
    assert all(s["bars"] == [] and s["partial"] is True for s in r["series"])


def test_etf_series_default_window_is_6m(client, db):
    db[PRICE_HISTORY].insert_one(price_doc("XLK", daily_bars(400)))
    r = client.get("/sectors/etf-series").json()
    assert r["window"] == "6m"


def test_etf_series_422_on_invalid_window(client, db):
    assert client.get("/sectors/etf-series?window=bogus").status_code == 422


def test_etf_series_window_slices_history(client, db):
    db[PRICE_HISTORY].insert_one(price_doc("XLK", daily_bars(400)))

    r1y = client.get("/sectors/etf-series?window=1y").json()
    r1m = client.get("/sectors/etf-series?window=1m").json()

    xlk_1y = next(s for s in r1y["series"] if s["ticker"] == "XLK")
    xlk_1m = next(s for s in r1m["series"] if s["ticker"] == "XLK")
    assert len(xlk_1m["bars"]) < len(xlk_1y["bars"])


def test_etf_series_only_close_and_date_are_projected(client, db):
    db[PRICE_HISTORY].insert_one(price_doc("XLK", daily_bars(10)))
    r = client.get("/sectors/etf-series?window=1m").json()
    xlk = next(s for s in r["series"] if s["ticker"] == "XLK")
    assert set(xlk["bars"][0].keys()) == {"date", "close"}


def test_etf_series_partial_true_when_history_starts_after_window(client, db):
    """Only 5 days of history stored — far short of even the 1m window."""
    db[PRICE_HISTORY].insert_one(price_doc("XLK", daily_bars(5)))
    r = client.get("/sectors/etf-series?window=1y").json()
    xlk = next(s for s in r["series"] if s["ticker"] == "XLK")
    assert xlk["partial"] is True
    assert len(xlk["bars"]) == 5  # still rendered, not dropped


def test_etf_series_full_history_is_not_partial(client, db):
    db[PRICE_HISTORY].insert_one(price_doc("XLK", daily_bars(400)))
    r = client.get("/sectors/etf-series?window=1m").json()
    xlk = next(s for s in r["series"] if s["ticker"] == "XLK")
    assert xlk["partial"] is False


def test_etf_series_refresh_enqueues_job(client, db):
    r = client.post("/sectors/etf-series/refresh").json()
    assert r["status"] == "enqueued"
    assert db[WORK_QUEUE].find_one({"job_type": "sector_etf_pull"})["status"] == "pending"


def test_etf_series_refresh_dedupes_active_job(client, db):
    first = client.post("/sectors/etf-series/refresh").json()
    second = client.post("/sectors/etf-series/refresh").json()
    assert second["status"] == "already_queued"
    assert second["job_id"] == first["job_id"]
