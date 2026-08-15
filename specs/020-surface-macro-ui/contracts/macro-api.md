# Contract: `GET /market/macro`

**Feature**: `specs/020-surface-macro-ui` | Router: `backend/routers/market.py`

Read-only projection over `macro_analysis_cache` — no computation, no fetching, consistent with the market router's charter ("serves what the agent-runner wrote").

## Request

`GET /market/macro` — no parameters.

## Response `200 application/json`

| Field | Type | Rules |
|---|---|---|
| `sectors` | array | One entry per `macro_analysis_cache` document. Sorted by `computed_at` descending. `[]` when the collection is empty (fresh install / worker hasn't run) — never an error. |
| `sectors[].sector` | string | As stored. |
| `sectors[].computed_at` | ISO-8601 string | From the cache doc. |
| `sectors[].inflation_impact` | object | `result.inflation_impact` verbatim (includes optional `cpi_latest`). |
| `sectors[].rate_impact` | object | `result.rate_impact` verbatim (includes optional `fed_funds_rate`). |
| `sectors[].growth_backdrop` | object | `result.growth_backdrop` verbatim (includes optional `yield_curve_spread`, `curve_inverted`). |
| `sectors[].consumer_backdrop` | string | verbatim |
| `sectors[].sector_rotation_signal` | string | verbatim |
| `sectors[].overall_macro_signal` | `"bullish"\|"bearish"\|"neutral"` | verbatim |
| `sectors[].confidence` | `"high"\|"medium"\|"low"` | verbatim |
| `as_of` | ISO-8601 string \| null | `max(computed_at)` across entries; `null` when `sectors` is empty. |

`_id` is always excluded. Missing optional numeric context (e.g. `cpi_latest`) is passed through as absent/null, never invented (spec edge case "partially formed macro read").

## Error modes

None specific — standard FastAPI/Mongo failure handling. An empty collection is a `200` with `sectors: []`.

## Consumers

- `frontend/src/hooks/useMacro.ts` → `useMacroReads()` (TanStack Query, `staleTime` 1 day, no polling).
- Macro page (`frontend/src/pages/Macro.tsx`): renders one card per `sectors[]` entry with a freshness line from `computed_at`; renders the empty state when `sectors` is `[]`.

## Test obligations (`backend/tests/test_market.py`)

1. Empty collection → `200 {"sectors": [], "as_of": null}`.
2. Two seeded sector docs → both returned, newest `computed_at` first, `as_of` equals the newest, `_id` absent, `result` fields flattened per the table above.
