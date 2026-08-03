"""Upcoming earnings calendar + per-ticker post-earnings move history.
Spec: specs/component-specs/agent-runner/tools/earnings_calendar.md

Sourcing (probed live 2026-08-02 — deviations from the spec's pseudocode):
- FMP `earnings-calendar` truncates to ~15 rows on this key → the calendar
  comes from **Finnhub `calendar/earnings`** (complete, includes bmo/amc hour).
- Neither calendar carries market cap/name/sector, FMP's screener is 402
  paid-tier, and per-ticker profile calls would blow the Finnhub rate limit →
  the pre-screen joins against the **Nasdaq screener API** universe (one call
  for all US-listed stocks, browser UA, cached 24h) — same public-screen
  fallback pattern as breadth's constituent scrape.
- Finnhub candles are 403 premium, and `stock/earnings` "period" is the fiscal
  quarter end, NOT the report date → post-earnings moves are computed from
  **yfinance** (report timestamps via get_earnings_dates, prices via history).

Cache docs live in `earnings_cache` and are shared with the API container —
keep shapes in sync with backend/earnings_data.py.
"""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests
import yfinance as yf
from pymongo.database import Database

from logging_config import get_logger
from tools.db import EARNINGS_CACHE, get_db
from tools.finnhub_client import finnhub_get

logger = get_logger(__name__)

MIN_MARKET_CAP = 500_000_000  # $500M floor per spec
CALENDAR_CACHE_HOURS = 4
UNIVERSE_CACHE_HOURS = 24
HISTORY_CACHE_HOURS = 24

NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _cache_get(db: Database, query: dict, max_age_hours: int) -> dict | None:
    cutoff = _utcnow() - timedelta(hours=max_age_hours)
    return db[EARNINGS_CACHE].find_one({**query, "fetched_at": {"$gt": cutoff}})


def _cache_put(db: Database, key: dict, data) -> None:
    db[EARNINGS_CACHE].replace_one(key, {**key, "data": data, "fetched_at": _utcnow()}, upsert=True)


# --- universe (market cap / name / sector for the pre-screen) -----------------

def _fetch_universe() -> dict:
    """All US-listed stocks above the cap floor: {SYM: {market_cap, name, sector}}."""
    r = requests.get(
        NASDAQ_SCREENER_URL,
        params={"limit": 25000, "download": "true"},
        headers={"User-Agent": BROWSER_UA},
        timeout=60,
    )
    r.raise_for_status()
    rows = r.json().get("data", {}).get("rows", []) or []

    universe = {}
    for row in rows:
        try:
            cap = float((row.get("marketCap") or "").replace(",", ""))
        except ValueError:
            continue
        if cap < MIN_MARKET_CAP:
            continue
        universe[row["symbol"].strip().upper()] = {
            "market_cap": cap,
            "name": (row.get("name") or "").strip(),
            "sector": (row.get("sector") or "").strip() or None,
        }
    if not universe:
        raise RuntimeError("Nasdaq screener returned no usable rows")
    return universe


def get_screener_universe(db: Database | None = None) -> dict:
    db = db if db is not None else get_db()
    cached = _cache_get(db, {"type": "universe"}, UNIVERSE_CACHE_HOURS)
    if cached:
        return cached["data"]
    universe = _fetch_universe()
    _cache_put(db, {"type": "universe"}, universe)
    return universe


# --- calendar ------------------------------------------------------------------

