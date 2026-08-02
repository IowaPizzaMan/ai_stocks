# api/routers/stocks.py

## Purpose
Stock search (autocomplete), per-ticker financial/signal data endpoints, and admin management of the ticker registry (the Admin page's disable/delete/bulk-add actions).

`ticker_index` — the collection backing search here — is also the master ticker registry described in `models/ticker.md`: every ticker that's entered the system via manual queue, watchlist add, an earnings calendar pull, or an institutional flow scan. `POST /queue/all` (Run All, see `routers/queue.md`) sweeps this same collection, so search results and the Run All universe are always the same set. The Admin page (`pages/Admin.md`) exists specifically to let the user prune this set down — disabling or deleting tickers they don't want swept — so Run All stays fast as the registry naturally accumulates entries from earnings/institutional-flow discovery over time.

## Endpoints

### `GET /stocks/search?q=`
Instant ticker/name search against the ticker registry.

```python
@router.get("/stocks/search", response_model=list[StockSearchResult])
def search_stocks(q: str, limit: int = 10, db = Depends(db_dependency)):
    # Case-insensitive regex match on ticker or company name
    regex = { "$regex": f"^{re.escape(q)}", "$options": "i" }
    results = list(db.ticker_index.find(
        { "$or": [{ "ticker": regex }, { "name": regex }] },
        { "_id": 0 }
    ).limit(limit))
    
    # Enrich with latest signal from analyses
    for r in results:
        r.setdefault("status", "active")
        latest = db.analyses.find_one(
            { "ticker": r["ticker"] },
            { "signal": 1, "conviction": 1, "timestamp": 1, "_id": 0 },
            sort=[("timestamp", -1)]
        )
        if latest:
            r.update(latest)
    return results
```

### `GET /tickers`
Full-registry view, sorted so the user can scan it. Backs `GET /tickers` used by the (previously debug-only) `GET /tickers` view and now also the Admin page table (`pages/Admin.md`). Optional `status` filter.

```python
@router.get("/tickers", response_model=TickerListResponse)
def list_tickers(status: str | None = None, db = Depends(db_dependency)):
    filter = { "status": status } if status else {}
    items = list(db.ticker_index.find(filter, { "_id": 0 }).sort("ticker", 1))
    return {
        "items": items,
        "total": len(items),
        "active_count": sum(1 for i in items if i.get("status", "active") == "active"),
        "disabled_count": sum(1 for i in items if i.get("status") == "disabled"),
        "removed_count": sum(1 for i in items if i.get("status") == "removed_from_market"),
    }
```

### `PATCH /tickers/{ticker}`
Toggle a ticker's admin status between `active` and `disabled`. This is the Admin page's on/off switch — a disabled ticker keeps its data (analyses, financials cache) but is skipped by `POST /queue/all`. Fully reversible.

```python
from pymongo import ReturnDocument

@router.patch("/tickers/{ticker}", response_model=TickerRecord)
def update_ticker_status(ticker: str, body: TickerStatusUpdate, db = Depends(db_dependency)):
    ticker = ticker.upper()
    updated = db.ticker_index.find_one_and_update(
        { "ticker": ticker },
        { "$set": { "status": body.status } },
        projection={ "_id": 0 },
        return_document=ReturnDocument.AFTER
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Unknown ticker.")
    return updated
```

### `DELETE /tickers/{ticker}`
Permanently remove a ticker and every piece of cached data tied to it — the registry entry, past analyses, financials cache, watchlist entry (if any), and any pending/running queue jobs. This is the destructive option on the Admin page, distinct from `disabled`: use it when the goal is actually shrinking the dataset, not just skipping future sweeps.

```python
@router.delete("/tickers/{ticker}")
def delete_ticker(ticker: str, db = Depends(db_dependency)):
    ticker = ticker.upper()
    result = db.ticker_index.delete_one({ "ticker": ticker })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Unknown ticker.")

    db.analyses.delete_many({ "ticker": ticker })
    db.financials_cache.delete_many({ "ticker": ticker })
    db.watchlist.delete_one({ "ticker": ticker })
    db.work_queue.delete_many({ "ticker": ticker, "status": { "$in": ["pending", "running"] } })
    db.institutional_flow.delete_many({ "ticker": ticker })

    return { "deleted": ticker }
```

### `POST /tickers/bulk`
Mass-add endpoint for the Admin page's paste box — accepts a blob of text with many tickers separated by commas, whitespace, or newlines (so pasting a column from a spreadsheet or a comma list both work). Registers each valid ticker via the same `register_ticker()` helper as every other entry path, and reactivates any that were previously `disabled` or `removed_from_market` — pasting a ticker in is an explicit signal the user wants it tracked again.

```python
import re
from registry import register_ticker

TICKER_PATTERN = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")

@router.post("/tickers/bulk", response_model=BulkAddResponse)
def bulk_add_tickers(body: BulkAddRequest, db = Depends(db_dependency)):
    candidates = [t for t in re.split(r"[\s,]+", body.tickers.strip().upper()) if t]

    added, already_existed, invalid = [], [], []
    seen = set()
    for ticker in candidates:
        if ticker in seen:
            continue
        seen.add(ticker)

        if not TICKER_PATTERN.match(ticker):
            invalid.append(ticker)
            continue

        existing = db.ticker_index.find_one({ "ticker": ticker })
        if existing:
            already_existed.append(ticker)
            if existing.get("status") != "active":
                db.ticker_index.update_one({ "ticker": ticker }, { "$set": { "status": "active" } })
        else:
            added.append(ticker)

        register_ticker(db, ticker, source="manual")

    return { "added": added, "already_existed": already_existed, "invalid": invalid }
```

### `GET /stocks/{ticker}`
Basic registry record for a ticker — name, sector, and `status`. Used by `StockDetail.md` to show `TickerStatusBadge` and disable the Pull button when a ticker is `removed_from_market`, without pulling the (much larger) financials or signals payloads just to check status.

```python
@router.get("/stocks/{ticker}", response_model=TickerRecord)
def get_ticker(ticker: str, db = Depends(db_dependency)):
    record = db.ticker_index.find_one({ "ticker": ticker.upper() }, { "_id": 0 })
    if not record:
        raise HTTPException(status_code=404, detail="Unknown ticker.")
    return record
```

### `GET /stocks/{ticker}/financials`
Cached financials from MongoDB (populated by the agent pipeline). Returns structured financial statements and ratios.

```python
@router.get("/stocks/{ticker}/financials", response_model=StockFinancials)
def get_financials(ticker: str, db = Depends(db_dependency)):
    cached = db.financials_cache.find_one({ "ticker": ticker.upper() }, { "_id": 0 })
    if not cached:
        raise HTTPException(status_code=404, detail="No financial data cached for this ticker. Run analysis first.")
    return cached["data"]
```

### `GET /stocks/{ticker}/signals`
Agent-level sub-reports for a ticker from the most recent analysis run. Powers the tabs in Stock Detail view.

```python
@router.get("/stocks/{ticker}/signals", response_model=AgentSignals)
def get_signals(ticker: str, db = Depends(db_dependency)):
    doc = db.analyses.find_one(
        { "ticker": ticker.upper() },
        { "_id": 0 },
        sort=[("timestamp", -1)]
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No analysis found for this ticker.")
    return {
        "ticker": doc["ticker"],
        "timestamp": doc["timestamp"],
        **doc.get("sub_reports", {})
    }
```
