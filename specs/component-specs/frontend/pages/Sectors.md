# frontend/src/pages/Sectors.tsx

## Purpose
URL: `/sectors` (overview) and `/sectors/:sector` (detail). Shows a heatmap-style grid of all tickers in a sector colored by signal, plus a sorted list with key stats.

## Sector Overview (`/sectors`)

### All-Sectors Summary Chart
Above the grid of sector cards: one chart giving a market-wide read across every sector at a glance, before drilling into any single one. Stacked horizontal bar, one row per sector — bullish/neutral/bearish counts as proportional segments (green/slate/red, same palette as the heatmap tiles below), sorted by bullish % descending so the strongest sectors surface at the top. Sourced from the same `GET /sectors` aggregate (`backend/routers/sectors.md`) that already backs the cards, so this is a different view of data already fetched, not a new endpoint. Doubles as the "strategy analysis per sector" summary — hovering/clicking a row shows the same bullish/bearish/neutral breakdown as its card below, just comparable across all sectors in one place instead of one grid tile at a time.

### Sector Cards
Grid of sector cards — one per GICS sector. Each card shows:
- Sector name
- Bullish / Neutral / Bearish count (small bar showing proportion)
- Most bullish ticker in that sector

Click → navigates to `/sectors/:sector` (the heatmap + sorted-list detail view below, richer than a filtered feed since it's purpose-built for scanning one sector). A secondary "View in Feed →" link/icon on each card instead routes to `/?sector={sector}`, reusing the Analysis Feed's existing sector filter (`FilterBar.md`) for anyone who wants the feed's chronological/summary-card layout rather than the heatmap.

## Sector Detail (`/sectors/:sector`)
Header includes the same "View in Feed →" link as the overview cards (`/?sector={sector}`), so users can cross into the chronological feed view from the detail page too, not just the overview.

### Heatmap Grid
Grid of ticker "tiles" — each tile:
- Background: green (bullish), red (bearish), slate (neutral) — with opacity proportional to conviction
- Label: ticker symbol + conviction dots
- Size: uniform (future enhancement: size by market cap)
- Click: navigate to `/stock/:ticker`

```tsx
function SignalTile({ item }: { item: AnalysisFeedItem }) {
  const bgClass = {
    bullish: 'bg-green-500/20 border-green-500/30 hover:bg-green-500/30',
    bearish: 'bg-red-500/20 border-red-500/30 hover:bg-red-500/30',
    neutral: 'bg-slate-800 border-slate-700 hover:bg-slate-700',
  }[item.signal]
  
  return (
    <div className={`${bgClass} border rounded-lg p-3 cursor-pointer transition-colors`}
         onClick={() => navigate(`/stock/${item.ticker}`)}>
      <div className="font-bold text-white text-sm">{item.ticker}</div>
      <ConvictionMeter conviction={item.conviction} />
    </div>
  )
}
```

### Sorted List (below heatmap)
Table of all sector tickers with: ticker, signal badge, conviction, last analyzed timestamp, one-line summary. Default sort: signal strength (bullish high → bearish low).

Sort controls: by signal, by conviction, by last analyzed.

## Dependencies
- `useSectorAnalysis`
- `SignalBadge`, `ConvictionMeter`
- `react-router-dom`

## Amendments

- **specs/028-dashboard-tweaks-batch US5**: the overview (`/sectors`) gained a
  `SectorEtfChart` — a percentage-change comparison line chart for 11 fixed sector ETF
  tickers (XLC/XLY/XLP/XLE/XLF/XLI/XLV/XLB/XLRE/XLK/XLU), independent of the
  analysis-based rollup above (its own data source, own loading/empty/error states,
  own Refresh control). Renders once above all four rollup states (loading/error/empty/
  populated). Window selector (1M/3M/6M/1Y) stored in `?window=`. Backed by
  `GET/POST /sectors/etf-series`, fed by the agent-runner's `sector_etf_pull` job, which
  reuses `price_store` unchanged. See `contracts/sector-etf-series-api.md` in that spec.
