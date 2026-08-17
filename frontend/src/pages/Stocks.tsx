// Spec: specs/component-specs/frontend/pages/Stocks.md
//
// Stock-specific only (renamed from "Feed" — specs/020-surface-macro-ui):
// filter bar and the analysis tile board. Market-breadth cards and macro
// context moved to the Macro page.
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import AnalysisTile from "../components/feed/AnalysisTile";
import FilterBar from "../components/feed/FilterBar";
import MarketNewsPanel from "../components/feed/MarketNewsPanel";
import SkeletonTile from "../components/feed/SkeletonTile";
import { groupBySignal } from "../lib/groupFeed";
import { useFeed } from "../hooks/useAnalysis";
import { useIntersectionObserver } from "../hooks/useIntersectionObserver";

const GROUP_LABEL: Record<string, string> = {
  bullish: "Bullish",
  neutral: "Neutral",
  bearish: "Bearish",
  unknown: "Unrecognized",
};

const SKELETON_BOARD_SIZE = 30;

export default function Stocks() {
  const [searchParams] = useSearchParams();
  const filters = {
    ticker: searchParams.get("ticker") ?? undefined,
    signal: searchParams.get("signal") ?? undefined,
    sector: searchParams.get("sector") ?? undefined,
    conviction: searchParams.get("conviction") ?? undefined,
  };

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useFeed(filters);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.title = "StockAI — Stocks";
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

      {/* Market-wide headlines (specs/022). Independent of the filter bar above
          and of the feed query's state, so a news outage can't affect the grid. */}
      <MarketNewsPanel />
    </div>
  );
}
