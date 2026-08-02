# api/routers/queue.py

## Purpose
Queue management endpoints. The frontend's "Pull [Ticker]" and "Run All" (Pull All) buttons call these. The agent-runner polls MongoDB directly — no direct connection between FastAPI and the agent-runner process.

There are two ways a ticker enters the system and becomes eligible for analysis:
1. **Manual** — a user types a ticker and hits Pull, or adds it to the watchlist. Handled here (`POST /queue/{ticker}`) and in `routers/watchlist.md`.
2. **Discovery** — a ticker surfaces from an earnings calendar pull (`routers/earnings.md`) or an institutional flow scan (`institutional_flow_worker.md`). Those paths call the same `register_ticker()` helper and enqueue directly.

Either way, the ticker lands in `ticker_index` (the master registry — see `models/ticker.md`) and, typically, `work_queue`. **Run All** (`POST /queue/all`) doesn't care which path a ticker came from — it just sweeps every `active` ticker in `ticker_index` and enqueues whatever isn't already pending/running.

## Endpoints

### `POST /queue/{ticker}`
Enqueue a single ticker for analysis. This is the manual-entry path.

```python
from registry import register_ticker

@router.post("/queue/{ticker}", response_model=EnqueueResponse)
def enqueue_ticker(ticker: str, db = Depends(db_dependency)):
    ticker = ticker.upper()

    record = db.ticker_index.find_one({ "ticker": ticker })
    if record and record.get("status") == "removed_from_market":
        # Don't silently skip — the user explicitly asked to queue this ticker, so
        # reactivate it. Maybe it relisted, or the delisting check was a false positive.
        db.ticker_index.update_one(
            { "ticker": ticker },
            { "$set": { "status": "active" }, "$unset": { "delisted_at": "", "delisted_reason": "" } }
        )

    register_ticker(db, ticker, source="manual")

    # Idempotent: don't re-add if already pending or running
    existing = db.work_queue.find_one({ "ticker": ticker, "status": { "$in": ["pending", "running"] } })
    if existing:
        return { "ticker": ticker, "job_id": str(existing["_id"]), "status": "already_queued" }

    job = {
        "ticker": ticker,
        "status": "pending",
        "source": "manual",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.work_queue.insert_one(job)
    return { "ticker": ticker, "job_id": str(result.inserted_id), "status": "enqueued" }
```

### `POST /queue/all`
**Run All.** Enqueues every `active` ticker in the system-wide registry (`ticker_index`) — not just the watchlist. This is the union of everything manually queued, watchlisted, pulled from an earnings calendar sweep, or surfaced by an institutional flow scan. Tickers flagged `removed_from_market` are skipped, as are tickers manually turned off (`disabled`) from the Admin page (`pages/Admin.md`) — the whole point of that page is trimming this sweep down to keep Run All fast as the registry grows.

```python
@router.post("/queue/all")
def enqueue_all(db = Depends(db_dependency)):
    universe = list(db.ticker_index.find({ "status": "active" }, { "ticker": 1, "_id": 0 }))
    enqueued = []
    skipped = []
    for item in universe:
        result = enqueue_ticker(item["ticker"], db)
        (enqueued if result["status"] == "enqueued" else skipped).append(item["ticker"])
    return { "enqueued": enqueued, "already_queued": skipped, "universe_size": len(universe) }
```

### `GET /queue`
Current queue state — pending and running jobs.

```python
@router.get("/queue", response_model=QueueStatus)
def get_queue(db = Depends(db_dependency)):
    pending = list(db.work_queue.find({ "status": "pending" }, { "_id": 0 }).sort("created_at", 1))
    running = list(db.work_queue.find({ "status": "running" }, { "_id": 0 }))
    return {
        "pending": pending,
        "running": running,
        "pending_count": len(pending),
        "running_count": len(running)
    }
```

## Dependencies
- `registry.register_ticker` (shared helper, see `backend/db.md`)
- `models.queue`, `models.ticker`
