"""Unit tests for skills/accumulation.py against specs/accumulation_volume_rules.md."""
import numpy as np
import pandas as pd
import pytest

from skills import accumulation


def make_df(rows, up_vol, down_vol, pattern="alternate", spike_at=None, spike_vol=None):
    """Builds an OHLCV frame. `pattern`: 'alternate' = green/red alternating;
    'green' = all up days; 'red' = all down days."""
    dates = pd.date_range("2026-01-01", periods=rows, freq="B")
    opens = np.full(rows, 100.0)
    closes = np.empty(rows)
    volumes = np.empty(rows)
    for i in range(rows):
        if pattern == "green" or (pattern == "alternate" and i % 2 == 0):
            closes[i] = 101.0
            volumes[i] = up_vol
        else:
            closes[i] = 99.0
            volumes[i] = down_vol
    if spike_at is not None:
        closes[spike_at] = 101.0
        volumes[spike_at] = spike_vol
    return pd.DataFrame(
        {"Open": opens, "High": closes + 1, "Low": opens - 2, "Close": closes, "Volume": volumes},
        index=dates,
    )


def test_insufficient_history_is_neutral():
    df = make_df(10, 1_000_000, 1_000_000)
    out = accumulation.run("AAPL", df)
    assert out["signal"] == "NEUTRAL"
    assert out["accumulation_score"] == 0
    assert "insufficient history" in out["rationale"]


def test_neutral_when_volume_symmetric():
    df = make_df(80, 1_000_000, 1_000_000)
    out = accumulation.run("AAPL", df)
    assert out["signal"] == "NEUTRAL"
    assert out["up_down_volume_ratio"] == pytest.approx(1.0)
    assert out["distribution_warning"] is False


def test_strong_sustained_accumulation():
    # 3x asymmetry sustained across the whole 80-day frame
    df = make_df(80, 3_000_000, 1_000_000)
    out = accumulation.run("AAPL", df)
    assert out["up_down_volume_ratio"] == pytest.approx(3.0)
    assert out["pattern_duration_days"] >= accumulation.SUSTAINED_DAYS
    # +1 ratio>1.5, +1 ratio>2.5, +1 sustained
    assert out["accumulation_score"] == 3
    assert out["signal"] == "ACCUMULATION"


def test_volume_spike_adds_point():
    df = make_df(80, 3_000_000, 1_000_000, spike_at=75, spike_vol=12_000_000)
    out = accumulation.run("AAPL", df)
    assert out["max_volume_spike_vs_adv"] > accumulation.SPIKE_RATIO
    assert out["accumulation_score"] == 4


def test_peg_amplifier_reaches_max_conviction():
    df = make_df(80, 3_000_000, 1_000_000, spike_at=75, spike_vol=12_000_000)
    out = accumulation.run("AAPL", df, gap_score=4)
    assert out["peg_amplifier"] is True
    assert out["accumulation_score"] == 5
    assert out["signal"] == "ACCUMULATION"


def test_low_gap_score_is_not_amplifier():
    df = make_df(80, 3_000_000, 1_000_000)
    out = accumulation.run("AAPL", df, gap_score=2)
    assert out["peg_amplifier"] is False


def test_distribution_warning():
    # heavy volume on red days, light on green
    df = make_df(80, 1_000_000, 3_000_000)
    out = accumulation.run("AAPL", df)
    assert out["up_down_volume_ratio"] < accumulation.DISTRIBUTION_RATIO
    assert out["signal"] == "DISTRIBUTION_WARNING"
    assert out["distribution_warning"] is True


def test_early_accumulation():
    # symmetric history, asymmetry appears only in the last few sessions
    base = make_df(76, 1_000_000, 1_000_000)
    recent = make_df(4, 5_000_000, 1_000_000, pattern="green")
    recent.index = pd.date_range(base.index[-1] + pd.Timedelta(days=1), periods=4, freq="B")
    df = pd.concat([base, recent])
    out = accumulation.run("AAPL", df)
    assert out["signal"] == "EARLY_ACCUMULATION"
    assert 0 < out["pattern_duration_days"] < accumulation.EARLY_DAYS


def test_all_up_days_infinite_ratio_serializes_as_none():
    df = make_df(80, 2_000_000, 0, pattern="green")
    out = accumulation.run("AAPL", df)
    assert out["up_down_volume_ratio"] is None
    assert "no meaningful down-day volume" in out["rationale"]


def test_accepts_price_history_dict():
    df = make_df(80, 3_000_000, 1_000_000)
    data = {"daily": df.reset_index().rename(columns={"index": "Date"}).to_dict(orient="records")}
    out = accumulation.run("AAPL", data)
    assert out["signal"] == "ACCUMULATION"


def test_rejects_unknown_input():
    with pytest.raises(TypeError):
        accumulation.run("AAPL", [1, 2, 3])
