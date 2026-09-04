# Phase 1 Data Model: Stocks Page Organization, Conviction Rework & Activity Trail

**Feature**: `037-stocks-conviction-and-activity` | **Date**: 2026-09-04

Two changes to an existing collection, one new collection, one cached-payload widening.
Nothing is removed.

---

## 1. `analyses` — two new top-level fields

One document per ticker (unique index on `ticker`). The board's feed projection excludes
`sub_reports`, so anything the tiles or the sort need must ride **top-level** — the same
reasoning `crew.py` already applies to `recent_institutional_activity`.

### `conviction` *(existing field, new provenance)*

`"high" | "medium" | "low"`. Unchanged type and unchanged consumers. It is now written by
`skills/conviction.py` rather than by `agents/portfolio_strategist.py`'s LLM output.

### `conviction_rank` *(new)*

| Field | Type | Values |
|-------|------|--------|
| `conviction_rank` | int | `3` = high, `2` = medium, `1` = low, `0` = unknown/absent |

Denormalised sort key for `GET /analysis/feed` (research R5). It MUST be written in the same
operation as `conviction` and MUST always agree with it — a contract test asserts the mapping
in both services.

### `conviction_detail` *(new)*

The rule trace behind the rating. Consumed by FR-010 (rationale on the detail page) and
FR-028 (change reasons in the history trail).

```jsonc
{
  "level": "high",              // mirrors `conviction`
  "rank": 3,                    // mirrors `conviction_rank`
  "computed_at": "<datetime>",
  "conditions": {
    "strategies": {
      "pass": true,
      "calls": {                // one entry per entry strategy (research R2)
        "the_strat":     {"call": "buy",     "why": "full TFC bullish; weekly revstrat_2bar_bullish"},
        "accumulation":  {"call": "buy",     "why": "ACCUMULATION, score 4"},
        "gap_analysis":  {"call": "buy",     "why": "down-gap score 3"}
      }
    },
    "zscore": {
      "pass": true,
      "daily":  {"value": -1.84, "p25": -1.12, "in_bottom_quartile": true,  "sample": 232},
      "weekly": {"value": -1.31, "p25": -0.97, "in_bottom_quartile": true,  "sample": 84}
    },
    "revenue": {
      "pass": true,
      "growth_yoy": 0.081,      // fraction; FMP's own annual YoY growth figure (most recent fiscal year vs the one before) — reused from `financials["growth"]`, same figure tools/screener.py exposes as `revenue_growth_yoy`
      "change_qoq": 0.014,      // fraction; latest cached quarter vs the prior cached quarter
      "yoy_growing": true,
      "qoq_declining": false
    }
  },
  "blockers": [],               // human-readable reasons the level is not higher
  "caveats": ["market breadth is overbought — timing headwind"],  // FR-006b / research R10
  "missing_inputs": []          // FR-009: which inputs could not be evaluated
}
```

**Validation rules**

- `level == "high"` **iff** `conditions.strategies.pass && conditions.zscore.pass && conditions.revenue.pass` (FR-006).
- `call` ∈ `{"buy", "not-buy", "no-call"}`; `strategies.pass` is true only when all three are `"buy"` (FR-006a).
- `zscore.pass` requires `daily.in_bottom_quartile && weekly.in_bottom_quartile` (FR-006, both timeframes — FR/US2 scenario 4).
- `in_bottom_quartile` is `value <= p25`, **inclusive** (FR-011).
- A timeframe with `sample < 60` (daily) or `< 30` (weekly) sets `in_bottom_quartile: null`, adds to `missing_inputs`, and forces `zscore.pass = false` (FR-009).
- `revenue.pass` requires `yoy_growing && !qoq_declining`; either figure being `null` means `pass = false` and an entry in `missing_inputs` (spec Edge Cases: "Revenue data gaps").
- `level` is never `"high"` when `missing_inputs` is non-empty.
- `blockers` is empty **iff** `level == "high"`; otherwise it names at least one failing condition (SC-003).
- `caveats` never affects `level` (FR-006b).

