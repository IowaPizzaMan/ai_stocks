"""Spec: specs/component-specs/frontend/components/stock/BreadthDivergenceChart.md,
specs/026-macro-market-dashboard/contracts/macro-api.md

Read-only view over what the agent-runner's daily breadth/economics passes
already wrote to Mongo — no provider calls here. The oscillator math, SPY
fetch and divergence detection live in agent-runner/tools/breadth.py; the
treasury/calendar/indicator/risk-premium pulls live in
agent-runner/tools/economics.py. This router just serves and shapes the
cached data so the frontend can draw it.
"""
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Depends, Query

from db import (
    BREADTH_CACHE,
    BREADTH_DIVERGENCES,
    BREADTH_META,
    DATASET_META,
    ECONOMIC_CALENDAR_EVENTS,
    ECONOMIC_INDICATORS,
    MACRO_ANALYSIS_CACHE,
    MARKET_FLOW_EVENTS,
    MARKET_MOVERS,
    MARKET_NEWS_CACHE,
    MARKET_RISK_PREMIUM,
    TREASURY_RATES,
    WORK_QUEUE,
)
from deps import db_dependency
from fmp import FmpBudgetExceededError, fmp_get
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/market", tags=["market"])

NO_DIVERGENCE = {"type": "none", "description": "no breadth data yet",
                 "price_points": [], "osc_points": []}


def _rows(db, exchange: str, lookback_days: int) -> list[dict]:
    """Cached breadth rows for one exchange, oldest first."""
    rows = list(
        db[BREADTH_CACHE]
        .find({"exchange": exchange}, {"_id": 0, "date": 1, "mcclellan": 1, "spy_close": 1})
        .sort("date", -1)
        .limit(lookback_days)
    )
    return list(reversed(rows))


@router.get("/breadth")
def get_breadth(lookback_days: int = Query(default=60, ge=10, le=250),
                db=Depends(db_dependency)):
    nyse = _rows(db, "nyse", lookback_days)
    nasdaq = _rows(db, "nasdaq", lookback_days)
    meta = db[BREADTH_META].find_one({"key": "last_divergence"})
    history = list(
        db[BREADTH_DIVERGENCES]
        .find({"resolved": {"$ne": None}}, {"_id": 0})
        .sort("resolved", -1)
        .limit(20)
    )

    return {
        # SPY is stored on the nyse rows — the divergence read is SPY vs NYMO
        "spy": [{"date": r["date"], "close": r["spy_close"]}
                for r in nyse if r.get("spy_close") is not None],
        "nymo": [{"date": r["date"], "value": r["mcclellan"]} for r in nyse],
        "namo": [{"date": r["date"], "value": r["mcclellan"]} for r in nasdaq],
        "divergence": (meta or {}).get("value") or NO_DIVERGENCE,
        "divergence_history": list(reversed(history)),
        "as_of": nyse[-1]["date"] if nyse else None,
        "method": "computed_ratio_adjusted",
    }


@router.get("/flow-events")
def get_flow_events(limit: int = Query(default=5, ge=1, le=50),
                    db=Depends(db_dependency)):
    """Market-wide events (currently breadth divergences) for the feed —
    ticker-less, so they can't ride the per-ticker analysis feed."""
    return list(
        db[MARKET_FLOW_EVENTS].find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    )


# ──────────────────────────────────────────────────────────────────────────
# Top Traded Stocks — specs/028-dashboard-tweaks-batch US6
#
# Read-only over market_movers (category="actives"), written by the
# agent-runner's market_movers_pull admin job
# (agent-runner/tools/market_movers.py). This router never calls a provider
# itself; POST /refresh only enqueues that job, deduped like Portfolio
# Summary's regenerate (routers/portfolio.py).
#
# The provider supplies no volume, so ordering can't come from it — the job
# stamps its own array position as `rank`, and that is what this endpoint
# sorts by (R9). `volume` is never present in the response, not sent as null.
# ──────────────────────────────────────────────────────────────────────────

MOST_ACTIVES_DEFAULT_LIMIT = 20
MOST_ACTIVES_MAX_LIMIT = 100


