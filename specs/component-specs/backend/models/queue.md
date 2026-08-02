# api/models/queue.md

## Purpose
Pydantic models for the work queue — enqueuing jobs and reading queue state.

## Models

### `QueueJob`
```python
from typing import Literal

class QueueJob(BaseModel):
    ticker: str
    status: Literal["pending", "running", "done", "failed"]
    source: Literal["manual", "watchlist", "earnings_calendar", "earnings_scanner", "institutional_flow"] = "manual"
    # "earnings_calendar" = auto-enqueued from GET /earnings/calendar (every pre-screened ticker)
    # "earnings_scanner"  = user explicitly selected this ticker from scored scan results (POST /earnings/analyze)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    delisted: bool = False  # set true if the job failed specifically because the ticker no longer trades — see queue_worker.md
```

### `QueueStatus`
```python
class QueueStatus(BaseModel):
    pending: list[QueueJob]
    running: list[QueueJob]
    pending_count: int
    running_count: int
```

### `EnqueueRequest`
```python
class EnqueueRequest(BaseModel):
    ticker: str
```

### `EnqueueResponse`
```python
class EnqueueResponse(BaseModel):
    ticker: str
    job_id: str
    status: str   # "enqueued" or "already_queued"
```
