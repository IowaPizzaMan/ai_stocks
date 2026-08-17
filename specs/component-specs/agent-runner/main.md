# agent-runner/main.py

## Purpose
Entry point for the agent-runner Docker service. Starts the persistent queue polling loop — runs forever, sleeping 30 seconds between polls. Bootstraps all shared connections (MongoDB, Ollama) once at startup and passes them down.

## Responsibilities
- Load environment variables from `.env` (via `python-dotenv`)
- Initialize MongoDB client and verify connection
- Verify Ollama is reachable (GET `/api/tags` — log warning if not, keep running)
- Import and instantiate `QueueWorker`
- Import and instantiate `InstitutionalFlowWorker` (see `institutional_flow_worker.md`) — runs on its own daily timer, independent of ticker jobs
- Call `run_daily_breadth_if_due` each tick — daily NYMO/NAMO + SPY divergence refresh, independent of ticker jobs
- Call `macro_worker.run_macro_refresh_if_due` each tick (see `macro_worker.md`) — per-sector economic reads, throttled to at most once an hour, independent of ticker jobs (specs/020-surface-macro-ui: macro analysis is decoupled from crew.py entirely)
- Run the blocking poll loop

## Implementation

```python
import asyncio
import os
import time
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from queue_worker import QueueWorker

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", 30))

def main():
    mongo = MongoClient(os.getenv("MONGO_URI", "mongodb://mongodb:27017"))
    db = mongo["stockai"]
    worker = QueueWorker(db)
    flow_worker = InstitutionalFlowWorker(db)
    scan_interval = int(os.getenv("INSTITUTIONAL_SCAN_INTERVAL_HOURS", 24)) * 3600
    last_scan = 0
    log.info("agent-runner started — polling every %ds", POLL_INTERVAL)
    while True:
        try:
            worker.poll()
            if time.time() - last_scan > scan_interval:
                flow_worker.run_scan()
                last_scan = time.time()
        except Exception as e:
            log.error("poll loop error: %s", e)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
```

## Environment Variables Used
| Variable | Default | Purpose |
|---|---|---|
| `MONGO_URI` | `mongodb://mongodb:27017` | MongoDB connection string |
| `OLLAMA_URL` | `http://ollama:11434` | Ollama base URL |
| `POLL_INTERVAL_SECONDS` | `30` | Seconds between queue polls |
| `FMP_API_KEY` | — | Financial Modeling Prep key |
| `FINNHUB_API_KEY` | — | Finnhub key |
| `FRED_API_KEY` | — | FRED key |
| `INSTITUTIONAL_SCAN_INTERVAL_HOURS` | `24` | Hours between market-wide institutional flow scans |

## Dependencies
- `pymongo`
- `python-dotenv`
- `queue_worker.QueueWorker`
- `institutional_flow_worker.InstitutionalFlowWorker`
