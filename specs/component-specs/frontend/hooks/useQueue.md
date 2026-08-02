# frontend/src/hooks/useQueue.ts

## Purpose
React Query hooks for the work queue. Polls frequently to show live queue status. Provides mutation hooks for the Pull All and Pull [Ticker] buttons.

## Hooks

### `useQueue()`
Polls the queue every 10 seconds while the page is visible.

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getQueue, enqueueAll, enqueueTicker } from '@/lib/api'

export function useQueue() {
  return useQuery({
    queryKey: ['queue'],
    queryFn: getQueue,
    staleTime: 10_000,
    refetchInterval: 10_000,       // poll every 10s
    refetchIntervalInBackground: false,  // stop polling when tab is hidden
  })
}
```

### `useEnqueueAll()`
Mutation for the Pull All (Run All) button. Calls `POST /queue/all`, which sweeps every `active` ticker in the system-wide `ticker_index` registry — not just the watchlist (see `routers/queue.md`). On success, invalidates the queue query so the UI updates immediately.

```typescript
export function useEnqueueAll() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: enqueueAll,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['queue'] })
  })
}
```

### `useEnqueueTicker()`
Mutation for per-ticker Pull button.

```typescript
export function useEnqueueTicker() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ticker: string) => enqueueTicker(ticker),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['queue'] })
  })
}
```
