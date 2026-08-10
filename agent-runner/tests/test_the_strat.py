"""Unit tests for skills/the_strat.py against specs/the-strat-spec.md."""
import pandas as pd
import pytest

from skills import the_strat


def bars(rows):
    """rows: list of (open, high, low, close) tuples."""
    idx = pd.date_range("2026-06-01", periods=len(rows), freq="B")
    return pd.DataFrame(
        {
            "Open": [r[0] for r in rows], "High": [r[1] for r in rows],
            "Low": [r[2] for r in rows], "Close": [r[3] for r in rows],
        },
        index=idx,
    )


BASE = (100, 110, 90, 105)  # wide reference bar


def test_bar_classification():
    df = bars([
        BASE,
        (100, 108, 92, 104),   # inside (1)
        (105, 112, 95, 110),   # 2U (higher high, no lower low)
        (108, 111, 88, 92),    # 2D? low 88 < 95, high 111 <= 112 → 2D
        (90, 115, 85, 100),    # 3 (both sides)
    ])
    assert the_strat.classify_bars(df) == ["1", "2U", "2D", "3"]


def test_hammer_and_shooter_detection():
    hammer = bars([BASE, (95, 102, 80, 100)])       # 2D, close in top third of 80-102
    assert the_strat.is_hammer(hammer, 1)
    shooter = bars([BASE, (105, 120, 95, 98)])      # 2U wait low 95>=90 ok, close near low
    assert the_strat.is_shooter(shooter, 1)
    plain_2d = bars([BASE, (95, 102, 80, 82)])      # 2D closing weak — not a hammer
    assert not the_strat.is_hammer(plain_2d, 1)


def test_inside_bar_setup_pattern():
    df = bars([BASE, BASE, (100, 108, 92, 104)])
    patterns = the_strat.detect_patterns(df)
    names = [p["name"] for p in patterns]
    assert "inside_bar_setup" in names
    setup = patterns[names.index("inside_bar_setup")]
    assert setup["buy_trigger"] == 108
    assert setup["sell_trigger"] == 92


def test_2bar_revstrat_bullish():
    df = bars([
        BASE,
        (100, 108, 92, 104),   # inside
        (100, 106, 85, 103),   # hammer: 2D (low 85<92, high 106<=108), close top third of 85-106
    ])
    names = [p["name"] for p in the_strat.detect_patterns(df)]
    assert "revstrat_2bar_bullish" in names


def test_1bar_revstrat_directions():
    up = bars([
        BASE,
        (100, 108, 92, 104),   # inside
        (95, 112, 88, 110),    # outside, closes upper half
    ])
    assert "revstrat_1bar_bullish" in [p["name"] for p in the_strat.detect_patterns(up)]

    down = bars([
        BASE,
        (100, 108, 92, 104),
        (105, 112, 88, 90),    # outside, closes lower half
    ])
    assert "revstrat_1bar_bearish" in [p["name"] for p in the_strat.detect_patterns(down)]


def test_212_reversal_bullish():
    df = bars([
        BASE,
        (98, 105, 85, 88),     # 2D
        (90, 100, 86, 95),     # inside vs previous (high 100<=105, low 86>=85)
        (96, 108, 88, 106),    # 2U
    ])
    names = [p["name"] for p in the_strat.detect_patterns(df)]
    assert "212_reversal_bullish" in names


def test_22_reversal_bearish():
    df = bars([
        BASE,
        (105, 115, 95, 112),   # 2U
        (110, 114, 85, 88),    # 2D (low 85 < 95, high 114 <= 115)
    ])
    names = [p["name"] for p in the_strat.detect_patterns(df)]
    assert "22_reversal_bearish" in names


def test_kicking_bullish():
    df = bars([
        BASE,
        (104, 106, 96, 98),    # red bar
        (108, 112, 107, 111),  # opens above prior high 106
    ])
    patterns = the_strat.detect_patterns(df)
    kick = next(p for p in patterns if p["name"] == "kicking_bullish")
    assert kick["in_force_above"] == 108


def run_input(daily, weekly, monthly, quarterly=None, yearly=None):
    return {
        "daily": daily, "weekly": weekly, "monthly": monthly,
        "quarterly": monthly if quarterly is None else quarterly,
        "yearly": monthly if yearly is None else yearly,
    }


