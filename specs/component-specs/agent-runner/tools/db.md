# agent-runner/tools/db.py

## Purpose
MongoDB helper functions used by agents and tools. Provides simple read/write wrappers and collection accessors so agents don't need to construct queries directly.

## Collections Used

| Collection | Contents |
|---|---|
| `work_queue` | Job documents (ticker, status, timestamps) |
| `analyses` | Final analysis results per ticker |
| `financials_cache` | FMP financial statements (90-day TTL) |
| `institutional_cache` | 13F holdings data (90-day TTL) |
| `transcripts_cache` | Earnings call transcripts (permanent) |
| `macro_cache` | FRED macro data (24-hour TTL) |
| `dataroma_meta` | Last Dataroma pull timestamp |
| `fmp_usage` | Daily FMP API call counter |
| `watchlist` | User's tracked tickers |
| `ticker_index` | Master ticker registry — every ticker the system knows about, with `status` (`active`/`removed_from_market`) and `sources` it entered from. Swept by `POST /queue/all` (Run All). |

## Functions

### `query_db(collection: str, filter: dict, limit: int = 100) -> list`
```python
def query_db(collection: str, filter: dict, limit: int = 100) -> list:
    return list(db[collection].find(filter, {"_id": 0}).limit(limit))
```

### `write_db(collection: str, data: dict, upsert_key: str = None) -> None`
```python
def write_db(collection: str, data: dict, upsert_key: str = None) -> None:
    if upsert_key:
        db[collection].replace_one({ upsert_key: data[upsert_key] }, data, upsert=True)
    else:
        db[collection].insert_one(data)
```

### `get_latest_analysis(ticker: str) -> dict | None`
```python
def get_latest_analysis(ticker: str) -> dict | None:
    return db.analyses.find_one({ "ticker": ticker }, sort=[("timestamp", -1)], projection={"_id": 0})
```

### `register_ticker(ticker: str, source: str, name: str = None, sector: str = None) -> None`
Agent-runner's copy of the same upsert the API uses (`api/registry.py`, see `backend/db.md`) — used by `institutional_flow_worker.py`, which writes to MongoDB directly rather than through FastAPI.

```python
def register_ticker(ticker: str, source: str, name: str | None = None, sector: str | None = None) -> None:
    ticker = ticker.upper()
    now = datetime.utcnow()
    update = {
        "$addToSet": { "sources": source },
        "$set": { "last_seen_at": now },
        "$setOnInsert": { "ticker": ticker, "first_seen_at": now, "status": "active" },
    }
    if name: update["$set"]["name"] = name
    if sector: update["$set"]["sector"] = sector
    db.ticker_index.update_one({ "ticker": ticker }, update, upsert=True)
```

### `mark_ticker_removed(ticker: str, reason: str) -> None`
Called by `queue_worker.py` when a job fails because the ticker no longer has any live data (see `queue_worker.md`, `crew.md`). Updates both the registry and, if present, the watchlist entry so the UI can badge it without removing the user's history.

```python
def mark_ticker_removed(ticker: str, reason: str) -> None:
    now = datetime.utcnow()
    db.ticker_index.update_one(
        { "ticker": ticker },
        { "$set": { "status": "removed_from_market", "delisted_at": now, "delisted_reason": reason } }
    )
    db.watchlist.update_one(
        { "ticker": ticker },
        { "$set": { "status": "removed_from_market", "delisted_at": now } }
    )
```

### `track_fmp_call() -> int`
Increments the daily FMP call counter. Returns current count. Resets at midnight UTC.
```python
def track_fmp_call() -> int:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    result = db.fmp_usage.find_one_and_update(
        { "date": today },
        { "$inc": { "count": 1 } },
        upsert=True,
        return_document=True
    )
    return result["count"]
```

## Indexes (created on startup)
```python
db.work_queue.create_index([("status", 1), ("created_at", 1)])
db.analyses.create_index([("ticker", 1), ("timestamp", -1)])
db.financials_cache.create_index([("ticker", 1), ("fetched_at", -1)])
db.transcripts_cache.create_index([("ticker", 1), ("year", 1), ("quarter", 1)], unique=True)
db.ticker_index.create_index([("ticker", 1)], unique=True)
db.ticker_index.create_index([("status", 1)])
```

## Dependencies
- `pymongo`
