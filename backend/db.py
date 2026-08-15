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
