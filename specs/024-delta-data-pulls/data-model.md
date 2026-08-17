# Phase 1 Data Model: Delta-Only Data Pulls

**Feature**: `specs/024-delta-data-pulls` | **Date**: 2026-08-17

Collection constants are declared in **both** `backend/db.py` and
`agent-runner/tools/db.py`, kept in sync by hand (constitution Principle VI, research
D4).

---

## New collection: `price_history`

One document per ticker holding the complete daily OHLCV series plus its coverage
envelope. Replaces the backend's `price_cache` (four documents per ticker, one per
chart resolution).

```
{
  ticker: "AAPL",                    // unique key, uppercase
  bars: [                            // ascending by date, no duplicate dates
    { date: "1998-01-02", open: 0.0, high: 0.0, low: 0.0, close: 0.0, volume: 0 },
    ...
  ],
  coverage: {
    first_date:      "1998-01-02",   // oldest bar held
    last_date:       "2026-08-15",   // newest bar held — the delta anchor
    bar_count:       7182,
    established_at:  ISODate(...),   // last FULL build (first pull or full refresh)
    extended_at:     ISODate(...),   // last successful delta append
    source:          "fmp"
  }
}
```

**Indexes**

- `{ ticker: 1 }` unique.

No TTL index. This collection is a maintained store, not a cache — expiry would
reintroduce the whole-dataset re-download this feature exists to remove.

**Validation rules**

| Rule | Source |
|---|---|
| `bars` strictly ascending by `date`, no duplicate dates | FR-008 |
| `coverage.last_date` equals `bars[-1].date` | FR-006 |
| `coverage.first_date` equals `bars[0].date` | FR-006 |
| `coverage.bar_count` equals `len(bars)` | FR-008 |
| A delta append advances `extended_at` only; it never touches `established_at` | FR-010 |
| A full build sets both timestamps and replaces `bars` wholesale | FR-025 |
| Non-finite floats are sanitized to `null` before write | existing `sanitize_floats` |

**State transitions**

```
        (no document)
              │  first pull / full refresh — FR-007, FR-023
              ▼
        ESTABLISHED ──── delta pull (new bars) ────► EXTENDED
              ▲                                        │
              │                                        │ delta pull, no new bars
              │ full refresh — FR-023                  │ (weekend/holiday) → no-op
              │                                        ▼
              └────────────────────────────────── EXTENDED
```

A full refresh always returns the document to ESTABLISHED. There is no automatic
transition back — nothing re-establishes on a schedule (FR-010).

**Failure behavior**

The new series is built entirely in memory and written with a single `replace_one`.
A fetch that fails before that call leaves the prior document untouched (FR-030).

---

## Modified: `stock_news_cache`

Gains a coverage envelope so news can be fetched incrementally. Existing documents
remain readable — an absent `coverage` block is treated as "no baseline" and triggers
one full-window fetch that writes the envelope (FR-021).

```
{
  ticker: "AAPL",
  articles: [ ... ],                 // descending by publishedDate, unique by url
  coverage: {
    newest_published: "2026-08-16",  // delta anchor
    oldest_published: "2026-07-18",
    window_days:      30,            // NEWS_DAYS at time of write
    established_at:   ISODate(...),
    extended_at:      ISODate(...)
  },
  fetched_at: ISODate(...)           // retained for the existing TTL index
}
```

**Index change**: the existing 24-hour TTL on `fetched_at` must be **removed**. A TTL
that deletes the document also deletes the baseline every delta depends on, which
would silently restore full-window fetching. Retention is instead enforced in the merge
step, which drops articles older than `NEWS_DAYS` (FR-017).

> Removing a TTL index is a one-time operational step, not a code change — see
> `quickstart.md`.

**Merge identity**: `url`. A re-fetched article overwrites its stored copy rather than
appending a duplicate (FR-008, research D5).

---

## Modified: `work_queue`

Gains one optional field. Absent means `"delta"`, so every existing enqueue call site
and any in-flight job stays valid with no migration (FR-021).

```
{
  ticker: "AAPL",
  status: "pending",
  mode: "delta" | "full",            // NEW — absent = "delta"
  source: "manual",
  parallel_prefetch: false,
  created_at: ..., updated_at: ...
}
```

**Validation rules**

| Rule | Source |
|---|---|
| `mode` absent or `"delta"` → delta pull | FR-009 |
| `mode: "full"` → every delta shortcut bypassed for this ticker | FR-023, FR-024 |
| A full request arriving while a **pending** job exists upgrades that job to `full` | research D8 |
| A full request arriving while a job is **running** is reported, not silently dropped | research D8 |

---

## New collection: `pull_metrics`

One document per completed pull (US1). Diagnostic data.

```
{
  ticker:       "AAPL",
  job_id:       "...",
  mode:         "delta" | "full",    // FR-028
  started_at:   ISODate(...),
  completed_at: ISODate(...),
  total_ms:     41230,               // wall clock — FR-004
  outcome:      "done" | "failed" | "degraded",
  stages: [
    {
      name:        "price",
      elapsed_ms:  1840,
      requests:    1,
      bytes:       412_889,
      retrieval:   "incremental" | "full" | "stored",   // FR-002
      outcome:     "fetched" | "stored" | "degraded" | "skipped"
    },
    ...
  ]
}
```

**Indexes**

- `{ ticker: 1, started_at: -1 }` — latest pull for a ticker.
- `{ started_at: 1 }` with `expireAfterSeconds: 2_592_000` (30 days) — research D10.

**Validation rules**

| Rule | Source |
|---|---|
| `sum(stages[].elapsed_ms) ≤ total_ms`; the remainder is unattributed time and stays visible | FR-004 |
| A stage that degraded records `outcome: "degraded"`, never `"fetched"` | FR-002 |
| A failure while writing metrics never fails the pull | FR-005 |

---

## Entity mapping to the spec

| Spec entity | Implementation |
|---|---|
| **Pull** | one `pull_metrics` document + its `work_queue` job |
| **Stage** | one entry in `pull_metrics.stages[]` |
| **Coverage record** | the `coverage` sub-document on `price_history` / `stock_news_cache` |
| **Stored dataset** | `price_history.bars`, `stock_news_cache.articles` |

---

## Retired

| What | Why |
|---|---|
| `price_cache` collection (4 docs/ticker) | Replaced by `price_history` (research D3). Drop after cutover — it is pure cache, nothing is lost. |
| 24h TTL index on `stock_news_cache.fetched_at` | Deleting the document destroys the delta baseline (see above). |

---

## Out of scope for this data model

Unchanged by this feature: `financials_cache` (already outcome-tracked and
90-day-cached), `institutional_cache` (read-only, not entitled),
`beneficial_ownership_cache` (7-day TTL, single small payload), `earnings_cache`, and
every market-wide/admin collection.
