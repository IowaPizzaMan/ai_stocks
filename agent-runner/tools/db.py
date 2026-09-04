"""MongoDB helpers for agents and tools. Spec: specs/component-specs/agent-runner/tools/db.md"""
import math
from datetime import datetime, timezone
from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient, ReturnDocument
from pymongo.database import Database
from pymongo.errors import OperationFailure

from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

# Collection names — keep in sync with backend/db.py
ANALYSES = "analyses"
WORK_QUEUE = "work_queue"
WATCHLIST = "watchlist"
TICKER_INDEX = "ticker_index"
FINANCIALS_CACHE = "financials_cache"
# 0 live documents as of 2026-08-23, but do NOT treat as dead like
# FUND_HOLDINGS/STOCK_NEWS/MARKET_NEWS below were: this one is reserved for
# specs/007-earnings-transcripts (planned, not yet built), has an index
# bootstrapped below, and its cleanup-on-ticker-deletion is asserted by
# backend's test_routers.py — research.md R7.
TRANSCRIPTS_CACHE = "transcripts_cache"
MACRO_CACHE = "macro_cache"
MACRO_ANALYSIS_CACHE = "macro_analysis_cache"
INSTITUTIONAL_CACHE = "institutional_cache"
SUPERINVESTOR_MOVES_CACHE = "superinvestor_moves_cache"
EARNINGS_SCANS = "earnings_scans"
EARNINGS_CACHE = "earnings_cache"
INSTITUTIONAL_FLOW = "institutional_flow"
INSTITUTIONAL_FLOW_META = "institutional_flow_meta"
BREADTH_CACHE = "breadth_cache"
BREADTH_UNIVERSE = "breadth_universe"
BREADTH_DIVERGENCES = "breadth_divergences"
BREADTH_META = "breadth_meta"
MARKET_FLOW_EVENTS = "market_flow_events"
DATAROMA_META = "dataroma_meta"
FMP_USAGE = "fmp_usage"

# 017-fmp-migration-admin — keep in sync with backend/db.py.
# FUND_HOLDINGS/STOCK_NEWS/MARKET_NEWS (bare, distinct from *_CACHE below)
# were removed 2026-08-23 (specs/031-semantic-layer-chat, research.md R7) —
# no collection was ever created for them; they were dead constants only.
# Note: "sector_performance"/"fund_holdings" still appear as bare string
# literals in tools/fmp_client.py's probe-family dict — those are unrelated
# FMP entitlement keys, not this collection constant, and were left alone.
# FMP_ENTITLEMENTS below has 0 live documents for the same reason
# TRANSCRIPTS_CACHE does above — it's actively written
# (tools/fmp_client.py:191), just not yet exercised in this environment.
FMP_ENTITLEMENTS = "fmp_entitlements"
DATASET_META = "dataset_meta"
MARKET_MOVERS = "market_movers"
ECONOMIC_CALENDAR_EVENTS = "economic_calendar_events"
TREASURY_RATES = "treasury_rates"
MARKET_RISK_PREMIUM = "market_risk_premium"
ECONOMIC_INDICATORS = "economic_indicators"
CONGRESS_TRADES = "congress_trades"
COMPANY_INFO = "company_info"

# 021-stock-page-redesign — per-ticker pull-time caches
STOCK_NEWS_CACHE = "stock_news_cache"
BENEFICIAL_OWNERSHIP_CACHE = "beneficial_ownership_cache"

# 024-delta-data-pulls — keep in sync with backend/db.py.
# price_history is a maintained store, not a cache: one doc per ticker holding the
# full daily series, extended incrementally. It deliberately has NO TTL — expiry
# would destroy the baseline every delta pull depends on. Retired price_cache.
PRICE_HISTORY = "price_history"
INSIDER_CACHE = "insider_cache"

# 026-macro-market-dashboard — economics_worker's own daily-scheduling marker,
# separate from dataset_meta's success/failure freshness (mirrors BREADTH_META).
ECONOMICS_META = "economics_meta"

# 031-semantic-layer-chat — flat, pre-computed, one-doc-per-ticker screening
# collection. Every queryable field is top-level by design (data-model.md):
# it's the only shape a locally-generated chat query can reliably target.
# agent-runner (this service) is the sole writer; backend only reads it. Keep
# in sync with backend/db.py per constitution Principle VI.
SCREENER = "screener"

