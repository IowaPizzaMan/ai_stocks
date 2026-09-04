"""Unit tests for skills/gap_analysis.py against specs/gap_analysis_rules.md."""

import pandas as pd
import pytest

from skills import gap_analysis


def flat_days(n, price=100.0, volume=1_000_000, start="2026-03-02"):
    """n quiet sessions: tiny white candles, constant volume."""
    dates = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": price, "High": price + 1.0, "Low": price - 1.0,
            "Close": price + 0.5, "Volume": volume,
        },
        index=dates,
    )


def add_day(df, open_, high, low, close, volume):
    nxt = df.index[-1] + pd.tseries.offsets.BDay(1)
    row = pd.DataFrame(
        {"Open": [open_], "High": [high], "Low": [low], "Close": [close], "Volume": [volume]},
        index=[nxt],
    )
    return pd.concat([df, row])


def test_no_gaps():
    out = gap_analysis.run("AAPL", flat_days(40))
    assert out["gaps"] == []
    assert out["latest_gap"] is None
    assert out["signal"] == "no gaps in lookback window"


def test_insufficient_history():
    out = gap_analysis.run("AAPL", flat_days(1))
    assert out["signal"] == "insufficient history"


def test_up_gap_detected_with_pattern_and_class():
    # prior day: white (flat_days closes +0.5); gap up 3%, closes near high, huge volume
    df = add_day(flat_days(40), 104.5, 106.0, 104.2, 105.9, 3_000_000)
    out = gap_analysis.run("AAPL", df)

    gap = out["latest_gap"]
    assert gap["direction"] == "up"
    assert gap["size_pct"] == pytest.approx(3.17, abs=0.05)  # (104.2-101)/101
    assert gap["candle_pattern"] == "WUW"
    assert gap["volume_class"] == "extreme"
    assert gap["strong_close"] is True
    assert gap["filled"] is False


def test_down_gap_after_black_day_scores_high():
    df = flat_days(40)
    # black day, then gap down that stays above the 30-day SMA is impossible here,
    # so build: black candle day, then 2% gap down with low volume
    df = add_day(df, 101.0, 101.5, 99.0, 99.2, 1_000_000)   # black day (close<open)
    df = add_day(df, 96.5, 97.0, 96.0, 96.8, 400_000)       # gap down (high 97 < low 99), low vol
    out = gap_analysis.run("AAPL", df, market_trend="up")

    gap = out["latest_gap"]
    assert gap["direction"] == "down"
    assert gap["candle_pattern"][0] == "B"
    assert gap["volume_class"] == "low"
    # +1 size, +1 black prev, +1 low volume, +1 market up (below SMA30 → no point)
    assert gap["score"] == 4
    assert gap["bias"] in ("LONG day 1", "LONG at day 3+")
    assert "score 4" in out["signal"]


def test_gap_fill_tracked():
    df = add_day(flat_days(40), 104.5, 106.0, 104.2, 105.9, 3_000_000)  # up gap over high=101
    df = add_day(df, 105.0, 105.5, 100.5, 101.0, 1_000_000)             # low 100.5 <= 101 → filled
    out = gap_analysis.run("AAPL", df)
    gap = out["gaps"][0]
    assert gap["filled"] is True
    assert gap["days_to_fill"] == 1


def test_exhaustion_classification():
    # rising ~18% over the prior 20 sessions, then a gap up
    dates = pd.date_range("2026-03-02", periods=40, freq="B")
    close = pd.Series(range(40), index=dates) * 1.2 + 100
    df = pd.DataFrame(
        {"Open": close - 0.5, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1_000_000},
        index=dates,
    )
    df = add_day(df, 150.5, 152.5, 150.0, 151.5, 2_000_000)  # low 150 vs prior high 147.8 → 1.5% gap
    out = gap_analysis.run("AAPL", df)
    assert out["latest_gap"]["gap_type"] == "exhaustion"


def test_peg_qualification_and_r2g():
    df = flat_days(40)
    gap_day = df.index[-1] + pd.tseries.offsets.BDay(1)
    df = add_day(df, 106.0, 110.0, 105.5, 109.8, 5_000_000)  # gap up, closes top 10%, 5x volume

    out = gap_analysis.run(
        "AAPL", df,
        earnings_dates=[gap_day.date()],
        short_interest=15.0,
        nymo=-10.0,
        sector_uptrend=True,
    )
    peg = out["peg"]
    assert peg is not None
    # +2 strong close, +1 volume, +1 SI≥10, +1 sector, +1 NYMO<40
    assert peg["peg_score"] == 6
    assert peg["priority"] == "high"
    assert out["r2g_candidate"] is True   # PEG is the latest bar
    assert "PEG qualified" in out["signal"]


def test_peg_rejected_on_weak_close():
    df = flat_days(40)
    gap_day = df.index[-1] + pd.tseries.offsets.BDay(1)
    # gap up on earnings but closes red near lows — failed PEG
    df = add_day(df, 106.0, 110.0, 105.5, 105.8, 5_000_000)
    out = gap_analysis.run("AAPL", df, earnings_dates=[gap_day.date()])
    assert out["peg"] is None
    assert out["r2g_candidate"] is False


def test_peg_needs_earnings_catalyst():
    df = add_day(flat_days(40), 106.0, 110.0, 105.5, 109.8, 5_000_000)
    out = gap_analysis.run("AAPL", df)  # no earnings dates supplied
    assert out["peg"] is None


def test_peg_score_without_optional_context():
    df = flat_days(40)
    gap_day = df.index[-1] + pd.tseries.offsets.BDay(1)
    df = add_day(df, 106.0, 110.0, 105.5, 109.8, 5_000_000)
    out = gap_analysis.run("AAPL", df, earnings_dates=[gap_day.date()])
    # only +2 strong close +1 volume are knowable
    assert out["peg"]["peg_score"] == 3
    assert out["peg"]["priority"] == "watch"


def test_reversal_level_up_gap_is_prior_bar_high():
    # 032-weekly-strategy-picks: up gap's short-entry level is the pre-gap high
    df = add_day(flat_days(40), 104.5, 106.0, 104.2, 105.9, 3_000_000)
    out = gap_analysis.run("AAPL", df)
    gap = out["latest_gap"]
    assert gap["direction"] == "up"
    assert gap["reversal_level"] == pytest.approx(101.0)  # flat_days' High = price + 1.0


def test_reversal_level_down_gap_is_prior_bar_low():
    # 032-weekly-strategy-picks: down gap's long-entry level is the pre-gap low
    df = flat_days(40)
    df = add_day(df, 101.0, 101.5, 99.0, 99.2, 1_000_000)   # black day, Low = 99.0
    df = add_day(df, 96.5, 97.0, 96.0, 96.8, 400_000)       # gap down
    out = gap_analysis.run("AAPL", df, market_trend="up")
    gap = out["latest_gap"]
    assert gap["direction"] == "down"
    assert gap["reversal_level"] == pytest.approx(99.0)


def test_accepts_price_history_dict():
    df = add_day(flat_days(40), 104.5, 106.0, 104.2, 105.9, 3_000_000)
    data = {"daily": df.reset_index().rename(columns={"index": "Date"}).to_dict(orient="records")}
    out = gap_analysis.run("AAPL", data)
    assert out["latest_gap"]["direction"] == "up"
