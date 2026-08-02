"""NYMO/NAMO market-timing rules for the RecommenderAgent.
Rule system: specs/market_flow_rules.md — pure functions, no LLM calls.

Inputs come pre-fetched in `data`:
- "breadth": tools/breadth.get_market_breadth() output (required)
- "spy_close": list/Series of recent SPY closes aligned to the NYMO history
  (optional — enables §2B double-bottom divergence detection)
- "gap": skills/gap_analysis.run() output for this ticker (optional — §5 combos)
"""
DIVERGENCE_LOOKBACK = 20
DIVERGENCE_TROUGH = -50    # first trough must be at least this deep
DIVERGENCE_IMPROVE = 20    # NYMO must trough this much higher on the retest
RETEST_TOLERANCE = 0.015   # SPY retest within 1.5% of the first low


def classify_level(value: float | None) -> str:
    """§1 reading thresholds."""
    if value is None:
        return "unknown"
    if value <= -100:
        return "panic"
    if value <= -80:
        return "extreme_oversold"
    if value <= -60:
        return "oversold"
    if value <= -40:
        return "moderate_oversold"
    if value < 0:
        return "mild_weakness"
    if value <= 20:
        return "neutral"
    if value <= 60:
        return "bullish_momentum"
    return "overbought"


def detect_nymo_divergence(nymo_values: list[float], spy_closes: list[float],
                           lookback: int = DIVERGENCE_LOOKBACK) -> bool:
    """§2B: SPY double-bottoms while NYMO troughs meaningfully higher."""
    n = min(len(nymo_values), len(spy_closes), lookback)
    if n < 8:
        return False
    nymo = list(nymo_values[-n:])
    spy = list(spy_closes[-n:])

    half = n // 2
    i1 = min(range(half), key=lambda i: nymo[i])
    if nymo[i1] > DIVERGENCE_TROUGH:
        return False
    spy_low1 = min(spy[: half])

    later = range(i1 + 2, n)
    if not later:
        return False
    i2 = min(later, key=lambda i: spy[i])
    retest = abs(spy[i2] - spy_low1) / spy_low1 <= RETEST_TOLERANCE
    higher_low = nymo[i2] >= nymo[i1] + DIVERGENCE_IMPROVE
    return retest and higher_low


def _history_values(section: dict) -> list[float]:
    return [r["value"] for r in section.get("history", []) if r.get("value") is not None]