# 032-weekly-strategy-picks — one-doc-per-ticker precomputed The Strat / Gap
# Analysis signals (direction, entry price, strength). Deliberately a
# separate collection from SCREENER, not new fields on it: screener_refresh
# does a full-document replace_one per ticker, so a second writer adding
# fields there would have them silently wiped on the next screener refresh
# cycle (data-model.md). agent-runner (this service) is the sole writer;
# backend only reads it, plus the already-existing BREADTH_CACHE, to apply
# the Market Flow filter at read time. Keep in sync with backend/db.py per
# constitution Principle VI.
STRATEGY_SIGNALS = "strategy_signals"

# 035-chat-and-news-upgrade — one document per news story from any of three
# FMP feeds (general market, FMP editorial articles, stock-specific).
# agent-runner (this service) is the sole writer (tools/news_pull.py); backend
# only reads it. Keep in sync with backend/db.py per constitution Principle VI
# (amended v1.1.0 — see specs/035-chat-and-news-upgrade/contracts/news-collection.md).
NEWS_ARTICLES = "news_articles"

# 036-news-semantic-search — the in-use tag registry: one doc per distinct
# normalized topic tag with its own embedding + usage count (data-model.md §2).
# agent-runner (this service) is the sole writer
# (tools/news_enrich.upsert_tag_registry, called from the news_pull job);
# backend only reads it directly from semantic/news_rank.py with a fixed
# projection — it is NOT admitted to query_guard.READABLE_COLLECTIONS. Keep in
# sync with backend/db.py per constitution Principle VI
# (contracts/news-collection-v2.md §3).
NEWS_TAGS = "news_tags"

# 037-stocks-conviction-and-activity — append-only log backing both the
# Stocks-page activity feed (last 100, paged) and each stock's per-ticker
# change-history trail. Two writers in THIS service (register_ticker below,
# for "added"; queue_worker.py, for "updated"), plus a mirrored writer in
# backend/registry.py (also "added" — the two services share no Python
# package). NOT admitted to query_guard.READABLE_COLLECTIONS (research.md R9)
# — server-internal only, no semantic-layer schema entry needed. Keep the
# constant and its indexes in sync with backend/db.py per constitution
# Principle VI.
STOCK_EVENTS = "stock_events"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def get_db() -> Database:
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]


