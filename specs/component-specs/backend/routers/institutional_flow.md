# api/routers/institutional_flow.py

## Purpose
Endpoints for the market-wide Institutional Flow feed — new institutional/superinvestor activity across the whole tracked universe, not scoped to one ticker. Powers the standalone Institutional Flow page. Distinct from `routers/analysis.md`, which serves per-ticker analysis (including the per-ticker institutional sub-report).

## Endpoints

### `GET /institutional/flow`
Paginated list of institutional flow events, newest filing first. Powers the Institutional Flow page.

**Query params:** `page=1`, `page_size=20`, `action=new_position|add|trim|exit`, `fund=`, `ticker=`, `min_notability=`, `from_date=`, `to_date=`

```python
@router.get("/institutional/flow", response_model=InstitutionalFlowResponse)
def get_institutional_flow(
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    fund: str | None = None,
    ticker: str | None = None,
    min_notability: int | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    db = Depends(db_dependency)
):
    filter = {}
    if action: filter["action"] = action
    if fund: filter["fund"] = { "$regex": fund, "$options": "i" }
    if ticker: filter["ticker"] = ticker.upper()
    if min_notability is not None: filter["notability_score"] = { "$gte": min_notability }
    if from_date or to_date:
        filter["filed_at"] = {}
        if from_date: filter["filed_at"]["$gte"] = from_date
        if to_date: filter["filed_at"]["$lte"] = to_date

    projection = { "_id": 0 }
    total = db.institutional_flow.count_documents(filter)
    items = list(
        db.institutional_flow.find(filter, projection)
        .sort("filed_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return { "items": items, "total": total, "page": page, "page_size": page_size }
```

### `GET /institutional/flow/{ticker}`
All flow events for a single ticker — used as the "view full history" link from the Stock Detail Institutional tab.

```python
@router.get("/institutional/flow/{ticker}", response_model=list[InstitutionalFlowEvent])
def get_ticker_flow(ticker: str, limit: int = 20, db = Depends(db_dependency)):
    return list(
        db.institutional_flow.find({ "ticker": ticker.upper() }, { "_id": 0 })
        .sort("filed_at", -1)
        .limit(limit)
    )
```

### `POST /institutional/scan`
Manually trigger a fresh scan — mirrors the existing "Pull All" pattern used by `/queue/all`. Doesn't block on the scan itself; `InstitutionalFlowWorker` (agent-runner) picks up the trigger and runs it out-of-band.

```python
@router.post("/institutional/scan", response_model=InstitutionalScanResult)
def trigger_institutional_scan(db = Depends(db_dependency)):
    db.institutional_flow_meta.update_one(
        { "key": "manual_scan_requested" }, { "$set": { "value": True, "requested_at": datetime.utcnow() } }, upsert=True
    )
    return { "status": "queued", "message": "Institutional flow scan requested — results will appear shortly." }
```

## Dependencies
- `models.institutional_flow` — `InstitutionalFlowEvent`, `InstitutionalFlowResponse`, `InstitutionalScanResult`
- `db.db_dependency`
