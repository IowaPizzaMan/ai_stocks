# Contract: Pull mode on the queue endpoint

**Feature**: `specs/024-delta-data-pulls` (US5) | Modifies `backend/routers/queue.py`

Delta is the default. A full refresh is opt-in, per ticker, per request.

---

## `POST /queue/{ticker}`

Existing endpoint, one new optional query parameter.

### Request

| Parameter | In | Type | Default | Notes |
|---|---|---|---|---|
| `ticker` | path | string | — | Case-insensitive, uppercased server-side |
| `mode` | query | `delta` \| `full` | `delta` | `full` bypasses every delta shortcut for this ticker (FR-023) |

```
POST /queue/AAPL              → delta pull (unchanged behavior)
POST /queue/AAPL?mode=full    → full refresh
```

An unrecognized `mode` value is a `422`, not a silent fallback to delta — being
silently given a delta pull when you asked for a full refresh is the failure this
control exists to prevent.

### Response `200`

```json
{
  "ticker":  "AAPL",
  "job_id":  "66c0f1a2e4b0a1b2c3d4e5f6",
  "status":  "enqueued" | "already_queued" | "upgraded_to_full",
  "mode":    "delta" | "full"
}
```

`mode` is always echoed so the caller can confirm what was actually queued.

### Status semantics

| `status` | When | `mode` returned |
|---|---|---|
| `enqueued` | No pending/running job for this ticker | as requested |
| `already_queued` | A job exists that already satisfies the request | the existing job's mode |
| `upgraded_to_full` | `mode=full` requested, a **pending** delta job existed and was promoted in place | `full` |

**Upgrade rule** (research D8, FR-023): a `mode=full` request must never be answered
with `already_queued` while a *pending* delta job sits in the queue — the operator
would be told their request was handled and then receive a delta pull. The pending job
is updated to `mode: "full"` and the response says so.

**Running job**: if the existing job is already `running`, it is too late to upgrade.
Respond `already_queued` with the running job's mode. The caller is expected to surface
this (see UI contract below) rather than leave the operator believing a full refresh is
underway.

### Unchanged behavior

- A ticker flagged `removed_from_market` is reactivated on any enqueue, either mode.
- `register_ticker` is called before enqueueing, either mode.
- `POST /queue/all` is **delta only** — no `mode` parameter. Bulk full refresh is
  explicitly out of scope (spec, Out of Scope).

---

## `GET /queue`

Response shape unchanged, except each pending/running job now carries `mode`. Absent
means `delta` for jobs queued before this feature shipped.

```json
{
  "pending": [{ "ticker": "AAPL", "status": "pending", "mode": "full", ... }],
  "running": [...],
  "pending_count": 1,
  "running_count": 0
}
```

---

## `GET /stocks/{ticker}/pull-metrics`

New endpoint (US1). Serves the most recent pull's cost breakdown.

### Request

| Parameter | In | Type | Default | Notes |
|---|---|---|---|---|
| `ticker` | path | string | — | |
| `limit` | query | int | `1` | Recent pulls, newest first. Max `20`. |

### Response `200`

```json
{
  "ticker": "AAPL",
  "pulls": [
    {
      "job_id": "66c0...",
      "mode": "delta",
      "started_at": "2026-08-17T14:02:11Z",
      "completed_at": "2026-08-17T14:02:52Z",
      "total_ms": 41230,
      "outcome": "done",
      "accounted_ms": 38110,
      "unaccounted_ms": 3120,
      "stages": [
        {
          "name": "price",
          "elapsed_ms": 1840,
          "requests": 1,
          "bytes": 412889,
          "retrieval": "incremental",
          "outcome": "fetched"
        }
      ]
    }
  ]
}
```

`stages` is returned **sorted by `elapsed_ms` descending**, so the most expensive stage
is first — SC-006 asks the operator to identify the top three without reading code, and
sorting server-side means the client does not have to re-derive that.

`unaccounted_ms` is surfaced rather than hidden (FR-004): time the stage breakdown does
not explain is itself a finding.

### Response `404`

No pull has been recorded for this ticker yet. Not an error condition for the UI — it
renders the panel's empty state.

---

## UI contract (frontend)

### Full-refresh control — `StockDetail`

Sits beside the existing `Pull ▶` button
([StockDetail.tsx:94-105](../../../frontend/src/pages/StockDetail.tsx#L94-L105)).

| Requirement | Behavior |
|---|---|
| FR-023, SC-011 | One action triggers a full refresh of every delta-maintained dataset — no dataset picker |
| FR-024 | Labeled so it is clearly distinct from the ordinary `Pull ▶` (e.g. `Full Refresh ⟳`) |
| FR-028 | While running, the status chip states which mode is in flight — `analyzing…` is not enough |
| research D8 | On `already_queued` with a running job, the operator is told a pull is already running and their full refresh was **not** queued |

The control is always enabled, including when the ticker has no stored data (FR-029) —
it simply behaves as a first pull.

Given this is a destructive-by-nature action (it replaces stored data) that costs real
API budget, it follows the confirmation pattern already established by
`RemoveTickerConfirm.tsx` rather than firing on a single click.

### Pull-cost panel — `StockDetail`

Collapsed by default; diagnostic, not primary content.

| Requirement | Behavior |
|---|---|
| SC-006 | Top three stages by elapsed time are readable without expanding |
| FR-002 | Each stage shows whether it was incremental, full, or served from stored data |
| FR-028 | The pull's mode and outcome are shown |
| FR-004 | Unaccounted time is displayed, not silently dropped |

No polling (constitution: `refetchInterval: false` everywhere). The panel refetches when
the queue drains, reusing the existing invalidation in
[useQueue.ts:16-25](../../../frontend/src/hooks/useQueue.ts#L16-L25).