def ensure_indexes(db: Database | None = None) -> None:
    """Idempotent index bootstrap — called once at agent-runner startup."""
    db = db if db is not None else get_db()
    db[WORK_QUEUE].create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    db[WORK_QUEUE].create_index([("job_type", ASCENDING), ("created_at", DESCENDING)])
    db[ANALYSES].create_index([("ticker", ASCENDING), ("timestamp", DESCENDING)])
    try:
        db[ANALYSES].create_index([("ticker", ASCENDING)], unique=True)
    except OperationFailure:
        logger.warning(
            "unique ticker index on analyses blocked by existing duplicates — "
            "run scripts/dedupe_analyses.py"
        )
    # 037-stocks-conviction-and-activity — backs GET /analysis/feed's
    # (conviction_rank desc, ticker asc) sort. Because `analyses` carries the
    # unique ticker index just above, this compound key is a total order, so
    # a signal-group subset of it is already conviction-then-A→Z and skip/
    # limit paging over it strictly appends (contracts/feed-ordering.md).
    db[ANALYSES].create_index([("conviction_rank", DESCENDING), ("ticker", ASCENDING)])
    db[FINANCIALS_CACHE].create_index([("ticker", ASCENDING), ("fetched_at", DESCENDING)])
    db[TRANSCRIPTS_CACHE].create_index(
        [("ticker", ASCENDING), ("year", ASCENDING), ("quarter", ASCENDING)], unique=True
    )
    db[TICKER_INDEX].create_index([("ticker", ASCENDING)], unique=True)
    db[TICKER_INDEX].create_index([("status", ASCENDING)])
    # Non-ticker-specific pipeline steps, cached across all tickers sharing a
    # sector (macro) or the whole run (superinvestor) — see crew.py callers.
    db[MACRO_ANALYSIS_CACHE].create_index([("sector", ASCENDING)], unique=True)
    db[SUPERINVESTOR_MOVES_CACHE].create_index("fetched_at", expireAfterSeconds=7 * 24 * 3600)
    # 021 — 13D/G filings move on filing cadence (7d)
    # 024 — stock_news_cache deliberately has NO TTL any more: the document is
    # the baseline every delta news fetch reads from, so expiring it would
    # silently restore full-window fetching with no error anywhere. Retention is
    # enforced on merge instead (news.merge_articles drops articles past
    # NEWS_DAYS). Dropping the old index on existing deployments is a one-time
    # mongosh step — see specs/024-delta-data-pulls/quickstart.md.
    db[STOCK_NEWS_CACHE].create_index([("ticker", ASCENDING)], unique=True)
    db[BENEFICIAL_OWNERSHIP_CACHE].create_index("fetched_at", expireAfterSeconds=7 * 24 * 3600)
    db[BENEFICIAL_OWNERSHIP_CACHE].create_index([("ticker", ASCENDING)], unique=True)
    # 031-semantic-layer-chat — pre-existing gap found while auditing the data
    # layer (research.md R8): queried by ticker like its sibling cache
    # collections above, but had no index beyond _id until now.
    db[INSTITUTIONAL_CACHE].create_index([("ticker", ASCENDING)], unique=True)
    db[BREADTH_DIVERGENCES].create_index([("resolved", DESCENDING)])
    db[MARKET_FLOW_EVENTS].create_index([("event_id", ASCENDING)], unique=True)
    db[MARKET_FLOW_EVENTS].create_index([("created_at", DESCENDING)])
    # 024 — one series doc per ticker. No TTL: this is a store, not a cache.
    db[PRICE_HISTORY].create_index([("ticker", ASCENDING)], unique=True)
    # 024 — insider transactions become a maintained store too (US4). No TTL,
    # same reason as above; retention is trimmed on merge to LOOKBACK_DAYS.
    db[INSIDER_CACHE].create_index([("ticker", ASCENDING)], unique=True)
    # 026-macro-market-dashboard — treasury_rates is a maintained store (no TTL,
    # same discipline as price_history): a backfill-then-daily-extend history the
    # curve/spread reads depend on, so expiry would destroy the baseline.
    db[TREASURY_RATES].create_index([("date", ASCENDING)], unique=True)
    db[ECONOMIC_CALENDAR_EVENTS].create_index([("date", ASCENDING), ("event", ASCENDING)], unique=True)
    db[ECONOMIC_CALENDAR_EVENTS].create_index([("date", DESCENDING)])
    db[ECONOMIC_INDICATORS].create_index([("indicator", ASCENDING), ("date", ASCENDING)], unique=True)
    db[ECONOMIC_INDICATORS].create_index([("indicator", ASCENDING), ("date", DESCENDING)])
    db[MARKET_RISK_PREMIUM].create_index([("country", ASCENDING)], unique=True)
    # 028-dashboard-tweaks-batch US6 — provider's own array position (rank) is
    # what the read endpoint sorts on, since the endpoint supplies no volume
    # to sort by and upsert writes don't preserve insertion order (R9).
    db[MARKET_MOVERS].create_index(
        [("date", DESCENDING), ("category", ASCENDING), ("rank", ASCENDING)]
    )
    db[MARKET_MOVERS].create_index(
        [("date", ASCENDING), ("category", ASCENDING), ("ticker", ASCENDING)], unique=True
    )
    # 028-dashboard-tweaks-batch US4 — congress_trades: trade_id unique for
    # idempotent upsert; disclosure_date-ordered for the default listing and
    # the 90-day summary window (R8, judged on disclosure_date, not
    # transaction_date); ticker/person_id for their respective filters.
    db[CONGRESS_TRADES].create_index([("trade_id", ASCENDING)], unique=True)
    db[CONGRESS_TRADES].create_index([("disclosure_date", DESCENDING)])
    db[CONGRESS_TRADES].create_index([("ticker", ASCENDING), ("disclosure_date", DESCENDING)])
    db[CONGRESS_TRADES].create_index([("person_id", ASCENDING)])
    # 029-company-profile-tweaks — company_info was reserved (spec 017) but
    # never written to until now. No TTL: same discipline as price_history —
    # expiry would silently drop a ticker's sector/industry off the Sectors
    # rollup and the industry filter with no error anywhere.
    db[COMPANY_INFO].create_index([("ticker", ASCENDING)], unique=True)
    # 031-semantic-layer-chat — single-field indexes only. Generated chat queries
    # combine these predicates in unpredictable orders, so a compound index would
    # serve one ordering and be ignored by the rest (research.md R8); at 15x scale
    # (~8,340 docs / ~17MB) the collection is cache-resident and index
    # intersection is ample.
    db[SCREENER].create_index([("ticker", ASCENDING)], unique=True)
    db[SCREENER].create_index([("range_pct_20d", ASCENDING)])
    db[SCREENER].create_index([("zscore_20d", ASCENDING)])
    db[SCREENER].create_index([("weekly_change_pct", ASCENDING)])
    db[SCREENER].create_index([("financials_trend", ASCENDING)])
    db[SCREENER].create_index([("fcf_exceeds_debt", ASCENDING)])
    db[SCREENER].create_index([("sector", ASCENDING)])
    db[SCREENER].create_index([("is_tracked", ASCENDING)])
    # 032-weekly-strategy-picks — compound, unlike SCREENER's single-field
    # indexes: this collection is queried by exactly one deterministic code
    # path (backend/semantic/strategy_picks.py) with a fixed predicate/sort
    # shape per strategy, not by unpredictable LLM-generated pipelines.
    db[STRATEGY_SIGNALS].create_index([("ticker", ASCENDING)], unique=True)
    db[STRATEGY_SIGNALS].create_index(
        [("the_strat.direction", ASCENDING), ("the_strat.strength", DESCENDING)]
    )
    db[STRATEGY_SIGNALS].create_index(
        [("gap_analysis.direction", ASCENDING), ("gap_analysis.score", DESCENDING)]
    )
    # 035-chat-and-news-upgrade — data-model.md §1. No TTL: the 30-day launch
    # backfill is the archive this feature exists to make searchable, not a
    # rolling cache.
    db[NEWS_ARTICLES].create_index([("url", ASCENDING)], unique=True)
    db[NEWS_ARTICLES].create_index([("published_at", DESCENDING)])
    db[NEWS_ARTICLES].create_index([("tickers", ASCENDING)])
    db[NEWS_ARTICLES].create_index([("source_type", ASCENDING)])
    db[NEWS_ARTICLES].create_index([("title", TEXT), ("body_text", TEXT)])
    # 036-news-semantic-search — no enrichment-field indexes on news_articles:
    # the ranker reads a projected, published_at-sorted, capped candidate set
    # and the existing published_at/tickers indexes already serve that filter
    # (data-model.md §1). news_tags uses only its implicit `_id` unique index
    # (the `_id` IS the normalized tag) and is created lazily on the first
    # upsert_tag_registry() call — no bootstrap needed here.
    # 037-stocks-conviction-and-activity — data-model.md §2. First index backs
    # the global activity feed (newest-first, capped at 100); second backs the
    # per-stock change-history trail; third guards the "one added event per
    # ticker" invariant record_event()/register_ticker() rely on.
    db[STOCK_EVENTS].create_index([("occurred_at", DESCENDING)])
    db[STOCK_EVENTS].create_index([("ticker", ASCENDING), ("occurred_at", DESCENDING)])
    db[STOCK_EVENTS].create_index([("ticker", ASCENDING), ("event_type", ASCENDING)])


