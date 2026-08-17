# Data Model: Decouple Macro Analysis From Ticker Research

**Feature**: `specs/020-surface-macro-ui` | **Date**: 2026-08-15

No new collections. One collection changes ownership semantics, one document shape loses a key, and the API/TS layer gains projections of existing shapes.

## Collections

### `macro_analysis_cache` (existing — semantics change)

Was: a cache filled lazily whenever a crew run hit an uncached sector.
Becomes: the **primary store** of sector macro reads, written only by the macro worker.

| Field | Type | Notes |
|---|---|---|
| `sector` | string | Unique index (exists). GICS sector name from `ticker_index`; the worker skips tickers with `sector: null`. |
| `computed_at` | datetime (UTC) | Freshness anchor. Worker refreshes when older than 7 days (`CACHE_DAYS`). |
| `result` | object | The macro read (below). Shape unchanged from today's `macro_analyst` output. |

**`result` shape** (produced by `macro_analyst.SCHEMA` + attached hard numbers — unchanged):

| Field | Type |
|---|---|
| `inflation_impact` | `{trend: "rising"\|"falling"\|"stable", impact_on_sector: string, cpi_latest?: number\|null}` |
| `rate_impact` | `{direction: "hiking"\|"holding"\|"cutting", impact_on_valuation: string, fed_funds_rate?: number\|null}` |
| `growth_backdrop` | `{recession_signal: "none"\|"mild"\|"elevated"\|"strong", commentary: string, yield_curve_spread?: number\|null, curve_inverted?: boolean\|null}` |
| `consumer_backdrop` | string |
| `sector_rotation_signal` | string |
| `overall_macro_signal` | `"bullish"\|"bearish"\|"neutral"` |
| `confidence` | `"high"\|"medium"\|"low"` |

**Lifecycle**: created/replaced by `macro_worker` per sector; never deleted (a sector with no active tickers simply stops refreshing and ages visibly). No TTL.

### `analyses` (existing — document shape narrows going forward)

- New documents: `sub_reports` contains exactly `technical, fundamental, insider, institutional, sentiment, recommendation` — **no `macro` key**.
- Historical documents: may still contain `sub_reports.macro`; retained as-is, never read by the UI (research D6).
- Top-level `sector` field: unchanged (still stamped from `ticker_index` for feed filtering).

### Unchanged collections

`macro_cache` (FRED series, 24h TTL — still the data source the worker's context is built from), `breadth_cache`, `breadth_divergences`, `breadth_meta`, `market_flow_events`, `ticker_index` (now also read by the macro worker to enumerate `distinct("sector")` over active tickers).

## Cross-service constants (Constitution Principle VI)

| Constant | agent-runner/tools/db.py | backend/db.py |
|---|---|---|
| `MACRO_ANALYSIS_CACHE = "macro_analysis_cache"` | exists | **must be added** |

## API projection (`GET /market/macro`)

```jsonc
{
  "sectors": [            // one entry per macro_analysis_cache doc, newest computed_at first
    {
      "sector": "Technology",
      "computed_at": "2026-08-14T21:03:11Z",
      "inflation_impact": { ... },   // result.* flattened into the entry
      "rate_impact": { ... },
      "growth_backdrop": { ... },
      "consumer_backdrop": "...",
      "sector_rotation_signal": "...",
      "overall_macro_signal": "neutral",
      "confidence": "medium"
    }
  ],
  "as_of": "2026-08-14T21:03:11Z"   // newest computed_at, null when sectors is empty
}
```

## Frontend types (`frontend/src/api/types.ts`)

- `MacroReport` (exists): reused for the read fields.
- `SectorMacroRead` (new): `MacroReport & { sector: string; computed_at: string }`.
- `MacroReads` (new): `{ sectors: SectorMacroRead[]; as_of: string | null }`.
- `Analysis.sub_reports.macro?` (exists): kept optional for historical documents; no longer rendered anywhere.

## State transitions

```text
sector appears in ticker_index (first analyzed ticker in that sector)
        │  next hourly sweep: no cache doc → refresh
        ▼
macro_analysis_cache doc {sector, computed_at, result}
        │  computed_at > 7 days old → next sweep refreshes (replace_one upsert)
        │  LLM failure during refresh → doc untouched (stale, still served), retry next sweep
        ▼
sector has no active tickers → doc no longer refreshed; served with visibly old computed_at
```
