# Contract: `GET /earnings/calendar`

**Feature**: `025-earnings-page-filters` | **Status**: Breaking change to an existing endpoint

Replaces the current `?days=N` signature. Implemented in `backend/routers/earnings.py`,
backed by `backend/earnings_data.py::get_earnings_calendar`.

---

## Request

```http
GET /earnings/calendar?from=2026-08-15&to=2026-08-19
```

| Param | Type | Required | Rules |
|---|---|---|---|
| `from` | `YYYY-MM-DD` | yes | Inclusive window start |
| `to` | `YYYY-MM-DD` | yes | Inclusive window end |

**Validation** (422 on failure, per FastAPI/Pydantic defaults):

- Both params must parse as ISO dates.
- `from <= to` — an inverted range is rejected, never silently swapped (FR-004).
- Span capped at **90 days**. The UI cannot request more (±30 is its widest preset), so a
  larger span means a hand-crafted URL; the cap protects against a payload that would pull
  tens of thousands of provider rows.

The endpoint remains **read-only**. It must not register tickers or write to `work_queue` —
the existing `test_calendar_is_read_only` test guards this deliberate deviation from the
original spec and must keep passing.

---

## Response `200 OK`

```json
{
  "entries": [
    {
      "ticker": "TJX",
      "company": "TJX Companies Inc",
      "sector": "Consumer Discretionary",
      "market_cap": 138400000000,
      "report_date": "2026-08-19",
      "eps_estimate": 1.19,
      "eps_actual": null,
      "revenue_estimate": 15177230000,
      "revenue_actual": null,
      "eps_surprise_pct": null,
      "revenue_surprise_pct": null,
      "beat": null,
      "reporting_state": "upcoming",
      "last_updated": "2026-08-17"
    }
  ],
  "total_before_screen": 789,
  "stale": false,
  "fetched_at": "2026-08-17T14:02:11Z"
}
```

**The response shape changes from a bare array to an object.** The current endpoint returns
a JSON array; the envelope is needed because FR-021 requires a pre-filter count and FR-028
requires staleness to be visible. This is a breaking change for the frontend — see below.

| Field | Type | Purpose |
|---|---|---|
| `entries` | array | Screened, deduped, market-cap-descending rows (data-model.md §2, §5) |
| `total_before_screen` | int | Raw provider row count, before the universe screen — feeds FR-021's "count before filtering" |
| `stale` | bool | `true` when served from cache past its TTL because the budget was spent (FR-028) |
| `fetched_at` | ISO 8601 UTC | When the underlying data was actually fetched — lets the UI say how old a stale view is |

Ordering is part of the contract: `entries` arrives sorted by `market_cap` descending,
tie-broken by `ticker`. The client must not re-sort (FR-019).

---

## Degraded and error responses

| Condition | Status | Body |
|---|---|---|
| Budget spent, cached window exists (any age) | `200` | Normal body with `"stale": true` and the original `fetched_at` |
| Budget spent, no cached window at all | `503` | `{"detail": "Earnings calendar temporarily unavailable — FMP daily budget spent"}` |
| Provider unreachable or 5xx, cached window exists | `200` | `"stale": true` |
| Provider unreachable, no cache | `502` | `{"detail": "Earnings calendar provider unavailable"}` |
| Universe cache miss and Nasdaq screener fails | `502` | `{"detail": "Company universe unavailable"}` |
| Invalid or inverted dates, or span > 90 days | `422` | Standard validation error |

`FmpBudgetExceededError` must never surface as an unhandled 5xx — Constitution Principle IV
requires failing soft to stale cache. The 503 case is the genuine floor: no data of any age
exists to serve.

**The client must distinguish 200-with-stale from an error.** A stale 200 renders rows with
a staleness banner; an error renders an explicit error state. Neither may render an empty
table, which would read as "nobody reports this week" (FR-028, SC-010).

---

## Caching

- Key: `earnings_cache` doc `{type: "calendar_range", from, to}`, TTL 4h.
- `type` is deliberately **not** `"calendar"` — the agent-runner writes
  `{type: "calendar", days: N}` docs with a different shape into the same collection, and
  reusing the key would have the two services silently overwrite each other
  (research.md D7, Constitution Principle VI).
- Outbound FMP calls go through `backend/fmp.py::fmp_get` so they count against
  `fmp_usage`. Bare `requests.get` is not acceptable here — routing this call site through
  the budget guard closes an open KNOWN_ISSUES item.

---

## Breaking changes for the frontend

All in `frontend/src/`:

1. **Query params**: `?days=N` → `?from=&to=`. Call site: `useEarningsCalendar` in
   `hooks/useEarningsScan.ts`.
2. **Response shape**: bare array → `{entries, total_before_screen, stale, fetched_at}`.
3. **`EarningsCalendarEntry` in `api/types.ts`**:
   - **removed** — `report_time` (no longer available from the provider; research.md D4)
   - **added** — `eps_actual`, `revenue_actual`, `eps_surprise_pct`,
     `revenue_surprise_pct`, `beat`, `reporting_state`, `last_updated`
4. **Query key**: `["earnings-calendar", days]` → `["earnings-calendar", from, to]`.

Backend tests in `backend/tests/test_earnings.py` that call `?days=5` and index the
response as an array must be updated in the same change, not after it.

---

## Unchanged endpoints

`POST /earnings/analyze`, `GET /earnings/history/{ticker}`, `POST /earnings/scan`, and
`GET /earnings/scan/{scan_id}` are untouched by this feature. The two scan endpoints lose
their only caller when the scan UI is removed and become dormant — recorded in KNOWN_ISSUES
rather than deleted, since the spec scopes their removal out.
