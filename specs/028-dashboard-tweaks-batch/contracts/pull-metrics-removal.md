# Contract: Pull-cost diagnostics removal

**Story**: US7 (FR-025, FR-026, FR-026a, FR-026b)
**Research**: R12

A removal, so the "contract" is a complete inventory and a safe order. Every reference
below was enumerated from the codebase, not estimated.

---

## Complete reference inventory

| # | Reference | File | Action |
|---|---|---|---|
| 1 | `PullCostPanel` component | `frontend/src/components/stock/PullCostPanel.tsx` | delete file |
| 2 | its test | `frontend/src/components/stock/PullCostPanel.test.tsx` | delete file |
| 3 | import + render | `frontend/src/pages/StockDetail.tsx:14`, `:134` | remove |
| 4 | `usePullMetrics` call | `frontend/src/pages/StockDetail.tsx:23`, `:57` | remove |
| 5 | hook | `frontend/src/hooks/usePullMetrics.ts` | delete file |
| 6 | `Pull`, `PullStage` types | `frontend/src/api/types.ts` | remove |
| 7 | endpoint | `backend/routers/stocks.py:169` (`get_pull_metrics`) + `MAX_PULL_METRICS:165` | remove |
| 8 | import | `backend/routers/stocks.py:20` | remove from import list |
| 9 | writer | `agent-runner/queue_worker.py:114` `_write_pull_metrics`, `:136` `_record_pull_metrics` | delete both |
| 10 | call sites | `agent-runner/queue_worker.py:180`, `:191`, `:199` | remove |
| 11 | import | `agent-runner/queue_worker.py:18` | remove from import list |
| 12 | indexes | `agent-runner/tools/db.py:127-128` | delete both declarations |
| 13 | constant | `agent-runner/tools/db.py:63` | delete |
| 14 | constant | `backend/db.py:62` | delete |
| 15 | existing tests | `agent-runner/tests/test_queue_worker.py` pull-metrics cases | delete |
| 16 | stored data | `pull_metrics` collection | one-time `drop()` |

---

## Removal order

**Frontend first (1–6), then backend endpoint (7–8), then writer (9–11), then storage
(12–16).**

Deleting the UI before the endpoint means no intermediate commit ships a frontend calling
a removed endpoint. Deleting the writer before the indexes means nothing is writing when
the collection is dropped.

---

## Why this is safe (FR-026b)

Writers: `queue_worker.py` only. Readers: one endpoint serving one hook serving one
panel. **Nothing** in the analysis pipeline, price baseline, or delta-pull decision path
reads `pull_metrics`.

The baseline delta pulls actually depend on is `price_history` — a separate collection
carrying its own explicit no-TTL warning (`backend/db.py:56-59`). So FR-026b holds
structurally: there is no code path from pull execution to `pull_metrics` reads at all,
not merely no *observed* dependency.

`pull_metrics` also already carried a 30-day TTL, so the drop discards at most 30 days of
data that nothing consumes.

`metrics.record_call` in `fmp_client.py` is **not** removed — it is in-process
instrumentation that feeds the crew's in-memory `last_pull`, unrelated to the persisted
collection. Removing it would change pull behavior, which FR-026b forbids.

---

## Data drop

Run once against the running MongoDB:

```js
db.pull_metrics.drop()
```

Dropping the collection removes its indexes with it; the declarations are still deleted
from `tools/db.py` so `ensure_indexes` does not recreate it on next start. **Order
matters**: drop *after* the index declarations are removed and the worker is restarted,
or the next `ensure_indexes` run recreates an empty collection.

---

## Assertions

- `StockDetail` renders with no "Pull cost" text present (FR-025).
- `StockDetail` renders correctly for a ticker with and without prior analysis, proving
  the removed hook was not load-bearing for layout.
- `GET /stocks/{ticker}/pull-metrics` returns 404 (route gone).
- A completed queue job writes no `pull_metrics` document.
- A completed queue job still produces its analysis normally (FR-026b) — the regression
  test that matters most here.
- `grep -ri "pull_metrics\|PullCost\|usePullMetrics"` over `backend/`, `agent-runner/`,
  and `frontend/src/` returns nothing.
