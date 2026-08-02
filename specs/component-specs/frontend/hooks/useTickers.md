# frontend/src/hooks/useTickers.ts

## Purpose
React Query hooks over the full ticker registry (`ticker_index`) — used by the Admin page (`pages/Admin.md`) to list every ticker the system knows about and let the user disable, delete, or mass-add tickers. Distinct from `useWatchlist.md`, which is scoped to the user's pinned subset.

## Hooks

### `useTickers(status?)`
```typescript
export function useTickers(status?: TickerStatus) {
  return useQuery({
    queryKey: ['tickers', status ?? 'all'],
    queryFn: () => listTickers(status),
    staleTime: STALE_TIMES.tickers,
  })
}
```

### `useUpdateTickerStatus()`
Toggles a ticker between `active` and `disabled` (the Admin page's on/off switch).
```typescript
export function useUpdateTickerStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ ticker, status }: { ticker: string, status: 'active' | 'disabled' }) =>
      updateTickerStatus(ticker, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tickers'] })
  })
}
```

### `useDeleteTicker()`
Permanently removes a ticker and its cached data. Also invalidates `watchlist` since delete can silently drop a watchlist entry too (see `DELETE /tickers/{ticker}` in `routers/stocks.md`).
```typescript
export function useDeleteTicker() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ticker: string) => deleteTicker(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickers'] })
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    }
  })
}
```

### `useBulkAddTickers()`
Backs the mass-add textarea. Returns `{ added, already_existed, invalid }` so the page can show a summary toast.
```typescript
export function useBulkAddTickers() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (tickers: string) => bulkAddTickers(tickers),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tickers'] })
  })
}
```

## Dependencies
- `useEnqueueTicker` (from `useQueue.md`) — reused as-is for the Admin page's per-row "Pull" button; no new enqueue logic needed.
- `listTickers`, `updateTickerStatus`, `deleteTicker`, `bulkAddTickers` (`lib/api.md`)
