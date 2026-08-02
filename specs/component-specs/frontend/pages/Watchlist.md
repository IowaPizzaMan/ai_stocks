# frontend/src/pages/Watchlist.tsx

## Purpose
URL: `/watchlist`. Full-page watchlist view with signal status for each ticker and quick actions. Secondary view — the sidebar already shows the watchlist; this page adds manage/remove capability.

## Layout
```
Watchlist (12 tickers)                  [Pull All ▶]  [Queue Status]
──────────────────────────────────────────────────────
AAPL   Apple Inc.   [Bullish] ●●●   Analyzed 2h ago   [▶ Pull] [✕]
MSFT   Microsoft    [Bullish] ●●●   Analyzed 3h ago   [▶ Pull] [✕]
NVDA   NVIDIA       [Neutral] ●○○   Analyzed 1d ago   [▶ Pull] [✕]
...
+ Add ticker
```

## Implementation

```tsx
export function Watchlist() {
  const { data: watchlist } = useWatchlist()
  const removeFromWatchlist = useRemoveFromWatchlist()
  const enqueue = useEnqueueTicker()
  
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">
          Watchlist <span className="text-slate-500 font-normal text-lg">({watchlist?.count ?? 0})</span>
        </h1>
        <div className="flex items-center gap-3">
          <QueueStatus />
          <PullAllButton />
        </div>
      </div>
      
      <div className="space-y-2">
        {watchlist?.items.map(item => (
          <WatchlistRow key={item.ticker} item={item}
            onPull={() => enqueue.mutate(item.ticker)}
            onRemove={() => removeFromWatchlist.mutate(item.ticker)} />
        ))}
      </div>
      
      <AddTickerForm />
    </div>
  )
}
```

## `AddTickerForm`
- Text input + "Add" button at the bottom
- Validates that ticker is non-empty and uppercase
- Calls `useAddToWatchlist()` on submit
- Shows inline error if ticker already in list

## `WatchlistRow`
- Full-width row: ticker, name, signal badge, conviction meter, "analyzed X ago" timestamp, `TickerStatusBadge`
- Pull button (▶) — enqueues this ticker; shows spinner while running; when `item.status === 'removed_from_market'` it's dimmed with a tooltip, but stays clickable — a manual pull is exactly how the user re-checks and reactivates a ticker the system flagged
- Remove button (✕) — removes from watchlist with confirm (no modal, just a `window.confirm` or inline confirmation state)

## Delisted Rows
If `item.status === 'removed_from_market'`, the row renders dimmed (`opacity-60`) with the badge visible. The row is **not** hidden or auto-removed — the user's watchlist history for that ticker stays intact. Removing it entirely is still a manual action via the ✕ button.

## Dependencies
- `useWatchlist`, `useRemoveFromWatchlist`, `useAddToWatchlist`
- `useEnqueueTicker`
- `PullAllButton`, `QueueStatus`
- `SignalBadge`, `ConvictionMeter`, `TickerStatusBadge`
