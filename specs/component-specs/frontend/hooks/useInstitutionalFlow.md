# frontend/src/hooks/useInstitutionalFlow.ts

## Purpose
React Query hooks for the market-wide Institutional Flow feed. Sibling to `useAnalysis.md`'s `useFeed`, but backed by `/institutional/flow` instead of `/analysis/feed`.

## Hooks

### `useInstitutionalFlow(filters)`
Powers the Institutional Flow page. Infinite-scroll pagination, same shape as `useFeed`.

```typescript
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getInstitutionalFlow, triggerInstitutionalScan } from '@/lib/api'
import { STALE_TIMES } from '@/lib/constants'

interface InstitutionalFlowFilters {
  action?: string
  fund?: string
  ticker?: string
  min_notability?: number
}

export function useInstitutionalFlow(filters: InstitutionalFlowFilters = {}) {
  return useInfiniteQuery({
    queryKey: ['institutional-flow', filters],
    queryFn: ({ pageParam = 1 }) => getInstitutionalFlow({ ...filters, page: pageParam, page_size: 20 }),
    getNextPageParam: (lastPage) =>
      lastPage.page * lastPage.page_size < lastPage.total ? lastPage.page + 1 : undefined,
    staleTime: STALE_TIMES.institutionalFlow,
  })
}
```

### `useTickerFlow(ticker)`
Fetches flow history for a single ticker — used by the "view full history" link from the Stock Detail Institutional tab.

```typescript
export function useTickerFlow(ticker: string) {
  return useQuery({
    queryKey: ['institutional-flow', ticker],
    queryFn: () => getTickerFlow(ticker),
    staleTime: STALE_TIMES.institutionalFlow,
    enabled: !!ticker,
  })
}
```

### `useTriggerInstitutionalScan()`
Backs the "Scan Now" button in `InstitutionalFlowFilterBar`.

```typescript
export function useTriggerInstitutionalScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: triggerInstitutionalScan,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['institutional-flow'] }),
  })
}
```

## Dependencies
- `@tanstack/react-query`
- `getInstitutionalFlow`, `getTickerFlow`, `triggerInstitutionalScan` from `lib/api.ts`