def get_earnings_calendar(days_ahead: int = 7, db: Database | None = None) -> list[dict]:
    """Every company ≥ $500M cap reporting in the next N days, cached 4h."""
    db = db if db is not None else get_db()
    cached = _cache_get(db, {"type": "calendar", "days": days_ahead}, CALENDAR_CACHE_HOURS)
    if cached:
        return cached["data"]

    start = date.today()
    end = start + timedelta(days=days_ahead)
    raw = finnhub_get("calendar/earnings",
                      **{"from": start.isoformat(), "to": end.isoformat()})
    universe = get_screener_universe(db=db)

    screened, seen = [], set()
    for entry in raw.get("earningsCalendar", []):
        ticker = (entry.get("symbol") or "").upper()
        listed = universe.get(ticker)
        if not ticker or ticker in seen or listed is None:
            continue
        seen.add(ticker)
        hour = entry.get("hour")
        screened.append({
            "ticker": ticker,
            "company": listed["name"],
            "report_date": entry.get("date"),
            "report_time": hour if hour in ("bmo", "amc") else "unknown",
            "eps_estimate": entry.get("epsEstimate"),
            "revenue_estimate": entry.get("revenueEstimate"),
            "market_cap": listed["market_cap"],
            "sector": listed["sector"],
        })

    screened.sort(key=lambda e: (e["report_date"] or "", e["ticker"]))
    _cache_put(db, {"type": "calendar", "days": days_ahead}, screened)
    return screened


# --- per-ticker history --------------------------------------------------------

def _reaction_move(daily_closes: pd.Series, report_ts: pd.Timestamp) -> float | None:
    """% move on the session that first prices the report: the report day itself
    for a before-open print, the next session for an after-close one."""
    idx = daily_closes.index
    report_day = report_ts.normalize().tz_localize(None)
    is_bmo = report_ts.hour < 12

    pos = idx.searchsorted(report_day)
    if not is_bmo:
        # amc: reaction session is the first trading day strictly after report day
        while pos < len(idx) and idx[pos].normalize() <= report_day:
            pos += 1
    if pos <= 0 or pos >= len(idx):
        return None
    pre, post = daily_closes.iloc[pos - 1], daily_closes.iloc[pos]
    return round((float(post) / float(pre) - 1) * 100, 2)


def get_earnings_history(ticker: str, num_quarters: int = 8,
                         db: Database | None = None) -> dict:
    """Historical EPS surprises + the realized post-earnings move per quarter."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()
    cached = _cache_get(db, {"type": "history", "ticker": ticker}, HISTORY_CACHE_HOURS)
    if cached:
        return cached["data"]

    tk = yf.Ticker(ticker)
    try:
        dates = tk.get_earnings_dates(limit=num_quarters + 6)
    except Exception as exc:
        logger.info("earnings dates unavailable for %s: %s", ticker, exc)
        dates = None

    moves = []
    if dates is not None and not dates.empty:
        reported = dates[dates["Reported EPS"].notna()].sort_index(ascending=False)
        closes = tk.history(period="3y", interval="1d")["Close"]
        closes.index = closes.index.tz_localize(None)

        for report_ts, row in reported.head(num_quarters).iterrows():
            move_pct = _reaction_move(closes, report_ts)
            if move_pct is None:
                continue
            estimate = row.get("EPS Estimate")
            actual = row.get("Reported EPS")
            surprise = row.get("Surprise(%)")
            moves.append({
                "period": report_ts.date().isoformat(),
                "eps_estimate": None if pd.isna(estimate) else float(estimate),
                "eps_actual": None if pd.isna(actual) else float(actual),
                "surprise_pct": None if pd.isna(surprise) else round(float(surprise), 2),
                "beat": bool(not pd.isna(estimate) and not pd.isna(actual) and actual > estimate),
                "move_pct": move_pct,
                "move_abs": abs(move_pct),
            })

    avg_abs_move = sum(m["move_abs"] for m in moves) / len(moves) if moves else 0
    beat_rate = sum(1 for m in moves if m["beat"]) / len(moves) if moves else 0
    history = {
        "ticker": ticker,
        "quarters": moves,
        "avg_abs_move_pct": round(avg_abs_move, 2),
        "beat_rate": round(beat_rate, 2),
        "num_quarters": len(moves),
    }
    _cache_put(db, {"type": "history", "ticker": ticker}, history)
    return history
