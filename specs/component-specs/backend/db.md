# api/db.py

## Purpose
MongoDB connection singleton and collection accessors for the FastAPI backend. Establishes one connection at startup and reuses it for the lifetime of the process.

## Implementation

```python
from pymongo import MongoClient
from pymongo.database import Database
import os

_client: MongoClient | None = None
_db: Database | None = None

def get_db() -> Database:
    global _client, _db
    if _db is None:
        _client = MongoClient(os.getenv("MONGO_URI", "mongodb://mongodb:27017"))
        _db = _client["stockai"]
    return _db

# FastAPI dependency injection
def db_dependency():
    return get_db()
```

## Collection Accessors (convenience properties)

```python
class Collections:
    def __init__(self, db: Database):
        self.analyses = db["analyses"]
        self.work_queue = db["work_queue"]
        self.watchlist = db["watchlist"]
        self.financials_cache = db["financials_cache"]
        self.macro_cache = db["macro_cache"]
        self.institutional_flow = db["institutional_flow"]
        self.institutional_flow_meta = db["institutional_flow_meta"]
        self.ticker_index = db["ticker_index"]
```

## Usage in Routers
```python
from fastapi import Depends
from db import db_dependency

@router.get("/analysis/feed")
def get_feed(db = Depends(db_dependency)):
    return list(db.analyses.find({}, {"_id": 0}).sort("timestamp", -1).limit(50))
```

## `register_ticker()` — Shared Helper

Every path that can introduce a new ticker to the system (manual queue, watchlist add, earnings calendar pull, institutional flow scan) calls this instead of writing to `ticker_index` directly, so the upsert semantics stay consistent everywhere. Lives in a shared `api/registry.py` module, imported by `routers/queue.py`, `routers/watchlist.py`, and `routers/earnings.py`. The agent-runner side (`institutional_flow_worker.py`) has its own copy against the same collection, since it talks to MongoDB directly rather than through the API — see `agent-runner/tools/db.md`.

```python
from datetime import datetime

VALID_SOURCES = {"manual", "watchlist", "earnings_calendar", "institutional_flow"}

def register_ticker(db, ticker: str, source: str, name: str | None = None, sector: str | None = None) -> None:
    ticker = ticker.upper()
    assert source in VALID_SOURCES

    now = datetime.utcnow()
    update = {
        "$addToSet": { "sources": source },
        "$set": { "last_seen_at": now },
        "$setOnInsert": { "ticker": ticker, "first_seen_at": now, "status": "active" },
    }
    if name: update["$set"]["name"] = name
    if sector: update["$set"]["sector"] = sector

    db.ticker_index.update_one({ "ticker": ticker }, update, upsert=True)
    # Deliberately does NOT touch `status` on an existing document — re-registering a ticker
    # that was previously marked "removed_from_market" doesn't silently revive it. See
    # routers/queue.md for the explicit re-activation path.
```

## Notes
- No connection pooling config needed at this scale (single user, local Docker)
- `_id` fields are excluded from all API responses (`projection={"_id": 0}`)
- All timestamps stored and returned as UTC ISO strings
