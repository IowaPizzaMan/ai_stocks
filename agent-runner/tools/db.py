"""MongoDB helpers for agents and tools. Spec: specs/component-specs/agent-runner/tools/db.md"""
import math
from datetime import datetime, timezone
from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
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

# 017-fmp-migration-admin — keep in sync with backend/db.py
FMP_ENTITLEMENTS = "fmp_entitlements"
DATASET_META = "dataset_meta"
SECTOR_PERFORMANCE = "sector_performance"
MARKET_MOVERS = "market_movers"
ECONOMIC_CALENDAR_EVENTS = "economic_calendar_events"
TREASURY_RATES = "treasury_rates"
MARKET_RISK_PREMIUM = "market_risk_premium"
ECONOMIC_INDICATORS = "economic_indicators"
CONGRESS_TRADES = "congress_trades"
FUND_HOLDINGS = "fund_holdings"
STOCK_NEWS = "stock_news"
MARKET_NEWS = "market_news"
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
PULL_METRICS = "pull_metrics"

# 026-macro-market-dashboard — economics_worker's own daily-scheduling marker,
# separate from dataset_meta's success/failure freshness (mirrors BREADTH_META).
ECONOMICS_META = "economics_meta"


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
    db[BREADTH_DIVERGENCES].create_index([("resolved", DESCENDING)])
    db[MARKET_FLOW_EVENTS].create_index([("event_id", ASCENDING)], unique=True)
    db[MARKET_FLOW_EVENTS].create_index([("created_at", DESCENDING)])
    # 024 — one series doc per ticker. No TTL: this is a store, not a cache.
    db[PRICE_HISTORY].create_index([("ticker", ASCENDING)], unique=True)
    # 024 — insider transactions become a maintained store too (US4). No TTL,
    # same reason as above; retention is trimmed on merge to LOOKBACK_DAYS.
    db[INSIDER_CACHE].create_index([("ticker", ASCENDING)], unique=True)
    # 024 — pull diagnostics, expired after 30 days (only enough history to rank
    # stages over time, per spec FR-003)
    db[PULL_METRICS].create_index([("ticker", ASCENDING), ("started_at", DESCENDING)])
    db[PULL_METRICS].create_index("started_at", expireAfterSeconds=30 * 24 * 3600)
    # 026-macro-market-dashboard — treasury_rates is a maintained store (no TTL,
    # same discipline as price_history): a backfill-then-daily-extend history the
    # curve/spread reads depend on, so expiry would destroy the baseline.
    db[TREASURY_RATES].create_index([("date", ASCENDING)], unique=True)
    db[ECONOMIC_CALENDAR_EVENTS].create_index([("date", ASCENDING), ("event", ASCENDING)], unique=True)
    db[ECONOMIC_CALENDAR_EVENTS].create_index([("date", DESCENDING)])
    db[ECONOMIC_INDICATORS].create_index([("indicator", ASCENDING), ("date", ASCENDING)], unique=True)
    db[ECONOMIC_INDICATORS].create_index([("indicator", ASCENDING), ("date", DESCENDING)])
    db[MARKET_RISK_PREMIUM].create_index([("country", ASCENDING)], unique=True)


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
    db[TICKER_INDEX].update_one({"ticker": ticker}, update, upsert=True)


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
