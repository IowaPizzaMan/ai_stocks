"""Deterministic conviction rating — the rule engine behind "high conviction means buy
this now". Spec: specs/037-stocks-conviction-and-activity;
contracts/conviction-rules.md; data-model.md.

Pure, no LLM calls — this is exactly the "rule-engine skill" surface Constitution
Principle III reserves for deterministic code. It replaces the free-form conviction
judgement agents/portfolio_strategist.py's LLM used to make (the "everything is a 3"
bug): crew.py calls run() and OVERWRITES the synthesized conviction with this skill's
level, rather than trusting the model to self-calibrate.

Inputs (all already computed by crew.py before this runs — nothing here makes an I/O
call or invokes another skill):
  - the_strat: skills/the_strat.py::run() output
  - accumulation: skills/accumulation.py::run() output
  - gap_analysis: skills/gap_analysis.py::run() output
  - price_history: tools/price.py::get_price_history() dict (daily/weekly/...)
  - financials: tools/financials.py::get_financials() dict
  - market_flow: skills/market_flow.py::run() output — read for a CAVEAT only; it
    never gates the rating (FR-006b). market_flow is market-wide breadth timing, not
    a per-ticker entry call, and gating on it would make "high" unreachable outside
    oversold windows (clarification Q4).

A stock is rated **high** only when ALL of:
  1. the three stock-specific entry strategies (the_strat, accumulation, gap_analysis)
     each resolve to "buy" (Rule 1),
  2. its daily AND weekly z-score both sit in their own trailing bottom quartile (Rule 2),
  3. its revenue is growing YoY and not declining QoQ (Rule 3, see tools/revenue.py).
Anything short of that is medium or low (Rule 4).
"""
from datetime import datetime, timezone

from skills.accumulation import WINDOW as ACCUMULATION_MIN_SESSIONS
from tools.revenue import derive_revenue_trend

# Rule 2 — same 20-period rolling z-score definition as
# frontend/src/lib/indicators/zscore.ts (ZSCORE_WARMUP) and
# tools/screener.py::_price_signals's zscore_20d, so the number gating
# conviction is the same number the Charts tab shows.
Z_PERIOD = 20
# Trailing z-value sample sizes the quartile is measured over — bounded by
# what get_price_history() returns (~1y daily, ~2y weekly).
DAILY_Z_HISTORY = 252
WEEKLY_Z_HISTORY = 104
# Below these sample sizes the quartile would be noise, not signal — that
# timeframe becomes a `no-call` (missing_inputs), never a fabricated pass.
MIN_DAILY_Z_SAMPLE = 60
MIN_WEEKLY_Z_SAMPLE = 30

# gap_analysis's own actionability threshold (specs/gap_analysis_rules.md §9,
# "Score >= 3 = act on signal"), the same constant tools/strategy_signals.py
# pins as GAP_SCORE_THRESHOLD — hand-duplicated per project convention
# (small shared constants are duplicated, not imported, across features).
GAP_SCORE_THRESHOLD = 3

# market_flow.run()'s recommendation values that mean "timing headwind" —
# never a blocker (FR-006b), only a caveat in the rationale.
UNFAVORABLE_MARKET_FLOW_RECOMMENDATIONS = {"START_SELLING", "TRIM", "AVOID_ADD"}

