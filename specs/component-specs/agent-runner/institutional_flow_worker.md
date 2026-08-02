# agent-runner/institutional_flow_worker.py

## Purpose
Runs the market-wide `InstitutionalFlowScannerAgent` on its own schedule, separate from the per-ticker `work_queue` / `QueueWorker` loop. This scan isn't about any one ticker, so it doesn't belong in the ticker job queue — it runs once daily (default) and writes many small event documents instead of one per-ticker analysis.

This is also one of the two automatic ways a ticker enters the system (the other being an earnings calendar pull — see `routers/earnings.md`). Every distinct ticker seen in a scan's events is registered in `ticker_index` and enqueued into `work_queue`, so a fund opening a new position surfaces as a full analysis job without the user having to do anything.

## Class: `InstitutionalFlowWorker`

### `__init__(db)`
- Instantiates `superinvestor_tool` and `institutional_tool`
- Reads `last_scan_at` from `db.institutional_flow_meta` (falls back to 24h ago on first run)

### `run_scan() -> int`
Called on schedule (or on demand via `POST /institutional/scan`). Returns the number of new events written.

```python
def run_scan(self) -> int:
    since = self._get_last_scan_time()

    dataroma_moves = self.superinvestor_tool.get_recent_superinvestor_moves(since)
    filing_changes = self.institutional_tool.get_recent_13f_changes(since)

    events = self.agent.run(dataroma_moves=dataroma_moves, filing_changes=filing_changes, since=since)

    if events:
        for e in events:
            e["scanned_at"] = datetime.utcnow()
        self.db.institutional_flow.insert_many(events)
        self._register_and_enqueue(events)

    self.db.institutional_flow_meta.replace_one(
        { "key": "last_scan_at" }, { "key": "last_scan_at", "value": datetime.utcnow() }, upsert=True
    )
    return len(events)

def _register_and_enqueue(self, events: list[dict]) -> None:
    from tools.db import register_ticker

    for ticker in { e["ticker"] for e in events }:
        record = self.db.ticker_index.find_one({ "ticker": ticker })
        if record and record.get("status") == "removed_from_market":
            continue  # a fund's stale 13F reference shouldn't resurrect a known-delisted ticker

        register_ticker(ticker, source="institutional_flow")

        already_queued = self.db.work_queue.find_one({ "ticker": ticker, "status": { "$in": ["pending", "running"] } })
        if not already_queued:
            self.db.work_queue.insert_one({
                "ticker": ticker, "status": "pending", "source": "institutional_flow",
                "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()
            })
```

## Schedule
Started from `main.py` alongside the existing 30-second `QueueWorker.poll()` loop, on its own timer:

```python
# main.py — runs both loops from one process
INSTITUTIONAL_SCAN_INTERVAL = int(os.getenv("INSTITUTIONAL_SCAN_INTERVAL_HOURS", 24)) * 3600
last_scan = 0

while True:
    try:
        worker.poll()  # existing per-ticker queue, every 30s
        if time.time() - last_scan > INSTITUTIONAL_SCAN_INTERVAL:
            flow_worker.run_scan()
            last_scan = time.time()
    except Exception as e:
        log.error("poll loop error: %s", e)
    time.sleep(POLL_INTERVAL)
```

Default cadence: once daily, after market close. Configurable via `INSTITUTIONAL_SCAN_INTERVAL_HOURS`. Manual trigger available for "pull now" from the UI (mirrors the existing "Pull All" pattern) via `POST /institutional/scan`, which enqueues a one-off scan the worker picks up on its next loop tick.

## Error Handling
Same philosophy as `QueueWorker` — a failed scan is logged, `last_scan_at` is left unchanged so the next attempt re-covers the same window, and the main loop keeps running.

## Dependencies
- `pymongo`
- `agents.institutional_flow_scanner`
- `tools.superinvestor`, `tools.institutional`
- `datetime`, `logging`
