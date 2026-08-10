# frontend/src/components/feed/AnalysisCard.tsx

## Purpose
Card component displaying one analysis result in the feed. Clicking the card navigates to `/stock/:ticker`. This is the primary unit of the home feed — needs to be visually compact but information-dense.

## Props
```typescript
interface AnalysisCardProps {
  analysis: AnalysisFeedItem
}
```

## Layout
```
┌─────────────────────────────────────────────────────┐
│ AAPL  [Bullish]  Technology          2 hours ago     │
│                                                      │
│ Apple presents a high-conviction long setup driven   │
│ by cluster insider buying, 4/5 accumulation score,   │
│ and NYMO oversold bounce conditions...               │
│                                                      │
│ [↑ Institutions buying]  [10 buys, 2 sells]          │
│ ●●●  High conviction   ·  [+ Watchlist]             │
└─────────────────────────────────────────────────────┘
```

### Flag Row (optional, above the footer)
When `analysis.recent_institutional_activity` and/or `analysis.recent_insider_summary` (see `backend/models/analysis.md`) are present, render small pill badges between the summary and the footer — same visual weight as `SignalBadge` but muted (`text-slate-400 border-slate-700`), not competing with the primary signal badge in the header:
- `recent_institutional_activity` → "↑ Institutions buying" (emerald tint) / "↓ Institutions selling" (red tint) / "Institutions mixed" (slate)
- `recent_insider_summary` → rendered as-is (e.g. "10 buys, 2 sells")

Both are `null` until the backing scan/score exists (see `FilterBar.md` "Strategy Filters (Phase 2)") — the row simply doesn't render when both are absent, so today's cards are unaffected.

## Implementation

```tsx
import { useNavigate } from 'react-router-dom'
import { SignalBadge } from '@/components/shared/SignalBadge'
import { ConvictionMeter } from '@/components/shared/ConvictionMeter'
import { formatRelative } from 'date-fns'
import { useAddToWatchlist } from '@/hooks/useWatchlist'

export function AnalysisCard({ analysis }: AnalysisCardProps) {
  const navigate = useNavigate()
  const addToWatchlist = useAddToWatchlist()

  return (
    <article
      className="bg-slate-900 border border-slate-800 rounded-xl p-5 cursor-pointer hover:border-slate-700 hover:bg-slate-800/50 transition-all"
      onClick={() => navigate(`/stock/${analysis.ticker}`)}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-white font-bold text-lg">{analysis.ticker}</span>
          <SignalBadge signal={analysis.signal} />
          {analysis.sector && (
            <span className="text-xs text-slate-500">{analysis.sector}</span>
          )}
        </div>
        <span className="text-xs text-slate-500">
          {formatRelative(new Date(analysis.timestamp), new Date())}
        </span>
      </div>

      {/* Summary — truncate to 3 lines */}
      <p className="text-slate-300 text-sm leading-relaxed line-clamp-3 mb-4">
        {analysis.summary}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <ConvictionMeter conviction={analysis.conviction} label />
        <button
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          onClick={e => { e.stopPropagation(); addToWatchlist.mutate(analysis.ticker) }}
        >
          + Watchlist
        </button>
      </div>
    </article>
  )
}
```

## Key Details
- `onClick` on the whole card navigates to stock detail
- `e.stopPropagation()` on the watchlist button prevents the card click from firing
- Summary is clamped to 3 lines (`line-clamp-3`) — prevents layout inconsistency
- `hover:border-slate-700` gives a subtle lift effect on hover
- Uses `date-fns` for relative time formatting

## Dependencies
- `react-router-dom`
- `date-fns`
- `SignalBadge`, `ConvictionMeter`
- `useAddToWatchlist`
