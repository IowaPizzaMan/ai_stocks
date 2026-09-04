"""Pure signal computation + persistence for the `screener` collection.
Spec: specs/031-semantic-layer-chat; data-model.md; contracts/screener-collection.md.

`screener` is a flat, one-document-per-ticker collection where every
queryable field is top-level. That shape is load-bearing, not stylistic: a
locally-generated chat query can only reliably target a flat schema
(research.md R1) — the same question asked against the raw nested
`price_history`/`financials_cache` shapes produced syntactically invalid
MongoDB from the model. agent-runner is the sole writer of this collection;
backend/semantic/ only reads it.

compute_signals() is pure (no I/O, no bare `datetime.now()` — the timestamp
is an injectable keyword) and total: it never raises on missing, short, or
dirty input. Absence is always represented as `None`, never a fabricated
zero — SC-008 requires the API to report a signal as unavailable rather than
silently treat it as "does not match".
"""
import math
from datetime import datetime, timezone
from statistics import fmean, pstdev

from pymongo.database import Database

from logging_config import get_logger
from tools.db import COMPANY_INFO, FINANCIALS_CACHE, PRICE_HISTORY, SCREENER, TICKER_INDEX, get_db

logger = get_logger(__name__)

# Price signals need a 20-day window plus a 21-trading-day-back monthly
# comparison; 25 raw bars covers both with margin. Below this, every price
# signal is null and insufficient_history is set rather than computed on a
# too-small sample (data-model.md validation rules).
MIN_BARS_FOR_SIGNALS = 25
RANGE_WINDOW = 20
WEEKLY_LOOKBACK = 6   # bars[-6] vs bars[-1]  ~5 trading days, i.e. "the week"
MONTHLY_LOOKBACK = 21  # bars[-21] vs bars[-1] ~1 trading month


def _num(value):
    """Coerce a Mongo numeric wrapper ($numberLong et al.) or plain value to
    a finite float, or None. NaN/Infinity are treated as absent, matching
    tools/db.py::sanitize_floats's stance that non-finite floats never
    represent real data here."""
    if value is None:
        return None
    if isinstance(value, dict) and "$numberLong" in value:
        value = value["$numberLong"]
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _price_signals(bars: list[dict]) -> dict:
    null_result = {
        "last_close": None, "last_bar_date": None,
        "range_pct_20d": None, "zscore_20d": None,
        "weekly_change_pct": None, "monthly_change_pct": None,
        "weekly_trend": None, "insufficient_history": True,
    }
    if len(bars) < MIN_BARS_FOR_SIGNALS:
        return null_result

    last_close = _num(bars[-1].get("close"))
    result = {**null_result, "insufficient_history": False,
              "last_bar_date": bars[-1].get("date"), "last_close": last_close}
    if last_close is None:
        return result

    window = bars[-RANGE_WINDOW:]
    closes = [c for b in window for c in [_num(b.get("close"))] if c is not None]
    highs = [h for b in window for h in [_num(b.get("high"))] if h is not None]
    lows = [lo for b in window for lo in [_num(b.get("low"))] if lo is not None]

    if highs and lows:
        hi, lo = max(highs), min(lows)
        if hi > lo:
            result["range_pct_20d"] = (last_close - lo) / (hi - lo)

    if len(closes) >= 2:
        mean = fmean(closes)
        sd = pstdev(closes)
        if sd > 0:
            result["zscore_20d"] = (last_close - mean) / sd

    week_ago = _num(bars[-WEEKLY_LOOKBACK].get("close"))
    if week_ago:
        change = (last_close - week_ago) / week_ago * 100
        result["weekly_change_pct"] = change
        result["weekly_trend"] = "up" if change > 0 else ("down" if change < 0 else "flat")

    month_ago = _num(bars[-MONTHLY_LOOKBACK].get("close"))
    if month_ago:
        result["monthly_change_pct"] = (last_close - month_ago) / month_ago * 100

    return result


def _financial_signals(financials: dict | None) -> dict:
    result = {
        "revenue_growth_yoy": None, "net_income_growth_yoy": None,
        "net_profit_margin": None, "margin_trend": None,
        "financials_trend": None, "free_cash_flow": None,
        "total_debt": None, "fcf_exceeds_debt": None,
        "financials_as_of": None,
    }
    if not financials:
        return result

    growth = financials.get("growth") or []
    ratios = financials.get("ratios") or []
    cashflow = financials.get("cashflow_annual") or []
    balance = financials.get("balance_annual") or []
    income = financials.get("income_annual") or []

    if income:
        result["financials_as_of"] = income[0].get("date")

    revenue_growth = _num(growth[0].get("growthRevenue")) if growth else None
    net_income_growth = _num(growth[0].get("growthNetIncome")) if growth else None
    result["revenue_growth_yoy"] = revenue_growth
    result["net_income_growth_yoy"] = net_income_growth
    result["net_profit_margin"] = _num(ratios[0].get("netProfitMargin")) if ratios else None

    fcf = _num(cashflow[0].get("freeCashFlow")) if cashflow else None
    debt = _num(balance[0].get("totalDebt")) if balance else None
    result["free_cash_flow"] = fcf
    result["total_debt"] = debt
    result["fcf_exceeds_debt"] = (fcf > debt) if (fcf is not None and debt is not None) else None

    # Trend fields require >= 2 periods (data-model.md) — a single annual
    # period gives a valid point-in-time growth figure (FMP's growth record
    # is already YoY) but cannot establish a trend on its own.
    if len(ratios) < 2:
        return result

    latest_margin = result["net_profit_margin"]
    prior_margin = _num(ratios[1].get("netProfitMargin"))
    margin_trend = None
    if latest_margin is not None and prior_margin is not None:
        if latest_margin > prior_margin:
            margin_trend = "improving"
        elif latest_margin < prior_margin:
            margin_trend = "deteriorating"
        else:
            margin_trend = "flat"
    result["margin_trend"] = margin_trend

    positive = sum([
        revenue_growth is not None and revenue_growth > 0,
        net_income_growth is not None and net_income_growth > 0,
        margin_trend == "improving",
    ])
    negative = sum([
        revenue_growth is not None and revenue_growth < 0,
        net_income_growth is not None and net_income_growth < 0,
        margin_trend == "deteriorating",
    ])
    if positive >= 2:
        result["financials_trend"] = "improving"
    elif negative >= 2:
        result["financials_trend"] = "deteriorating"
    else:
        result["financials_trend"] = "flat"

    return result


