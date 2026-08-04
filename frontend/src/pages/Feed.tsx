// Spec: specs/component-specs/frontend/pages/Feed.md
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import AnalysisCard from "../components/feed/AnalysisCard";
import FilterBar from "../components/feed/FilterBar";
import SkeletonCard from "../components/shared/SkeletonCard";
import { useFeed } from "../hooks/useAnalysis";
import { useIntersectionObserver } from "../hooks/useIntersectionObserver";

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
  const loadMoreRef = useRef<HTMLDivElement>(null);

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
