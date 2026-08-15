# frontend/src/pages/Feed.tsx

## Purpose
Default home view. A dense, checkerboard-style grid of compact stock tiles — grouped by
signal (bullish → neutral → bearish) — so a large analyzed universe fits on one screen.
Includes the filter bar, a skeleton-tile loading board, and infinite scroll. Redesigned in
feature 019 (`specs/019-feed-checkerboard-grid/`) from a single-column large-card list; see
that feature's spec for the full rationale.

## Layout
```
[FilterBar — sticky]
──────────────────────────────────────────────────
[MarketFlowCard]  (only when unfiltered, ≤14 days old)
──────────────────────────────────────────────────
BULLISH
[Tile][Tile][Tile][Tile][Tile][Tile][Tile][Tile]...
[Tile][Tile][Tile]...

NEUTRAL
[Tile][Tile][Tile][Tile]...

BEARISH
[Tile][Tile]...

[Load More] (intersection observer triggers)
```

Each `[Tile]` is `AnalysisTile` (see `../components/feed/AnalysisTile.md`) — ticker + a
signal-colored fill + 1–3 conviction dots, nothing else on its face. Hovering or focusing a
tile reveals `TilePreview`, which carries the detail the old `AnalysisCard` used to show on
its face (summary, recency, watchlist add).

## Implementation

```tsx
import { useFeed } from '@/hooks/useAnalysis'
import { useSearchParams } from 'react-router-dom'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'
import { groupBySignal } from '@/lib/groupFeed'

export function Feed() {
  const [searchParams] = useSearchParams()
  const filters = {
    ticker: searchParams.get('ticker') || undefined,
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
  const groups = groupBySignal(allItems) // bullish → neutral → bearish → unknown, newest-first within each

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <FilterBar />

      {isLoading
        ? <div className="grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-2">
            {Array.from({ length: 30 }).map((_, i) => <SkeletonTile key={i} />)}
          </div>
        : groups.map(group => (
            <section key={group.signal}>
              <h2>{group.signal}</h2>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-2">
                {group.items.map(item => <AnalysisTile key={item.ticker} analysis={item} />)}
              </div>
            </section>
          ))
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
- `useInfiniteQuery` pages load automatically as the user scrolls to the sentinel div; the
  feed page size is 60 (raised from 20) so a single fetch fills a dense grid without an
  immediate second request.
- Grouping (`groupBySignal`) is a pure client-side re-derivation of the flattened, already
  newest-first, already-deduped `/analysis/feed` response — it does not change the API
  contract. It re-runs on every render, so tiles loaded by later pages merge into their
  correct signal group rather than appending to the bottom of the board.
- Skeleton tiles (a ~30-tile board) are shown only on initial load, not on "load more".
- Filter changes reset to page 1 automatically (React Query key includes filters).
- Market-flow events remain pinned above the grid, unfiltered + ≤14 days old only — unchanged
  from the pre-019 behavior, just visually adjacent to a denser board now.
- Page title: `document.title = 'StockAI — Feed'`.
- Page container widened from `max-w-3xl` to `max-w-7xl` to make room for the grid.

## Dependencies
- `useFeed`, `FilterBar`, `AnalysisTile`, `SkeletonTile`, `MarketFlowCard`, `groupBySignal`
- `react-router-dom` (useSearchParams)
