# agent-runner/macro_worker.py

## Purpose
Refreshes per-sector macro/economic reads independently of ticker analysis (specs/020-surface-macro-ui). `crew.py` no longer computes macro at all — this worker is the only caller of `agents/macro_analyst.py`, and its output feeds the frontend's Macro page via `GET /market/macro`, never a ticker's `sub_reports`.

Mirrors `breadth_worker.py`'s "called every tick from `main.py`'s loop" shape, but is **staleness-driven** rather than meta-key-driven: the 7-day freshness contract already lives on each sector's `macro_analysis_cache` document (`computed_at` vs. `macro_analyst.CACHE_DAYS`), so there's no separate last-run bookkeeping to maintain.

## `run_macro_refresh_if_due(now: datetime, db=None, client=None, get_macro_data=None, get_yield_curve_status=None) -> int`

1. **Throttle**: at most one sweep per hour via an in-process module-level timestamp (single agent-runner process per compose deployment). Off-window calls return `0` immediately without touching the database.
2. **Sector universe**: `ticker_index.distinct("sector", {"sector": {"$nin": [None, ""]}, "status": {"$ne": "removed_from_market"}})`.
3. **Due check**: a sector is due when it has no `macro_analysis_cache` doc, or its `computed_at` is older than `macro_analyst.CACHE_DAYS` (7 days) — the single source of truth is imported, not duplicated.
4. **Refresh**: builds one shared context (`get_macro_data(db=db)`, `get_yield_curve_status(db=db)` — both cache-first, 24h TTL) per sweep, then calls `macro_analyst.run(sector, context, client=client, db=db)` per due sector; the agent itself performs the cache upsert.
5. **Failure isolation**: one sector's exception is logged and skipped; the sweep continues and never raises into `main.py`'s loop.

Returns the count of sectors actually refreshed (`0` on a throttled or no-op tick) — useful for tests and log context, not consumed by `main.py`'s idle-sleep decision.

## Dependencies
- `agents.macro_analyst` (the only caller after specs/020-surface-macro-ui)
- `tools.macro` (`get_macro_data`, `get_yield_curve_status`)
- `tools.db` (`TICKER_INDEX`, `MACRO_ANALYSIS_CACHE`, `get_db`)

## Tests
`agent-runner/tests/test_macro_worker.py` — mongomock + fake LLM: no active sectors → no-op; new sector → refreshed; fresh sector → skipped; stale sector → refreshed; one sector's LLM failure doesn't block another; a second call inside the throttle window is a no-op.
