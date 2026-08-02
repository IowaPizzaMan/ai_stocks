# agent-runner/queue_worker.py

## Purpose
Claims jobs from the `work_queue` MongoDB collection, runs the full CrewAI pipeline for each ticker, and marks jobs done or failed. This is the main orchestration hub between the API (which enqueues jobs) and the crew (which does the analysis).

## Job Document Schema

```json
{
  "_id": ObjectId,
  "ticker": "AAPL",
  "status": "pending" | "running" | "done" | "failed",
  "created_at": ISODate,
  "updated_at": ISODate,
  "error": "string (only on failed)",
  "started_at": ISODate,
  "completed_at": ISODate
}
```

## Key Methods

### `poll()`
Called by main.py every 30 seconds.
- Queries `work_queue` for `{ status: "pending" }`, sorted by `created_at` ascending (FIFO)
- For each job found (process one at a time — no parallelism initially):
  1. Atomically claim it: `find_one_and_update({ _id: job._id, status: "pending" }, { $set: { status: "running", started_at: now, updated_at: now } }, return_document=AFTER)` — if the update returns None, another worker claimed it first; skip.
  2. Call `self._run_job(job)`
  3. On success: set `status: "done"`, `completed_at: now`
  4. On exception: set `status: "failed"`, `error: str(e)`, log full traceback

### `_run_job(job)`
- Imports and instantiates `Crew` from `crew.py`
- Calls `crew.run(job["ticker"])`
- Result (structured dict from PortfolioStrategist) is written to `analyses` collection
- Catches `TickerDelistedError` specifically (see `crew.md`) and handles it via `_handle_delisted`, distinct from the generic failure path below

```python
from crew import Crew, TickerDelistedError
from tools.db import mark_ticker_removed

def _run_job(self, job):
    crew = Crew(self.db)
    try:
        result = crew.run(job["ticker"])
        self.db.analyses.insert_one(result)
        self._mark_done(job)
    except TickerDelistedError as e:
        self._handle_delisted(job, e)

def _handle_delisted(self, job, error: "TickerDelistedError"):
    log.warning("%s appears delisted — marking removed_from_market", error.ticker)
    mark_ticker_removed(error.ticker, reason=str(error))
    self.db.work_queue.update_one(
        { "_id": job["_id"] },
        { "$set": {
            "status": "failed", "delisted": True, "error": str(error),
            "completed_at": datetime.utcnow(), "updated_at": datetime.utcnow()
        } }
    )
```

## Error Handling
- `TickerDelistedError` is handled distinctly (see above) — it updates `ticker_index` and the `watchlist` entry (if present) to `status: "removed_from_market"`, so future `POST /queue/all` sweeps skip it and the UI can badge it, instead of the ticker just quietly failing every run forever
- Any other exception inside `_run_job` is caught at the `poll()` level — the worker **never crashes**; it marks the job `failed` (with `delisted: false`) and continues to the next job. A ticker failing for an ordinary reason (rate limit, network blip) stays `active` in `ticker_index` and gets retried on the next Run All
- Stale `running` jobs (started > 30 min ago with no completion) are reset to `pending` on startup — handles crashes mid-job

## Stale Job Recovery (on startup)

```python
# On __init__, reset any jobs stuck in "running" state from a prior crash
cutoff = datetime.utcnow() - timedelta(minutes=30)
db.work_queue.update_many(
    { "status": "running", "started_at": { "$lt": cutoff } },
    { "$set": { "status": "pending", "updated_at": datetime.utcnow() } }
)
```

## Dependencies
- `pymongo`
- `crew.Crew`
- `datetime`, `logging`
