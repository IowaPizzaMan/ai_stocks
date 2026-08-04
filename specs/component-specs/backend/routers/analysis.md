# api/routers/analysis.py

## Purpose
Endpoints for reading analysis results. The frontend's primary data source — powers the feed, stock detail view, and sector view.

## Endpoints

### `GET /analysis/feed`
Paginated list of analyses, newest first. Powers the home feed.

**Query params:** `page=1`, `page_size=20`, `ticker=`, `signal=bullish|bearish|neutral`, `sector=`, `conviction=high|medium|low`, `from_date=`, `to_date=`, `institutional_activity=buying|selling` (see `FilterBar.md` "Strategy Filters (Phase 2)" — undecided/not yet scored, param shape spec'd ahead of the backing data)

```python
@router.get("/analysis/feed", response_model=AnalysisFeedResponse)
def get_feed(
    page: int = 1,
    page_size: int = 20,
    ticker: str | None = None,
    signal: str | None = None,
    sector: str | None = None,
    conviction: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    institutional_activity: str | None = None,
    db = Depends(db_dependency)
):
    filter = {}
    if ticker: filter["ticker"] = { "$regex": f"^{re.escape(ticker)}", "$options": "i" }
    if signal: filter["signal"] = signal
    if sector: filter["sector"] = sector
    if conviction: filter["conviction"] = conviction
    if institutional_activity: filter["recent_institutional_activity"] = institutional_activity
    if from_date or to_date:
        filter["timestamp"] = {}
        if from_date: filter["timestamp"]["$gte"] = from_date
        if to_date: filter["timestamp"]["$lte"] = to_date
    
    # Exclude sub_reports from feed (too large) — project only feed fields
    projection = { "_id": 0, "sub_reports": 0 }
    total = db.analyses.count_documents(filter)
    items = list(
        db.analyses.find(filter, projection)
        .sort("timestamp", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return { "items": items, "total": total, "page": page, "page_size": page_size }
```

### `GET /analysis/{ticker}`
Full analysis history for a single ticker. Returns all analyses sorted newest-first.

**Query params:** `limit=10`

```python
@router.get("/analysis/{ticker}", response_model=list[Analysis])
def get_ticker_analysis(ticker: str, limit: int = 10, db = Depends(db_dependency)):
    return list(
        db.analyses.find({ "ticker": ticker.upper() }, { "_id": 0 })
        .sort("timestamp", -1)
        .limit(limit)
    )
```

### `GET /analysis/sector/{sector}`
All latest analyses for tickers in a given sector. Returns one analysis per ticker (the most recent).

```python
@router.get("/analysis/sector/{sector}", response_model=list[AnalysisFeedItem])
def get_sector_analysis(sector: str, db = Depends(db_dependency)):
    # Aggregate: group by ticker, get most recent analysis per ticker
    pipeline = [
        { "$match": { "sector": sector } },
        { "$sort": { "timestamp": -1 } },
        { "$group": { "_id": "$ticker", "doc": { "$first": "$$ROOT" } } },
        { "$replaceRoot": { "newRoot": "$doc" } },
        { "$project": { "_id": 0, "sub_reports": 0 } }
    ]
    return list(db.analyses.aggregate(pipeline))
```
