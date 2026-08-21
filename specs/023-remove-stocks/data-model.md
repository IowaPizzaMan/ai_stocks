# Data Model: Remove Stocks from Watchlist and Stocks Page

This feature introduces no new collections, fields, or schema changes. It reuses three
existing entities exactly as they are defined today, and its only data-shape work is
precisely specifying the *deletion scope* across existing collections (Key Entity #3 below).

## Entities (from spec's Key Entities section)

### Watchlist entry

Existing collection: `watchlist` (`backend/db.py::WATCHLIST`).

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | Uppercased symbol, unique per watchlist |
| `name` | string \| null | Display name, optional |
| `sector` | string \| null | Optional |
| `status` | string | `"active"` or `"removed_from_market"` |
| `added_at` | datetime | UTC |

**Removal effect (User Story 1)**: `delete_one({"ticker": T})` on this collection only. No
other collection is touched. This is the existing `DELETE /watchlist/{ticker}` behaviour —
unchanged by this feature.

### Tracked ticker

Existing collection: `ticker_index` (`backend/db.py::TICKER_INDEX`).

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | Unique |
| `name` / `sector` | string \| null | Optional |
| `status` | string | `"active"` \| `"disabled"` \| `"removed_from_market"` |
| `sources` | string[] | e.g. `"manual"`, `"watchlist"`, `"earnings_calendar"` |
| `first_seen_at` / `last_seen_at` | datetime | UTC |

**Deletion effect (User Story 2)**: `delete_one({"ticker": T})` on this collection, plus the
cascade below. This record's removal is what makes the ticker disappear from search,
the tile board, and `/tickers` listings — those all query `ticker_index` as the source of
truth for "does this ticker exist."

### Per-ticker stored data (deletion scope by collection)

The spec's FR-009 requires deleting "all data ... scoped to that ticker." The table below is
the authoritative inventory, built by tracing every read/write site of every collection
constant declared in `backend/db.py` / `agent-runner/tools/db.py` (see
[research.md](research.md) item 1 for method). **Bold** rows are already purged by the
existing `delete_ticker` handler; *italic* rows are the gap this feature closes.

| Collection | Ticker-scoped? | Delete filter | Currently purged? |
|---|---|---|---|
| **`ticker_index`** | yes (is the record) | `{"ticker": T}` | yes |
| **`analyses`** | yes | `{"ticker": T}` | yes |
| **`financials_cache`** | yes | `{"ticker": T}` | yes |
| **`watchlist`** | yes | `{"ticker": T}` | yes |
| **`work_queue`** | yes | `{"ticker": T, "status": {"$in": ["pending", "running"]}}` | yes (in-flight/queued jobs only — see note below) |
| **`institutional_flow`** | yes | `{"ticker": T}` | yes |
| *`transcripts_cache`* | yes | `{"ticker": T}` | **no — add** |
| *`earnings_cache`* | yes, mixed | `{"type": "history", "ticker": T}` **only** — this collection also holds market-wide `type: "calendar"` and `type: "universe"` docs with no `ticker` field, which MUST NOT be touched | **no — add** |
| *`stock_news_cache`* | yes | `{"ticker": T}` | **no — add** |
| *`institutional_cache`* | yes (legacy, read-only since specs/017) | `{"ticker": T}` | **no — add** |
| *`beneficial_ownership_cache`* | yes | `{"ticker": T}` | **no — add** |

**Not ticker-scoped — explicitly out of deletion scope** (per spec Assumptions: "Market-wide
and macro data ... is out of scope for deletion"):

`macro_cache`, `macro_analysis_cache` (sector-keyed, not ticker-keyed),
`superinvestor_moves_cache` (single whole-market blob), `breadth_cache`/`breadth_universe`/
`breadth_divergences`/`breadth_meta`, `market_flow_events` (events reference a plural
`tickers` array across the market, not owned by one ticker), `earnings_scans` (a scan-run
document, not per-ticker data), `institutional_flow_meta` (sweep-cursor state, keyed by
`key`, not `ticker`), `dataroma_meta`, `fmp_usage`, `fmp_entitlements`, `dataset_meta`,
`sector_performance`, `market_movers`, `economic_calendar_events`, `treasury_rates`,
`market_risk_premium`, `economic_indicators`, `market_news`.

Also declared as constants but never written anywhere in the current codebase —
`congress_trades`, `fund_holdings`, `stock_news`, `company_info` — so a defensive
`delete_many({"ticker": T})` against them is a harmless no-op today; they are listed here for
completeness, not because they currently hold data.

**Work-queue note**: only `pending`/`running` jobs are cancelled (matches the existing
handler and FR-009's "any pending or running queued work"). A `completed`/`failed` job
history row for a deleted ticker is left alone, consistent with the existing behaviour and
with treating deletion as a forward-looking purge rather than an audit-log rewrite — no
requirement in the spec calls for erasing completed job history, and Constitution Principle V
favors not adding new deletion semantics beyond what's asked.

## State transitions

No new state machine. `ticker_index.status` already has three values
(`active`/`disabled`/`removed_from_market`); this feature does not add a fourth. Deletion is
a hard `delete_one`, not a status transition — a deleted ticker has no `ticker_index` row at
all afterward, and per FR-014/resolved clarification, a later automated discovery pass is
free to re-insert it as a brand-new row with `first_seen_at` reset.

## Relationships affected by deletion

```text
ticker_index (1) ──┬── watchlist (0..1)            [pin — cleared by both User Story 1 and 2]
                    ├── analyses (0..1)              [cleared by User Story 2 only]
                    ├── financials_cache (0..1)       "
                    ├── transcripts_cache (0..*)      "  (one doc per year+quarter)
                    ├── earnings_cache (0..1, type=history) "
                    ├── stock_news_cache (0..1)       "
                    ├── institutional_cache (0..1)    "
                    ├── beneficial_ownership_cache (0..1) "
                    ├── institutional_flow (0..*)     "
                    └── work_queue (0..*, pending/running only) "
```

User Story 1 (watchlist unpin) removes only the `watchlist` edge. User Story 2 (Stocks-page
deletion) removes the `ticker_index` node itself and every edge shown above.
