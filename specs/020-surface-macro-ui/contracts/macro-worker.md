# Contract: Macro Worker & Crew Decoupling

**Feature**: `specs/020-surface-macro-ui`

## Part A — `agent-runner/macro_worker.py` (new)

```python
run_macro_refresh_if_due(now: datetime, db=None, client=None) -> int
```

Called every tick from `main.py`'s loop, after the breadth worker. Returns the number of sectors refreshed (0 on throttled/no-op ticks) so `main.py` can keep its "did anything work happen" idle logic simple and tests can assert precisely.

### Behavior

1. **Throttle**: at most one sweep per hour (module-level in-process timestamp; single-process deployment). Between sweeps: return `0` immediately.
2. **Sector universe**: `db[TICKER_INDEX].distinct("sector", {"sector": {"$nin": [None, ""]}, "status": {"$ne": "removed_from_market"}})`.
3. **Due check per sector**: refresh when `macro_analysis_cache` has no doc for the sector OR its `computed_at` is older than 7 days (`macro_analyst.CACHE_DAYS` — single source of truth, imported not duplicated).
4. **Refresh**: build context once per sweep (`get_macro_data(db=db)`, `get_yield_curve_status(db=db)` — both cache-first, 24h TTL respected), then call `macro_analyst.run(sector, context, client=client, db=db)` per due sector, which writes the cache doc itself (existing upsert logic).
5. **Failure**: per-sector try/except — log warning, continue with remaining sectors; failed sector's stale doc remains served and is retried next sweep. A sweep never raises into the main loop.

### Test obligations (`agent-runner/tests/test_macro_worker.py`, mongomock + fake LLM)

1. No sectors in `ticker_index` → returns 0, cache untouched.
2. Sector with no cache doc → refreshed (doc created with `computed_at` ≈ now).
3. Sector with fresh doc (< 7 days) → not refreshed (LLM call count 0).
4. Sector with stale doc (> 7 days) → refreshed (doc replaced).
5. Two due sectors, first one's LLM call raises → second still refreshed, return value 1, no exception escapes.
6. Second call within the throttle window → returns 0 without touching the db.

## Part B — `agent-runner/agents/macro_analyst.py` (modified)

```python
run(sector: str, context: dict, client=None, db=None) -> dict   # was run(ticker, context, ...)
```

- `context` = `{"macro": get_macro_data() output, "yield_curve": get_yield_curve_status() output}` — the `sector` key moves from context to the positional parameter.
- Prompt: ticker mentions removed; assessment is for the sector. SCHEMA, hard-number attachment, per-sector cache read/write, and `CACHE_DAYS = 7` unchanged.
- Existing tests (`test_phase5_agents.py`, `test_macro_analyst_cache.py`) update to the new signature; cache-behavior assertions carry over unchanged.

## Part C — `agent-runner/crew.py` (modified)

| Removal | Detail |
|---|---|
| Prefetch jobs | `"macro"` and `"yield_curve"` entries deleted from `_prefetch` (used only by the macro analyst). `"breadth"` **stays** — gap_analysis, market_flow, recommender consume it. |
| Agent call | `macro_analyst.run(...)` call and import deleted. |
| Sub-report | `"macro"` key gone; `sub_reports` = exactly `{technical, fundamental, insider, institutional, sentiment, recommendation}`. |
| Strategist input | `portfolio_strategist` receives sub_reports without macro. Its SYSTEM prompt and instruction #2 drop the macro-weighting language ("macro alone is a mild concern unless fundamentals are deteriorating" etc.) per FR-003 — an intentional verdict-behavior change per the spec. |

The top-level `sector` stamp on the analysis document (from `ticker_index`) is unchanged — feed filtering still depends on it.

### Test obligations (updates to existing suites)

1. `test_crew.py`: `sub_reports` key set excludes `"macro"`; LLM call count drops 8 → 7 (6 agents + strategist); the cross-ticker macro-cache test moves conceptually to `test_macro_worker.py` (crew no longer exercises that path).
2. `test_phase5_agents.py`: macro test uses sector-based signature.
3. Strategist prompt: no assertion needed beyond existing schema tests (prompt wording is not a tested contract).

## Part D — `agent-runner/main.py` (modified)

`run_macro_refresh_if_due(now=now)` added to the loop body alongside `run_daily_breadth_if_due(now=now)`. Its return value participates in the existing `if not (scanned or worked)` idle decision only if trivially convenient; sleeping through a no-op macro tick is acceptable (the throttle makes it free either way).
