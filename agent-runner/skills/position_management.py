"""Stair-step trailing stop management for open swing positions.
Rule system: specs/position_management_agent_spec.md — pure functions, no LLM calls.

run(ticker, data) processes ONE position per call (the standard skill
interface); the PositionManagement agent loops it over the ledger.

data = {
    "position": { entry_price, entry_date, current_stop, shares, breakout_level },
    "daily": [ {Date, Open, High, Low, Close, ...}, ... ]  # ≥2 sessions, oldest→newest
    "market_condition": "favorable" | "neutral" | "unfavorable"   (default neutral)
    "earnings_date": date/datetime/ISO string                      (optional)
    "config": { stop_buffer_fixed, stop_buffer_pct, use_close_vs_intraday,
                min_profit_to_trail, max_days_held }               (optional overrides)
}
"""
from datetime import date, datetime

DEFAULTS = {
    "stop_buffer_fixed": 0.15,
    "stop_buffer_pct": None,       # overrides fixed when set (e.g. 0.003 = 0.3%)
    "use_close_vs_intraday": "intraday",
    "min_profit_to_trail": 0.05,
    "max_days_held": None,
}
EARNINGS_WARN_DAYS = 3


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _bar_date(bar) -> date | None:
    for key in ("Date", "date", "index"):
        if key in bar:
            return _as_date(bar[key])
    return None


def run(ticker: str, data: dict) -> dict:
    position = data.get("position")
    daily = data.get("daily")
    if not position or not daily or len(daily) < 2:
        raise ValueError("position_management.run needs data['position'] and ≥2 daily bars")

    cfg = {**DEFAULTS, **(data.get("config") or {})}
    market_condition = data.get("market_condition", "neutral")

    entry_price = float(position["entry_price"])
    current_stop = float(position["current_stop"])
    prev_stop = current_stop

    today, prior = daily[-1], daily[-2]
    prior_day_low = float(prior["Low"])
    open_, low, close = float(today["Open"]), float(today["Low"]), float(today["Close"])

    buffer = (prior_day_low * cfg["stop_buffer_pct"] if cfg["stop_buffer_pct"]
              else cfg["stop_buffer_fixed"])
    candidate_stop = round(prior_day_low - buffer, 4)

    pnl_pct = (close - entry_price) / entry_price * 100
    today_date = _bar_date(today)
    entry_date = _as_date(position.get("entry_date"))
    days_held = (today_date - entry_date).days if today_date and entry_date else None

    alerts = []
    notes = []

    earnings = _as_date(data.get("earnings_date"))
    if earnings and today_date and 0 <= (earnings - today_date).days <= EARNINGS_WARN_DAYS:
        alerts.append(f"earnings on {earnings.isoformat()} — within {EARNINGS_WARN_DAYS} sessions; "
                      "consider tightening the stop or exiting before the event")

    # --- exit triggers first (a stop that's hit outranks everything) ---
    if open_ <= current_stop:
        alerts.append("gapped down through the stop at the open — exit immediately")
        return _report(ticker, "EXIT", prior_day_low, current_stop, prev_stop, entry_price,
                       pnl_pct, days_held, market_condition, alerts,
                       "gap-down open below stop; exit at market")
    breached = low <= current_stop if cfg["use_close_vs_intraday"] == "intraday" else close <= current_stop
    if breached:
        return _report(ticker, "EXIT", prior_day_low, current_stop, prev_stop, entry_price,
                       pnl_pct, days_held, market_condition, alerts,
                       "price broke below prior day's low — stop triggered")

    # --- market condition gate ---
    if market_condition == "unfavorable":
        alerts.append("market condition unfavorable — position flagged for manual review; "
                      "trailing paused (consider tightening or exiting)")
        return _report(ticker, "REVIEW", prior_day_low, current_stop, prev_stop, entry_price,
                       pnl_pct, days_held, market_condition, alerts,
                       "trailing paused while market is unfavorable")

    # --- stair-step: stop only ever moves up ---
    if pnl_pct < 0:
        notes.append("position is below entry — reverting to the initial stop; no trailing")
        action = "HOLD"
    elif pnl_pct / 100 < cfg["min_profit_to_trail"]:
        notes.append(f"profit {pnl_pct:.1f}% below the {cfg['min_profit_to_trail']:.0%} "
                     "trail threshold — holding the initial stop")
        action = "HOLD"
    elif candidate_stop > current_stop:
        current_stop = candidate_stop
        moved = round(current_stop - prev_stop, 4)
        alerts.append(f"stop raised {moved:+.2f} to {current_stop:.2f}")
        notes.append(f"stop walked up {moved:.2f}; position continues to trend")
        action = "UPDATE"
    else:
        notes.append("prior day's low did not make a higher stop — keeping the existing level")
        action = "HOLD"

    if cfg["max_days_held"] and days_held is not None and days_held > cfg["max_days_held"]:
        alerts.append(f"held {days_held} days (> {cfg['max_days_held']}) — review the position")

    return _report(ticker, action, prior_day_low, current_stop, prev_stop, entry_price,
                   pnl_pct, days_held, market_condition, alerts, "; ".join(notes))


def _report(ticker, action, prior_day_low, new_stop, previous_stop, entry_price,
            pnl_pct, days_held, market_condition, alerts, notes) -> dict:
    return {
        "ticker": ticker,
        "action": action,
        "prior_day_low": round(prior_day_low, 4),
        "new_stop": round(new_stop, 4),
        "previous_stop": round(previous_stop, 4),
        "stop_moved_by": round(new_stop - previous_stop, 4),
        "entry_price": round(entry_price, 4),
        "unrealized_pnl_pct": round(pnl_pct, 2),
        "days_held": days_held,
        "market_condition": market_condition,
        "alerts": alerts,
        "notes": notes,
    }
