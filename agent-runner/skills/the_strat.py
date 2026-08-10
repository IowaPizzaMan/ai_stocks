"""The Strat: objective bar classification, pattern detection, and Time Frame
Continuity. Rule system: specs/the-strat-spec.md ("Pattern Identification
Reference" section) — pure functions, no LLM calls.

Works on the daily/weekly/monthly/quarterly/yearly frames returned by
tools/price.py get_price_history(). The 60-minute participation group isn't
available from a daily data feed, so it's out of scope here. TFC alignment
itself is computed over weekly/monthly/quarterly/yearly only — Daily is
intentionally excluded (per product decision: too noisy to count toward
"all participation groups agree") but still checked separately for a notable
candle (hammer/shooter/outside bar/kicking/reversal) worth calling out even
when it doesn't move the alignment needle. Quarterly and yearly aren't part
of the canonical Strat's 4 major groups (Monthly/Weekly/Daily/60-min) but are
included anyway, per product decision, so Full TFC reflects the
longer-horizon groups relevant to this app's position/swing trades.
"""
import pandas as pd

TOP_THIRD = 0.67
BOTTOM_THIRD = 0.33


def _to_df(frame) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    df = pd.DataFrame(frame)
    if "Date" in df.columns:
        df = df.set_index("Date")
    return df


def bar_type(df: pd.DataFrame, i: int) -> str:
    """1 / 2U / 2D / 3 — the only four things a bar can do."""
    hh = df["High"].iloc[i] > df["High"].iloc[i - 1]
    ll = df["Low"].iloc[i] < df["Low"].iloc[i - 1]
    if hh and ll:
        return "3"
    if hh:
        return "2U"
    if ll:
        return "2D"
    return "1"


def classify_bars(df: pd.DataFrame) -> list[str]:
    return [bar_type(df, i) for i in range(1, len(df))]


def _range_pos(df: pd.DataFrame, i: int) -> float | None:
    """Close's position within the bar's range: 0 = low, 1 = high."""
    rng = df["High"].iloc[i] - df["Low"].iloc[i]
    if rng <= 0:
        return None
    return (df["Close"].iloc[i] - df["Low"].iloc[i]) / rng


def is_hammer(df: pd.DataFrame, i: int) -> bool:
    """2D bar closing in the top third — seller exhaustion off the lows."""
    pos = _range_pos(df, i)
    return bar_type(df, i) == "2D" and pos is not None and pos >= TOP_THIRD


def is_shooter(df: pd.DataFrame, i: int) -> bool:
    """2U bar closing in the bottom third — buyer exhaustion off the highs."""
    pos = _range_pos(df, i)
    return bar_type(df, i) == "2U" and pos is not None and pos <= BOTTOM_THIRD


def _color(df: pd.DataFrame, i: int) -> str:
    return "green" if df["Close"].iloc[i] > df["Open"].iloc[i] else "red"


def detect_patterns(df: pd.DataFrame) -> list[dict]:
    """Actionable patterns present at the latest closed bar. Each entry carries
    direction and the entry trigger level per the execution rules table."""
    n = len(df)
    if n < 3:
        return []
    i = n - 1
    t0, t1 = bar_type(df, i), bar_type(df, i - 1)
    high, low = float(df["High"].iloc[i]), float(df["Low"].iloc[i])
    patterns = []

    if t0 == "1":
        patterns.append({
            "name": "inside_bar_setup", "direction": "either",
            "buy_trigger": high, "sell_trigger": low,
            "note": "equilibrium — actionable on break of either side",
        })

    if is_hammer(df, i):
        if t1 == "1":
            patterns.append({"name": "revstrat_2bar_bullish", "direction": "long",
                             "buy_trigger": high, "note": "inside bar then hammer — triggers immediately"})
        else:
            patterns.append({"name": "hammer", "direction": "long", "buy_trigger": high,
                             "note": "in force above the hammer high"})
    if is_shooter(df, i):
        if t1 == "1":
            patterns.append({"name": "revstrat_2bar_bearish", "direction": "short",
                             "sell_trigger": low, "note": "inside bar then shooter — triggers immediately"})
        else:
            patterns.append({"name": "shooting_star", "direction": "short", "sell_trigger": low,
                             "note": "in force below the shooting star low"})

    if t1 == "1" and t0 == "3":
        pos = _range_pos(df, i)
        if pos is not None and pos >= 0.5:
            patterns.append({"name": "revstrat_1bar_bullish", "direction": "long",
                             "buy_trigger": high,
                             "note": "inside bar broke down then reversed up — trapped shorts; BF risk"})
        else:
            patterns.append({"name": "revstrat_1bar_bearish", "direction": "short",
                             "sell_trigger": low,
                             "note": "inside bar broke up then reversed down — trapped longs; BF risk"})

    if n >= 4:
        t2 = bar_type(df, i - 2)
        if t2 == "2D" and t1 == "1" and t0 == "2U":
            patterns.append({"name": "212_reversal_bullish", "direction": "long",
                             "buy_trigger": high, "note": "2D-1-2U reversal"})
        if t2 == "2U" and t1 == "1" and t0 == "2D":
            patterns.append({"name": "212_reversal_bearish", "direction": "short",
                             "sell_trigger": low, "note": "2U-1-2D reversal"})

    if t1 == "2D" and t0 == "2U":
        patterns.append({"name": "22_reversal_bullish", "direction": "long",
                         "buy_trigger": high, "note": "immediate directional flip up"})
    if t1 == "2U" and t0 == "2D":
        patterns.append({"name": "22_reversal_bearish", "direction": "short",
                         "sell_trigger": low, "note": "immediate directional flip down"})

    if _color(df, i - 1) == "red" and df["Open"].iloc[i] > df["High"].iloc[i - 1]:
        patterns.append({"name": "kicking_bullish", "direction": "long",
                         "in_force_above": float(df["Open"].iloc[i]),
                         "note": "gap over the red bar — shorts trapped; needs intraday confirmation"})
    if _color(df, i - 1) == "green" and df["Open"].iloc[i] < df["Low"].iloc[i - 1]:
        patterns.append({"name": "kicking_bearish", "direction": "short",
                         "in_force_below": float(df["Open"].iloc[i]),
                         "note": "gap under the green bar — longs trapped; needs intraday confirmation"})

    return patterns


