# Contract: Price store accessor

**Feature**: `specs/024-delta-data-pulls` (US2)

Implemented **twice** — `agent-runner/tools/price_store.py` and
`backend/price_store.py` — kept in sync by hand (constitution Principle V/VI, research
D4). Both read and write the same `price_history` documents.

The merge and coverage logic is expressed as **pure functions over plain data** so both
copies can be tested against an identical case table. That shared table is what actually
enforces consistency between the two services; divergence surfaces as a test failure
rather than as corrupted stored data.

---

## Pure functions (no Mongo, no HTTP — the tested core)

### `merge_bars(stored, fetched) -> list[dict]`

Merges newly fetched bars into a stored series.

| Guarantee | Source |
|---|---|
| Result is ascending by `date` with no duplicate dates | FR-008 |
| On a `date` collision the **fetched** bar wins | research D5 — a re-fetched bar is a correction |
| Empty `fetched` returns `stored` unchanged | spec edge case: non-trading day |
| Empty `stored` returns `fetched` sorted | FR-007 |
| Never mutates its arguments | testability |

### `delta_start(coverage, today, max_gap_days=730) -> date | None`

Decides what to request.

| Input | Returns | Source |
|---|---|---|
| No coverage / no `last_date` | `None` → caller fetches full | FR-007 |
| `last_date` older than `max_gap_days` | `None` → caller fetches full | FR-011, research D11 |
| Otherwise | `last_date − 1 day` | research D5 — deliberate overlap, never `+1` |

The one-day back-off is the point of this function. Requesting from `last_date + 1`
silently drops a trading day whenever the provider's day boundary and the stored date
disagree; re-requesting one held day costs a single row and `merge_bars` discards it.

### `build_coverage(bars, previous, mode) -> dict`

Recomputes the coverage envelope from the merged series.

| Guarantee | Source |
|---|---|
| `first_date`/`last_date`/`bar_count` derived from `bars`, never carried forward | data-model validation |
| `mode="full"` sets both `established_at` and `extended_at` | FR-025 |
| `mode="delta"` advances `extended_at` only, preserving `established_at` | FR-010 |

---

## I/O function

### `get_series(ticker, refresh, db) -> (DataFrame, meta)`

`refresh` is explicit — there is no implicit time-based freshness anywhere in this
module (research D6, and the whole point of the feature).

| `refresh` | Behavior |
|---|---|
| `"none"` | Read stored bars. Never contacts the provider. |
| `"delta"` | Fetch from `delta_start(...)`, merge, persist. Falls back to full when `delta_start` returns `None`. |
| `"full"` | Fetch the entire history, replace the stored series outright. |

**Returns** an OHLCV `DataFrame` with an ascending `DatetimeIndex` named `Date` and
columns `Open/High/Low/Close/Volume` — byte-identical in shape to today's
`fetch_eod_history` output, so `_resample`, `_slice_period`, and `compute_indicators`
need no changes (FR-020).

`meta` carries `{requests, bytes, retrieval, outcome}` for the stage recorder (FR-002).

### Guarantees

| Guarantee | Source |
|---|---|
| Writes are a single atomic `replace_one` on one document | FR-030, FR-031 |
| The new series is built fully in memory **before** any write | FR-030 |
| A fetch failure leaves the stored series untouched and returns it with `outcome: "degraded"` | FR-012, FR-030 |
| `FmpBudgetExceededError` is caught, stored bars are served, `outcome: "degraded"` | FR-012, FR-027 |
| Every provider call routes through the service's budget-guarded client | FR-012, Principle IV |
| One `refresh != "none"` call per ticker per pull; later readers pass `"none"` | FR-014, SC-003 |

---

## Call-site changes

### agent-runner

| Site | Change |
|---|---|
| [crew.py:143-153](../../../agent-runner/crew.py#L143-L153) `_prefetch` | Refresh the series **once** before the job map is built; every job below reads `refresh="none"` |
| [tools/price.py:44](../../../agent-runner/tools/price.py#L44) `get_price_history` | `fetch_eod_history` → `price_store.get_series(refresh="none")` |
| [tools/price.py:102](../../../agent-runner/tools/price.py#L102) `get_technical_indicators` | same — this is the duplicate download (research D0) |
| [tools/price.py:109](../../../agent-runner/tools/price.py#L109) `get_accumulation_score` | same |
| [tools/earnings_calendar.py:178](../../../agent-runner/tools/earnings_calendar.py#L178) | `refresh="delta"` — scan path, own lifecycle |
| [tools/breadth.py:123,181](../../../agent-runner/tools/breadth.py#L123) | `refresh="delta"` — market-wide, benefits incidentally |

`fetch_eod_history` in `tools/fmp_client.py` stays as the raw provider call; it gains a
`start` parameter and becomes the store's fetch primitive rather than a general-purpose
entry point.

### backend

| Site | Change |
|---|---|
| [routers/price.py](../../../backend/routers/price.py) `get_price` | Read the stored daily series, resample locally per resolution. Deletes `PRICE_CACHE`, `CACHE_MINUTES`, `_fetch_eod`, and the four-way `RESOLUTIONS` fetch matrix — SC-004 |
| [routers/price.py:87](../../../backend/routers/price.py#L87) | Bare `requests.get` → the store, which routes through `backend/fmp.py::fmp_get` — closes half of a logged `KNOWN_ISSUES.md` entry (research D9) |

The backend keeps `RESOLUTIONS` as a **resample rule map** (`daily→none`, `weekly→W`,
`monthly→ME`, `yearly→YE`) plus display windows. What it loses is the per-resolution
*fetch*.

---

## Non-goals

- No drift or corporate-action detection (FR-010). A split silently invalidates stored
  bars until the operator triggers a full refresh — the spec's stated accepted risk.
- No per-bar documents, no time-series collection, no partial-range queries. One
  document, whole series, read in full (research D3).