**Level assignment** (FR-007 / FR-008, full truth table in [contracts/conviction-rules.md](./contracts/conviction-rules.md)):

| Level | Rule |
|-------|------|
| `high` | all three conditions pass |
| `medium` | ≥ 2 of 3 strategies `buy`, **and** ≥ 1 z-score timeframe bottom-quartile, **and** revenue not in QoQ decline |
| `low` | everything else |

### New index

```text
analyses: [("conviction_rank", DESCENDING), ("ticker", ASCENDING)]
```

Backs the feed's total-order sort. Declared in **both** `agent-runner/tools/db.py` and
`backend/db.py` alongside the existing `analyses` indexes.

---

## 2. `stock_events` — new collection

Append-only log serving both the global activity feed (US3) and the per-stock change history
(US5). Constant `STOCK_EVENTS = "stock_events"` mirrored in `agent-runner/tools/db.py` and
`backend/db.py`.

```jsonc
{
  "ticker": "AVB",
  "event_type": "added",          // "added" | "updated"
  "occurred_at": "<datetime>",    // UTC; the ordering key
  "changed": false,               // "updated" only; always false for "added"
  "changes": {                    // present only when changed == true
    "signal":     {"from": "neutral", "to": "bullish"},
    "conviction": {"from": "medium",  "to": "high"}
  },
  "reason": "all three strategies aligned; revenue +8.1% YoY",  // FR-028; null when changed == false
  "source": "agent_runner"        // provenance: "agent_runner" | "backend_api" | "backfill" (implementation-time refinement — tags by which SERVICE wrote the row, not by module, since register_ticker's "added" and queue_worker's "updated" both originate in agent-runner)
}
```

| Field | Type | Notes |
|-------|------|-------|
| `ticker` | string | Uppercase. Not unique — a ticker accumulates many events. |
| `event_type` | string | `"added"` on first registration, `"updated"` on every completed re-analysis (FR-018, clarification Q5). |
| `occurred_at` | datetime | UTC. Sort key for both views. For back-filled `added` events this is the ticker's `first_seen_at`, not the back-fill run time (FR-021a). |
| `changed` | bool | `true` when the re-analysis moved `signal` or `conviction` (FR-018a). Drives the visual flag and the US5 filter. |
| `changes` | object \| null | Only the fields that actually moved appear. Same shape as `crew.py`'s existing `diff_since_last` output, reused deliberately (research R6). |
| `reason` | string \| null | Derived from `conviction_detail`, never LLM prose (FR-028). |
| `source` | string | Distinguishes back-filled rows so the one-shot script stays idempotent. |

**Validation rules**

- `event_type == "added"` ⇒ `changed == false`, `changes` absent, `reason` null.
- `changed == true` ⇒ `changes` has at least one of `signal` / `conviction`, each with differing `from` / `to`.
- `changed == false` on an `updated` event ⇒ no `changes`, no `reason` (FR-029 — such an event appears in the activity feed but never in the per-stock history trail).
- At most one `added` event per ticker; the back-fill and both live registration paths must upsert-guard on `{ticker, event_type: "added"}` (research R7).
- Documents are never updated or deleted in normal operation.

**State transitions**: a ticker's event stream is `added` → (`updated`)\*. There is no
`removed` event type — a delisted ticker keeps its history and its link resolves to the
removed-state page (spec Edge Cases).

**Indexes**

```text
stock_events: [("occurred_at", DESCENDING)]                          # global feed
stock_events: [("ticker", ASCENDING), ("occurred_at", DESCENDING)]   # per-stock trail
stock_events: [("ticker", ASCENDING), ("event_type", ASCENDING)]     # added-once guard
```