@router.get("/most-actives")
def get_most_actives(
    limit: int = Query(default=MOST_ACTIVES_DEFAULT_LIMIT, ge=1, le=MOST_ACTIVES_MAX_LIMIT),
    db=Depends(db_dependency),
):
    """Always 200 — an empty result before the first refresh is a valid
    state, not an error (mirrors /market/news and /portfolio/digest)."""
    latest = db[MARKET_MOVERS].find_one(
        {"category": "actives"}, {"_id": 0, "date": 1}, sort=[("date", -1)]
    )
    if not latest:
        return {"items": [], "as_of": None, "date": None}

    date = latest["date"]
    items = list(
        db[MARKET_MOVERS]
        .find({"category": "actives", "date": date}, {"_id": 0, "volume": 0})
        .sort("rank", 1)
        .limit(limit)
    )
    as_of = max((i["collected_at"] for i in items), default=None)
    for i in items:
        i.pop("collected_at", None)
        i.pop("date", None)
        i.pop("category", None)
        i.pop("rank", None)
        i.pop("source", None)
    return {
        "items": items,
        "as_of": _as_utc(as_of).isoformat() if as_of else None,
        "date": date,
    }


@router.post("/most-actives/refresh")
def refresh_most_actives(db=Depends(db_dependency)):
    existing = db[WORK_QUEUE].find_one(
        {"job_type": "market_movers_pull", "status": {"$in": ["pending", "running"]}}
    )
    if existing:
        return {"status": "already_queued", "job_id": str(existing["_id"])}

    now = datetime.now(timezone.utc)
    result = db[WORK_QUEUE].insert_one({
        "job_type": "market_movers_pull",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    })
    return {"status": "enqueued", "job_id": str(result.inserted_id)}


# ──────────────────────────────────────────────────────────────────────────
# Market news — specs/022-market-news-feed
#
# The Stocks page's headline panel. Cache-first from the start: at most one
# provider call an hour no matter how often the page is opened (FR-011), and
# a failed refresh serves the previous articles rather than erroring (FR-013).
# Freshness is compared here rather than via a TTL index, because a TTL index
# would delete the very copy the stale fallback needs (data-model.md §2).
# ──────────────────────────────────────────────────────────────────────────

NEWS_KEY = "stock-latest"
NEWS_LIMIT = 20
NEWS_MAX_AGE = timedelta(minutes=60)
EXCERPT_CHARS = 400


def _normalize(rows: list) -> list[dict]:
    """FMP's camelCase → the shape the panel reads, newest first, capped.

    A headline with no title or link can't be read or followed, so it's dropped
    rather than rendered as a dead row.
    """
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        if not title or not url:
            continue
        published = str(r.get("publishedDate") or "")
        out.append({
            "ticker": r.get("symbol") or None,
            "datetime": published,
            "date": published[:10],
            "source": r.get("publisher") or r.get("site") or "unknown",
            "headline": title,
            "url": url,
            "text_excerpt": (r.get("text") or "")[:EXCERPT_CHARS],
        })
    out.sort(key=lambda a: a["datetime"], reverse=True)
    return out[:NEWS_LIMIT]


@router.get("/news")
def get_market_news(db=Depends(db_dependency)):
    """Recent market-wide headlines, refreshed at most hourly.

    Always returns 200 — this backs a panel on the app's home page, where a
    red error state would be worse than an empty, labeled list (FR-012).
    """
    cached = db[MARKET_NEWS_CACHE].find_one({"key": NEWS_KEY}, {"_id": 0})
    # Truncated to milliseconds because that is all MongoDB stores — otherwise
    # `as_of` would change on the round trip and look like a refresh that never
    # happened to any client comparing it across requests.
    now = datetime.now(timezone.utc).replace(microsecond=0)

    if cached:
        fetched_at = cached.get("fetched_at")
        if fetched_at is not None:
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if now - fetched_at < NEWS_MAX_AGE:
                return {"articles": cached.get("articles", []),
                        "as_of": fetched_at.isoformat(), "stale": False}

    try:
        rows = fmp_get(f"news/stock-latest?limit={NEWS_LIMIT * 5}", db=db)
    except FmpBudgetExceededError:
        logger.warning("market news: daily FMP budget spent — serving cached articles")
        return _stale(cached)
    except (requests.HTTPError, requests.RequestException) as exc:
        logger.warning("market news fetch failed (%s) — serving cached articles", exc)
        return _stale(cached)

    articles = _normalize(rows if isinstance(rows, list) else [])
    db[MARKET_NEWS_CACHE].replace_one(
        {"key": NEWS_KEY},
        {"key": NEWS_KEY, "articles": articles, "fetched_at": now},
        upsert=True,
    )
    return {"articles": articles, "as_of": now.isoformat(), "stale": False}


