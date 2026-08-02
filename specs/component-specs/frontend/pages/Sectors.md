# frontend/src/pages/Sectors.tsx

## Purpose
URL: `/sectors` (overview) and `/sectors/:sector` (detail). Shows a heatmap-style grid of all tickers in a sector colored by signal, plus a sorted list with key stats.

## Sector Overview (`/sectors`)
Grid of sector cards — one per GICS sector. Each card shows:
- Sector name
- Bullish / Neutral / Bearish count (small bar showing proportion)
- Most bullish ticker in that sector

Click → navigates to `/sectors/:sector`

## Sector Detail (`/sectors/:sector`)

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
