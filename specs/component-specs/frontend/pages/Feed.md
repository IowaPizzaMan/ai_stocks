# frontend/src/pages/Feed.tsx

## Purpose
Default home view. Infinite-scroll stream of completed AI analyses, newest first. Includes filter bar, skeleton loading, and a live indicator when new analyses arrive.

## Layout
```
[FilterBar — sticky]
──────────────────────────────────────────────────
[AnalysisCard]
[AnalysisCard]
[AnalysisCard]
...
[Load More] (intersection observer triggers)
```

## Implementation

```tsx
import { useFeed } from '@/hooks/useAnalysis'
import { useSearchParams } from 'react-router-dom'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'

export function Feed() {
  const [searchParams] = useSearchParams()
  const filters = {
    signal: searchParams.get('signal') || undefined,
    sector: searchParams.get('sector') || undefined,
    conviction: searchParams.get('conviction') || undefined,
  }
  
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useFeed(filters)
  const loadMoreRef = useRef<HTMLDivElement>(null)
  
  // Infinite scroll via IntersectionObserver
  useIntersectionObserver(loadMoreRef, () => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage()
  })
  
  const allItems = data?.pages.flatMap(p => p.items) ?? []
  
  return (
    <div className="space-y-4">
      <FilterBar />
      
      {isLoading
        ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
        : allItems.map(item => <AnalysisCard key={`${item.ticker}-${item.timestamp}`} analysis={item} />)
      }
      
      {/* Sentinel div — triggers next page load */}
      <div ref={loadMoreRef} className="h-8">
        {isFetchingNextPage && <Spinner />}
      </div>
    </div>
  )
}
```

## Key Details
- `useInfiniteQuery` pages load automatically as the user scrolls to the sentinel div
- Skeleton cards shown only on initial load (not on "load more")
- Filter changes reset to page 1 automatically (React Query key includes filters)
- Page title: `document.title = 'StockAI — Feed'`

## Dependencies
- `useFeed`, `FilterBar`, `AnalysisCard`, `SkeletonCard`
- `react-router-dom` (useSearchParams)
