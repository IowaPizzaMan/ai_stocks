"""Earnings calendar / universe / history fetch for the API container.

Mirror of agent-runner/tools/earnings_calendar.py — the two containers only
share MongoDB, so the fetch layer is intentionally duplicated (same precedent
as db.py's collection constants and routers/price.py's FMP fetch). Both
sides read and write the SAME `earnings_cache` docs, so in practice whichever
container touches a window first fetches and the other serves from cache.
Keep shapes and constants in sync by hand.

Sourcing rationale (probed live 2026-08-02): Finnhub `calendar/earnings` for
the sweep (FMP truncates on this key), Nasdaq screener API for the $500M
cap/name/sector pre-screen. Post-earnings reaction moves are computed from
FMP as of specs/017-fmp-migration-admin — previously yfinance.
"""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests
from pymongo.database import Database

from db import EARNINGS_CACHE
from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

MIN_MARKET_CAP = 500_000_000
CALENDAR_CACHE_HOURS = 4
UNIVERSE_CACHE_HOURS = 24
HISTORY_CACHE_HOURS = 24

FINNHUB_BASE = "https://finnhub.io/api/v1/"
FMP_BASE = "https://financialmodelingprep.com/stable/"
NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _cache_get(db: Database, query: dict, max_age_hours: int) -> dict | None:
    cutoff = _utcnow() - timedelta(hours=max_age_hours)
    return db[EARNINGS_CACHE].find_one({**query, "fetched_at": {"$gt": cutoff}})


def _cache_put(db: Database, key: dict, data) -> None:
    db[EARNINGS_CACHE].replace_one(key, {**key, "data": data, "fetched_at": _utcnow()}, upsert=True)


def _finnhub_get(path: str, **params) -> dict | list:
    params["token"] = settings.finnhub_api_key
    r = requests.get(f"{FINNHUB_BASE}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _fmp_get(path: str) -> dict | list:
    sep = "&" if "?" in path else "?"
    url = f"{FMP_BASE}{path}{sep}apikey={settings.fmp_api_key}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def _fetch_eod_closes(ticker: str) -> pd.Series:
    raw = _fmp_get(f"historical-price-eod/full?symbol={ticker}")
    rows = raw.get("historical", raw) if isinstance(raw, dict) else raw
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df["close"]


# --- universe (market cap / name / sector for the pre-screen) -----------------

def _fetch_universe() -> dict:
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


def get_screener_universe(db: Database) -> dict:
    cached = _cache_get(db, {"type": "universe"}, UNIVERSE_CACHE_HOURS)
    if cached:
        return cached["data"]
    universe = _fetch_universe()
    _cache_put(db, {"type": "universe"}, universe)
    return universe


# --- calendar ------------------------------------------------------------------

def get_earnings_calendar(days_ahead: int, db: Database) -> list[dict]:
    """Every company ≥ $500M cap reporting in the next N days, cached 4h."""
    cached = _cache_get(db, {"type": "calendar", "days": days_ahead}, CALENDAR_CACHE_HOURS)
    if cached:
        return cached["data"]

    start = date.today()
    end = start + timedelta(days=days_ahead)
    raw = _finnhub_get("calendar/earnings",
                       **{"from": start.isoformat(), "to": end.isoformat()})
    universe = get_screener_universe(db)

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

def _reaction_move(daily_closes: pd.Series, report_date: str, is_bmo: bool) -> float | None:
    """% move on the session that first prices the report: the report day itself
    for a before-open print, the next session for an after-close one."""
    idx = daily_closes.index
    report_day = pd.Timestamp(report_date).normalize()

    pos = idx.searchsorted(report_day)
    if not is_bmo:
        while pos < len(idx) and idx[pos].normalize() <= report_day:
            pos += 1
    if pos <= 0 or pos >= len(idx):
        return None
    pre, post = daily_closes.iloc[pos - 1], daily_closes.iloc[pos]
    return round((float(post) / float(pre) - 1) * 100, 2)


def get_earnings_history(ticker: str, db: Database, num_quarters: int = 8) -> dict:
    """Historical EPS surprises + the realized post-earnings move per quarter.
    Sourced from FMP: `earnings` for dates/EPS, EOD closes for the reaction move."""
    ticker = ticker.upper()
    cached = _cache_get(db, {"type": "history", "ticker": ticker}, HISTORY_CACHE_HOURS)
    if cached:
        return cached["data"]

    try:
        raw = _fmp_get(f"earnings?symbol={ticker}&limit={num_quarters + 6}")
    except Exception as exc:
        logger.info("earnings dates unavailable for %s: %s", ticker, exc)
        raw = []

    reported = sorted(
        (e for e in (raw or []) if e.get("epsActual") is not None and e.get("date")),
        key=lambda e: e["date"], reverse=True,
    )

    moves = []
    if reported:
        try:
            closes = _fetch_eod_closes(ticker)
        except Exception as exc:
            logger.info("price history unavailable for %s: %s", ticker, exc)
            closes = pd.Series(dtype=float)

        for entry in reported[:num_quarters]:
            is_bmo = entry.get("time") == "bmo"
            move_pct = _reaction_move(closes, entry["date"], is_bmo)
            if move_pct is None:
                continue
            estimate = entry.get("epsEstimated")
            actual = entry.get("epsActual")
            surprise = None
            if estimate not in (None, 0) and actual is not None:
                surprise = round((actual - estimate) / abs(estimate) * 100, 2)
            moves.append({
                "period": entry["date"],
                "eps_estimate": estimate,
                "eps_actual": actual,
                "surprise_pct": surprise,
                "beat": bool(estimate is not None and actual is not None and actual > estimate),
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