def run(ticker: str, data: dict) -> dict:
    breadth = data.get("breadth")
    if not breadth:
        raise KeyError("market_flow.run needs data['breadth'] from tools/breadth.get_market_breadth()")

    nymo, namo = breadth["nymo"], breadth["namo"]
    nymo_current, namo_current = nymo.get("current"), namo.get("current")
    nymo_signal = classify_level(nymo_current)
    namo_signal = classify_level(namo_current)
    nymo_values = _history_values(nymo)

    spy = data.get("spy_close")
    divergence = (detect_nymo_divergence(nymo_values, list(spy))
                  if spy is not None and nymo_values else False)

    gap = data.get("gap") or {}
    latest_gap = gap.get("latest_gap")
    peg = gap.get("peg")
    gap_score = latest_gap["score"] if latest_gap else None
    gap_type = (f"{latest_gap['direction']}_gap_{latest_gap['gap_type']}" if latest_gap else None)

    # §2C recovery: was ≤ -60 recently, now back above -40
    recovered = (bool(nymo_values) and min(nymo_values) <= -60
                 and nymo_current is not None and nymo_current > -40)
    # trend-shift cross from positive to negative
    crossed_negative = (len(nymo_values) >= 2 and nymo_values[-2] > 0
                        and nymo_current is not None and nymo_current < 0)

    caveats = []
    if nymo_current is None:
        recommendation, conviction = "HOLD", "low"
        rationale = "no NYMO reading available — defer to per-stock signals"
    elif divergence and nymo_signal in ("extreme_oversold", "panic"):
        recommendation, conviction = "BUY_MORE", "max"
        rationale = (f"NYMO {nymo_current} with SPY double-bottom / NYMO higher-low divergence — "
                     "the strongest signal in the rulebook; look out above")
    elif divergence:
        recommendation, conviction = "BUY_MORE", "high"
        rationale = f"SPY double-bottom with NYMO higher low (NYMO {nymo_current}) — aggressive add"
    elif nymo_signal in ("extreme_oversold", "panic"):
        recommendation, conviction = "BUY_MORE", "high"
        rationale = f"NYMO {nymo_current} — rare extreme (~1-2x/year); strong bounce setup"
        caveats.append("scale in, don't go all-in — wait for confirmation")
    elif nymo_signal == "oversold":
        recommendation, conviction = "BUY_MORE", "medium"
        rationale = f"NYMO {nymo_current} in the oversold zone — bounce candidates favored"
        if gap_score is not None and latest_gap["direction"] == "down" and gap_score >= 3:
            conviction = "high"
            rationale += f"; down-gap score {gap_score} confirms — act"
    elif recovered:
        recommendation, conviction = "BUY_MORE", "medium"
        rationale = f"NYMO recovered to {nymo_current} after an oversold extreme — bounce underway, adds fine"
    elif nymo_signal == "overbought":
        exhaustion = latest_gap and latest_gap["direction"] == "up" and latest_gap["gap_type"] == "exhaustion"
        wuw = latest_gap and latest_gap.get("candle_pattern") == "WUW"
        if exhaustion:
            recommendation, conviction = "START_SELLING", "high"
            rationale = f"NYMO {nymo_current} overbought plus an exhaustion up-gap — reduce meaningfully"
        elif wuw:
            recommendation, conviction = "TRIM", "medium"
            rationale = f"NYMO {nymo_current} overbought with WUW up-gap — short-term trim"
        else:
            recommendation, conviction = "TRIM", "medium"
            rationale = f"NYMO {nymo_current} overbought after an extended run — start lightening up (25-50%)"
    elif nymo_current > 40:
        recommendation, conviction = "AVOID_ADD", "medium"
        rationale = f"NYMO {nymo_current} — already stretched; don't chase adds"
    elif crossed_negative:
        recommendation, conviction = "WATCH", "medium"
        rationale = f"NYMO crossed from positive to {nymo_current} — trend shift; reduce risk"
    else:
        recommendation, conviction = "HOLD", "low"
        rationale = (f"NYMO {nymo_current} ({nymo_signal}) — no strong market timing signal; "
                     "defer to individual stock signals")

    # §4: NAMO refines the read for tech/growth names
    if namo_signal in ("oversold", "extreme_oversold", "panic") and nymo_signal not in (
            "oversold", "extreme_oversold", "panic"):
        caveats.append(f"NAMO {namo_current} is extreme while NYMO is mild — tech-specific stress")
    if (nymo_signal in ("oversold", "extreme_oversold", "panic")
            and namo_signal in ("oversold", "extreme_oversold", "panic")):
        caveats.append("NYMO and NAMO both at extremes — highest-confidence reading")

    # §5: PEG timing combos
    if peg and peg.get("peg_score", 0) >= 4:
        if nymo_current is not None and nymo_current < 40:
            caveats.append(f"PEG score {peg['peg_score']} with NYMO < +40 — watch for chart-pattern entry")
            if recommendation == "HOLD":
                recommendation, conviction = "WATCH", "medium"
                rationale += "; high-priority PEG on the watchlist"
        elif nymo_signal == "overbought":
            caveats.append("PEG candidate but NYMO overbought — hold off entry until the market cools")

    return {
        "ticker": ticker,
        "nymo_current": nymo_current,
        "namo_current": namo_current,
        "nymo_signal": nymo_signal,
        "namo_signal": namo_signal,
        "divergence_detected": divergence,
        "gap_score": gap_score,
        "gap_type": gap_type,
        "recommendation": recommendation,
        "conviction": conviction,
        "rationale": rationale,
        "caveats": caveats,
    }
