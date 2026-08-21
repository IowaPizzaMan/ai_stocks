"""Per-ticker stock news + deterministic tone tally.
Spec: specs/021-stock-page-redesign (US5, FR-018..FR-022a)

Sourcing: FMP's `news/stock` is entitled on this key (verified 2026-08-16) and
returns article bodies, not just headlines — so the bullish/bearish tally reads
real text rather than guessing from titles. The counting, aggregation, and trend
label here are pure functions with no LLM involvement (constitution Principle
III); agents/news_analyst.py writes the prose on top of this output.

News is fetched during a ticker pull only, never on page load (FR-022a).
"""
from datetime import date, datetime, timedelta, timezone

import requests
from pymongo.database import Database

from logging_config import get_logger
from tools import metrics
from tools.db import STOCK_NEWS_CACHE, get_db
from tools.fmp_client import FmpBudgetExceededError, fmp_get

logger = get_logger(__name__)

NEWS_DAYS = 30
# FMP caps a page at 250 and pages backwards in time with no overlap (verified
# 2026-08-16). A heavily-covered mega-cap runs ~250 articles per 15 days, so a
# month is 2-3 pages; MAX_PAGES is the runaway guard, not the expected cost.
PAGE_SIZE = 250
MAX_PAGES = 5
MAX_ARTICLES = PAGE_SIZE * MAX_PAGES
EXCERPT_CHARS = 400
TREND_WINDOW_DAYS = 7

# Extends the SentimentAnalyst's lists (agents/sentiment_analyst.py) with terms
# that show up in article bodies rather than analyst-speak. Kept here because
# this module is the only place per-article counting happens.
BULLISH_TERMS = [
    "accelerating", "record", "strong demand", "raised guidance", "confident",
    "outperform", "inflection", "momentum", "beat", "upgrade", "strong",
    "surge", "rally", "growth", "expansion", "optimistic", "bullish",
    "tailwind", "breakthrough", "exceeded", "profit", "gains",
]
BEARISH_TERMS = [
    "headwind", "uncertainty", "cautious", "challenging", "monitoring",
    "softness", "normalizing", "slowdown", "miss", "downgrade", "cut",
    "decline", "plunge", "weak", "loss", "lawsuit", "investigation",
    "bearish", "recall", "layoff", "warning", "disappointing", "risk",
]


def _count_terms(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(term) for term in terms)


def tally_article(article: dict) -> dict:
    """Bullish/bearish term counts for one raw FMP article, plus the normalized
    shape the UI reads. Articles with no recognized terms score 0/0 — neutral,
    never bearish (spec edge case)."""
    published = str(article.get("publishedDate") or "")
    body = article.get("text") or ""
    haystack = f"{article.get('title') or ''} {body}"
    return {
        "date": published[:10],
        "datetime": published,
        "source": article.get("publisher") or article.get("site") or "unknown",
        "headline": article.get("title") or "",
        "url": article.get("url") or "",
        "text_excerpt": body[:EXCERPT_CHARS],
        "bullish_count": _count_terms(haystack, BULLISH_TERMS),
        "bearish_count": _count_terms(haystack, BEARISH_TERMS),
        "ai_summary": None,  # filled in by agents/news_analyst.py
    }


def build_timeline(articles: list[dict]) -> list[dict]:
    """One point per calendar date that has coverage, ascending."""
    by_date: dict[str, dict] = {}
    for a in articles:
        day = a.get("date")
        if not day:
            continue
        point = by_date.setdefault(day, {"date": day, "bullish": 0, "bearish": 0, "article_count": 0})
        point["bullish"] += a.get("bullish_count", 0)
        point["bearish"] += a.get("bearish_count", 0)
        point["article_count"] += 1
    return [by_date[d] for d in sorted(by_date)]