def test_full_tfc_bullish():
    daily = bars([BASE, (100, 111, 95, 110)])
    weekly = bars([BASE, (100, 112, 95, 110)])
    monthly = bars([BASE, (99, 113, 95, 110)])
    quarterly = bars([BASE, (98, 114, 95, 110)])
    yearly = bars([BASE, (95, 115, 90, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, monthly, quarterly, yearly))
    assert out["tfc"]["status"] == "full_bullish"
    assert out["tfc"]["last_sale"] == 110
    assert "full TFC bullish" in out["signal"]


def test_daily_excluded_from_tfc_alignment():
    # Daily's own bar is red (close 100 < its own open 115) — but "last sale"
    # for TFC purposes is that same 100, which is still above every other
    # group's open, so Full TFC should hold: Daily's color doesn't count.
    daily = bars([BASE, (115, 118, 90, 100)])
    weekly = bars([BASE, (95, 112, 90, 110)])
    monthly = bars([BASE, (94, 113, 90, 110)])
    quarterly = bars([BASE, (93, 114, 90, 110)])
    yearly = bars([BASE, (90, 115, 85, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, monthly, quarterly, yearly))
    assert out["tfc"]["status"] == "full_bullish"
    assert out["tfc"]["last_sale"] == 100
    assert "daily" not in out["tfc"]
    assert set(out["tfc"]) >= {"weekly", "monthly", "quarterly", "yearly", "status", "last_sale"}


def test_tfc_conflict():
    daily = bars([BASE, (100, 111, 95, 110)])       # green — irrelevant to TFC status
    weekly = bars([BASE, (115, 118, 95, 110)])      # last sale 110 < weekly open 115 → red
    monthly = bars([BASE, (99, 113, 95, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, monthly))
    assert out["tfc"]["status"] == "conflict"
    assert "conflict" in out["signal"]


def test_tfc_conflict_from_quarterly_or_yearly():
    # weekly/monthly all green; quarterly alone dissents → still conflict
    daily = bars([BASE, (100, 111, 95, 110)])
    weekly = bars([BASE, (100, 112, 95, 110)])
    monthly = bars([BASE, (99, 113, 95, 110)])
    quarterly = bars([BASE, (115, 118, 95, 110)])   # last sale 110 < quarterly open 115 → red
    out = the_strat.run("AAPL", run_input(daily, weekly, monthly, quarterly=quarterly))
    assert out["tfc"]["status"] == "conflict"
    assert out["tfc"]["quarterly"] == "red"
    assert out["tfc"]["yearly"] == "green"  # defaults to monthly bar, unaffected


def test_tfc_covers_four_groups_timeframes_still_report_five():
    daily = bars([BASE, (100, 111, 95, 110)])
    weekly = bars([BASE, (100, 112, 95, 110)])
    monthly = bars([BASE, (99, 113, 95, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, monthly))
    assert set(out["tfc"]) == {"weekly", "monthly", "quarterly", "yearly", "status", "last_sale"}
    assert set(out["timeframes"]) == {"daily", "weekly", "monthly", "quarterly", "yearly"}


def test_daily_notable_hammer_called_out():
    daily = bars([BASE, (105, 112, 95, 110), (95, 102, 80, 100)])  # last bar is a hammer
    weekly = bars([BASE, (100, 112, 95, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, weekly))
    notable = out["daily_notable_candle"]
    assert notable is not None
    assert "hammer" in notable["reasons"]
    assert "notable daily candle" in out["signal"]


def test_daily_notable_outside_bar_called_out():
    daily = bars([BASE, (100, 108, 92, 104), (90, 115, 85, 100)])  # last bar breaks both sides
    weekly = bars([BASE, (100, 112, 95, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, weekly))
    notable = out["daily_notable_candle"]
    assert notable is not None
    assert "outside_bar" in notable["reasons"]


def test_daily_plain_bar_not_notable():
    daily = bars([BASE, (100, 108, 92, 104), (105, 109, 96, 107)])  # ordinary 2U, nothing special
    weekly = bars([BASE, (100, 112, 95, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, weekly))
    assert out["daily_notable_candle"] is None
    assert "notable daily candle" not in out["signal"]


def test_daily_inside_bar_alone_not_notable():
    # An inside bar is the default "nothing happened" state, not a notable candle.
    daily = bars([BASE, BASE, (100, 108, 92, 104)])
    weekly = bars([BASE, (100, 112, 95, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, weekly))
    assert out["daily_notable_candle"] is None


def test_run_reports_timeframe_details():
    daily = bars([BASE, (100, 108, 92, 104), (100, 107, 93, 105)])  # last bar inside
    weekly = bars([BASE, (105, 115, 95, 112)])
    monthly = bars([BASE, (99, 113, 95, 110)])
    out = the_strat.run("AAPL", run_input(daily, weekly, monthly))
    assert out["timeframes"]["daily"]["last_bar"] == "1"
    assert any(p["name"] == "inside_bar_setup" for p in out["timeframes"]["daily"]["patterns"])
    assert out["timeframes"]["weekly"]["last_bar"] == "2U"


def test_accepts_record_lists():
    daily = bars([BASE, (100, 111, 95, 110)])
    records = daily.reset_index().rename(columns={"index": "Date"}).to_dict(orient="records")
    out = the_strat.run("AAPL", run_input(records, records, records))
    assert out["tfc"]["status"] == "full_bullish"


def test_missing_timeframe_raises():
    daily = bars([BASE, BASE])
    with pytest.raises(KeyError):
        the_strat.run("AAPL", {"daily": daily})
