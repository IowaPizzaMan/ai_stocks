"""Unit tests for skills/market_flow.py against specs/market_flow_rules.md."""
import pytest

from skills import market_flow


def breadth(nymo_current, namo_current=0, nymo_history=None, namo_history=None):
    def section(current, history):
        hist = history if history is not None else [current]
        return {
            "history": [{"date": f"2026-07-{i+1:02d}", "value": v} for i, v in enumerate(hist)],
            "current": current, "zone": "neutral", "trend": "flat",
        }
    return {
        "nymo": section(nymo_current, nymo_history),
        "namo": section(namo_current, namo_history),
        "divergence": {"type": "none", "description": ""},
        "method": "computed_ratio_adjusted",
    }


def test_classify_level_thresholds():
    cases = [(-120, "panic"), (-85, "extreme_oversold"), (-70, "oversold"),
             (-50, "moderate_oversold"), (-10, "mild_weakness"), (5, "neutral"),
             (40, "bullish_momentum"), (75, "overbought"), (None, "unknown")]
    for value, expected in cases:
        assert market_flow.classify_level(value) == expected


def test_missing_breadth_raises():
    with pytest.raises(KeyError):
        market_flow.run("AAPL", {})


def test_extreme_oversold_buy():
    out = market_flow.run("AAPL", {"breadth": breadth(-85)})
    assert out["recommendation"] == "BUY_MORE"
    assert out["conviction"] == "high"
    assert any("scale in" in c for c in out["caveats"])


def test_oversold_zone_medium_conviction():
    out = market_flow.run("AAPL", {"breadth": breadth(-65)})
    assert out["recommendation"] == "BUY_MORE"
    assert out["conviction"] == "medium"


def test_oversold_plus_strong_down_gap_upgrades():
    gap = {"latest_gap": {"direction": "down", "score": 4, "gap_type": "runaway",
                          "candle_pattern": "BDB"}, "peg": None}
    out = market_flow.run("AAPL", {"breadth": breadth(-65), "gap": gap})
    assert out["recommendation"] == "BUY_MORE"
    assert out["conviction"] == "high"
    assert out["gap_score"] == 4
    assert out["gap_type"] == "down_gap_runaway"


def test_recovery_confirm_buy():
    hist = [-70, -65, -50, -30, -20]
    out = market_flow.run("AAPL", {"breadth": breadth(-20, nymo_history=hist)})
    assert out["recommendation"] == "BUY_MORE"
    assert "recovered" in out["rationale"]


def test_overbought_trim():
    out = market_flow.run("AAPL", {"breadth": breadth(70)})
    assert out["recommendation"] == "TRIM"


def test_overbought_plus_exhaustion_gap_sells():
    gap = {"latest_gap": {"direction": "up", "score": 4, "gap_type": "exhaustion",
                          "candle_pattern": "WUW"}, "peg": None}
    out = market_flow.run("AAPL", {"breadth": breadth(70), "gap": gap})
    assert out["recommendation"] == "START_SELLING"
    assert out["conviction"] == "high"


def test_stretched_avoid_add():
    out = market_flow.run("AAPL", {"breadth": breadth(50)})
    assert out["recommendation"] == "AVOID_ADD"


def test_cross_negative_watch():
    hist = [15, 5, -5]
    out = market_flow.run("AAPL", {"breadth": breadth(-5, nymo_history=hist)})
    assert out["recommendation"] == "WATCH"
    assert "trend shift" in out["rationale"]


def test_neutral_holds():
    out = market_flow.run("AAPL", {"breadth": breadth(10)})
    assert out["recommendation"] == "HOLD"


def test_namo_extreme_flags_tech_stress():
    out = market_flow.run("AAPL", {"breadth": breadth(-10, namo_current=-85)})
    assert any("tech-specific" in c for c in out["caveats"])


def test_both_extreme_highest_confidence():
    out = market_flow.run("AAPL", {"breadth": breadth(-85, namo_current=-90)})
    assert any("highest-confidence" in c for c in out["caveats"])


def test_divergence_detection_positive():
    # trough -70 early, SPY double-bottoms, NYMO only reaches -30
    nymo = [-20, -70, -40, -10, 0, -10, -20, -30, -25, -20]
    spy = [480, 450, 460, 470, 475, 468, 460, 451, 458, 462]
    assert market_flow.detect_nymo_divergence(nymo, spy) is True


def test_divergence_needs_deep_first_trough():
    nymo = [-20, -45, -40, -10, 0, -10, -20, -30, -25, -20]
    spy = [480, 450, 460, 470, 475, 468, 460, 451, 458, 462]
    assert market_flow.detect_nymo_divergence(nymo, spy) is False


def test_divergence_needs_retest():
    nymo = [-20, -70, -40, -10, 0, -10, -20, -30, -25, -20]
    spy = [480, 450, 460, 470, 475, 474, 472, 471, 470, 469]  # never retests 450
    assert market_flow.detect_nymo_divergence(nymo, spy) is False


def test_divergence_drives_max_conviction():
    nymo_hist = [-20, -85, -40, -10, 0, -10, -20, -30, -25, -82]
    spy = [480, 450, 460, 470, 475, 468, 460, 451, 458, 462]
    out = market_flow.run("AAPL", {"breadth": breadth(-82, nymo_history=nymo_hist),
                                   "spy_close": spy})
    assert out["divergence_detected"] is True
    assert out["recommendation"] == "BUY_MORE"
    assert out["conviction"] == "max"


def test_peg_watch_combo():
    gap = {"latest_gap": None, "peg": {"peg_score": 5, "priority": "high"}}
    out = market_flow.run("AAPL", {"breadth": breadth(10), "gap": gap})
    assert out["recommendation"] == "WATCH"
    assert any("PEG" in c for c in out["caveats"])


def test_peg_overbought_hold_off():
    gap = {"latest_gap": None, "peg": {"peg_score": 5, "priority": "high"}}
    out = market_flow.run("AAPL", {"breadth": breadth(70), "gap": gap})
    assert any("hold off" in c for c in out["caveats"])
