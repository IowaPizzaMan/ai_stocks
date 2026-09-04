"""Gap detection, classification, scoring, and PEG watchlist logic.
Rule system: specs/gap_analysis_rules.md — pure functions, no LLM calls.

Rules needing data beyond daily OHLCV (short interest, NYMO, market trend,
earnings dates, sector strength) take them as optional kwargs; a missing input
simply forfeits that rule's score point rather than failing.
"""
from datetime import date

import pandas as pd

GAP_LOOKBACK = 60          # sessions scanned for gaps
MIN_GAP_PCT = 0.01         # "large gap" threshold (§9)
VOLUME_AVG_WINDOW = 10
PEG_VOLUME_RATIO = 2.0     # ≥200% of 10-day average (§10.5)
PEG_STRONG_CLOSE = 0.90    # close in top 10% of day's range
NYMO_OVERBOUGHT = 40       # PEG filter: NYMO must be < +40


def _normalize(data) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, dict) and "daily" in data:
        df = pd.DataFrame(data["daily"])
        if "Date" in df.columns:
            df = df.set_index("Date")
        return df
    raise TypeError("gap_analysis.run expects an OHLCV DataFrame or a dict with 'daily' records")


def _candle(open_, close) -> str:
    return "W" if close > open_ else "B"


def _volume_class(volume: float, avg: float) -> str:
    if avg is None or pd.isna(avg) or avg <= 0:
        return "unknown"
    ratio = volume / avg
    if ratio > 2.0:
        return "extreme"
    if ratio > 1.25:
        return "high"
    if ratio >= 0.75:
        return "average"
    return "low"


def _gap_type(df: pd.DataFrame, i: int, direction: str, size_pct: float) -> str:
    """Heuristic classification from prior 20-session context (§2)."""
    prior = df.iloc[max(0, i - 20):i]
    if len(prior) < 10 or abs(size_pct) < MIN_GAP_PCT:
        return "common"
    prior_range = (prior["High"].max() - prior["Low"].min()) / prior["Close"].iloc[-1]
    prior_move = (prior["Close"].iloc[-1] - prior["Close"].iloc[0]) / prior["Close"].iloc[0]
    trending_with_gap = prior_move > 0.15 if direction == "up" else prior_move < -0.15
    if trending_with_gap:
        return "exhaustion"
    if prior_range < 0.05:
        return "breakaway"
    return "runaway"


def _fill_status(df: pd.DataFrame, i: int, direction: str) -> tuple[bool, int | None]:
    """A gap up fills when a later Low touches the pre-gap High (and vice versa)."""
    if direction == "up":
        level = df["High"].iloc[i - 1]
        later = df["Low"].iloc[i + 1:]
        hits = later[later <= level]
    else:
        level = df["Low"].iloc[i - 1]
        later = df["High"].iloc[i + 1:]
        hits = later[later >= level]
    if hits.empty:
        return False, None
    return True, int(later.index.get_loc(hits.index[0])) + 1


def _score_gap(gap: dict, market_trend: str | None) -> int:
    """§9 signal-strength scoring: layered confirmations, 0–5."""
    score = 0
    if abs(gap["size_pct"]) > MIN_GAP_PCT * 100:
        score += 1
    if gap["direction"] == "down":
        if gap["candle_pattern"][0] == "B":
            score += 1
        if gap["above_sma30"]:
            score += 1
        if gap["volume_class"] == "low":
            score += 1
        if market_trend in ("up", "neutral"):
            score += 1
    else:
        if gap["candle_pattern"] == "WUW":
            score += 1
        if not gap["above_sma30"]:
            score += 1
        if gap["volume_class"] in ("high", "extreme"):
            score += 1
        if gap["gap_type"] == "exhaustion":
            score += 1
    return score


def _bias(gap: dict) -> str:
    """§3/§4 direction-and-horizon read for the crew."""
    if gap["direction"] == "down":
        if gap["candle_pattern"] in ("BDB", "BDW"):
            return "LONG day 1"
        if gap["candle_pattern"] == "WDB":
            return "avoid long through day 30"
        return "LONG at day 3+"
    if gap["candle_pattern"] == "BUW":
        return "LONG day 1"
    return "SHORT days 1-10, LONG by day 30"


def _near_earnings(gap_date, earnings_dates) -> bool:
    if not earnings_dates:
        return False
    for d in earnings_dates:
        d = d.date() if hasattr(d, "date") else d
        if isinstance(d, date) and abs((gap_date - d).days) <= 1:
            return True
    return False


def _peg_score(gap: dict, short_interest: float | None, nymo: float | None,
               sector_uptrend: bool | None) -> int:
    """§10.5 PEG signal score; SI/NYMO/sector points forfeit when unknown."""
    score = 0
    if gap["strong_close"]:
        score += 2
    if gap["volume_ratio"] is not None and gap["volume_ratio"] >= PEG_VOLUME_RATIO:
        score += 1
    if short_interest is not None and short_interest >= 10:
        score += 1
    if sector_uptrend:
        score += 1
    if nymo is not None and nymo < NYMO_OVERBOUGHT:
        score += 1
    return score


