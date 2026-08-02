"""Unit tests for tools/macro.py — FRED is faked; no network."""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

from tools import macro
from tools.db import MACRO_CACHE


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


@pytest.fixture
def fake_fred(monkeypatch):
    calls = []

    def _fred_get(series_id):
        calls.append(series_id)
        return [
            {"date": "2026-08-01", "value": None},
            {"date": "2026-07-31", "value": 1.25},
            {"date": "2026-07-30", "value": 1.20},
        ]

    monkeypatch.setattr(macro, "fred_get", _fred_get)
    return calls


def test_cold_fetch_defaults_and_caches(db, fake_fred):
    data = macro.get_macro_data(db=db)

    assert set(data) == set(macro.DEFAULT_INDICATORS)
    assert sorted(fake_fred) == sorted(macro.DEFAULT_INDICATORS)
    assert db[MACRO_CACHE].count_documents({}) == 1


def test_warm_cache_no_fetch(db, fake_fred):
    macro.get_macro_data(["FEDFUNDS"], db=db)
    fake_fred.clear()

    data = macro.get_macro_data(["FEDFUNDS"], db=db)
    assert fake_fred == []
    assert data["FEDFUNDS"][1]["value"] == 1.25


def test_warm_cache_fetches_only_missing_series(db, fake_fred):
    macro.get_macro_data(["FEDFUNDS"], db=db)
    fake_fred.clear()

    data = macro.get_macro_data(["FEDFUNDS", "UNRATE"], db=db)
    assert fake_fred == ["UNRATE"]
    assert set(data) == {"FEDFUNDS", "UNRATE"}


def test_expired_cache_refetches(db, fake_fred):
    stale = datetime.now(timezone.utc) - timedelta(hours=macro.CACHE_HOURS + 1)
    db[MACRO_CACHE].insert_one({"data": {"FEDFUNDS": [{"date": "2026-01-01", "value": 9.9}]}, "fetched_at": stale})

    data = macro.get_macro_data(["FEDFUNDS"], db=db)
    assert fake_fred == ["FEDFUNDS"]
    assert data["FEDFUNDS"][1]["value"] == 1.25


def test_yield_curve_status_skips_null_leading_values(db, monkeypatch):
    series = {
        "T10Y2Y": [{"date": "2026-08-01", "value": None}, {"date": "2026-07-31", "value": -0.62}],
        "T10Y3M": [{"date": "2026-08-01", "value": 0.10}],
        "DGS10": [{"date": "2026-08-01", "value": 4.0}],
        "DGS2": [{"date": "2026-08-01", "value": 4.6}],
    }
    monkeypatch.setattr(macro, "fred_get", lambda s: series[s])

    status = macro.get_yield_curve_status(db=db)
    assert status["10y_2y_spread"] == -0.62
    assert status["inverted"] is True
    assert status["inversion_severity"] == "deep"


def test_yield_curve_mild_and_none(db, monkeypatch):
    def make(v):
        return {
            "T10Y2Y": [{"date": "2026-08-01", "value": v}],
            "T10Y3M": [{"date": "2026-08-01", "value": 0.5}],
            "DGS10": [{"date": "2026-08-01", "value": 4.0}],
            "DGS2": [{"date": "2026-08-01", "value": 4.0}],
        }

    monkeypatch.setattr(macro, "fred_get", lambda s, _d=make(-0.2): _d[s])
    assert macro.get_yield_curve_status(db=mongomock.MongoClient()["a"])["inversion_severity"] == "mild"

    monkeypatch.setattr(macro, "fred_get", lambda s, _d=make(0.8): _d[s])
    status = macro.get_yield_curve_status(db=mongomock.MongoClient()["b"])
    assert status["inversion_severity"] == "none"
    assert status["inverted"] is False
