"""Unit tests for tools/earnings_calendar.py — offline (mongomock + fakes)."""
from datetime import datetime, timedelta, timezone

import mongomock
import pandas as pd
import pytest

from tools import earnings_calendar as ec
from tools.db import EARNINGS_CACHE


@pytest.fixture
def db():
    return mongomock.MongoClient()["earnings_test"]


UNIVERSE = {
    "BIGCO": {"market_cap": 12e9, "name": "Big Co Inc.", "sector": "Technology"},
    "MIDCO": {"market_cap": 800e6, "name": "Mid Co", "sector": "Industrials"},
}


def fake_calendar_response():
    return {"earningsCalendar": [
        {"symbol": "BIGCO", "date": "2026-08-05", "hour": "amc",
         "epsEstimate": 1.5, "revenueEstimate": 2e9},
        {"symbol": "MIDCO", "date": "2026-08-04", "hour": "bmo",
         "epsEstimate": 0.2, "revenueEstimate": 3e8},
        {"symbol": "MIDCO", "date": "2026-08-04", "hour": "bmo",
         "epsEstimate": 0.2, "revenueEstimate": 3e8},  # duplicate row
        {"symbol": "TINY", "date": "2026-08-04", "hour": "",
         "epsEstimate": None, "revenueEstimate": None},  # not in universe (micro cap)
    ]}


# --- calendar -----------------------------------------------------------------

def test_calendar_screens_joins_and_sorts(db, monkeypatch):
    monkeypatch.setattr(ec, "finnhub_get", lambda path, **kw: fake_calendar_response())
    monkeypatch.setattr(ec, "_fetch_universe", lambda: UNIVERSE)

    out = ec.get_earnings_calendar(days_ahead=7, db=db)

    assert [e["ticker"] for e in out] == ["MIDCO", "BIGCO"]  # sorted by report_date
    big = out[1]
    assert big["company"] == "Big Co Inc."
    assert big["report_time"] == "amc"
    assert big["market_cap"] == 12e9
    assert big["sector"] == "Technology"
    assert big["eps_estimate"] == 1.5


def test_calendar_unknown_hour_and_cache(db, monkeypatch):
    calls = {"n": 0}

    def counting_get(path, **kw):
        calls["n"] += 1
        return {"earningsCalendar": [
            {"symbol": "BIGCO", "date": "2026-08-05", "hour": "dmh",
             "epsEstimate": None, "revenueEstimate": None}]}

    monkeypatch.setattr(ec, "finnhub_get", counting_get)
    monkeypatch.setattr(ec, "_fetch_universe", lambda: UNIVERSE)

    first = ec.get_earnings_calendar(days_ahead=3, db=db)
    assert first[0]["report_time"] == "unknown"

    again = ec.get_earnings_calendar(days_ahead=3, db=db)
    assert calls["n"] == 1  # served from 4h cache
    assert again == first


def test_universe_cached_24h(db, monkeypatch):
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return UNIVERSE

    monkeypatch.setattr(ec, "_fetch_universe", fetch)
    ec.get_screener_universe(db=db)
    ec.get_screener_universe(db=db)
    assert calls["n"] == 1

    # expire the cache → refetches
    db[EARNINGS_CACHE].update_one(
        {"type": "universe"},
        {"$set": {"fetched_at": datetime.now(timezone.utc) - timedelta(hours=25)}})
    ec.get_screener_universe(db=db)
    assert calls["n"] == 2


def test_universe_parses_screener_rows(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"rows": [
                {"symbol": "AAA", "name": "Alpha Corp ", "marketCap": "1,200,000,000.00",
                 "sector": "Energy"},
                {"symbol": "BBB", "name": "Beta", "marketCap": "100000000.00", "sector": "X"},
                {"symbol": "CCC", "name": "Gamma", "marketCap": "", "sector": ""},
            ]}}

    monkeypatch.setattr(ec.requests, "get", lambda *a, **kw: FakeResponse())
    universe = ec._fetch_universe()
    assert set(universe) == {"AAA"}  # BBB below floor, CCC unparseable cap
    assert universe["AAA"] == {"market_cap": 1.2e9, "name": "Alpha Corp", "sector": "Energy"}


