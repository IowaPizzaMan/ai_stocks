"""Unit tests for skills/position_management.py (stair-step stop method)."""
import pytest

from skills import position_management as pm


def bar(d, open_, high, low, close):
    return {"Date": d, "Open": open_, "High": high, "Low": low, "Close": close}


def base_data(**overrides):
    data = {
        "position": {
            "entry_price": 37.00, "entry_date": "2026-07-10",
            "current_stop": 44.50, "shares": 100, "breakout_level": 37.00,
        },
        "daily": [
            bar("2026-07-27", 47.0, 48.9, 46.8, 48.5),
            bar("2026-07-28", 48.6, 49.5, 48.2, 49.1),  # prior low 48.2
        ],
        "market_condition": "favorable",
    }
    data.update(overrides)
    return data


def test_stop_walks_up():
    daily = [
        bar("2026-07-27", 47.0, 48.9, 46.8, 48.5),   # prior: low 46.8... wait, prior is [-2]
        bar("2026-07-28", 48.6, 49.5, 48.2, 49.1),
    ]
    out = pm.run("NTNX", base_data(daily=daily))
    # prior day = 07-27 low 46.8 → new stop 46.65
    assert out["action"] == "UPDATE"
    assert out["prior_day_low"] == 46.8
    assert out["new_stop"] == pytest.approx(46.65)
    assert out["stop_moved_by"] == pytest.approx(2.15)
    assert out["unrealized_pnl_pct"] == pytest.approx((49.1 - 37) / 37 * 100, abs=0.01)
    assert out["days_held"] == 18
    assert any("stop raised" in a for a in out["alerts"])


def test_stop_never_moves_down():
    data = base_data()
    data["position"]["current_stop"] = 48.50   # already above candidate 48.2-0.15=48.05
    data["daily"] = [
        bar("2026-07-27", 49.0, 49.9, 48.2, 49.5),
        bar("2026-07-28", 49.6, 50.5, 48.9, 50.1),
    ]
    # prior low 48.2 → candidate 48.05 < current 48.50 → HOLD
    out = pm.run("NTNX", data)
    assert out["action"] == "HOLD"
    assert out["new_stop"] == 48.50
    assert out["stop_moved_by"] == 0


def test_percentage_buffer():
    data = base_data(config={"stop_buffer_pct": 0.003})
    data["daily"] = [
        bar("2026-07-27", 49.0, 49.9, 48.0, 49.5),
        bar("2026-07-28", 49.6, 50.5, 48.9, 50.1),
    ]
    out = pm.run("NTNX", data)
    assert out["new_stop"] == pytest.approx(48.0 - 48.0 * 0.003)


def test_exit_on_intraday_break():
    data = base_data()
    data["daily"] = [
        bar("2026-07-27", 47.0, 48.9, 46.8, 48.5),
        bar("2026-07-28", 45.5, 45.8, 44.0, 44.2),  # low 44.0 <= stop 44.50, open above
    ]
    out = pm.run("NTNX", data)
    assert out["action"] == "EXIT"
    assert "stop triggered" in out["notes"]


def test_close_mode_ignores_intraday_break():
    data = base_data(config={"use_close_vs_intraday": "close"})
    data["daily"] = [
        bar("2026-07-27", 47.0, 48.9, 46.8, 48.5),
        bar("2026-07-28", 45.5, 46.8, 44.0, 46.5),  # intraday low breaches, close 46.5 holds
    ]
    out = pm.run("NTNX", data)
    assert out["action"] != "EXIT"


def test_gap_down_open_exits_with_alert():
    data = base_data()
    data["daily"] = [
        bar("2026-07-27", 47.0, 48.9, 46.8, 48.5),
        bar("2026-07-28", 43.0, 44.0, 42.5, 43.8),  # opens 43.0 < stop 44.50
    ]
    out = pm.run("NTNX", data)
    assert out["action"] == "EXIT"
    assert any("gapped down" in a for a in out["alerts"])


def test_unfavorable_market_goes_to_review():
    out = pm.run("NTNX", base_data(market_condition="unfavorable"))
    assert out["action"] == "REVIEW"
    assert any("manual review" in a for a in out["alerts"])


def test_no_trailing_below_profit_threshold():
    data = base_data()
    data["position"]["entry_price"] = 48.0   # only ~2% profit at close 49.1
    data["position"]["current_stop"] = 46.0
    out = pm.run("NTNX", data)
    assert out["action"] == "HOLD"
    assert "trail threshold" in out["notes"]


def test_negative_position_flagged():
    data = base_data()
    data["position"]["entry_price"] = 55.0   # close 49.1 → negative
    data["position"]["current_stop"] = 44.0
    out = pm.run("NTNX", data)
    assert out["action"] == "HOLD"
    assert "below entry" in out["notes"]


def test_earnings_warning():
    out = pm.run("NTNX", base_data(earnings_date="2026-07-30"))
    assert any("earnings" in a for a in out["alerts"])


def test_earnings_far_away_no_warning():
    out = pm.run("NTNX", base_data(earnings_date="2026-09-15"))
    assert not any("earnings" in a for a in out["alerts"])


def test_max_days_held_flag():
    out = pm.run("NTNX", base_data(config={"max_days_held": 10}))
    assert any("review the position" in a for a in out["alerts"])


def test_requires_position_and_bars():
    with pytest.raises(ValueError):
        pm.run("NTNX", {"position": None, "daily": []})
