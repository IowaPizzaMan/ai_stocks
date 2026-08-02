"""MongoDB connection + collection accessors. Spec: specs/component-specs/backend/db.md"""
from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from settings import settings

# Collection names — keep in sync with agent-runner/tools/db.py
ANALYSES = "analyses"
WORK_QUEUE = "work_queue"
WATCHLIST = "watchlist"
TICKER_INDEX = "ticker_index"
FINANCIALS_CACHE = "financials_cache"
TRANSCRIPTS_CACHE = "transcripts_cache"
MACRO_CACHE = "macro_cache"
INSTITUTIONAL_CACHE = "institutional_cache"
EARNINGS_SCANS = "earnings_scans"
EARNINGS_CACHE = "earnings_cache"
INSTITUTIONAL_FLOW = "institutional_flow"
INSTITUTIONAL_FLOW_META = "institutional_flow_meta"
BREADTH_CACHE = "breadth_cache"
BREADTH_UNIVERSE = "breadth_universe"


@lru_cache(maxsize=1)
def get_db() -> Database:
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]


def ensure_indexes(db: Database) -> None:
    """Idempotent index bootstrap — called once at API startup."""
    db[ANALYSES].create_index([("ticker", ASCENDING), ("timestamp", DESCENDING)])
    db[ANALYSES].create_index([("timestamp", DESCENDING)])
    db[WORK_QUEUE].create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    db[TICKER_INDEX].create_index([("ticker", ASCENDING)], unique=True)
    db[TICKER_INDEX].create_index([("status", ASCENDING)])
    db[INSTITUTIONAL_FLOW].create_index([("filed_at", DESCENDING)])
    db[INSTITUTIONAL_FLOW].create_index([("ticker", ASCENDING), ("filed_at", DESCENDING)])
    db[BREADTH_CACHE].create_index([("exchange", ASCENDING), ("date", DESCENDING)])
    # TTL caches (seconds): macro 24h; financials use quarterly re-fetch logic instead of TTL
    db[MACRO_CACHE].create_index("fetched_at", expireAfterSeconds=24 * 3600)