# --- history --------------------------------------------------------------------

def make_closes():
    # Mon 2026-07-27 .. Fri 2026-07-31, close = 100, 102, 110, 111, 100
    idx = pd.to_datetime(["2026-07-27", "2026-07-28", "2026-07-29",
                          "2026-07-30", "2026-07-31"])
    return pd.Series([100.0, 102.0, 110.0, 111.0, 100.0], index=idx)


def test_reaction_move_bmo_prices_report_day():
    # bmo on the 29th → move = close(29th)/close(28th) - 1
    assert ec._reaction_move(make_closes(), "2026-07-29", True) == pytest.approx(7.84, abs=0.01)


def test_reaction_move_amc_prices_next_session():
    # amc on the 28th → reaction session is the 29th: close(29)/close(28) - 1
    assert ec._reaction_move(make_closes(), "2026-07-28", False) == pytest.approx(7.84, abs=0.01)


def test_reaction_move_outside_history_is_none():
    # amc on last bar → no next session yet
    assert ec._reaction_move(make_closes(), "2026-07-31", False) is None


FAKE_EARNINGS = [
    {"symbol": "BIGCO", "date": "2026-10-29", "epsEstimated": 2.0, "epsActual": None, "time": "amc"},
    {"symbol": "BIGCO", "date": "2026-07-28", "epsEstimated": 1.5, "epsActual": 1.8, "time": "amc"},
    {"symbol": "BIGCO", "date": "2026-04-28", "epsEstimated": 1.0, "epsActual": 0.9, "time": "amc"},
    {"symbol": "BIGCO", "date": "2026-01-27", "epsEstimated": 1.2, "epsActual": 1.5, "time": "amc"},
]


def _fake_closes() -> pd.DataFrame:
    base = pd.bdate_range("2026-01-20", "2026-07-31")
    closes = pd.Series(100.0, index=base)
    # engineered reactions: +7.84% after the July print, -5% after April, +2% after Jan
    closes.loc["2026-07-29":] = 107.84
    closes.loc["2026-04-29":"2026-07-28"] = 95.0
    closes.loc["2026-01-28":"2026-04-28"] = 102.0
    closes.loc[:"2026-01-27"] = 100.0
    return pd.DataFrame({"Close": closes})


def test_earnings_history_end_to_end(db, monkeypatch):
    monkeypatch.setattr(ec, "fmp_get", lambda path, db=None: FAKE_EARNINGS)
    monkeypatch.setattr(ec, "fetch_eod_history", lambda ticker, db=None: _fake_closes())
    out = ec.get_earnings_history("bigco", num_quarters=8, db=db)

    assert out["ticker"] == "BIGCO"
    assert out["num_quarters"] == 3  # future quarter (no epsActual) excluded
    july, april, jan = out["quarters"]
    assert july["period"] == "2026-07-28"
    assert july["beat"] is True and july["surprise_pct"] == 20.0
    assert july["move_pct"] == pytest.approx(13.52, abs=0.01)  # 95 → 107.84
    assert april["beat"] is False
    assert april["move_pct"] == pytest.approx(-6.86, abs=0.01)  # 102 → 95
    assert out["beat_rate"] == pytest.approx(0.67, abs=0.01)
    assert out["avg_abs_move_pct"] > 0

    # cached — second call must not hit fmp_get again
    monkeypatch.setattr(ec, "fmp_get", lambda path, db=None: pytest.fail("should be cached"))
    again = ec.get_earnings_history("BIGCO", db=db)
    assert again == out


def test_earnings_history_degrades_to_empty(db, monkeypatch):
    def _raise(path, db=None):
        raise RuntimeError("fmp hiccup")

    monkeypatch.setattr(ec, "fmp_get", _raise)
    out = ec.get_earnings_history("XYZ", db=db)
    assert out["quarters"] == [] and out["num_quarters"] == 0
    assert out["avg_abs_move_pct"] == 0 and out["beat_rate"] == 0
