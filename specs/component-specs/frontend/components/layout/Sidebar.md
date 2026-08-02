# frontend/src/components/layout/Sidebar.tsx

## Purpose
Left sidebar with the user's watchlist. Visible on all pages. Each watchlist item shows ticker, signal badge, and a quick-enqueue button.

## Layout (fixed left, below Navbar)
```
WATCHLIST                    [+ Add]
─────────────────────────────
AAPL   [Bullish] ●●●  [▶]
MSFT   [Neutral] ●●○  [▶]
NVDA   [Bullish] ●●●  [▶]
...
```

## Props
None — reads from `useWatchlist()` and `useEnqueueTicker()`.

## Implementation

```tsx
export function Sidebar() {
  const { data: watchlist, isLoading } = useWatchlist()
  const enqueue = useEnqueueTicker()
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <aside className="w-56 fixed left-0 top-14 bottom-0 bg-slate-950 border-r border-slate-800 overflow-y-auto">
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Watchlist</span>
          <AddTickerButton />
        </div>
        {watchlist?.items.map(item => (
          <WatchlistRow
            key={item.ticker}
            item={item}
            isActive={location.pathname === `/stock/${item.ticker}`}
            onNavigate={() => navigate(`/stock/${item.ticker}`)}
            onEnqueue={() => enqueue.mutate(item.ticker)}
          />
        ))}
      </div>
    </aside>
  )
}
```

### `WatchlistRow` (inline sub-component)
Shows: ticker (bold), signal badge (sm), conviction dots, enqueue button (▶ icon, shows spinner while enqueuing), `TickerStatusBadge` (renders nothing unless the ticker is `removed_from_market`). When removed, the row is dimmed (`opacity-60`) and the enqueue button gets a tooltip explaining the ticker looks delisted — clicking it still works and re-checks/reactivates the ticker (see `TickerStatusBadge.md`).

### `AddTickerButton`
Small `+` icon button — opens an inline input for typing a ticker symbol, calls `useAddToWatchlist()` on submit.

## Styling
- `w-56` fixed sidebar
- Active item: `bg-slate-800/50` highlight
- Enqueue button: `opacity-0 group-hover:opacity-100` (only visible on hover)
- Scrollable with custom scrollbar (`scrollbar-thin scrollbar-thumb-slate-700`)
