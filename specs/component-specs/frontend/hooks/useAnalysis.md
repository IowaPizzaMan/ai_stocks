# frontend/src/hooks/useAnalysis.ts

## Purpose
React Query hooks for fetching analysis data. Used by Feed page, StockDetail page, and Sector view. Handles caching, loading states, and pagination.

## Hooks

### `useFeed(filters)`
Powers the Analysis Feed page. Supports filtering and pagination.

```typescript
import { useQuery, useInfiniteQuery } from '@tanstack/react-query'
import { getFeed } from '@/lib/api'
import { STALE_TIMES } from '@/lib/constants'

interface FeedFilters {
  signal?: string
  sector?: string
  conviction?: string
  from_date?: string
  to_date?: string
}

export function useFeed(filters: FeedFilters = {}) {
  return useInfiniteQuery({
    queryKey: ['feed', filters],
    queryFn: ({ pageParam = 1 }) => getFeed({ ...filters, page: pageParam, page_size: 20 }),
    getNextPageParam: (lastPage) =>
      lastPage.page * lastPage.page_size < lastPage.total ? lastPage.page + 1 : undefined,
    staleTime: STALE_TIMES.feed,
  })
}
```

### `useTickerAnalysis(ticker)`
Fetches the full analysis history for a single ticker. Used in StockDetail.

```typescript
export function useTickerAnalysis(ticker: string) {
  return useQuery({
    queryKey: ['analysis', ticker],
    queryFn: () => getTickerAnalysis(ticker),
    staleTime: STALE_TIMES.analysis,
    enabled: !!ticker,
  })
}
```

### `useStockSignals(ticker)`
Fetches agent-level sub-reports for a ticker. Used in StockDetail tabs.

```typescript
export function useStockSignals(ticker: string) {
  return useQuery({
    queryKey: ['signals', ticker],
    queryFn: () => getStockSignals(ticker),
    staleTime: STALE_TIMES.analysis,
    enabled: !!ticker,
  })
}
```

### `useStockFinancials(ticker)`
```typescript
export function useStockFinancials(ticker: string) {
  return useQuery({
    queryKey: ['financials', ticker],
    queryFn: () => getStockFinancials(ticker),
    staleTime: STALE_TIMES.analysis,
    enabled: !!ticker,
  })
}
```

### `useTickerRecord(ticker)`
Lightweight registry lookup — name, sector, `status`. Used by `StockDetail.md` to show `TickerStatusBadge` and gate the Pull button without pulling full signals/financials just to check status.

```typescript
export function useTickerRecord(ticker: string) {
  return useQuery({
    queryKey: ['ticker-record', ticker],
    queryFn: () => getTickerRecord(ticker),
    staleTime: STALE_TIMES.analysis,
    enabled: !!ticker,
  })
}
```

### `useSectorAnalysis(sector)`
```typescript
export function useSectorAnalysis(sector: string) {
  return useQuery({
    queryKey: ['sector', sector],
    queryFn: () => getSectorAnalysis(sector),
    staleTime: STALE_TIMES.feed,
    enabled: !!sector,
  })
}
```
