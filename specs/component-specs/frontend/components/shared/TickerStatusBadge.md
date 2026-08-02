# frontend/src/components/shared/TickerStatusBadge.tsx

## Purpose
Small pill shown next to a ticker when its registry status (`ticker_index` / `models/ticker.md`) isn't the normal `active` state — `disabled` (manually turned off from the Admin page) or `removed_from_market` (system-detected delisting). Renders nothing in the common case, so it can be dropped into any ticker header without a conditional at every call site.

## Props
```typescript
interface TickerStatusBadgeProps {
  status: 'active' | 'disabled' | 'removed_from_market'
  size?: 'sm' | 'md'   // default 'sm'
}
```

## Implementation
```tsx
import { TICKER_STATUS_CONFIG } from '@/lib/constants'

export function TickerStatusBadge({ status, size = 'sm' }: TickerStatusBadgeProps) {
  const config = TICKER_STATUS_CONFIG[status]
  if (!config.label) return null

  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-3 py-1'
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  )
}
```

## Used By
- `Sidebar.md` (`WatchlistRow`) — next to the ticker, dims the row and disables the enqueue button
- `pages/Watchlist.md` (`WatchlistRow`) — same treatment, full-page view
- `pages/StockDetail.md` — in the hero header, next to `SignalBadge`; also disables the "Pull" button
- `components/feed/AnalysisCard.md` — optional, only relevant if a past analysis exists for a now-delisted ticker
- `pages/Admin.md` — every row in the ticker table shows this badge; `disabled` is the common case there since that's the whole point of the page

## Key Details
- Deliberately muted styling (slate, not red) — this isn't an error state, just informational. The user's history for the ticker is still fully intact and viewable.
- Wherever this badge appears, the corresponding "Pull"/enqueue button stays clickable (not disabled) — `POST /queue/{ticker}` (`routers/queue.md`) explicitly treats a manual pull on a `removed_from_market` ticker as "try again," resetting it back to `active` before enqueuing. The button just gets a dimmed style and a tooltip explaining what clicking it will do, so the user isn't blocked from double-checking a ticker the system may have flagged incorrectly.
