# Data Model: Feed Checkerboard Grid

**Feature**: 019-feed-checkerboard-grid | **Date**: 2026-08-15

No new persisted data. All entities below are existing API/frontend types (in `frontend/src/api/types.ts`) plus one new derived view-model. MongoDB collections, backend schemas, and the `/analysis/feed` contract are unchanged.

## Existing entities (consumed as-is)

### AnalysisFeedItem (existing — source of every tile)

| Field | Type | Used by grid? | Notes |
|-------|------|---------------|-------|
| `ticker` | `string` | Tile face | Only text on the tile; 1–6+ chars, may contain `.` (BRK.B) |
| `signal` | `Signal` = `"bullish" \| "bearish" \| "neutral"` | Tile fill color; grouping key | Unrecognized/missing → fallback style + `unknown` group |
| `conviction` | `Conviction` = `"high" \| "medium" \| "low"` | Dot count | `high`→3, `medium`→2, `low`→1 dots; missing/unknown → 0 dots |
| `timestamp` | `string` (ISO) | Preview (recency); within-group sort | Newest-first within each signal group |
| `summary` | `string` | Preview only | Line-clamped snippet; never on tile face |
| `sector` | `string?` | — | Not displayed on tile; still filterable via FilterBar |
| `flags`, `key_trends`, institutional/insider fields | various | — | Relocated to stock detail page (FR-012) |

**Identity/uniqueness**: one feed item per ticker (existing backend dedupe, feature 016). Tile React key: `ticker`.

### MarketFlowEvent (existing — unchanged)

Ticker-less market-wide event; pinned above the grid when no filters active, ≤14 days old. No model changes.

### FeedResponse (existing — unchanged contract)

`{ items: AnalysisFeedItem[], total: number, page: number, page_size: number }`. Only the *requested* `page_size` value changes (20 → 60); the shape does not.

## New derived view-model (frontend only, not persisted)

### GroupedFeed (output of `groupBySignal(items)`)

```
GroupedFeed = Array<{
  signal: "bullish" | "neutral" | "bearish" | "unknown"   // fixed render order
  items:  AnalysisFeedItem[]                               // newest-first (timestamp desc)
}>
```

**Rules** (all enforced by the pure helper, exhaustively tested):

1. Group render order is fixed: `bullish`, `neutral`, `bearish`, then `unknown` (only present if non-empty).
2. Within a group, items sort by `timestamp` descending.
3. Empty groups are omitted (no empty divider rows).
4. Input is the flattened concatenation of all loaded pages; the helper is re-applied on every page merge, which is what makes later-loaded items appear inside earlier groups (FR-014).
5. The helper is pure and side-effect free: same input → same output.

### Tile display mapping (component-level constants)

| Input | Visual |
|-------|--------|
| `signal: "bullish"` | emerald translucent fill + emerald border/text |
| `signal: "bearish"` | red translucent fill + red border/text |
| `signal: "neutral"` | zinc translucent fill + zinc border/text |
| unknown signal | dashed zinc border, no fill (conspicuous fallback) |
| `conviction: "high" / "medium" / "low"` | 3 / 2 / 1 filled dots (neutral color, `aria-hidden`) |
| unknown/missing conviction | 0 filled dots |

**Accessible name** (per tile): `"{ticker} — {signal}, {conviction} conviction ({n} of 3), analyzed {relative time}"`, with graceful omissions when fields are missing.

## State transitions

None — the grid is a read-only projection. The only mutation reachable from the Feed is the existing add-to-watchlist mutation (`useAddToWatchlist`), moved from the card face into the tile preview; its contract is unchanged.