def compute_trend(timeline: list[dict], window_days: int = TREND_WINDOW_DAYS) -> str:
    """Direction of the most recent `window_days` of coverage, by net term count.
    Falls back to the whole timeline when the recent window is empty so a
    thinly-covered ticker still gets a real read rather than a default."""
    if not timeline:
        return "mixed"
    newest = datetime.fromisoformat(timeline[-1]["date"]).date()
    cutoff = newest - timedelta(days=window_days)
    recent = [p for p in timeline if datetime.fromisoformat(p["date"]).date() >= cutoff]
    window = recent or timeline
    net = sum(p["bullish"] for p in window) - sum(p["bearish"] for p in window)
    if net > 0:
        return "bullish"
    if net < 0:
        return "bearish"
    return "mixed"


def _mark_stage(retrieval: str | None = None, outcome: str | None = None) -> None:
    """Reports this stage's retrieval kind / outcome to the pull-cost recorder
    (024 FR-002). A no-op outside a pull, so non-pull callers are unaffected."""
    stage = metrics.current_stage()
    if stage is not None:
        stage.mark(retrieval=retrieval, outcome=outcome)


def _cached(ticker: str, db: Database) -> list[dict]:
    doc = db[STOCK_NEWS_CACHE].find_one({"ticker": ticker}, {"_id": 0})
    return (doc or {}).get("articles", [])


def _published_day(article: dict) -> str:
    return str(article.get("publishedDate") or "")[:10]


# --- delta window (024 US3) ----------------------------------------------------

def merge_articles(stored: list[dict], fetched: list[dict], cutoff: date) -> list[dict]:
    """Unions stored and fetched articles by URL, newest first, dropping anything
    that has aged out of the window.

    Fetched wins on a URL collision (the provider's copy is the current one), and
    the cutoff trim is what keeps storage bounded now that the document is no
    longer wiped by a TTL (FR-008, FR-017).
    """
    by_url: dict[str, dict] = {}
    for source in (stored or [], fetched or []):
        for item in source:
            day = _published_day(item)
            if not day or day < cutoff.isoformat():
                continue
            # Articles without a URL can't be deduplicated; key them by identity
            # so they are kept rather than silently collapsed into one.
            by_url[item.get("url") or f"_nourl:{id(item)}"] = item
    return sorted(by_url.values(), key=_published_day, reverse=True)


def _build_coverage(articles: list[dict], previous: dict | None, rebuild: bool) -> dict:
    """Coverage envelope for the retained window. Mirrors the price store's
    shape: a delta advances `extended_at` only, a rebuild resets both."""
    now = datetime.now(timezone.utc)
    days = [d for d in (_published_day(a) for a in articles) if d]
    established = (previous or {}).get("established_at") if not rebuild else None
    return {
        "newest_published": max(days) if days else None,
        "oldest_published": min(days) if days else None,
        "window_days": NEWS_DAYS,
        "established_at": established or now,
        "extended_at": now,
    }


def delta_from(stored: list[dict], cutoff: date) -> date:
    """Where to start the request. One day back from the newest stored article
    for the same reason the price store backs off a day — a boundary mismatch
    would silently skip a day's coverage, and the URL-keyed merge absorbs the
    overlap for free (research D5)."""
    days = [d for d in (_published_day(a) for a in stored or []) if d]
    if not days:
        return cutoff
    try:
        newest = date.fromisoformat(max(days))
    except ValueError:
        return cutoff
    return max(cutoff, newest - timedelta(days=1))


def _fetch_window(ticker: str, start: date, end: date, db: Database | None) -> list[dict]:
    """Pages backwards through the window until it's covered.

    Stops as soon as a page comes back short (no more coverage) or reaches past
    `start`, so a thinly-covered ticker costs one call and only a mega-cap pays
    for several. A mid-way failure keeps the pages already collected rather than
    losing the whole window (Principle IV).
    """
    collected: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(MAX_PAGES):
        path = (
            f"news/stock?symbols={ticker}"
            f"&from={start.isoformat()}&to={end.isoformat()}"
            f"&limit={PAGE_SIZE}&page={page}"
        )
        try:
            response = fmp_get(path, db=db)
        except (FmpBudgetExceededError, requests.RequestException):
            # Pages already in hand are real coverage — keep them and let the
            # caller work with a short window. With nothing yet, re-raise so the
            # caller falls back to its cache instead of reporting "no news".
            if collected:
                logger.warning(
                    "%s: news page %s failed — keeping the %s articles already fetched",
                    ticker, page, len(collected),
                )
                break
            raise

        rows = response if isinstance(response, list) else []
        if not rows:
            break

        fresh = [r for r in rows if (r.get("url") or id(r)) not in seen_urls]
        for r in fresh:
            if r.get("url"):
                seen_urls.add(r["url"])
        collected.extend(fresh)

        oldest = min((_published_day(r) for r in rows if _published_day(r)), default="")
        # a short page means FMP has nothing older; reaching `start` means we're done
        if len(rows) < PAGE_SIZE or (oldest and oldest <= start.isoformat()):
            break

    return collected


