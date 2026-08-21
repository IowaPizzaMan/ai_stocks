"""Earnings calendar / universe / history fetch for the API container.

Mirror of agent-runner/tools/earnings_calendar.py — the two containers only
share MongoDB, so the fetch layer is intentionally duplicated (same precedent
as db.py's collection constants and routers/price.py's FMP fetch). The
agent-runner's scanner stays on Finnhub for its forward-only screen and
writes `{"type": "calendar", "days": N}` docs; this module now sources the
calendar from FMP and writes `{"type": "calendar_range", "from", "to"}` docs
instead — deliberately a different key shape so the two services' differently
-sourced data never collides in the shared `earnings_cache` collection
(constitution Principle VI; specs/025-earnings-page-filters research.md D7).

Sourcing rationale (probed live 2026-08-17, specs/025-earnings-page-filters):
FMP `stable/earnings-calendar?from=&to=` for the sweep — the "~15 rows"
truncation that previously ruled this endpoint out (see KNOWN_ISSUES.md) did
not reproduce (789 rows for a 5-day window, 2,347 for 6 days), and unlike
Finnhub's calendar it carries `epsActual`/`revenueActual`, which the surprise
feature requires. It has no before-open/after-close marker, so that column is
dropped. Nasdaq screener API still supplies the $500M cap/name/sector
pre-screen. Post-earnings reaction moves (get_earnings_history below) are
computed from FMP as of specs/017-fmp-migration-admin — previously yfinance.
"""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests
from pymongo.database import Database

from db import EARNINGS_CACHE
from fmp import FmpBudgetExceededError, fmp_get
from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

MIN_MARKET_CAP = 500_000_000
CALENDAR_CACHE_HOURS = 4
UNIVERSE_CACHE_HOURS = 24
HISTORY_CACHE_HOURS = 24

FMP_BASE = "https://financialmodelingprep.com/stable/"
NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class CalendarUnavailableError(RuntimeError):
    """The calendar provider is unreachable and no cached window exists to
    fall back to. Distinct from FmpBudgetExceededError, which the router
    maps to a different status (contracts/earnings-calendar.md)."""


