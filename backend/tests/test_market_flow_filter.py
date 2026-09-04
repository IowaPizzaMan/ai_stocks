"""Market Flow breadth filter for strategy picks. Spec: specs/032-weekly-strategy-picks."""
import pytest

from db import BREADTH_CACHE
from semantic import market_flow_filter as mff


# --- classify_level boundaries (mirrors skills/market_flow.py::classify_level) ---

@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "unknown"),
        (-150, "panic"),
        (-100, "panic"),
        (-99.9, "extreme_oversold"),
        (-80, "extreme_oversold"),
        (-79.9, "oversold"),
        (-60, "oversold"),
        (-59.9, "moderate_oversold"),
        (-40, "moderate_oversold"),
        (-39.9, "mild_weakness"),
        (-0.1, "mild_weakness"),
        (0, "neutral"),
        (20, "neutral"),
        (20.1, "bullish_momentum"),
        (60, "bullish_momentum"),
        (60.1, "overbought"),
        (150, "overbought"),
    ],
)
def test_classify_level_boundaries(value, expected):
    assert mff.classify_level(value) == expected


# --- get_market_condition --------------------------------------------------------

def test_get_market_condition_unavailable_when_no_breadth_data(db):
    condition = mff.get_market_condition(db)
    assert condition == {"nymo": None, "level": "unknown", "available": False}


def test_get_market_condition_uses_the_most_recent_nyse_row(db):
    db[BREADTH_CACHE].insert_many([
        {"exchange": "nyse", "date": "2026-08-20", "mcclellan": 10.0},
        {"exchange": "nyse", "date": "2026-08-23", "mcclellan": 68.0},  # latest
        {"exchange": "nasdaq", "date": "2026-08-24", "mcclellan": -90.0},  # wrong exchange, ignored
    ])
    condition = mff.get_market_condition(db)
    assert condition == {"nymo": 68.0, "level": "overbought", "available": True}


# --- apply_filter (pure, given an already-fetched condition) --------------------

def _candidates():
    return [{"ticker": "AAPL", "entry_price": 187.5}, {"ticker": "MSFT", "entry_price": 412.0}]


def _condition(nymo):
    return {"nymo": nymo, "level": mff.classify_level(nymo), "available": nymo is not None}


def test_apply_filter_unavailable_condition_keeps_everything():
    result = mff.apply_filter(_candidates(), "buy", _condition(None))
    assert result == {"kept": _candidates(), "excluded": [], "note": None}


def test_apply_filter_neutral_reading_keeps_everything():
    result = mff.apply_filter(_candidates(), "buy", _condition(10.0))
    assert result == {"kept": _candidates(), "excluded": [], "note": None}


def test_apply_filter_overbought_excludes_buy_candidates():
    result = mff.apply_filter(_candidates(), "buy", _condition(68.0))
    assert result["kept"] == []
    assert {c["ticker"] for c in result["excluded"]} == {"AAPL", "MSFT"}
    assert "overbought" in result["note"]
    assert "NYMO +68" in result["note"]
    assert all("overbought" in c["reason"] for c in result["excluded"])


def test_apply_filter_overbought_does_not_touch_short_candidates():
    result = mff.apply_filter(_candidates(), "short", _condition(68.0))
    assert result == {"kept": _candidates(), "excluded": [], "note": None}


def test_apply_filter_oversold_excludes_short_candidates():
    result = mff.apply_filter(_candidates(), "short", _condition(-72.0))
    assert result["kept"] == []
    assert {c["ticker"] for c in result["excluded"]} == {"AAPL", "MSFT"}
    assert "oversold" in result["note"]
    assert "NYMO -72" in result["note"]


def test_apply_filter_oversold_does_not_touch_buy_candidates():
    result = mff.apply_filter(_candidates(), "buy", _condition(-72.0))
    assert result == {"kept": _candidates(), "excluded": [], "note": None}


@pytest.mark.parametrize("value", [-85.0, -110.0])
def test_apply_filter_extreme_oversold_and_panic_also_exclude_shorts(value):
    result = mff.apply_filter(_candidates(), "short", _condition(value))
    assert result["kept"] == []


def test_apply_filter_empty_candidate_list_is_a_noop():
    result = mff.apply_filter([], "buy", _condition(68.0))
    assert result == {"kept": [], "excluded": [], "note": None}


# --- describe_override (used for a top-level note even when lists are empty) ----

def test_describe_override_none_when_unavailable():
    assert mff.describe_override("buy", _condition(None)) is None


def test_describe_override_none_when_not_overridden():
    assert mff.describe_override("buy", _condition(10.0)) is None
    assert mff.describe_override("short", _condition(10.0)) is None


def test_describe_override_present_for_overbought_buys():
    note = mff.describe_override("buy", _condition(68.0))
    assert note is not None and "overbought" in note


def test_describe_override_present_for_oversold_shorts():
    note = mff.describe_override("short", _condition(-72.0))
    assert note is not None and "oversold" in note
