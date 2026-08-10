// Spec: specs/component-specs/frontend/pages/Feed.md
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import AnalysisCard from "../components/feed/AnalysisCard";
import FilterBar from "../components/feed/FilterBar";
import MarketFlowCard from "../components/feed/MarketFlowCard";
import SkeletonCard from "../components/shared/SkeletonCard";
import { useFeed } from "../hooks/useAnalysis";
import { useIntersectionObserver } from "../hooks/useIntersectionObserver";
import { useMarketBreadth, useMarketFlowEvents } from "../hooks/useMarketBreadth";

// Market-flow events are pinned above the analyses rather than interleaved —
// they're market-wide and have no ticker, so chronological position in a
// per-ticker feed would bury them. They age out after two weeks.
const MARKET_EVENT_MAX_AGE_DAYS = 14;

export default function Feed() {
  const [searchParams] = useSearchParams();
  const filters = {
    ticker: searchParams.get("ticker") ?? undefined,
    signal: searchParams.get("signal") ?? undefined,
    sector: searchParams.get("sector") ?? undefined,
    conviction: searchParams.get("conviction") ?? undefined,
  };

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useFeed(filters);
  const { data: marketEvents } = useMarketFlowEvents();
  const { data: breadth } = useMarketBreadth();
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // A market-wide card is noise once the user has narrowed to a ticker/sector.
  const filtered = Object.values(filters).some(Boolean);
  const cutoff = Date.now() - MARKET_EVENT_MAX_AGE_DAYS * 86_400_000;
  const pinnedEvents = filtered
    ? []
    : (marketEvents ?? []).filter((e) => new Date(e.created_at).getTime() >= cutoff);

  useEffect(() => {
    document.title = "StockAI — Feed";
  }, []);

  useIntersectionObserver(loadMoreRef, () => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  });

  const allItems = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="sr-only">Analysis Feed</h1>
      <FilterBar />

      {pinnedEvents.map((event) => (
        <MarketFlowCard key={event.event_id} event={event} breadth={breadth} />
      ))}

      {isLoading &&
        Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}

      {isError && (
        <p className="py-12 text-center text-sm text-red-400">
          Couldn't reach the API — is the backend running?
        </p>
      )}

      {!isLoading && !isError && allItems.length === 0 && (
        <div className="py-16 text-center text-zinc-500">
          <p className="mb-1 text-lg text-zinc-400">No analyses yet</p>
          <p className="text-sm">
            Type a ticker above and hit Pull — the analysis will appear here when the
            agent finishes.
          </p>
        </div>
      )}

      {allItems.map((item) => (
        <AnalysisCard key={`${item.ticker}-${item.timestamp}`} analysis={item} />
      ))}

      <div ref={loadMoreRef} className="h-8 text-center text-xs text-zinc-600">
        {isFetchingNextPage && "loading…"}
      </div>
    </div>
  );
}