def sanitize_floats(value):
    """Recursively replaces non-finite floats (NaN/Infinity) with None.
    BSON round-trips them fine, but they crash the backend's JSON encoder
    on the way back out, so keep them out of Mongo entirely."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: sanitize_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_floats(v) for v in value]
    return value


def query_db(collection: str, filter: dict, limit: int = 100, db: Database | None = None) -> list:
    db = db if db is not None else get_db()
    return list(db[collection].find(filter, {"_id": 0}).limit(limit))


def write_db(collection: str, data: dict, upsert_key: str | None = None, db: Database | None = None) -> None:
    db = db if db is not None else get_db()
    if upsert_key:
        db[collection].replace_one({upsert_key: data[upsert_key]}, data, upsert=True)
    else:
        db[collection].insert_one(data)


def get_latest_analysis(ticker: str, db: Database | None = None) -> dict | None:
    db = db if db is not None else get_db()
    return db[ANALYSES].find_one({"ticker": ticker}, sort=[("timestamp", -1)], projection={"_id": 0})


def record_event(
    ticker: str,
    event_type: str,
    *,
    changed: bool = False,
    changes: dict | None = None,
    reason: str | None = None,
    source: str = "agent_runner",
    occurred_at: datetime | None = None,
    db: Database | None = None,
) -> None:
    """Appends one `stock_events` document — the write side of both the
    Stocks-page activity feed and each stock's per-ticker change-history
    trail. Spec: specs/037-stocks-conviction-and-activity; data-model.md §2.

    `event_type` is "added" or "updated". `changed`/`changes`/`reason` only
    apply to "updated" (an "added" event is never itself a change). `source`
    is internal provenance only (never exposed by the API) — "agent_runner"
    (this service; both register_ticker's "added" and queue_worker's
    "updated"), "backend_api" (the mirrored writer in backend/registry.py —
    the two services share no Python package, constitution Principle VI), or
    "backfill" (the one-shot script)."""
    db = db if db is not None else get_db()
    db[STOCK_EVENTS].insert_one({
        "ticker": ticker.upper(),
        "event_type": event_type,
        "occurred_at": occurred_at or _utcnow(),
        "changed": changed,
        "changes": changes,
        "reason": reason,
        "source": source,
    })


def register_ticker(
    ticker: str,
    source: str,
    name: str | None = None,
    sector: str | None = None,
    db: Database | None = None,
) -> None:
    """Same upsert the API uses (backend registry) — institutional_flow_worker writes
    to MongoDB directly rather than through FastAPI."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()
    now = _utcnow()
    update = {
        "$addToSet": {"sources": source},
        "$set": {"last_seen_at": now},
        "$setOnInsert": {"ticker": ticker, "first_seen_at": now, "status": "active"},
    }
    if name:
        update["$set"]["name"] = name
    if sector:
        update["$set"]["sector"] = sector
    result = db[TICKER_INDEX].update_one({"ticker": ticker}, update, upsert=True)
    # 037-stocks-conviction-and-activity — `upserted_id` is only set when this
    # call actually created the document, so this is race-free and naturally
    # idempotent: a repeat registration of an existing ticker never
    # duplicates the "added" event (FR-021a's back-fill relies on the same
    # one-event-per-ticker invariant).
    if result.upserted_id is not None:
        record_event(ticker, "added", occurred_at=now, db=db)