LEVEL_RANK = {"high": 3, "medium": 2, "low": 1}


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (numpy's default 'linear' method),
    implemented without a numpy dependency."""
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    idx = (n - 1) * pct / 100
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _rolling_zscores(records: list[dict], period: int = Z_PERIOD) -> list[float]:
    """The z-score at each bar once `period` closes are available — same
    formula as zscore.ts: population stdev, z=0 on a zero-variance window.
    Leading bars with < period history simply contribute no value (they are
    not represented as 0 or None in this list — there is nothing to quote)."""
    closes = []
    for record in records:
        close = record.get("Close")
        closes.append(float(close) if close is not None else None)

    out = []
    for i in range(len(closes)):
        if i + 1 < period:
            continue
        window = closes[i + 1 - period: i + 1]
        if any(c is None for c in window):
            continue
        mean = sum(window) / period
        variance = sum((c - mean) ** 2 for c in window) / period
        sd = variance ** 0.5
        out.append(0.0 if sd == 0 else (closes[i] - mean) / sd)
    return out


def _quartile_status(records: list[dict], history: int, min_sample: int) -> dict:
    """Is the timeframe's latest z-score in its own trailing bottom quartile?
    `in_bottom_quartile` is None (not False) when the sample is too small to
    trust — that is a missing input (FR-009), not a failed condition."""
    z_series = _rolling_zscores(records)
    sample = z_series[-history:] if len(z_series) > history else z_series
    if len(sample) < min_sample:
        return {"value": None, "p25": None, "in_bottom_quartile": None, "sample": len(sample)}
    p25 = _percentile(sample, 25)
    latest = sample[-1]
    return {
        "value": latest,
        "p25": p25,
        "in_bottom_quartile": latest <= p25,  # inclusive of the boundary (FR-011)
        "sample": len(sample),
    }


# the_strat.py's inside_bar_setup is an equilibrium state (direction "either"
# with no real conviction either way at that timeframe) and kicking_bullish/
# kicking_bearish need intraday confirmation this app has no feed for — none
# of the three count toward alignment strength. Same exclusion
# tools/strategy_signals.py::NON_TRIGGER_PATTERNS applies, hand-duplicated
# here rather than imported (skills stay independent of tools).
NON_TRIGGER_PATTERNS = {"inside_bar_setup", "kicking_bullish", "kicking_bearish"}
ALIGNMENT_TIMEFRAMES = ("yearly", "quarterly", "monthly", "weekly")


def _the_strat_call(the_strat_out: dict) -> tuple[str, str]:
    tfc = the_strat_out.get("tfc")
    if tfc is None:
        return "no-call", "insufficient price history for The Strat's TFC"
    if tfc.get("status") != "full_bullish":
        return "not-buy", f"TFC not full bullish (status: {tfc.get('status')})"

    timeframes = the_strat_out.get("timeframes") or {}
    aligned = [
        f"{tf} {p['name']}"
        for tf in ALIGNMENT_TIMEFRAMES
        for p in (timeframes.get(tf, {}).get("patterns") or [])
        if p.get("name") not in NON_TRIGGER_PATTERNS and p.get("direction") in ("long", "either")
    ]
    if not aligned:
        return "not-buy", "TFC full bullish but no aligned trigger pattern on any timeframe"
    return "buy", "full TFC bullish; aligned setups: " + ", ".join(aligned)


def _accumulation_call(accumulation_out: dict, daily_bar_count: int) -> tuple[str, str]:
    if daily_bar_count < ACCUMULATION_MIN_SESSIONS:
        return "no-call", "insufficient price history for accumulation"
    signal = accumulation_out.get("signal")
    if accumulation_out.get("distribution_warning"):
        return "not-buy", "distribution warning — heavy down-day volume"
    if signal == "ACCUMULATION":
        return "buy", accumulation_out.get("rationale") or "accumulation confirmed"
    if signal == "EARLY_ACCUMULATION":
        return "not-buy", "early accumulation only (pattern too new to confirm)"
    return "not-buy", "no accumulation signal"


def _gap_analysis_call(gap_out: dict) -> tuple[str, str]:
    if gap_out.get("signal") == "insufficient history" or gap_out.get("latest_gap") is None:
        return "no-call", "insufficient price history for gap analysis"
    latest = gap_out["latest_gap"]
    if latest.get("direction") == "down" and (latest.get("score") or 0) >= GAP_SCORE_THRESHOLD:
        return "buy", f"down-gap score {latest.get('score')} — {latest.get('bias')}"
    return "not-buy", f"{latest.get('direction')}-gap score {latest.get('score')} below actionable threshold"


def _market_flow_caveats(market_flow_out: dict | None) -> list[str]:
    if not market_flow_out:
        return []
    recommendation = market_flow_out.get("recommendation")
    if recommendation in UNFAVORABLE_MARKET_FLOW_RECOMMENDATIONS:
        return [f"market breadth timing is unfavorable ({recommendation.replace('_', ' ').lower()}) "
                "— a timing headwind, not a rating blocker"]
    return []


def _summary(level: str, blockers: list[str]) -> str:
    if level == "high":
        return ("all three entry strategies aligned, both z-score timeframes bottom-quartile, "
                "revenue trend favorable")
    if blockers:
        return "; ".join(blockers)
    return "conditions not met"


def describe_transition(old_detail: dict | None, new_detail: dict) -> str:
    """Rule-derived reason for a conviction change, for stock_events.reason
    (FR-028) — composed from which condition flipped, never LLM prose."""
    if not old_detail:
        return _summary(new_detail["level"], new_detail["blockers"])

    old_conditions = old_detail.get("conditions") or {}
    new_conditions = new_detail.get("conditions") or {}
    changed = []
    for key, label in (("strategies", "strategy alignment"), ("zscore", "z-score quartile position"),
                        ("revenue", "revenue trend")):
        if (old_conditions.get(key) or {}).get("pass") != (new_conditions.get(key) or {}).get("pass"):
            changed.append(label)

    summary = _summary(new_detail["level"], new_detail["blockers"])
    if not changed:
        return summary
    return ", ".join(changed) + " changed — " + summary


def run(ticker: str, data: dict, *, now: datetime | None = None) -> dict:
    """`data`: {'the_strat', 'accumulation', 'gap_analysis', 'price_history',
    'financials', 'market_flow'} — see module docstring for each shape."""
    now = now or datetime.now(timezone.utc)

    the_strat_out = data.get("the_strat") or {}
    accumulation_out = data.get("accumulation") or {}
    gap_out = data.get("gap_analysis") or {}
    price_history = data.get("price_history") or {}
    financials = data.get("financials")
    market_flow_out = data.get("market_flow")

    daily_records = price_history.get("daily") or []
    weekly_records = price_history.get("weekly") or []

    strat_call, strat_why = _the_strat_call(the_strat_out)
    accum_call, accum_why = _accumulation_call(accumulation_out, len(daily_records))
    gap_call, gap_why = _gap_analysis_call(gap_out)
    calls = {
        "the_strat": {"call": strat_call, "why": strat_why},
        "accumulation": {"call": accum_call, "why": accum_why},
        "gap_analysis": {"call": gap_call, "why": gap_why},
    }
    buy_count = sum(1 for c in calls.values() if c["call"] == "buy")
    strategies_pass = buy_count == 3

    daily_z = _quartile_status(daily_records, DAILY_Z_HISTORY, MIN_DAILY_Z_SAMPLE)
    weekly_z = _quartile_status(weekly_records, WEEKLY_Z_HISTORY, MIN_WEEKLY_Z_SAMPLE)
    daily_ok = bool(daily_z["in_bottom_quartile"])
    weekly_ok = bool(weekly_z["in_bottom_quartile"])
    zscore_pass = daily_ok and weekly_ok

    revenue = derive_revenue_trend(financials)
    revenue_pass = not revenue["missing"] and revenue["yoy_growing"] and not revenue["qoq_declining"]

    missing_inputs = [f"strategy:{name}" for name, c in calls.items() if c["call"] == "no-call"]
    if daily_z["in_bottom_quartile"] is None:
        missing_inputs.append("zscore:daily")
    if weekly_z["in_bottom_quartile"] is None:
        missing_inputs.append("zscore:weekly")
    if "growth_yoy" in revenue["missing"]:
        missing_inputs.append("revenue:yoy")
    if "change_qoq" in revenue["missing"]:
        missing_inputs.append("revenue:qoq")

    blockers = []
    if not strategies_pass:
        failing = [name for name, c in calls.items() if c["call"] != "buy"]
        blockers.append(f"strategies not aligned: {', '.join(failing)} not calling buy")
    if not zscore_pass:
        if daily_z["in_bottom_quartile"] is None:
            blockers.append("insufficient daily price history for z-score quartile")
        elif not daily_ok:
            blockers.append("daily z-score not in bottom quartile")
        if weekly_z["in_bottom_quartile"] is None:
            blockers.append("insufficient weekly price history for z-score quartile")
        elif not weekly_ok:
            blockers.append("weekly z-score not in bottom quartile")
    if not revenue_pass:
        if revenue["missing"]:
            blockers.append(f"revenue data unavailable ({', '.join(revenue['missing'])})")
        else:
            if not revenue["yoy_growing"]:
                blockers.append("revenue not growing year over year")
            if revenue["qoq_declining"]:
                blockers.append("revenue declined quarter over quarter")

    if strategies_pass and zscore_pass and revenue_pass:
        level = "high"
    elif buy_count >= 2 and (daily_ok or weekly_ok) and not revenue["qoq_declining"]:
        level = "medium"
    else:
        level = "low"

    detail = {
        "ticker": ticker,
        "level": level,
        "rank": LEVEL_RANK[level],
        "computed_at": now,
        "conditions": {
            "strategies": {"pass": strategies_pass, "calls": calls},
            "zscore": {"pass": zscore_pass, "daily": daily_z, "weekly": weekly_z},
            "revenue": {
                "pass": revenue_pass,
                "growth_yoy": revenue["growth_yoy"],
                "change_qoq": revenue["change_qoq"],
                "yoy_growing": revenue["yoy_growing"],
                "qoq_declining": revenue["qoq_declining"],
            },
        },
        "blockers": blockers,
        "caveats": _market_flow_caveats(market_flow_out),
        "missing_inputs": missing_inputs,
    }
    return detail
