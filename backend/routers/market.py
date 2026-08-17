"""Spec: specs/component-specs/frontend/components/stock/BreadthDivergenceChart.md

Read-only view over what the agent-runner's daily breadth pass already wrote to
Mongo — no computation here. The oscillator math, SPY fetch and divergence
detection all live in agent-runner/tools/breadth.py; this router just serves
the cached series so the frontend can draw them.
"""
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Depends, Query

from db import (
    BREADTH_CACHE,
    BREADTH_DIVERGENCES,
    BREADTH_META,
    MACRO_ANALYSIS_CACHE,
    MARKET_FLOW_EVENTS,
    MARKET_NEWS_CACHE,
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
