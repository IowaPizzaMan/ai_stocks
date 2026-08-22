"""MongoDB connection + collection accessors. Spec: specs/component-specs/backend/db.md"""
from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import OperationFailure

from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

# Collection names — keep in sync with agent-runner/tools/db.py
ANALYSES = "analyses"
WORK_QUEUE = "work_queue"
WATCHLIST = "watchlist"
TICKER_INDEX = "ticker_index"
FINANCIALS_CACHE = "financials_cache"
TRANSCRIPTS_CACHE = "transcripts_cache"
MACRO_CACHE = "macro_cache"
MACRO_ANALYSIS_CACHE = "macro_analysis_cache"
INSTITUTIONAL_CACHE = "institutional_cache"
EARNINGS_SCANS = "earnings_scans"
EARNINGS_CACHE = "earnings_cache"
INSTITUTIONAL_FLOW = "institutional_flow"
INSTITUTIONAL_FLOW_META = "institutional_flow_meta"
BREADTH_CACHE = "breadth_cache"
BREADTH_UNIVERSE = "breadth_universe"
BREADTH_DIVERGENCES = "breadth_divergences"
BREADTH_META = "breadth_meta"
MARKET_FLOW_EVENTS = "market_flow_events"

# 017-fmp-migration-admin — keep in sync with agent-runner/tools/db.py
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

# 021-stock-page-redesign — per-ticker pull-time caches, keep in sync with agent-runner/tools/db.py
STOCK_NEWS_CACHE = "stock_news_cache"
BENEFICIAL_OWNERSHIP_CACHE = "beneficial_ownership_cache"

# 022-market-news-feed — keep in sync with agent-runner/tools/db.py
MARKET_NEWS_CACHE = "market_news_cache"
FMP_USAGE = "fmp_usage"

# 024-delta-data-pulls — keep in sync with agent-runner/tools/db.py.
# price_history is a maintained store, not a cache: one doc per ticker holding the
# full daily series, extended incrementally. It deliberately has NO TTL — expiry
# would destroy the baseline every delta pull depends on. Retired price_cache.
PRICE_HISTORY = "price_history"
INSIDER_CACHE = "insider_cache"

# 026-macro-market-dashboard — agent-runner's economics_worker scheduling
# marker; backend never reads it, kept in sync per constitution VI convention.
ECONOMICS_META = "economics_meta"


@lru_cache(maxsize=1)
def get_db() -> Database:
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]


def ensure_indexes(db: Database) -> None:
    """Idempotent index bootstrap — called once at API startup."""
    db[ANALYSES].create_index([("ticker", ASCENDING), ("timestamp", DESCENDING)])
    db[ANALYSES].create_index([("timestamp", DESCENDING)])
    try:
        db[ANALYSES].create_index([("ticker", ASCENDING)], unique=True)
    except OperationFailure:
        logger.warning(
            "unique ticker index on analyses blocked by existing duplicates — "
            "run scripts/dedupe_analyses.py"
        )
    db[WORK_QUEUE].create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    db[WORK_QUEUE].create_index([("job_type", ASCENDING), ("created_at", DESCENDING)])
    db[TICKER_INDEX].create_index([("ticker", ASCENDING)], unique=True)
    db[TICKER_INDEX].create_index([("status", ASCENDING)])
    db[INSTITUTIONAL_FLOW].create_index([("filed_at", DESCENDING)])
    db[INSTITUTIONAL_FLOW].create_index([("ticker", ASCENDING), ("filed_at", DESCENDING)])
    db[BREADTH_CACHE].create_index([("exchange", ASCENDING), ("date", DESCENDING)])
    db[MARKET_FLOW_EVENTS].create_index([("created_at", DESCENDING)])
    # TTL caches (seconds): macro 24h; financials use quarterly re-fetch logic instead of TTL
    db[MACRO_CACHE].create_index("fetched_at", expireAfterSeconds=24 * 3600)
    # Market news is a single row keyed by source. Deliberately NO TTL index: the
    # 60-minute window is compared in code so the stale copy survives expiry and
    # can still be served when a refresh fails (specs/022 data-model.md §2).
    db[MARKET_NEWS_CACHE].create_index([("key", ASCENDING)], unique=True)
    # 026-macro-market-dashboard — written by agent-runner's economics_pull job;
    # backend only reads these, but declares the same indexes per constitution VI.
    db[TREASURY_RATES].create_index([("date", ASCENDING)], unique=True)
    db[ECONOMIC_CALENDAR_EVENTS].create_index([("date", ASCENDING), ("event", ASCENDING)], unique=True)
    db[ECONOMIC_CALENDAR_EVENTS].create_index([("date", DESCENDING)])
    db[ECONOMIC_INDICATORS].create_index([("indicator", ASCENDING), ("date", ASCENDING)], unique=True)
    db[ECONOMIC_INDICATORS].create_index([("indicator", ASCENDING), ("date", DESCENDING)])
    db[MARKET_RISK_PREMIUM].create_index([("country", ASCENDING)], unique=True)
