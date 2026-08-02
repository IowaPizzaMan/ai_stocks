# api/routers/earnings.py

## Purpose
API endpoints for the earnings scanner feature. Handles calendar fetching, scan triggering (async), polling for results, and enqueuing tickers for full analysis. Not conversational — selecting a ticker calls `POST /earnings/analyze` directly, no chat turn.

Pulling the calendar is also one of the two ways a ticker can enter the system automatically (the other being an institutional flow scan — see `institutional_flow_worker.md`). Every ticker returned by `GET /earnings/calendar` is registered in `ticker_index` and enqueued for analysis, so it's picked up by the queue worker without the user having to select it individually. The existing `POST /earnings/analyze` handoff (user selects specific tickers from the scored, ranked list) still works exactly as before for "analyze this one right now" — the two paths just both feed the same `work_queue`.

## Endpoints

### `GET /earnings/calendar?days=7`
Returns the pre-screened upcoming earnings list (raw, without scoring). Fast — hits cache if available. Registers and enqueues every ticker in the result, whether served from cache or freshly fetched — cheap and idempotent, since `register_ticker` and the queue's pending/running check are both no-ops on repeat calls.

```python
from registry import register_ticker

@router.get("/earnings/calendar")
def get_earnings_calendar(days: int = 7, db = Depends(db_dependency)):
    cached = db.earnings_cache.find_one(
        { "type": "calendar", "days": days, "fetched_at": { "$gt": four_hours_ago() } },
        { "_id": 0 }
    )
    if cached:
        data = cached["data"]
    else:
        # Trigger a fresh fetch (synchronous — calendar fetch is fast, ~1s)
        from tools.earnings_calendar import get_earnings_calendar as fetch_calendar
        data = fetch_calendar(days_ahead=days)
        db.earnings_cache.replace_one(
            { "type": "calendar", "days": days },
            { "type": "calendar", "days": days, "data": data, "fetched_at": datetime.utcnow() },
            upsert=True
        )

    _register_and_enqueue_calendar(data, db)
    return data

def _register_and_enqueue_calendar(calendar: list[dict], db) -> None:
    for entry in calendar:
        ticker = entry["ticker"].upper()
        record = db.ticker_index.find_one({ "ticker": ticker })
        if record and record.get("status") == "removed_from_market":
            continue  # don't resurrect a known-delisted ticker just because it appears on a stale calendar row

        register_ticker(db, ticker, source="earnings_calendar", name=entry.get("company"), sector=entry.get("sector"))

        already_queued = db.work_queue.find_one({ "ticker": ticker, "status": { "$in": ["pending", "running"] } })
        if not already_queued:
            db.work_queue.insert_one({
                "ticker": ticker, "status": "pending", "source": "earnings_calendar",
                "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()
            })
```

### `POST /earnings/scan`
Kicks off a full scoring scan (async — takes 30–60s). Returns a `scan_id` immediately. Frontend polls `GET /earnings/scan/{scan_id}` for results.

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

@router.post("/earnings/scan")
async def trigger_scan(body: ScanRequest, background_tasks: BackgroundTasks, db = Depends(db_dependency)):
    import uuid
    scan_id = str(uuid.uuid4())
    
    # Record scan as "running" immediately
    db.earnings_scans.insert_one({
        "scan_id": scan_id,
        "status": "running",
        "days_ahead": body.days_ahead,
        "started_at": datetime.utcnow()
    })
    
    # Run the scoring scan in a background task
    background_tasks.add_task(_run_scan, scan_id, body.days_ahead, db)
    
    return { "scan_id": scan_id, "status": "running" }

async def _run_scan(scan_id: str, days_ahead: int, db):
    # Runs EarningsScannerAgent via crew-lite (no full CrewAI overhead)
    try:
        from agents.earnings_scanner import run_scan
        results = run_scan(days_ahead=days_ahead)
        db.earnings_scans.update_one(
            { "scan_id": scan_id },
            { "$set": { "status": "complete", "candidates": results, "completed_at": datetime.utcnow() } }
        )
    except Exception as e:
        db.earnings_scans.update_one(
            { "scan_id": scan_id },
            { "$set": { "status": "failed", "error": str(e) } }
        )
```

### `GET /earnings/scan/{scan_id}`
Poll for scan results.

```python
@router.get("/earnings/scan/{scan_id}")
def get_scan(scan_id: str, db = Depends(db_dependency)):
    doc = db.earnings_scans.find_one({ "scan_id": scan_id }, { "_id": 0 })
    if not doc:
        raise HTTPException(status_code=404, detail="Scan not found")
    return doc
```

### `POST /earnings/analyze`
Enqueue full parallel crew analysis for selected tickers. This is what fires when the user clicks a ticker (or row of tickers) on the calendar — a direct, synchronous write to `work_queue`, no LLM/chat step in between. `queue_worker.py` picks the job up on its next poll.

```python
@router.post("/earnings/analyze")
def analyze_tickers(body: AnalyzeRequest, db = Depends(db_dependency)):
    # body.tickers: list of ticker strings
    enqueued = []
    for ticker in body.tickers:
        ticker = ticker.upper()
        existing = db.work_queue.find_one({ "ticker": ticker, "status": { "$in": ["pending", "running"] } })
        if existing:
            continue
        db.work_queue.insert_one({
            "ticker": ticker,
            "status": "pending",
            "source": "earnings_scanner",
            "parallel_prefetch": True,   # flag for crew.py to use parallel fetching
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        enqueued.append(ticker)
    return { "enqueued": enqueued }
```

### `GET /earnings/history/{ticker}`
Post-earnings move log — how the stock actually moved after prior reports.

```python
@router.get("/earnings/history/{ticker}")
def get_earnings_history(ticker: str, db = Depends(db_dependency)):
    from tools.earnings_calendar import get_earnings_history as fetch_history
    return fetch_history(ticker.upper(), num_quarters=8)
```

## New Pydantic Models

```python
class ScanRequest(BaseModel):
    days_ahead: int = 7

class AnalyzeRequest(BaseModel):
    tickers: list[str]
```

## Dependencies
- `fastapi` (BackgroundTasks)
- `agents/earnings_scanner.py`
- `tools/earnings_calendar.py`
