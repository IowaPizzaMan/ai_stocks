# Quickstart: Stocks Page Organization, Conviction Rework & Activity Trail

**Feature**: `037-stocks-conviction-and-activity`

**Depends on**: `ticker_index`, `price_history`, and `analyses` already populated for a
handful of tickers (any prior analysis run does this), and `financials_cache` reachable for
at least one ticker whose fundamentals FMP covers on this plan.

This is a validation guide — run it end-to-end to prove the five deliverables work.
Implementation details live in [contracts/](./contracts/) and [data-model.md](./data-model.md).

---

## Prerequisites

```bash
docker compose up -d --build          # mongodb, backend, frontend, agent-runner, ollama
```

Confirm there is something to look at:

```js
db.ticker_index.countDocuments({})    // > 0
db.analyses.countDocuments({})        // > 0
```

---

## 0. Gates — run these first and after every change

```bash
# agent-runner (its own venv)
cd agent-runner && python -m pytest && ruff check .

# backend (its own venv)
cd backend   && python -m pytest && ruff check .

# repo-root ruff over both services
ruff check backend/ agent-runner/ scripts/

# frontend
cd frontend  && npm test && npm run typecheck
```

Constitution: tests and `ruff` must pass before a change is done, and hooks are never
skipped with `--no-verify`.

---

## 1. Back-fill the activity log (one-shot, idempotent)

```bash
docker compose exec backend python -m scripts.backfill_stock_events
```

**Expected outcome**: one `added` event per registered ticker, dated from its
`first_seen_at` — not from the time you ran the script.

```js
db.stock_events.countDocuments({ event_type: "added" })   // == db.ticker_index.countDocuments({})
db.stock_events.findOne({ ticker: "AVB", event_type: "added" })
// -> { ticker: "AVB", event_type: "added", occurred_at: <first_seen_at>,
//      changed: false, changes: null, reason: null, source: "backfill" }
db.stock_events.countDocuments({ event_type: "updated" })  // 0 — updates are never back-filled
```

Run it a second time. The counts must not change (FR-021a idempotency).

---

## 2. Recompute conviction on a real ticker

Queue an analysis the normal way (the Stocks page's ticker input, or a `work_queue` insert)
for a ticker with ≥ 1 year of daily history.

**Expected outcome** — the analyses document now carries the rule trace:

```js
db.analyses.findOne({ ticker: "AVB" }, { conviction: 1, conviction_rank: 1, conviction_detail: 1 })
```

Check each invariant from [contracts/conviction-rules.md](./contracts/conviction-rules.md):

- `conviction_rank` matches `conviction` (`high→3`, `medium→2`, `low→1`).
- `conviction_detail.conditions.strategies.calls` has exactly three entries —
  `the_strat`, `accumulation`, `gap_analysis` — each `"buy" | "not-buy" | "no-call"`.
  **`market_flow` and `position_management` must not appear here** (FR-006b).
- `conviction_detail.conditions.zscore` has both `daily` and `weekly`, each with `value`,
  `p25`, `in_bottom_quartile`, `sample`.
- `conviction_detail.conditions.revenue` has `growth_yoy` and `change_qoq`.
- `blockers` is empty **iff** `conviction == "high"`.
- Top-level `conviction` is **independent of** `sub_reports.recommendation.conviction`
  (that one is `market_flow`'s *timing* confidence — a different value with the same name).

### The distribution actually spread out (SC-002)

```js
db.analyses.aggregate([{ $group: { _id: "$conviction", n: { $sum: 1 } } }])
```

**Expected outcome**: after re-analysing the board, `high` is a minority — no more than ~25%
— and all three levels are present once 20+ stocks have been recomputed. This is the
"everything is a 3" regression check; if `high` still dominates, the rules are not being
applied (or `portfolio_strategist` is still emitting `conviction`).

### Revenue inputs are actually there

No endpoint changed (research R4 Amendment — the FMP plan 402s quarterly statements beyond
~4 periods, so widening the fetch would break it). Both figures reuse what's already cached:

```js
var fin = db.financials_cache.findOne({ ticker: "AVB" }).data
fin.growth.length              // >= 1 — feeds growth_yoy (same figure as screener.revenue_growth_yoy)
fin.income_quarterly.length    // >= 2 — feeds change_qoq ([0] vs [1])
```

A cache document missing `growth` or with fewer than 2 quarters yields a `null` figure;
expect `conviction_detail.missing_inputs` to name it and the level to be below `high`. It
self-heals when the 90-day cache window rolls over or the ticker is re-pulled.

---

## 3. Board ordering (US1)

```bash
curl -s 'http://localhost:8000/analysis/feed?page=1&page_size=20' | \
  python -c "import json,sys;[print(i['conviction_rank'], i['ticker'], i['signal']) for i in json.load(sys.stdin)['items']]"
```

**Expected outcome**: ranks are non-increasing down the list, and tickers ascend
alphabetically within each rank block. Fetch `page=2` — every item on it must sort at or
after the last item of page 1.

In the browser at `/`:

- Groups still read Bullish → Neutral → Bearish top-to-bottom.
- Within a group, high-conviction tiles come first, then medium, then low; A→Z inside each
  block.
- Click **Load more**: already-visible tiles must not move (FR-003). Watch a specific tile's
  position before and after.
- Apply a sector or sentiment filter — ordering must survive (FR-004).

---

## 4. Activity feed (US3)

```bash
curl -s 'http://localhost:8000/events?page=1&page_size=20' | python -m json.tool
```

**Expected outcome**: newest first; `total` never exceeds `100`; `window: 100`; no `source`
field in the response.

On the Stocks page:

- Entries read like `AVB was added on 9/4`, with `AVB` linking to `/stock/AVB`.
- Re-run an analysis that moves a stock's conviction → a new `updated` entry appears
  **flagged**, annotated `conviction medium→high` (FR-018a).
- Re-run an analysis that changes nothing → an `updated` entry appears **unflagged**.
- Page forward past 100 events → empty, no error.
- The browser window itself must still not scroll — only the page's own grid region does
  (FR-022).

---

## 5. Per-stock change history (US5)

```bash
curl -s 'http://localhost:8000/events/AVB?limit=20' | python -m json.tool
```

**Expected outcome**: the `added` event plus only those `updated` events where
`changed: true` — the unchanged re-analysis from step 4 must be **absent** here while still
being present in `GET /events` (FR-029; the global feed is a superset).

On `/stock/AVB`: dated entries showing the transition and a reason drawn from the conviction
rules. A freshly added, never-analysed ticker shows just its `added` entry.

---

## 6. Breadcrumbs (US4)

Navigate in the browser and check the trail above the page content:

| Go to | Trail |
|-------|-------|
| `/` | `Stocks` |
| `/stock/AVB` | `Stocks / AVB` |
| `/stock/AVB#news` | `Stocks / AVB / News` |
| `/macro` | `Macro` |

- Every segment except the last is a link; clicking `Stocks` returns to the board, clicking
  `AVB` from a sub-tab lands on that stock's default view.
- A top-level page shows one segment with **no** trailing separator (FR-025).
- **Paste `/stock/AVB#news` into a fresh tab** — the full trail must render from the URL
  alone, with no in-app navigation history (FR-026). This is the case a history-based
  implementation gets wrong.

---

## Rollback

Nothing is destructive and no migration runs.

- `stock_events` can be dropped; the endpoints return empty states and the UI renders its
  empty-state copy.
- `conviction_rank` / `conviction_detail` can be `$unset`; the feed treats a missing rank as
  `0` and the detail page shows "rating not yet recomputed".
- No `financials.py` change was made, so there is nothing to revert there.