class UniverseUnavailableError(RuntimeError):
    """The screener universe (market cap / name / sector) is unavailable."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _cache_get(db: Database, query: dict, max_age_hours: int) -> dict | None:
    cutoff = _utcnow() - timedelta(hours=max_age_hours)
    return db[EARNINGS_CACHE].find_one({**query, "fetched_at": {"$gt": cutoff}})


def _cache_put(db: Database, key: dict, data) -> None:
    db[EARNINGS_CACHE].replace_one(key, {**key, "data": data, "fetched_at": _utcnow()}, upsert=True)


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

def _surprise_pct(actual: float | None, estimate: float | None) -> float | None:
    """Signed % surprise relative to |estimate|. None (never 0 or inf) when the
    comparison cannot be made — missing actual, missing estimate, or a zero
    estimate. `abs(estimate)` in the denominator is what makes a negative-EPS
    beat (e.g. actual -0.20 vs estimate -0.30) resolve as a beat rather than
    inverting to a miss (spec FR-009/FR-011, data-model.md ss4)."""
    if actual is None or estimate is None or estimate == 0:
        return None
    return round((actual - estimate) / abs(estimate) * 100, 2)


def _reporting_state(report_date: str | None, eps_actual, revenue_actual, today: date) -> str:
    """`reported` if either actual is in; else `awaiting` for a past date with
    no actuals yet, `upcoming` otherwise (data-model.md ss3). A past date with
    no actuals is common, not an error — it must never be shown as a miss."""
    if eps_actual is not None or revenue_actual is not None:
        return "reported"
    try:
        parsed = date.fromisoformat(report_date) if report_date else None
    except ValueError:
        parsed = None
    if parsed is not None and parsed < today:
        return "awaiting"
    return "upcoming"


def _dedupe_calendar_rows(rows: list[dict]) -> list[dict]:
    """Real FMP windows contain duplicate symbols (observed: NVVE, ZCAR, SDOT,
    UGP and others in a single 6-day window). Collapse on symbol, keeping the
    row with the latest lastUpdated; tie-break on the later report date so a
    stale duplicate can never displace a fresh one (spec Edge Cases)."""
    best: dict[str, dict] = {}
    for row in rows:
        symbol = (row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        current = best.get(symbol)
        if current is None:
            best[symbol] = row
            continue
        new_key = (row.get("lastUpdated") or "", row.get("date") or "")
        old_key = (current.get("lastUpdated") or "", current.get("date") or "")
        if new_key > old_key:
            best[symbol] = row
    return list(best.values())


def _build_entry(row: dict, symbol: str, listed: dict, today: date) -> dict:
    eps_estimate = row.get("epsEstimated")
    eps_actual = row.get("epsActual")
    revenue_estimate = row.get("revenueEstimated")
    revenue_actual = row.get("revenueActual")
    eps_surprise = _surprise_pct(eps_actual, eps_estimate)
    revenue_surprise = _surprise_pct(revenue_actual, revenue_estimate)
    return {
        "ticker": symbol,
        "company": listed["name"],
        "sector": listed["sector"],
        "market_cap": listed["market_cap"],
        "report_date": row.get("date"),
        "eps_estimate": eps_estimate,
        "eps_actual": eps_actual,
        "revenue_estimate": revenue_estimate,
        "revenue_actual": revenue_actual,
        "eps_surprise_pct": eps_surprise,
        "revenue_surprise_pct": revenue_surprise,
        "beat": (eps_surprise > 0) if eps_surprise is not None else None,
        "reporting_state": _reporting_state(row.get("date"), eps_actual, revenue_actual, today),
        "last_updated": row.get("lastUpdated"),
    }


def _screen_and_build(raw_rows: list[dict], universe: dict, today: date) -> list[dict]:
    """Dedupe, drop symbols outside the >=$500M universe (this both enforces
    the noise screen and guarantees every surviving row has a market_cap to
    sort on), then order by market cap descending / ticker ascending — fixed,
    not user-overridable (FR-019, FR-020, data-model.md ss5)."""
    entries = []
    for row in _dedupe_calendar_rows(raw_rows):
        symbol = (row.get("symbol") or "").strip().upper()
        listed = universe.get(symbol)
        if not symbol or listed is None:
            continue
        entries.append(_build_entry(row, symbol, listed, today))
    entries.sort(key=lambda e: (-(e["market_cap"] or 0), e["ticker"]))
    return entries


def _cached_calendar_payload(doc: dict, stale: bool) -> dict:
    fetched_at = doc["fetched_at"]
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return {
        "entries": doc["data"]["entries"],
        "total_before_screen": doc["data"]["total_before_screen"],
        "stale": stale,
        "fetched_at": fetched_at.isoformat(),
    }


def get_earnings_calendar(start: date, end: date, db: Database) -> dict:
    """Every company >=$500M cap reporting between start and end (inclusive),
    with actuals/surprise for anything already reported. Cached 4h per exact
    window under `{"type": "calendar_range", "from", "to"}` (contracts/
    earnings-calendar.md). On a spent FMP budget or an unreachable provider,
    serves the newest cached window regardless of age and marks it stale;
    raises only when nothing cached exists for the router to translate into
    503/502 (see CalendarUnavailableError, UniverseUnavailableError)."""
    cache_key = {"type": "calendar_range", "from": start.isoformat(), "to": end.isoformat()}

    cached = _cache_get(db, cache_key, CALENDAR_CACHE_HOURS)
    if cached:
        return _cached_calendar_payload(cached, stale=False)

    try:
        raw = fmp_get(f"earnings-calendar?from={start.isoformat()}&to={end.isoformat()}", db=db)
    except FmpBudgetExceededError:
        stale_doc = db[EARNINGS_CACHE].find_one(cache_key)
        if stale_doc:
            logger.warning("earnings calendar %s..%s: FMP budget spent — serving stale cache",
                           start, end)
            return _cached_calendar_payload(stale_doc, stale=True)
        raise
    except requests.RequestException as exc:
        stale_doc = db[EARNINGS_CACHE].find_one(cache_key)
        if stale_doc:
            logger.warning("earnings calendar %s..%s: fetch failed (%s) — serving stale cache",
                           start, end, exc)
            return _cached_calendar_payload(stale_doc, stale=True)
        raise CalendarUnavailableError(str(exc)) from exc

    try:
        universe = get_screener_universe(db)
    except Exception as exc:
        raise UniverseUnavailableError(str(exc)) from exc

    raw_rows = raw if isinstance(raw, list) else []
    entries = _screen_and_build(raw_rows, universe, date.today())
    payload = {"entries": entries, "total_before_screen": len(raw_rows)}
    _cache_put(db, cache_key, payload)
    return {**payload, "stale": False, "fetched_at": _utcnow().isoformat()}


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