def _tfc(last_sale: float, frames: dict[str, pd.DataFrame]) -> dict:
    """Time Frame Continuity: last sale vs each open bar's open, across the
    participation groups being compared for alignment (weekly/monthly/
    quarterly/yearly — daily is excluded here, see run())."""
    colors = {}
    for tf, df in frames.items():
        open_ = float(df["Open"].iloc[-1])
        colors[tf] = "green" if last_sale > open_ else "red"

    values = set(colors.values())
    if values == {"green"}:
        status = "full_bullish"
    elif values == {"red"}:
        status = "full_bearish"
    else:
        status = "conflict"
    return {**colors, "status": status, "last_sale": last_sale}


_NOTABLE_EXCLUDE = {"inside_bar_setup"}


def _daily_notable(df: pd.DataFrame, patterns: list[dict]) -> dict | None:
    """The Daily bar doesn't count toward Full TFC, but a notable candle
    there (hammer/shooter/outside bar/kicking/reversal) is still worth
    surfacing. Notable = anything actionable besides the default inside-bar
    equilibrium setup — an inside bar is the "nothing happened" state, not a
    candle worth calling out on its own."""
    i = len(df) - 1
    reasons = [p["name"] for p in patterns if p["name"] not in _NOTABLE_EXCLUDE]
    if bar_type(df, i) == "3" and "outside_bar" not in reasons:
        reasons.append("outside_bar")
    if not reasons:
        return None
    return {"bar_type": bar_type(df, i), "candle_color": _color(df, i), "reasons": reasons}


def run(ticker: str, data: dict) -> dict:
    """`data` is a get_price_history() dict: {'daily': ..., 'weekly': ...,
    'monthly': ..., 'quarterly': ..., 'yearly': ...} of record lists or
    DataFrames."""
    frames = {}
    for tf in ("daily", "weekly", "monthly", "quarterly", "yearly"):
        if tf not in data:
            raise KeyError(f"the_strat.run needs '{tf}' price data")
        df = _to_df(data[tf])
        if len(df) < 2:
            return {"ticker": ticker, "timeframes": {}, "tfc": None,
                    "signal": f"insufficient {tf} history"}
        frames[tf] = df

    timeframes = {}
    for tf, df in frames.items():
        seq = classify_bars(df)
        timeframes[tf] = {
            "last_bar": seq[-1],
            "sequence": seq[-5:],
            "candle_color": _color(df, len(df) - 1),
            "patterns": detect_patterns(df),
        }

    last_sale = float(frames["daily"]["Close"].iloc[-1])
    tfc = _tfc(last_sale, {tf: df for tf, df in frames.items() if tf != "daily"})
    daily_notable = _daily_notable(frames["daily"], timeframes["daily"]["patterns"])

    actionable = [(tf, p) for tf in ("yearly", "quarterly", "monthly", "weekly")
                  for p in timeframes[tf]["patterns"]]
    if tfc["status"] == "full_bullish":
        aligned = [f"{tf} {p['name']}" for tf, p in actionable if p["direction"] in ("long", "either")]
        signal = "full TFC bullish" + (f"; aligned setups: {', '.join(aligned)}" if aligned else "; no aligned setups")
    elif tfc["status"] == "full_bearish":
        aligned = [f"{tf} {p['name']}" for tf, p in actionable if p["direction"] in ("short", "either")]
        signal = "full TFC bearish" + (f"; aligned setups: {', '.join(aligned)}" if aligned else "; no aligned setups")
    else:
        signal = "TFC in conflict — reduced conviction; expect chop"
        if actionable:
            signal += "; setups present: " + ", ".join(f"{tf} {p['name']}" for tf, p in actionable)

    if daily_notable:
        signal += (f"; notable daily candle ({daily_notable['candle_color']}): "
                   + ", ".join(daily_notable["reasons"]))

    return {"ticker": ticker, "timeframes": timeframes, "tfc": tfc,
            "daily_notable_candle": daily_notable, "signal": signal}
