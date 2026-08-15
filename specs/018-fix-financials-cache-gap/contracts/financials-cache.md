# Contract: `get_financials()` and the `financials_cache` collection

**Feature**: 018-fix-financials-cache-gap | **Date**: 2026-08-15
**Implementers**: `agent-runner/tools/financials.py` (writer), `backend/routers/stocks.py` (reader)

## Function contract — `get_financials(ticker, db=None) -> dict`

Return value: dict with exactly the keys of `ENDPOINTS`
(`income_annual`, `income_quarterly`, `balance_annual`, `cashflow_annual`, `ratios`,
`key_metrics`, `growth`), each a list. Unchanged from today.

### Behavior matrix

| Cache state on entry | Action | FMP calls | `fetched_at` |
|---|---|---|---|
| No doc, or doc older than 90 days | Full fetch of all 7 keys; write doc with fresh `outcomes` | 7 | set to now |
| Doc in window, all keys `confirmed` | Return `data` as-is | 0 | untouched |
| Doc in window, some keys `unavailable` | Re-fetch only those keys; merge results into `data`, update `outcomes`; return merged dict | 1 per retried key | untouched (D4) |
| Doc in window, **no `outcomes` field** (legacy) | Derive: empty value → `unavailable`, non-empty → `confirmed`; then behave per the rows above | per derivation | untouched |

### Outcome recording (per key, on any fetch or retry)

| FMP result | `data[key]` | `outcomes[key]` |
|---|---|---|
| HTTP 200, records present | payload | `confirmed` |
| HTTP 200, empty payload | `[]` | `confirmed` (provider affirmatively has none — settled for the window) |
| HTTP 402 / 403 | `[]` | `unavailable` |
| `FmpBudgetExceededError` | `[]` | `unavailable` |
| Any other `requests.HTTPError` | — | function raises; doc not written for a full fetch / key left as-was for a retry |

### Invariants

1. Fail-soft: a 402/403/budget condition never raises out of `get_financials` and never
   blocks the analysis run (spec FR-004).
2. All FMP traffic goes through `tools/fmp_client.fmp_get` — retries get the same
   throttle + daily-soft-cap protection as first fetches (constitution IV, spec FR-006).
3. A `confirmed` key is never re-fetched inside its 90-day window (spec FR-003).
4. An `unavailable` key is re-fetched on **every** subsequent `get_financials` call within
   the window until it becomes `confirmed` (spec FR-001, clarification 2026-08-15).
5. The returned dict's shape never varies with cache state — consumers
   (`agents/fundamental_analyst.py`, backend route) need no changes.

## HTTP contract — `GET /stocks/{ticker}/financials` (backend)

**Unchanged.** Responds with `cached["data"]` (all seven keys) or 404 when no cache doc
exists. The new `outcomes` field is internal to the collection and MUST NOT appear in the
response. Existing tests in `backend/tests/test_routers.py` remain the contract's guard.

## Component-spec sync obligation

`specs/component-specs/agent-runner/tools/financials.md` — the "Caching logic" section
MUST be rewritten during implementation to describe the outcome map, per-key retry, and
`fetched_at` preservation, keeping the component spec authoritative (constitution II).