def mark_ticker_removed(ticker: str, reason: str, db: Database | None = None) -> None:
    """Flags a delisted/dead ticker in both the registry and (if present) the
    watchlist, so the UI can badge it without deleting the user's history."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()
    now = _utcnow()
    db[TICKER_INDEX].update_one(
        {"ticker": ticker},
        {"$set": {"status": "removed_from_market", "delisted_at": now, "delisted_reason": reason}},
    )
    db[WATCHLIST].update_one(
        {"ticker": ticker},
        {"$set": {"status": "removed_from_market", "delisted_at": now}},
    )


def track_fmp_call(db: Database | None = None) -> int:
    """Increments today's FMP call counter and returns the new count (UTC day bucket)."""
    db = db if db is not None else get_db()
    today = _utcnow().strftime("%Y-%m-%d")
    result = db[FMP_USAGE].find_one_and_update(
        {"date": today},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result["count"]


def write_dataset_meta(
    dataset: str,
    status: str,
    record_count: int = 0,
    source: str = "fmp",
    db: Database | None = None,
) -> None:
    """Freshness envelope for a market-wide/admin-job dataset (research D9).
    `status` is "success" or "failed" — only "success" advances
    last_success_at, so a failed run never claims fresher data than it wrote
    (data-model.md validation rule)."""
    db = db if db is not None else get_db()
    update = {"$set": {"last_run_status": status, "source": source}}
    if status == "success":
        update["$set"]["last_success_at"] = _utcnow()
        update["$set"]["record_count"] = record_count
    db[DATASET_META].update_one({"dataset": dataset}, update, upsert=True)