def _stale(cached: dict | None) -> dict:
    """Last known articles, flagged as not current. Empty when nothing was ever
    cached — the panel shows its unavailable state rather than an error."""
    if not cached:
        return {"articles": [], "as_of": None, "stale": True}
    fetched_at = cached.get("fetched_at")
    return {
        "articles": cached.get("articles", []),
        "as_of": fetched_at.isoformat() if fetched_at else None,
        "stale": True,
    }


@router.get("/macro")
def get_macro(db=Depends(db_dependency)):
    """Every sector's macro read, produced independently by the agent-runner's
    macro worker (not per-ticker) — newest first."""
    docs = list(db[MACRO_ANALYSIS_CACHE].find({}, {"_id": 0}).sort("computed_at", -1))
    sectors = [{"sector": doc["sector"], "computed_at": doc["computed_at"], **doc["result"]}
               for doc in docs]
    return {"sectors": sectors, "as_of": sectors[0]["computed_at"] if sectors else None}


# ──────────────────────────────────────────────────────────────────────────
# Economics dashboard — specs/026-macro-market-dashboard
#
# Every endpoint below is a read-only shape over what
# agent-runner/tools/economics.py already wrote (constitution IV — no
# provider call belongs on a request path). All four always return 200; a
# missing/failed economics_pull run is reflected in the freshness envelope
# (`as_of`/`stale`), never as an HTTP error (FR-028).
# ──────────────────────────────────────────────────────────────────────────