def _profile_signals(profile: dict | None) -> dict:
    profile = profile or {}
    return {
        "name": profile.get("name"),
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "market_cap": _num(profile.get("market_cap")),
    }


def compute_signals(
    bars: list[dict],
    financials: dict | None,
    profile: dict | None,
    *,
    ticker: str,
    is_tracked: bool,
    now: datetime | None = None,
    liked_status: str | None = None,
) -> dict:
    """Pure: same inputs -> identical output. `financials` is the
    `financials_cache.data` sub-document (income_annual/balance_annual/
    cashflow_annual/ratios/growth), not the whole cache document.
    `liked_status` is copied verbatim from `ticker_index.sentiment`
    ("liked" | "disliked" | None) — never fabricated from absence."""
    now = now or datetime.now(timezone.utc)
    bars = bars or []
    doc = {
        "ticker": ticker.upper(),
        "is_tracked": bool(is_tracked),
        "signals_as_of": now,
        "price_data_through": bars[-1]["date"] if bars else None,
        "liked_status": liked_status,
    }
    doc.update(_profile_signals(profile))
    doc.update(_price_signals(bars))
    doc.update(_financial_signals(financials))
    return doc


def refresh_all(db: Database | None = None) -> int:
    """Recomputes and upserts `screener` for every ticker that has a
    `price_history` document — the union of the tracked universe and the
    breadth-only market universe (research.md R7). Single writer, full-
    document replace keyed on ticker (safe here, unlike price_history, which
    has two writers — research.md R11). Returns the number of documents
    written."""
    db = db if db is not None else get_db()
    tracked_rows = list(db[TICKER_INDEX].find({}, {"ticker": 1, "sentiment": 1}))
    tracked = {row["ticker"] for row in tracked_rows}
    liked_status_by_ticker = {row["ticker"]: row.get("sentiment") for row in tracked_rows}

    count = 0
    for row in db[PRICE_HISTORY].find({}, {"ticker": 1, "bars": 1}):
        ticker = row["ticker"]
        financials_doc = db[FINANCIALS_CACHE].find_one({"ticker": ticker}, {"data": 1})
        profile_doc = db[COMPANY_INFO].find_one({"ticker": ticker}, {"profile": 1})
        doc = compute_signals(
            row.get("bars") or [],
            (financials_doc or {}).get("data"),
            (profile_doc or {}).get("profile"),
            ticker=ticker,
            is_tracked=ticker in tracked,
            liked_status=liked_status_by_ticker.get(ticker),
        )
        db[SCREENER].replace_one({"ticker": ticker}, doc, upsert=True)
        count += 1

    logger.info("screener refresh: wrote %s documents", count)
    return count


def refresh_one(ticker: str, db: Database | None = None) -> dict | None:
    """Recomputes `screener` for a single ticker, called right after that
    ticker's price/financials prefetch completes so signals never lag their
    inputs by a cycle. Returns the written document, or None if the ticker
    has no price history yet."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    price_doc = db[PRICE_HISTORY].find_one({"ticker": ticker}, {"bars": 1})
    if not price_doc:
        return None

    financials_doc = db[FINANCIALS_CACHE].find_one({"ticker": ticker}, {"data": 1})
    profile_doc = db[COMPANY_INFO].find_one({"ticker": ticker}, {"profile": 1})
    ticker_index_doc = db[TICKER_INDEX].find_one({"ticker": ticker})
    is_tracked = ticker_index_doc is not None
    liked_status = ticker_index_doc.get("sentiment") if ticker_index_doc else None

    doc = compute_signals(
        price_doc.get("bars") or [],
        (financials_doc or {}).get("data"),
        (profile_doc or {}).get("profile"),
        ticker=ticker,
        is_tracked=is_tracked,
        liked_status=liked_status,
    )
    db[SCREENER].replace_one({"ticker": ticker}, doc, upsert=True)
    return doc


def run_screener_refresh(db: Database) -> int:
    """Admin job entry point (tools/admin_jobs.py's JOB_HANDLERS shape:
    handler(db) -> record_count)."""
    return refresh_all(db)
