# Contract: Analysis Feed Ordering & Paging

**Feature**: `037-stocks-conviction-and-activity` | **Implements**: FR-001 – FR-004

**Producer**: `backend/routers/analysis.py` → `GET /analysis/feed`
**Consumers**: `frontend/src/hooks/useAnalysis.ts` (`useFeed`), `frontend/src/lib/groupFeed.ts`,
`frontend/src/pages/Stocks.tsx`

---

## Endpoint

```
GET /analysis/feed?page=1&page_size=20
                  [&ticker=&signal=&sector=&industry=&conviction=&sentiment=&from_date=&to_date=]
```

Request parameters, filter semantics, response envelope
(`{items, total, page, page_size}`), the `sub_reports` projection exclusion, and the
single batched `ticker_index` lookup for `name`/`logo_url` are all **unchanged** from
today. This contract changes exactly one thing: the sort.

---

## The ordering guarantee

```diff
- .sort("timestamp", -1)
+ .sort([("conviction_rank", -1), ("ticker", 1)])
```

**Guarantee**: results are returned in a **total order** — conviction descending, then
ticker ascending — across the whole filtered result set, with pagination applied over that
order.

Why this is a total order, and why it is enough:

1. `analyses` carries a **unique index on `ticker`** (`backend/db.py`,
   `agent-runner/tools/db.py`) — exactly one document per ticker — so `(conviction_rank,
   ticker)` admits no ties.
2. The board groups by signal **on the client**. A subsequence of a totally-ordered list is
   itself ordered, so each signal bucket comes out conviction-desc-then-A→Z for free; the
   server never needs to know about grouping (FR-002).
3. `skip`/`limit` over a total order means page *n+1* sorts strictly after page *n*, so
   "Load more" strictly appends and no visible tile moves (FR-003).

### `conviction_rank`

`3` = high, `2` = medium, `1` = low, **missing or unrecognised = `0`** (sorts last within
its signal group). Written on the analyses document by `crew.py` — see
[conviction-rules.md](./conviction-rules.md#rule-5--integration-into-the-analyses-document-fr-012-fr-014).

Sorting on the string `conviction` directly is **wrong** and must not be used: it orders
alphabetically (`high` < `low` < `medium`).

### Required index

```text
analyses: [("conviction_rank", DESCENDING), ("ticker", ASCENDING)]
```

Declared in both `backend/db.py` and `agent-runner/tools/db.py` (Principle VI).

### Filters

Every existing filter continues to compose as an `$and` of `ticker` conditions plus direct
field matches; the sort applies **after** filtering, so ordering holds for any filter
combination (FR-004). `timestamp` remains on the document and remains filterable via
`from_date` / `to_date`; it is simply no longer the sort key.

---

## Client contract: `groupFeed.ts`

`groupBySignal(items)` MUST **preserve the order of `items`** within each bucket.

```diff
  return GROUP_ORDER.filter((signal) => buckets.has(signal)).map((signal) => ({
    signal,
-   items: [...buckets.get(signal)!].sort(
-     (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
-   ),
+   items: buckets.get(signal)!,
  }));
```

The existing timestamp re-sort would undo the server order on every render. Removing it
also strengthens the function's own docstring promise ("pure and stateless — called with the
full flattened item list on every render, so pages merging in via infinite scroll land in
their correct group automatically").

Bucket order (`bullish`, `neutral`, `bearish`, `unknown`) and the "never silently fold an
unrecognised signal into neutral" rule are unchanged (FR-001).

---

## Acceptance tests

**Backend** — `backend/tests/test_analysis_feed_ordering.py`

| # | Given | Then |
|---|-------|------|
| 1 | analyses with mixed `conviction_rank` | items come back rank-descending |
| 2 | several tickers sharing a rank | those are ticker-ascending among themselves |
| 3 | a document with no `conviction_rank` | it sorts after all ranked documents |
| 4 | `page=1` then `page=2` at `page_size=n` | every page-2 item sorts strictly after every page-1 item |
| 5 | any filter applied (`sector`, `signal`, `sentiment`, …) | ordering guarantee still holds |
| 6 | `conviction=high` filter | only rank-3 items, still ticker-ascending |

**Frontend** — `frontend/src/lib/groupFeed.test.ts`

| # | Given | Then |
|---|-------|------|
| 7 | items already in server order, mixed signals | each bucket preserves relative input order |
| 8 | a second page appended to the flattened list | no earlier item's index within its bucket changes |
| 9 | an unrecognised signal value | still lands in the `unknown` bucket, order preserved |

**Frontend** — `frontend/src/pages/Stocks.test.tsx`

| # | Given | Then |
|---|-------|------|
| 10 | a Bullish group of MSFT(high), AVB(high), GOOG(medium), AAPL(low) | tiles render AVB, MSFT, GOOG, AAPL (US1 scenario 1) |
| 11 | "Load more" clicked | previously rendered tiles keep their positions (US1 scenario 4) |