**Retention**: no TTL. The collection grows by roughly one document per completed analysis;
at single-user scale that is negligible, and both read paths are capped (100 global, 20
per stock) so growth never reaches the API. Adding a TTL later is a one-line change if it
ever matters.

**Writers** (research R6):

| Event | Writer | Trigger |
|-------|--------|---------|
| `added` | `agent-runner/tools/db.py::register_ticker()` | worker-side registration |
| `added` | `backend/routers/queue.py` registration branch | API-side registration |
| `added` | `backend/scripts/backfill_stock_events.py` | one-shot, idempotent |
| `updated` | `agent-runner/queue_worker.py` | at the existing `write_db(ANALYSES, ...)` call site, diffing against the document read immediately before |

---

## 3. `financials_cache` — unchanged

**No schema or endpoint change.** The original plan proposed widening
`ENDPOINTS["income_quarterly"]` from `limit=4` to `limit=8` to support a true quarterly
year-over-year comparison. This was reverted during implementation: `KNOWN_ISSUES.md`
documents that this FMP plan 402s the **entire** `income-statement` call beyond ~4
quarterly periods, which `_fetch_statement()` treats as `outcome: "unavailable"` and
degrades to `[]` — widening the limit would have silently broken the existing 4-quarter
fetch rather than adding rows (research R4 Amendment).

The corrected design reads two payloads already cached at today's limits:

- `financials["growth"]` (`income-statement-growth`, annual, `limit=4`, unchanged) supplies
  `growth[0]["growthRevenue"]` — the YoY figure (Rule 3 in
  [contracts/conviction-rules.md](./contracts/conviction-rules.md)).
- `financials["income_quarterly"]` (`limit=4`, unchanged) supplies `[0]` and `[1]` for the
  QoQ comparison — only 2 of the 4 cached quarters are ever needed.

Both series are **newest-first**, exactly as `agents/fundamental_analyst.py` already
consumes them. A cached document missing either key (a 402/403-degraded fetch, or a series
shorter than needed) yields `growth_yoy: null` or `change_qoq: null` — a revenue-condition
failure per FR-009, not a silent skip — and self-heals on the next 90-day cache refresh or
re-pull.

---

## 4. Derived / transient shapes (not persisted)

### `RevenueTrend` — `agent-runner/tools/revenue.py`

```jsonc
{ "growth_yoy": 0.081, "change_qoq": 0.014, "yoy_growing": true, "qoq_declining": false,
  "latest_period": "2026-06-30", "missing": [] }
```

`growth_yoy` reads `financials["growth"][0]["growthRevenue"]`; `change_qoq` reads
`financials["income_quarterly"][0]` vs `[1]`. `latest_period` is the quarterly series'
`[0]["date"]`. `missing` names whichever of `growth_yoy`/`change_qoq` could not be computed.

### `Crumb` — `frontend/src/lib/breadcrumbs.ts`

```jsonc
{ "label": "AVB", "to": "/stock/AVB" }   // `to` is null for the final (current) crumb
```

The trail is computed per render from `useLocation()`; nothing is stored (FR-026).

---

## Entity → requirement map

| Spec entity | Realised as | Requirements |
|-------------|-------------|--------------|
| Ticker registry entry | `ticker_index` (unchanged) | FR-018, FR-021a |
| Analysis result | `analyses` + `conviction_rank`, `conviction_detail` | FR-002, FR-005, FR-012 |
| Strategy call set | `conviction_detail.conditions.strategies.calls` | FR-006, FR-006a |
| Z-score reading | `conviction_detail.conditions.zscore` | FR-006, FR-011 |
| Revenue trend | `conviction_detail.conditions.revenue`, from `tools/revenue.py` | FR-006 |
| Activity event | `stock_events` | FR-015 – FR-021a |
| Verdict change entry | `stock_events` rows with `changed == true` | FR-027 – FR-030 |
| Breadcrumb trail | `lib/breadcrumbs.ts` (transient) | FR-023 – FR-026 |