def get_stock_news(ticker: str, db: Database | None = None, rebuild: bool = False) -> dict:
    """A full NEWS_DAYS window of articles with per-article tone counts, a dated
    timeline, and a trend label. Serves stale cache when FMP is unavailable or
    the daily budget is spent — never raises on a data-source failure
    (Principle IV, FR-026).

    As of 024 the request is bounded to what is missing rather than re-fetching
    the whole window: a mega-cap that needed 2-5 pages on a cold fetch usually
    costs one on a repeat pull. Unlike price, this genuinely saves API calls —
    `news/stock` pages at 250 articles, so a narrower window means fewer
    requests (research D1). `rebuild=True` (operator full refresh) ignores the
    stored baseline and re-fetches the entire window.
    """
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    today = date.today()
    # inclusive on both ends, so subtract one to span exactly NEWS_DAYS dates
    cutoff = today - timedelta(days=NEWS_DAYS - 1)

    stored = _cached(ticker, db)
    start = cutoff if rebuild else delta_from(stored, cutoff)
    baseline = [] if rebuild else stored

    # Tell the pull-cost recorder what this stage actually did (FR-002).
    # Without this the stage infers "full" from having spent requests, which
    # would keep reporting full long after the fetch went incremental.
    _mark_stage(metrics.INCREMENTAL if start > cutoff else metrics.FULL)

    raw: list[dict] | None = None
    stale = False
    try:
        fetched = _fetch_window(ticker, start, today, db)
        raw = merge_articles(baseline, fetched, cutoff)
        db[STOCK_NEWS_CACHE].replace_one(
            {"ticker": ticker},
            {"ticker": ticker, "articles": raw,
             "coverage": _build_coverage(raw, (db[STOCK_NEWS_CACHE].find_one(
                 {"ticker": ticker}, {"_id": 0}) or {}).get("coverage"), rebuild),
             "fetched_at": datetime.now(timezone.utc)},
            upsert=True,
        )
    except FmpBudgetExceededError:
        logger.warning("%s: FMP budget spent — serving cached news", ticker)
        _mark_stage(outcome=metrics.DEGRADED)
        raw, stale = stored, True
    except (requests.HTTPError, requests.RequestException) as exc:
        logger.warning("%s: news fetch failed (%s) — serving cached news", ticker, exc)
        _mark_stage(outcome=metrics.DEGRADED)
        raw, stale = stored, True

    articles = []
    for item in raw or []:
        tallied = tally_article(item)
        if not tallied["date"]:
            continue
        try:
            if datetime.fromisoformat(tallied["date"]).date() < cutoff:
                continue
        except ValueError:
            continue
        articles.append(tallied)

    articles.sort(key=lambda a: a["datetime"], reverse=True)
    articles = articles[:MAX_ARTICLES]
    timeline = build_timeline(articles)

    return {
        "articles": articles,
        "timeline": timeline,
        "trend": compute_trend(timeline),
        "news_count": len(articles),
        # How much of the requested window actually came back — a thinly covered
        # ticker legitimately spans fewer days than NEWS_DAYS, and the UI says so
        # rather than implying a month of coverage it doesn't have.
        "days_covered": len(timeline),
        "window_days": NEWS_DAYS,
        "as_of": articles[0]["date"] if articles else None,
        "stale": stale,
    }
