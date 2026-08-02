# api/routers/watchlist.md

## Purpose
CRUD for the user's watchlist — the user's pinned/curated subset of tickers, shown in the sidebar. Distinct from the full ticker registry (`ticker_index`, see `models/ticker.md`), which is every ticker the system has ever encountered and is what `POST /queue/all` (Run All) actually sweeps. Adding to the watchlist also registers the ticker in that broader registry, so it's picked up by Run All even without an explicit manual queue action.

## Endpoints

### `GET /watchlist`
Returns all tickers in the watchlist with their latest signal info.

```python
@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(db = Depends(db_dependency)):
    items = list(db.watchlist.find({}, { "_id": 0 }))
    
    # Enrich each item with latest analysis signal
    for item in items:
        latest = db.analyses.find_one(
            { "ticker": item["ticker"] },
            { "signal": 1, "conviction": 1, "timestamp": 1, "_id": 0 },
            sort=[("timestamp", -1)]
        )
        if latest:
            item["last_signal"] = latest.get("signal")
            item["last_conviction"] = latest.get("conviction")
            item["last_analyzed"] = latest.get("timestamp")
        item.setdefault("status", "active")  # "removed_from_market" set by queue_worker.md if delisting is detected
    
    return { "items": items, "count": len(items) }
```

### `POST /watchlist`
Add a ticker to the watchlist. Also registers it in the system-wide ticker registry (`ticker_index`) with source `watchlist`, so it's included in future Run All sweeps even if it's never manually queued.

```python
from registry import register_ticker

@router.post("/watchlist", response_model=WatchlistItem)
def add_to_watchlist(body: AddToWatchlistRequest, db = Depends(db_dependency)):
    ticker = body.ticker.upper()
    existing = db.watchlist.find_one({ "ticker": ticker })
    if existing:
        raise HTTPException(status_code=409, detail=f"{ticker} already in watchlist.")
    
    register_ticker(db, ticker, source="watchlist", name=body.name, sector=body.sector)

    item = { "ticker": ticker, "name": body.name, "sector": body.sector, "status": "active", "added_at": datetime.utcnow() }
    db.watchlist.insert_one(item)
    item.pop("_id", None)
    return item
```

### `DELETE /watchlist/{ticker}`
Remove a ticker from the watchlist.

```python
@router.delete("/watchlist/{ticker}")
def remove_from_watchlist(ticker: str, db = Depends(db_dependency)):
    result = db.watchlist.delete_one({ "ticker": ticker.upper() })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist.")
    return { "removed": ticker.upper() }
```
