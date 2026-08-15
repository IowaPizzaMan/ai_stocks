"""Direct unit tests for earnings_data.py's FMP-sourced history fetch (the
router-level tests in test_earnings.py mock this module out entirely)."""
import pandas as pd
import pytest

import earnings_data as ed


def make_closes() -> pd.Series:
    idx = pd.to_datetime(["2026-07-27", "2026-07-28", "2026-07-29",
                          "2026-07-30", "2026-07-31"])
    return pd.Series([100.0, 102.0, 110.0, 111.0, 100.0], index=idx)


def test_reaction_move_bmo_prices_report_day():
    assert ed._reaction_move(make_closes(), "2026-07-29", True) == pytest.approx(7.84, abs=0.01)


def test_reaction_move_amc_prices_next_session():
    assert ed._reaction_move(make_closes(), "2026-07-28", False) == pytest.approx(7.84, abs=0.01)


def test_reaction_move_outside_history_is_none():
    assert ed._reaction_move(make_closes(), "2026-07-31", False) is None


FAKE_EARNINGS = [
    {"symbol": "BIGCO", "date": "2026-07-28", "epsEstimated": 1.5, "epsActual": 1.8, "time": "amc"},
    {"symbol": "BIGCO", "date": "2026-04-28", "epsEstimated": 1.0, "epsActual": 0.9, "time": "amc"},
]


def _fake_closes() -> pd.Series:
    base = pd.bdate_range("2026-04-01", "2026-07-31")
    closes = pd.Series(100.0, index=base)
    closes.loc["2026-07-29":] = 107.84
    closes.loc["2026-04-29":"2026-07-28"] = 95.0
    return closes


def test_earnings_history_end_to_end(db, monkeypatch):
    monkeypatch.setattr(ed, "_fmp_get", lambda path: FAKE_EARNINGS)
    monkeypatch.setattr(ed, "_fetch_eod_closes", lambda ticker: _fake_closes())

    out = ed.get_earnings_history("bigco", db)
    assert out["ticker"] == "BIGCO"
    assert out["num_quarters"] == 2
    july, april = out["quarters"]
    assert july["beat"] is True and july["surprise_pct"] == 20.0
    assert april["beat"] is False

    # cached — second call must not hit _fmp_get again
    monkeypatch.setattr(ed, "_fmp_get", lambda path: pytest.fail("should be cached"))
    again = ed.get_earnings_history("BIGCO", db)
    assert again == out


def test_earnings_history_degrades_to_empty(db, monkeypatch):
    def _raise(path):
        raise RuntimeError("fmp hiccup")

    monkeypatch.setattr(ed, "_fmp_get", _raise)
    out = ed.get_earnings_history("XYZ", db)
    assert out["quarters"] == [] and out["num_quarters"] == 0
