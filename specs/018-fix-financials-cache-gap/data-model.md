# Data Model: Fix Stale Empty Financials Cache

**Feature**: 018-fix-financials-cache-gap | **Date**: 2026-08-15

One entity changes: the `financials_cache` MongoDB document. No new collections.

## `financials_cache` document (one per ticker)

| Field | Type | Semantics |
|---|---|---|
| `ticker` | string (uppercase) | Unique key — `replace_one({"ticker": ...}, upsert=True)` semantics unchanged. |
| `data` | object: statement key → list | The seven statement payloads (`income_annual`, `income_quarterly`, `balance_annual`, `cashflow_annual`, `ratios`, `key_metrics`, `growth`). Shape unchanged — every consumer keeps reading this as-is. |
| `fetched_at` | UTC datetime | Set only by a **full** fetch (cache miss or 90-day expiry). A partial retry MUST NOT bump it (research D4). |
| `outcomes` | object: statement key → `"confirmed"` \| `"unavailable"` | **New, additive.** `confirmed` = FMP answered 200 for that key (payload may be empty). `unavailable` = key degraded to `[]` on a temporary condition (402/403 or budget guard). |

### Validation rules

- `data` and `outcomes` cover exactly the same key set (`ENDPOINTS` in
  `agent-runner/tools/financials.py`) whenever `outcomes` is present.
- `outcomes[key] == "unavailable"` implies `data[key] == []`. The converse does not hold —
  a `confirmed` key may legitimately be `[]` (provider affirmatively has no records).
- Legacy docs (no `outcomes` field) are valid; readers derive outcomes lazily:
  empty value → `unavailable`, non-empty value → `confirmed` (research D3).

### State transitions (per statement key)

```text
 (no doc / expired doc)
        │  full fetch
        ▼
  ┌─────────────┐   200 (data or empty)   ┌─────────────┐
  │ unavailable │ ──────────────────────▶ │  confirmed  │
  │ (402/403 or │   retry on any later    │ (settled for│
  │  budget)    │   analysis run          │  90-day win)│
  └─────────────┘                         └─────────────┘
        │  402/403/budget again on retry         │ 90-day expiry
        └──── stays unavailable (retry next run) └──▶ full fetch (either state possible)
```

`confirmed` never transitions back to `unavailable` within a window — confirmed keys are
not re-fetched until the doc expires (FR-003).

## Read/write responsibilities (constitution VI)

| Service | Access | Impact of this change |
|---|---|---|
| agent-runner (`tools/financials.py`) | read + write | Writes `outcomes`; performs partial retries; sole author of the collection. |
| backend (`routers/stocks.py` → `GET /stocks/{ticker}/financials`) | read only | Returns `cached["data"]` — untouched. The additive `outcomes` field is invisible to its response. |
