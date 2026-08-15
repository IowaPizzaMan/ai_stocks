# UI Contract: Feed Checkerboard Grid

**Feature**: 019-feed-checkerboard-grid | **Date**: 2026-08-15

This feature exposes no new network API. The backend contract it consumes is **unchanged**:

## Consumed API contract (existing, unchanged)

`GET /analysis/feed?page={n}&page_size={m}&ticker=&signal=&sector=&conviction=`
→ `FeedResponse { items: AnalysisFeedItem[], total, page, page_size }`, items deduped one-per-ticker, newest-first. The grid merely requests `page_size=60` instead of 20 — within the endpoint's existing parameter contract. Any backend change is out of scope for this feature.

## Component contracts (frontend)

### `<AnalysisTile analysis={AnalysisFeedItem} />`

| Aspect | Contract |
|--------|----------|
| Face content | Ticker text + 0–3 conviction dots. Nothing else. |
| Fill | Signal-mapped classes (emerald/red/zinc translucent per app convention); dashed-border fallback for unrecognized signal. |
| Size | Uniform across all tiles; min width fits 5-char tickers untruncated; 6+ chars step down font size, never ellipsize into ambiguity. |
| Interaction | Click/tap or Enter (focused) → navigate to `/stock/{ticker}`. Hover or keyboard focus → show `TilePreview`. Preview must not intercept the tile's click-to-navigate. |
| Accessibility | Focusable; `aria-label` = `"{ticker} — {signal}, {conviction} conviction ({n} of 3), analyzed {relative}"`. Dots `aria-hidden`. |

### `<TilePreview analysis={AnalysisFeedItem} />`

| Aspect | Contract |
|--------|----------|
| Content | `SignalBadge` (signal as text), `ConvictionMeter` with label, relative time (+ "data as of" date when available), summary snippet (line-clamped), add-to-watchlist button. |
| Behavior | Appears on tile hover/focus, dismisses on leave/blur; keyboard users can reach the watchlist button; watchlist click calls the existing `useAddToWatchlist` mutation and does **not** navigate (`stopPropagation`). Flips placement near viewport edges so it is never clipped. |
| Touch | Not required on touch devices; tap navigates instead (watchlist available on detail page). |

### `<SkeletonTile />`

Tile-shaped shimmer placeholder; Feed shows a board of them (~30) during initial load only. `SkeletonCard` (shared) is not modified.

### `groupBySignal(items: AnalysisFeedItem[]): GroupedFeed`

Pure function; contract defined in [data-model.md](../data-model.md) (fixed group order bullish → neutral → bearish → unknown; newest-first within group; empty groups omitted; deterministic).

### `Feed` page composition contract

1. Sticky `FilterBar` (unchanged) → pinned `MarketFlowCard`s (unchanged logic: only when unfiltered, ≤14 days) → signal-grouped tile grid → infinite-scroll sentinel.
2. Grid container: responsive CSS Grid (`auto-fill`, fixed min tile width), page width widened (`max-w-7xl`) to serve density; body never scrolls horizontally.
3. Each signal group renders under a thin labeled divider ("Bullish", "Neutral", "Bearish"); groups flow as one continuous board.
4. States preserved: skeleton board while loading; existing error message on failure; existing "No analyses yet" empty state; filters narrow the board via URL search params exactly as today.
5. No polling; data refreshes on navigation/filter change/scroll only.