def _as_utc(dt: datetime) -> datetime:
    """Mongo drivers hand back naive UTC datetimes — pin the tzinfo so both
    isoformat() output carries an explicit offset and comparisons against
    datetime.now(timezone.utc) are well-defined."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _economics_freshness(db) -> dict:
    """`dataset_meta.economics`, written by run_economics_pull. Absent ⇒ the
    job has never completed a successful run yet — as_of null, not stale
    (there's nothing to call stale)."""
    meta = db[DATASET_META].find_one({"dataset": "economics"}, {"_id": 0})
    if not meta:
        return {"as_of": None, "stale": False}
    last_success_at = meta.get("last_success_at")
    return {
        "as_of": _as_utc(last_success_at).isoformat() if last_success_at else None,
        "stale": meta.get("last_run_status") == "failed",
    }


# provider field -> (display maturity, stored field, months) — months gives
# the curve chart a proportional x-axis instead of evenly-spaced categories.
MATURITIES: list[tuple[str, str, int]] = [
    ("1M", "m1", 1), ("2M", "m2", 2), ("3M", "m3", 3), ("6M", "m6", 6),
    ("1Y", "y1", 12), ("2Y", "y2", 24), ("3Y", "y3", 36), ("5Y", "y5", 60),
    ("7Y", "y7", 84), ("10Y", "y10", 120), ("20Y", "y20", 240), ("30Y", "y30", 360),
]

# key, label, long-maturity field, short-maturity field — fixed order per
# contracts/macro-api.md, always present in the response even when null.
SPREADS: list[tuple[str, str, str, str]] = [
    ("10y-2y", "10y – 2y", "y10", "y2"),
    ("30y-10y", "30y – 10y", "y30", "y10"),
    ("10y-3m", "10y – 3m", "y10", "m3"),
]


def spread_bps(row: dict, long_key: str, short_key: str) -> float | None:
    """(long - short) in basis points, or None when either maturity is
    missing from this session — never a false zero."""
    long_v, short_v = row.get(long_key), row.get(short_key)
    if long_v is None or short_v is None:
        return None
    return round((long_v - short_v) * 100, 1)


def spread_series(rows: list[dict], long_key: str, short_key: str) -> list[dict]:
    """One {date, bps} per session that has both maturities — sessions
    missing either leg are dropped, not zero-filled."""
    out = []
    for row in rows:
        bps = spread_bps(row, long_key, short_key)
        if bps is not None:
            out.append({"date": row["date"], "bps": bps})
    return out


def session_change(series: list[dict]) -> float | None:
    """Last minus the *previous entry in this series* — since `series` only
    contains sessions where the spread was computable, this already skips
    over any date with a missing maturity, never comparing to a null."""
    if len(series) < 2:
        return None
    return round(series[-1]["bps"] - series[-2]["bps"], 1)


def is_inverted(bps: float | None) -> bool:
    return bps is not None and bps < 0


def nearest_session(dates: list[str], target: str) -> str | None:
    """Latest stored session at or before `target`. None when history
    doesn't reach that far back — callers must omit the overlay, never
    approximate it with a too-recent session. `dates` must be sorted
    ascending."""
    candidates = [d for d in dates if d <= target]
    return candidates[-1] if candidates else None


def align_curve(current_row: dict, month_ago_row: dict | None, year_ago_row: dict | None) -> list[dict]:
    """One point per maturity across the three overlaid sessions. A maturity
    absent from any of the three rows is None in that column — the chart
    draws a gap, never a zero."""
    return [
        {
            "maturity": maturity,
            "months": months,
            "current": current_row.get(field),
            "month_ago": month_ago_row.get(field) if month_ago_row else None,
            "year_ago": year_ago_row.get(field) if year_ago_row else None,
        }
        for maturity, field, months in MATURITIES
    ]


@router.get("/treasury-curve")
def get_treasury_curve(lookback_days: int = Query(default=180, ge=30, le=750),
                        db=Depends(db_dependency)):
    freshness = _economics_freshness(db)
    empty_spreads = [
        {"key": key, "label": label, "current_bps": None, "change_bps": None,
         "inverted": False, "series": []}
        for key, label, _long, _short in SPREADS
    ]

    rows = list(db[TREASURY_RATES].find({}, {"_id": 0}).sort("date", 1))
    if not rows:
        return {**freshness, "session": None, "curve": [],
                "comparison_sessions": {"month_ago": None, "year_ago": None},
                "spreads": empty_spreads}

    dates = [r["date"] for r in rows]
    by_date = {r["date"]: r for r in rows}
    current_date = dates[-1]
    current_row = by_date[current_date]

    current_dt = datetime.strptime(current_date, "%Y-%m-%d").date()
    month_ago_date = nearest_session(dates, (current_dt - timedelta(days=30)).isoformat())
    year_ago_date = nearest_session(dates, (current_dt - timedelta(days=365)).isoformat())

    curve = align_curve(
        current_row,
        by_date.get(month_ago_date) if month_ago_date else None,
        by_date.get(year_ago_date) if year_ago_date else None,
    )

    spreads_out = []
    for key, label, long_key, short_key in SPREADS:
        full_series = spread_series(rows, long_key, short_key)
        current_bps = full_series[-1]["bps"] if full_series else None
        change_bps = session_change(full_series)
        series = full_series[-lookback_days:] if lookback_days else full_series
        spreads_out.append({
            "key": key, "label": label,
            "current_bps": current_bps, "change_bps": change_bps,
            "inverted": is_inverted(current_bps), "series": series,
        })

    return {
        **freshness,
        "session": current_date,
        "curve": curve,
        "comparison_sessions": {"month_ago": month_ago_date, "year_ago": year_ago_date},
        "spreads": spreads_out,
    }


# Release times are quoted in US market convention (ET), regardless of the
# server's own timezone — labeled explicitly so a client never has to guess.
CALENDAR_TIMEZONE = "America/New_York"


def classify(actual: float | None, estimate: float | None) -> str | None:
    """Mechanical comparison only — no good/bad judgment (FR-021b). None when
    either side is missing, so a release with no estimate is never defaulted
    to "in_line" (FR-021c)."""
    if actual is None or estimate is None:
        return None
    if actual == estimate:
        return "in_line"
    return "above" if actual > estimate else "below"


def surprise(actual: float | None, estimate: float | None) -> float | None:
    if actual is None or estimate is None:
        return None
    return actual - estimate


@router.get("/economic-calendar")
def get_economic_calendar(forward_days: int = Query(default=14, ge=1, le=30),
                          back_days: int = Query(default=7, ge=1, le=30),
                          db=Depends(db_dependency)):
    freshness = _economics_freshness(db)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=back_days)
    window_end = now + timedelta(days=forward_days)

    rows = list(
        db[ECONOMIC_CALENDAR_EVENTS]
        .find({"date": {"$gte": window_start, "$lte": window_end}}, {"_id": 0})
        .sort("date", 1)
    )

    upcoming = []
    reported = []
    for r in rows:
        row_date = _as_utc(r["date"])
        actual = r.get("actual")
        base = {
            "date": row_date.isoformat(),
            "event": r["event"],
            "impact": r["impact"],
            "previous": r.get("previous"),
            "estimate": r.get("estimate"),
            "unit": r.get("unit"),
        }
        if actual is not None:
            reported.append({
                **base,
                "actual": actual,
                "comparison": classify(actual, r.get("estimate")),
                "surprise": surprise(actual, r.get("estimate")),
            })
        elif row_date > now:
            # A past-dated event still awaiting its print belongs in neither
            # list (contracts/macro-api.md) — only a *future* unreported
            # event is "upcoming" (FR-023: later today still counts).
            upcoming.append(base)

    reported.reverse()  # queried ascending; reported reads newest-first

    return {**freshness, "timezone": CALENDAR_TIMEZONE, "upcoming": upcoming, "reported": reported}


