"""Accumulation-volume detection (institutional footprint via volume asymmetry).
Rule system: specs/accumulation_volume_rules.md — pure functions, no LLM calls.
"""
import pandas as pd

WINDOW = 20                # rolling window for up/down ratio (trading days)
ADV_WINDOW = 50            # average daily volume baseline
SUSTAINED_DAYS = 15        # ≥3 weeks of trading days for a confirmed pattern
EARLY_DAYS = 5             # <1 week = EARLY_ACCUMULATION
SPIKE_RATIO = 3.0          # up-day volume > 3x ADV = institutional footprint
ELEVATED_VOL_RATIO = 1.5   # up-day volume ≥ 1.5x ADV counts toward the trend test
DISTRIBUTION_RATIO = 0.7   # up/down ratio below this = sellers dominate


def _normalize(data) -> pd.DataFrame:
    """Accepts an OHLCV DataFrame (as passed by tools/price.py) or a dict of
    daily records like get_price_history()['daily']."""
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, dict) and "daily" in data:
        df = pd.DataFrame(data["daily"])
        if "Date" in df.columns:
            df = df.set_index("Date")
        return df
    raise TypeError("accumulation.run expects an OHLCV DataFrame or a dict with 'daily' records")


def _up_down_ratio(df: pd.DataFrame) -> float | None:
    window = df.tail(WINDOW)
    up_vol = window.loc[window["Close"] > window["Open"], "Volume"]
    down_vol = window.loc[window["Close"] < window["Open"], "Volume"]
    if up_vol.empty:
        return 0.0
    if down_vol.empty or down_vol.mean() == 0:
        return float("inf")
    return float(up_vol.mean() / down_vol.mean())


def _pattern_duration(df: pd.DataFrame) -> int:
    """Consecutive sessions (ending today) where the rolling 20-day up/down
    ratio held at ≥1.5 — how long the asymmetry has persisted."""
    duration = 0
    for end in range(len(df), WINDOW - 1, -1):
        ratio = _up_down_ratio(df.iloc[:end])
        if ratio is not None and ratio >= 1.5:
            duration += 1
        else:
            break
    return duration


def run(ticker: str, data, gap_score: int | None = None) -> dict:
    """Score 0–5 accumulation signal per the rule spec. `gap_score` is the PEG
    score from gap_analysis for a gap in the last 60 days, if one exists —
    the caller (TechnicalAnalyst) wires the two skills together."""
    df = _normalize(data)
    if len(df) < WINDOW:
        return {
            "ticker": ticker, "accumulation_score": 0, "up_down_volume_ratio": None,
            "max_volume_spike_vs_adv": None, "pattern_duration_days": 0,
            "peg_amplifier": False, "signal": "NEUTRAL", "distribution_warning": False,
            "rationale": f"insufficient history ({len(df)} days, need {WINDOW})",
        }

    adv = df["Volume"].rolling(ADV_WINDOW, min_periods=WINDOW).mean().shift(1)
    vol_vs_adv = df["Volume"] / adv

    window = df.tail(WINDOW)
    up_mask = window["Close"] > window["Open"]
    up_spikes = vol_vs_adv.tail(WINDOW)[up_mask]
    max_spike = float(up_spikes.max()) if not up_spikes.dropna().empty else 0.0

    ratio = _up_down_ratio(df)
    duration = _pattern_duration(df)
    peg_amplifier = gap_score is not None and gap_score >= 3

    score = 0
    if ratio > 1.5:
        score += 1
    if ratio > 2.5:
        score += 1
    if max_spike > SPIKE_RATIO:
        score += 1
    if duration >= SUSTAINED_DAYS:
        score += 1
    if peg_amplifier:
        score += 1

    distribution_warning = ratio < DISTRIBUTION_RATIO
    if distribution_warning:
        signal = "DISTRIBUTION_WARNING"
    elif score >= 3:
        signal = "ACCUMULATION"
    elif ratio >= 1.5 and 0 < duration < EARLY_DAYS:
        signal = "EARLY_ACCUMULATION"
    else:
        signal = "NEUTRAL"

    ratio_out = None if ratio == float("inf") else round(ratio, 2)
    parts = []
    if ratio == float("inf"):
        parts.append("all recent volume on up days (no meaningful down-day volume)")
    else:
        parts.append(f"up/down volume ratio {ratio:.1f}x over last {WINDOW} sessions")
    if max_spike > SPIKE_RATIO:
        parts.append(f"volume spiked to {max_spike:.1f}x ADV on an up day")
    if duration >= SUSTAINED_DAYS:
        parts.append(f"pattern sustained {duration} sessions")
    elif 0 < duration < EARLY_DAYS:
        parts.append(f"pattern only {duration} session(s) old — early")
    if peg_amplifier:
        parts.append(f"follows a Power Earnings Gap (score {gap_score})")
    if distribution_warning:
        parts.append("heavy down-day volume — institutions may be rotating out")

    return {
        "ticker": ticker,
        "accumulation_score": score,
        "up_down_volume_ratio": ratio_out,
        "max_volume_spike_vs_adv": round(max_spike, 2),
        "pattern_duration_days": duration,
        "peg_amplifier": peg_amplifier,
        "signal": signal,
        "distribution_warning": distribution_warning,
        "rationale": "; ".join(parts),
    }