def run(ticker: str, data, market_trend: str | None = None,
        earnings_dates: list | None = None, short_interest: float | None = None,
        nymo: float | None = None, sector_uptrend: bool | None = None) -> dict:
    """Scan the last GAP_LOOKBACK sessions for gaps; score each per §9; qualify
    Power Earnings Gaps per §10. Optional kwargs are pre-fetched context."""
    df = _normalize(data)
    if len(df) < 2:
        return {"ticker": ticker, "gaps": [], "latest_gap": None, "peg": None,
                "r2g_candidate": False, "signal": "insufficient history"}

    sma30 = df["Close"].rolling(30, min_periods=10).mean()
    vol_avg = df["Volume"].rolling(VOLUME_AVG_WINDOW, min_periods=5).mean().shift(1)

    start = max(1, len(df) - GAP_LOOKBACK)
    gaps = []
    for i in range(start, len(df)):
        prev_high, prev_low = df["High"].iloc[i - 1], df["Low"].iloc[i - 1]
        low, high = df["Low"].iloc[i], df["High"].iloc[i]
        if low > prev_high:
            direction, size = "up", (low - prev_high) / prev_high
        elif high < prev_low:
            direction, size = "down", (high - prev_low) / prev_low
        else:
            continue

        open_, close, volume = df["Open"].iloc[i], df["Close"].iloc[i], df["Volume"].iloc[i]
        day_range = high - low
        avg = vol_avg.iloc[i]
        gap_date = df.index[i].date() if hasattr(df.index[i], "date") else df.index[i]
        filled, days_to_fill = _fill_status(df, i, direction)

        gap = {
            "date": gap_date.isoformat() if hasattr(gap_date, "isoformat") else str(gap_date),
            "direction": direction,
            "size_pct": round(size * 100, 2),
            "candle_pattern": f"{_candle(df['Open'].iloc[i - 1], df['Close'].iloc[i - 1])}"
                              f"{'U' if direction == 'up' else 'D'}{_candle(open_, close)}",
            "volume_class": _volume_class(volume, avg),
            "volume_ratio": round(volume / avg, 2) if avg is not None and not pd.isna(avg) and avg > 0 else None,
            "above_sma30": bool(low > sma30.iloc[i]) if not pd.isna(sma30.iloc[i]) else False,
            "gap_type": _gap_type(df, i, direction, size),
            "strong_close": bool(day_range > 0 and (close - low) / day_range >= PEG_STRONG_CLOSE),
            "filled": filled,
            "days_to_fill": days_to_fill,
            # 032-weekly-strategy-picks: the pre-gap extreme — the level price
            # must reclaim to "fill" the gap (§8). A down gap's reversal/long
            # entry level is the prior bar's low; an up gap's short entry
            # level is the prior bar's high. Both already computed above as
            # prev_low/prev_high; only newly *returned* here.
            "reversal_level": round(float(prev_low if direction == "down" else prev_high), 2),
            "_i": i, "_gap_date": gap_date,
        }
        gap["score"] = _score_gap(gap, market_trend)
        gap["bias"] = _bias(gap)
        gaps.append(gap)

    # PEG qualification (§10.1): up gap + earnings catalyst + strong close + huge volume
    peg = None
    r2g = False
    for gap in reversed(gaps):
        if (gap["direction"] == "up"
                and _near_earnings(gap["_gap_date"], earnings_dates)
                and gap["strong_close"]
                and gap["volume_ratio"] is not None
                and gap["volume_ratio"] >= PEG_VOLUME_RATIO):
            peg = {
                "date": gap["date"],
                "size_pct": gap["size_pct"],
                "volume_ratio": gap["volume_ratio"],
                "peg_score": _peg_score(gap, short_interest, nymo, sector_uptrend),
                "short_interest": short_interest,
            }
            peg["priority"] = ("high" if peg["peg_score"] >= 4
                               else "watch" if peg["peg_score"] >= 2 else "skip")
            # PEG on the latest completed bar → watch tomorrow's open for a
            # small-red-to-green day-trade entry (§10.7)
            r2g = gap["_i"] == len(df) - 1
            break

    for gap in gaps:
        gap.pop("_i", None)
        gap.pop("_gap_date", None)

    latest = gaps[-1] if gaps else None
    if latest is None:
        signal = "no gaps in lookback window"
    elif peg is not None and peg["priority"] == "high":
        signal = f"PEG qualified (score {peg['peg_score']}) — high-priority watchlist add"
    elif latest["score"] >= 3:
        signal = f"{latest['direction']}-gap score {latest['score']} — {latest['bias']}"
    else:
        signal = f"{latest['direction']}-gap score {latest['score']} — skip or paper trade"

    return {
        "ticker": ticker,
        "gaps": gaps,
        "latest_gap": latest,
        "peg": peg,
        "r2g_candidate": r2g,
        "signal": signal,
    }
