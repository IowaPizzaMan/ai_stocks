# frontend/src/hooks/useWatchlist.ts

## Purpose
React Query hooks for the user's watchlist. Used by Sidebar and Watchlist page.

## Hooks

### `useWatchlist()`
```typescript
export function useWatchlist() {
  return useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    staleTime: STALE_TIMES.watchlist,
  })
}
```

### `useAddToWatchlist()`
```typescript
export function useAddToWatchlist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ticker: string) => addToWatchlist(ticker),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] })
  })
}
```

### `useRemoveFromWatchlist()`
```typescript
export function useRemoveFromWatchlist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ticker: string) => removeFromWatchlist(ticker),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] })
  })
}
```
