# api/routers/earnings.py

## Purpose
API endpoints for the earnings feature. `GET /earnings/calendar` is the primary,
auto-loading endpoint behind the earnings page (specs/025-earnings-page-filters). The scan
lifecycle (`POST /scan`, `GET /scan/{scan_id}`) and `POST /earnings/analyze` remain for the
agent-runner's scoring worker but currently have no frontend caller — the earnings page's
manual scan trigger was removed in 025 (see KNOWN_ISSUES.md). Selecting a ticker off the
calendar still calls `POST /earnings/analyze` directly, no chat turn.

**Deviates from the original auto-ingest design described below in one respect that
predates 025 and remains true**: `GET /earnings/calendar` is read-only. It does not
register tickers or enqueue analysis — during earnings season the calendar holds hundreds
of names, and auto-enqueuing all of them meant multi-hour crew runs and a bloated
`ticker_index`. Tickers enter the system one at a time via `POST /earnings/analyze`
instead, fired from the calendar table's per-row Queue action.

## Endpoints

### `GET /earnings/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD` (spec 025)
Every company ≥$500M cap reporting in the inclusive `[from, to]` window, with actuals and
derived surprise for anything already reported. Replaced the previous `?days=N`
forward-only signature — a backward-looking window is required to show surprise data at
all, since reported companies live in the past. See
`specs/025-earnings-page-filters/contracts/earnings-calendar.md` for the full contract.

Read-only (see Purpose above) — never touches `work_queue` or `ticker_index`. Cached 4h
per exact `(from, to)` window in `earnings_cache` under
`{"type": "calendar_range", "from", "to"}` — deliberately not `{"type": "calendar", ...}`,
which `agent-runner/tools/earnings_calendar.py` still writes (Finnhub-sourced, forward-only,
no actuals) for the scoring scanner. The two shapes must never collide in the shared
collection (constitution Principle VI).

```python
@router.get("/calendar")
def get_calendar(from_: date = Query(..., alias="from"), to: date = Query(...), db=Depends(db_dependency)):
    if from_ > to:
        raise HTTPException(422, "'from' must not be after 'to'")
    if (to - from_).days > 90:
        raise HTTPException(422, "date range too wide (max 90 days)")
    try:
        return earnings_data.get_earnings_calendar(start=from_, end=to, db=db)
    except FmpBudgetExceededError:
        raise HTTPException(503, "...budget spent")  # no cached window for this range either
    except earnings_data.CalendarUnavailableError:
        raise HTTPException(502, "...provider unavailable")
    except earnings_data.UniverseUnavailableError:
        raise HTTPException(502, "...universe unavailable")
```

Response envelope: `{"entries": [...], "total_before_screen": int, "stale": bool, "fetched_at": iso8601}`.
Each entry carries `eps_actual`/`revenue_actual`/`eps_surprise_pct`/`revenue_surprise_pct`/
`beat`/`reporting_state` in addition to the estimates and market data the old shape had.
`report_time` (bmo/amc) is gone — the FMP source has no time-of-day field
(`research.md` D4). `entries` arrives sorted by `market_cap` descending; the client must
not re-sort.

On a spent FMP budget or an unreachable provider, serves the newest cached window
regardless of TTL age and marks it `stale: true`; only 502/503s when no cache exists at all
for that exact window (fail-soft, constitution Principle IV).

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
