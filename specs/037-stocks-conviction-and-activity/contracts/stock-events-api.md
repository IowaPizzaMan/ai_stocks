# Contract: Stock Events API (Activity Feed + Change History)

**Feature**: `037-stocks-conviction-and-activity` | **Implements**: FR-015 – FR-021a, FR-027 – FR-030

**Producer**: `backend/routers/events.py` (new router, `prefix="/events"`, registered in `backend/main.py`)
**Consumers**: `frontend/src/hooks/useStockEvents.ts` → `components/feed/ActivityFeed.tsx` (US3),
`components/stock/ChangeHistory.tsx` (US5)
**Backing collection**: `stock_events` — see [data-model.md](../data-model.md#2-stock_events--new-collection)

Both endpoints are read-only. Events are written by the agent-runner and by the registration
path in `backend/routers/queue.py`; nothing in this router writes.

---

## `GET /events` — global activity feed (US3)

```
GET /events?page=1&page_size=20
```

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `page` | int ≥ 1 | `1` | 1-indexed, matching `GET /analysis/feed` |
| `page_size` | int 1–100 | `20` | |

### Response

```jsonc
{
  "items": [
    {
      "ticker": "AVB",
      "event_type": "updated",
      "occurred_at": "2026-09-04T14:02:11Z",
      "changed": true,
      "changes": { "conviction": { "from": "medium", "to": "high" } },
      "reason": "all three strategies aligned; revenue +8.1% YoY"
    },
    {
      "ticker": "AVB",
      "event_type": "added",
      "occurred_at": "2026-09-04T09:15:00Z",
      "changed": false,
      "changes": null,
      "reason": null
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "window": 100
}
```

### Guarantees

- **Newest first** by `occurred_at` descending (FR-019).
- **Hard cap of 100 events total** (FR-019). The cap is a property of the endpoint, not of the
  collection: `total` is `min(count, 100)`, and any `page`/`page_size` combination whose
  offset reaches 100 returns an empty `items` list. `window` echoes the cap so the client
  need not hard-code it.
- Paging within the 100-event window works forward and backward (FR-020).
- An empty collection returns `items: []`, `total: 0` — the client renders the empty state
  (FR-021); it is not a 404.
- `source` is **not** exposed; it is an internal provenance field.

### Implementation note

Enforce the cap in the query, not after materialising:

```python
window = 100
skip = (page - 1) * page_size
limit = max(0, min(page_size, window - skip))
items = [] if limit == 0 else list(
    db[STOCK_EVENTS].find({}, {"_id": 0, "source": 0})
      .sort("occurred_at", -1).skip(skip).limit(limit)
)
total = min(db[STOCK_EVENTS].count_documents({}), window)
```

Served by the `[("occurred_at", DESCENDING)]` index.

---

## `GET /events/{ticker}` — per-stock change history (US5)

```
GET /events/AVB?limit=20
```

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `limit` | int 1–50 | `20` | The FR-030 cap; truncated, not paged |

### Response

```jsonc
{
  "ticker": "AVB",
  "items": [
    { "event_type": "updated", "occurred_at": "2026-09-04T14:02:11Z", "changed": true,
      "changes": { "conviction": { "from": "medium", "to": "high" } },
      "reason": "all three strategies aligned; revenue +8.1% YoY" },
    { "event_type": "added", "occurred_at": "2026-09-01T09:15:00Z", "changed": false,
      "changes": null, "reason": null }
  ],
  "total": 2,
  "limit": 20
}
```

### Guarantees

- Filtered to `{ticker, $or: [{event_type: "added"}, {changed: true}]}` — an `updated` event
  that moved nothing is **excluded** (FR-029). Those rows still appear in `GET /events`,
  which is what makes the global feed a superset (clarification Q5).
- Newest first, truncated at `limit`; older entries are dropped, not paged (FR-030).
- A ticker with only an `added` event returns that single item — the client renders the
  near-empty state (FR-030, spec Edge Case "Change history for a brand-new stock").
- An unknown ticker returns `items: []`, `total: 0`, **not** a 404 — the stock page renders
  for tickers with no events yet.
- `ticker` is upper-cased before lookup.

Served by the `[("ticker", ASCENDING), ("occurred_at", DESCENDING)]` index.

---

## Client rendering contract

### `ActivityFeed.tsx` (US3)

- Each row renders as `"{TICKER} was {added|updated} on {M/D}"` (FR-016), with `{TICKER}` a
  `<Link to={`/stock/${ticker}`}>` (FR-017).
- Rows with `changed: true` carry a visual flag and append the transition
  (e.g. `conviction medium→high`) (FR-018a). Rows with `changed: false` render plain.
- Lives inside the Stocks page's existing scrollable region so the page keeps its bounded,
  viewport-relative layout — the browser window itself must still never scroll (FR-022,
  the invariant spec 027 established).
- Uses TanStack Query with `refetchInterval: false` (Constitution: the frontend never polls).

### `ChangeHistory.tsx` (US5)

- Rendered on the stock detail page. Each entry shows the date, the transition
  (`signal` and/or `conviction`, `from→to`), and the `reason` (FR-028).
- A `null` reason on a back-filled or legacy row renders the entry without a reason line
  rather than erroring (spec Edge Case "Reason unavailable for an old change").

---

## Acceptance tests

**Backend** — `backend/tests/test_events_router.py`

| # | Given | Then |
|---|-------|------|
| 1 | mixed `added`/`updated` events | `GET /events` returns them `occurred_at` descending |
| 2 | 150 events in the collection | `total == 100`; paging past offset 100 yields `items: []` |
| 3 | empty collection | `200` with `items: []`, `total: 0` |
| 4 | a ticker with `added` + one changed + one unchanged `updated` | `GET /events/{t}` returns 2 items (the unchanged one excluded) |
| 5 | unknown ticker | `200` with `items: []`, not `404` |
| 6 | any response | no `source` field is exposed |
| 7 | `limit` above 50 or below 1 | rejected/clamped per the declared range |

**Backend** — `backend/tests/test_stock_events_contract.py` (Principle VI mirror)

| # | Assertion |
|---|-----------|
| 8 | `backend.db.STOCK_EVENTS == "stock_events"` |
| 9 | the declared `stock_events` indexes match `agent-runner/tools/db.py`'s |
| 10 | the event field vocabulary this router reads matches the writer's — mirrored verbatim by `agent-runner/tests/test_stock_events.py` |

**Agent-runner** — `agent-runner/tests/test_stock_events.py`

| # | Given | Then |
|---|-------|------|
| 11 | `register_ticker()` on a new ticker | exactly one `added` event, `changed: false` |
| 12 | `register_ticker()` called twice | still exactly one `added` event |
| 13 | analysis persisted with an unchanged verdict | one `updated` event, `changed: false`, no `changes`, no `reason` (FR-029 boundary) |
| 14 | analysis persisted with a moved conviction | `changed: true`, `changes.conviction` `{from, to}`, `reason` derived from `conviction_detail` — not LLM prose (FR-028) |
| 15 | analysis persisted for a ticker with no prior document | `updated` event with `changed: false` (nothing to diff against) |
| 16 | written document | field set matches exactly the vocabulary asserted in the backend mirror |

**Back-fill** — `backend/tests/test_backfill_stock_events.py`

| # | Given | Then |
|---|-------|------|
| 17 | tickers with `first_seen_at` and no events | one `added` event each, `occurred_at == first_seen_at`, `source: "backfill"` |
| 18 | script run twice | no duplicate `added` events (idempotent) |
| 19 | a ticker that already has a live `added` event | not duplicated |
| 20 | after back-fill | no `updated` events are created (clarification Q7) |
