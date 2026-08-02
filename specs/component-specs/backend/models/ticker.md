# api/models/ticker.py

## Purpose
Pydantic models for the **ticker registry** — the single source of truth for every ticker the system knows about, stored in the `ticker_index` collection. This is the "system" that `POST /queue/all` (Run All) sweeps: the union of every ticker that entered via manual entry, watchlist add, an earnings calendar pull, or an institutional flow scan.

This is distinct from `watchlist` (the user's pinned/curated subset, shown in the sidebar) and from `analyses` (results). A ticker can be in `ticker_index` without ever being in the watchlist — e.g. it showed up once in an earnings sweep and never got added to the watchlist. `ticker_index` also continues to back `GET /stocks/search` autocomplete (`stocks.md`), which is why it already existed before this feature — this just formalizes and extends it into the full universe registry.

## Models

### `TickerRecord`
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

class TickerRecord(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    status: Literal["active", "disabled", "removed_from_market"] = "active"
    sources: list[Literal["manual", "watchlist", "earnings_calendar", "institutional_flow"]]
    first_seen_at: datetime
    last_seen_at: datetime
    delisted_at: datetime | None = None
    delisted_reason: str | None = None
```

### `TickerListResponse`
Backs the `GET /tickers` admin endpoint (see `routers/stocks.md`) that powers the Admin page (`pages/Admin.md`) as well as the earlier debug use case of inspecting the universe.
```python
class TickerListResponse(BaseModel):
    items: list[TickerRecord]
    total: int
    active_count: int
    disabled_count: int
    removed_count: int
```

### `TickerStatusUpdate`
Body for `PATCH /tickers/{ticker}` — the Admin page's on/off toggle.
```python
class TickerStatusUpdate(BaseModel):
    status: Literal["active", "disabled"]
```

### `BulkAddRequest` / `BulkAddResponse`
Backs `POST /tickers/bulk` — the Admin page's mass-add textbox (paste many tickers at once).
```python
class BulkAddRequest(BaseModel):
    tickers: str  # raw pasted text: comma/space/newline separated, e.g. "AAPL MSFT, NVDA\nTSLA"

class BulkAddResponse(BaseModel):
    added: list[str]
    already_existed: list[str]
    invalid: list[str]
```

## Status Semantics
- **`active`** — default. Eligible for `POST /queue/all` sweeps.
- **`disabled`** — set manually from the Admin page (`pages/Admin.md`) via `PATCH /tickers/{ticker}`. This is the "turn off" action: the ticker and its cached data stay in the system, but it's skipped by `POST /queue/all` sweeps, which keeps run time down. Distinct from `removed_from_market` in that it's a deliberate, user-driven "I don't want this analyzed right now" rather than a system-detected delisting. Re-enabling (`PATCH` back to `active`) is fully reversible and touches no other data.
- **`removed_from_market`** — set when the agent-runner determines a ticker no longer has any live data (see `crew.md` prefetch validation and `queue_worker.md` error handling). The record is kept, not deleted — so its ticker page and any past analyses remain visible, just badged. Excluded from future `POST /queue/all` sweeps until/unless it's manually re-queued (which resets it back to `active`; see `routers/queue.md`).
- **Deleted (no status — record removed entirely)** — the Admin page's delete action (`DELETE /tickers/{ticker}`) is destructive: it removes the `ticker_index` record and all associated cached data (analyses, financials cache, watchlist entry, queued jobs). Use this over `disabled` when the goal is actually shrinking dataset size/storage, not just skipping future sweeps.

## Why `sources` Is a List, Not One Field
The same ticker often enters from more than one path (e.g. discovered in an earnings sweep, then later added to the watchlist). `sources` accumulates via `$addToSet` rather than being overwritten, so the registry keeps a full picture of how a ticker came to be tracked.
