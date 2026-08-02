# frontend/src/pages/InstitutionalFlow.tsx

## Purpose
Standalone page — a live feed of new institutional and superinvestor activity across the whole tracked universe, not scoped to one stock. Same infinite-scroll shell as `Feed.md`, but each item is an `InstitutionalFlowEvent` (a single 13F/Dataroma move) instead of a full AI stock analysis. Route: `/institutional-flow`.

## Layout
```
[InstitutionalFlowFilterBar — sticky]
──────────────────────────────────────────────────
[InstitutionalFlowCard]
[InstitutionalFlowCard]
[InstitutionalFlowCard]
...
[Load More] (intersection observer triggers)
```

## Implementation

```tsx
import { useInstitutionalFlow } from '@/hooks/useInstitutionalFlow'
import { useSearchParams } from 'react-router-dom'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'
import { InstitutionalFlowFilterBar } from '@/components/institutional/InstitutionalFlowFilterBar'
import { InstitutionalFlowCard } from '@/components/institutional/InstitutionalFlowCard'
import { SkeletonCard } from '@/components/shared/SkeletonCard'

export function InstitutionalFlow() {
  const [searchParams] = useSearchParams()
  const filters = {
    action: searchParams.get('action') || undefined,
    fund: searchParams.get('fund') || undefined,
    ticker: searchParams.get('ticker') || undefined,
    min_notability: searchParams.get('min_notability') || undefined,
  }

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useInstitutionalFlow(filters)
  const loadMoreRef = useRef<HTMLDivElement>(null)

  useIntersectionObserver(loadMoreRef, () => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage()
  })

  const allItems = data?.pages.flatMap(p => p.items) ?? []

  return (
    <div className="space-y-4">
      <InstitutionalFlowFilterBar />

      {isLoading
        ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
        : allItems.map(item => (
            <InstitutionalFlowCard key={`${item.ticker}-${item.fund}-${item.filed_at}`} event={item} />
          ))
      }

      <div ref={loadMoreRef} className="h-8">
        {isFetchingNextPage && <Spinner />}
      </div>
    </div>
  )
}
```

## Key Details
- Same infinite-scroll shell as the Analysis Feed (`Feed.md`) — `useInfiniteQuery`, sentinel div, skeletons only on initial load
- Filter state lives in URL params, same pattern as `FilterBar.md`
- Data does not poll (consistent with the rest of the app's "manual pull" model) — a "Scan Now" button in `InstitutionalFlowFilterBar` calls `POST /institutional/scan`, then the user refreshes
- Clicking a card's ticker navigates to `/stock/:ticker`; clicking the rest of the card can expand inline detail or also navigate — see `InstitutionalFlowCard.md`
- Page title: `document.title = 'StockAI — Institutional Flow'`

## Dependencies
- `useInstitutionalFlow`, `InstitutionalFlowFilterBar`, `InstitutionalFlowCard`, `SkeletonCard`
- `react-router-dom` (useSearchParams)
