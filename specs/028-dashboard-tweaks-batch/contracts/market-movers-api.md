# Contract: Top Traded Stocks (most-actives)

**Story**: US6 (FR-022, FR-023, FR-024)
**Research**: R4, R9

---

## Pull job: `market_movers_pull`

Already registered in 017's job registry (dataset `market_movers`, `stale_minutes: 10`);
this batch writes the handler in `agent-runner/tools/market_movers.py`.

**Scope**: pulls **only** `most-actives`, stored with `category: "actives"` — the
discriminator 017's schema already defines (R9). Gainers and losers remain valid category
values with no writer, so adding them later needs no schema change or migration.

This partial implementation is recorded deliberately: the registered job description
mentions all three categories, and a later reader should not assume it is fully delivered.

**Behavior**
1. `fmp_get("most-actives")` — 1 call.
2. Normalize to the `market_movers` schema (see [data-model](../data-model.md)), stamping
   today's `date`, `category: "actives"`, and **`rank` = the row's array index**.
3. Upsert on `(date, category, ticker)` — same-day re-runs are idempotent.
4. Return the row count.

**Field mapping** (R9 — confirmed against a live response): `symbol → ticker`,
`name → company`, `price`, `change`, `changesPercentage → change_pct`, `exchange`.

Two consequences:

- **`changesPercentage` is already a percent** (`3.35196` = +3.35%), not a fraction. Do not
  multiply by 100.
- **The endpoint returns no `volume`.** `volume` stays `None` on every `actives` row, and
  `rank` exists because ordering can no longer come from it — see below.

**Fail-soft**: catches `FmpBudgetExceededError` and `requests` errors, logs, and leaves
the previous day's rows intact rather than clearing them — a failed refresh degrades to
stale data rather than an empty panel (Principle IV).

## `POST /market/most-actives/refresh`

Enqueues `market_movers_pull`, same dedupe contract as every other refresh endpoint (R4).

- **200** `{ "status": "enqueued", "job_id": "…" }`
- **200** `{ "status": "already_queued", "job_id": "<existing>" }`

---

## `GET /market/most-actives?limit=20`

Added to the existing `market.py` — where the `market_movers` dataset naturally sits
(R10). Cache read only.

| Param | Type | Default | Max |
|---|---|---|---|
| `limit` | int | 20 | 100 |

Returns the most recent `date` present for `category: "actives"`, ordered by **`rank`
ascending** — the provider's own activity ordering, preserved at write time (R9).

Sorting by `volume` is not possible: the endpoint supplies none. Because the collection is
upsert-keyed, read order is not otherwise guaranteed, so `rank` is what keeps the panel
honest rather than arbitrarily ordered.

**Response** — always 200:

```jsonc
{
  "items": [
    { "ticker": "LUCY", "company": "Innovative Eyewear, Inc.", "price": 1.85,
      "change": 0.06, "change_pct": 3.35196, "exchange": "NASDAQ", "rank": 0 }
  ],
  "as_of": "2026-08-22T09:00:00Z",   // collected_at of the served date; null when empty
  "date": "2026-08-22"               // null when empty
}
```

`volume` is omitted from the response entirely rather than sent as `null`, so no consumer
is tempted to render a blank volume column.

Serving only the latest available date (rather than filtering to *today*) is what makes
the panel useful before the first refresh of a new day and over a weekend — the `date`
field lets the UI say plainly which session is shown.

---

## Frontend

### `MostActivesPanel.tsx` (FR-022, FR-023, FR-024)

Rendered in `Stocks.tsx` on the `grid` tab, **below** the ticker grid, inside the existing
scrollable region and within the grid column (so it sits under the tiles, not beside the
digest panel).

| State | Rendering |
|---|---|
| Loading | Existing skeleton/loading idiom |
| Populated | Ticker, company, price, change, change %; ticker links to `/stock/<TICKER>` (singular — R1). **No volume column** — the provider supplies none (R9) |
| Empty (never pulled) | Empty state naming the Refresh control |
| Error / unavailable | `Top traded stocks are unavailable right now.` (FR-024) — never a blank or silently empty section |

Shows the served `date` so a stale session is visible rather than implied.

Change percent uses the project's existing up/down status colors, paired with a sign so
direction is not conveyed by color alone.

**Assertions**
- Panel renders below the grid, within the grid column.
- Ticker cells link to `/stock/<TICKER>`.
- Empty response renders the empty state, not a bare heading.
- Error renders the unavailable message (FR-024).
- The served date is displayed.
- Rows render in `rank` order, not the order Mongo happens to return.
- `change_pct` of `3.35196` renders as `+3.35%` — not `+335.20%` (no fraction conversion).