# key, display label, provider series name, display unit — order pins the
# tile order in the response (contracts/macro-api.md). Duplicated (not
# imported) from agent-runner/tools/economics.py's INDICATOR_SERIES per
# constitution V/VI: same series names, kept in sync by hand across the two
# services rather than a shared package.
INDICATOR_TILES: list[tuple[str, str, str, str]] = [
    ("growth", "GDP", "GDP", "USD bn"),
    ("inflation", "Inflation rate", "inflationRate", "%"),
    ("employment", "Unemployment rate", "unemploymentRate", "%"),
    ("policy_rate", "Federal funds rate", "federalFunds", "%"),
    ("consumer_sentiment", "Consumer sentiment", "consumerSentiment", ""),
    ("retail_sales", "Retail sales", "retailSales", "USD mn"),
]

LAGGING_THRESHOLD_DAYS = 90


def direction(latest: float, prior: float | None) -> str | None:
    """None when no prior reading is retained yet — FR-024a forbids
    rendering a missing prior as flat or zero."""
    if prior is None:
        return None
    if latest > prior:
        return "up"
    if latest < prior:
        return "down"
    return "flat"


def is_lagging(as_of: str, now: datetime) -> bool:
    """True once a reading's period is more than 90 days old (FR-026a) —
    expected to be the normal case for most series from this source, not an
    error condition."""
    as_of_date = datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (now - as_of_date).days > LAGGING_THRESHOLD_DAYS


@router.get("/economic-indicators")
def get_economic_indicators(db=Depends(db_dependency)):
    freshness = _economics_freshness(db)
    now = datetime.now(timezone.utc)

    tiles = []
    for key, label, series, unit in INDICATOR_TILES:
        readings = list(
            db[ECONOMIC_INDICATORS]
            .find({"indicator": series}, {"_id": 0})
            .sort("date", -1)
            .limit(2)
        )
        if not readings:
            # Never fetched — omitted entirely rather than included with
            # nulls, so a partial pull degrades to fewer tiles (FR-024).
            continue
        latest = readings[0]
        prior = readings[1] if len(readings) > 1 else None
        prior_value = prior["value"] if prior else None
        tiles.append({
            "key": key, "label": label, "series": series,
            "value": latest["value"], "unit": unit, "as_of": latest["date"],
            "direction": direction(latest["value"], prior_value),
            "change": round(latest["value"] - prior_value, 2) if prior_value is not None else None,
            "lagging": is_lagging(latest["date"], now),
        })

    return {**freshness, "indicators": tiles}


@router.get("/risk-premium")
def get_risk_premium(db=Depends(db_dependency)):
    """Single US row (research D5 — the provider supplies no date field, so
    `collected_at` is the as-of proxy). Never an array (FR-025)."""
    freshness = _economics_freshness(db)
    doc = db[MARKET_RISK_PREMIUM].find_one({}, {"_id": 0})
    if not doc:
        return {**freshness, "country": None, "total_equity_risk_premium": None,
                "country_risk_premium": None, "collected_at": None}

    collected_at = doc.get("collected_at")
    return {
        **freshness,
        "country": doc.get("country"),
        "total_equity_risk_premium": doc.get("total_equity_risk_premium"),
        "country_risk_premium": doc.get("country_risk_premium"),
        "collected_at": _as_utc(collected_at).isoformat() if collected_at else None,
    }
