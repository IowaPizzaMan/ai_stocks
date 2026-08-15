// Spec: specs/component-specs/frontend/pages/Feed.md
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import AnalysisTile from "../components/feed/AnalysisTile";
import FilterBar from "../components/feed/FilterBar";
import MarketFlowCard from "../components/feed/MarketFlowCard";
import SkeletonTile from "../components/feed/SkeletonTile";
import { groupBySignal } from "../lib/groupFeed";
import { useFeed } from "../hooks/useAnalysis";
import { useIntersectionObserver } from "../hooks/useIntersectionObserver";
import { useMarketBreadth, useMarketFlowEvents } from "../hooks/useMarketBreadth";

// Market-flow events are pinned above the board rather than interleaved —
// they're market-wide and have no ticker, so a signal group would have
// nowhere sensible to put them. They age out after two weeks.
const MARKET_EVENT_MAX_AGE_DAYS = 14;

const GROUP_LABEL: Record<string, string> = {
  bullish: "Bullish",
  neutral: "Neutral",
  bearish: "Bearish",
  unknown: "Unrecognized",
};

const SKELETON_BOARD_SIZE = 30;

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
  const groups = groupBySignal(allItems);

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <h1 className="sr-only">Analysis Feed</h1>
      <FilterBar />

      {pinnedEvents.length > 0 && (
        <div className="space-y-3">
          {pinnedEvents.map((event) => (
            <MarketFlowCard key={event.event_id} event={event} breadth={breadth} />
          ))}
        </div>
      )}

      {isLoading && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-2">
          {Array.from({ length: SKELETON_BOARD_SIZE }).map((_, i) => (
            <SkeletonTile key={i} />
          ))}
        </div>
      )}

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

      {!isLoading &&
        !isError &&
        groups.map((group) => (
          <section key={group.signal} className="space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              {GROUP_LABEL[group.signal]}
            </h2>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-2">
              {group.items.map((item) => (
                <AnalysisTile key={item.ticker} analysis={item} />
              ))}
            </div>
          </section>
        ))}

      <div ref={loadMoreRef} className="h-8 text-center text-xs text-zinc-600">
        {isFetchingNextPage && "loading…"}
      </div>
    </div>
  );
}
