"""MongoDB helpers for agents and tools. Spec: specs/component-specs/agent-runner/tools/db.md"""
from datetime import datetime, timezone
from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.database import Database

from settings import settings

# Collection names — keep in sync with backend/db.py
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
DATAROMA_META = "dataroma_meta"
FMP_USAGE = "fmp_usage"


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
    db[ANALYSES].create_index([("ticker", ASCENDING), ("timestamp", DESCENDING)])
    db[FINANCIALS_CACHE].create_index([("ticker", ASCENDING), ("fetched_at", DESCENDING)])
    db[TRANSCRIPTS_CACHE].create_index(
        [("ticker", ASCENDING), ("year", ASCENDING), ("quarter", ASCENDING)], unique=True
    )
    db[TICKER_INDEX].create_index([("ticker", ASCENDING)], unique=True)
    db[TICKER_INDEX].create_index([("status", ASCENDING)])


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
