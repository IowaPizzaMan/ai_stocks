// Spec: specs/component-specs/frontend/pages/InstitutionalFlow.md
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import InstitutionalFlowCard from "../components/institutional/InstitutionalFlowCard";
import InstitutionalFlowFilterBar from "../components/institutional/InstitutionalFlowFilterBar";
import SkeletonCard from "../components/shared/SkeletonCard";
import { useInstitutionalFlow } from "../hooks/useInstitutionalFlow";
import { useIntersectionObserver } from "../hooks/useIntersectionObserver";

export default function InstitutionalFlow() {
  const [searchParams] = useSearchParams();
  const filters = {
    action: searchParams.get("action") ?? undefined,
    fund: searchParams.get("fund") ?? undefined,
    ticker: searchParams.get("ticker") ?? undefined,
    min_notability: searchParams.get("min_notability") ?? undefined,
  };

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInstitutionalFlow(filters);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.title = "StockAI — Institutional Flow";
  }, []);

  useIntersectionObserver(loadMoreRef, () => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  });

  const allItems = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="sr-only">Institutional Flow</h1>
      <InstitutionalFlowFilterBar />

      {isLoading &&
        Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}

      {isError && (
        <p className="py-12 text-center text-sm text-red-400">
          Couldn't reach the API — is the backend running?
        </p>
      )}

      {!isLoading && !isError && allItems.length === 0 && (
        <div className="py-16 text-center text-zinc-500">
          <p className="mb-1 text-lg text-zinc-400">No flow events yet</p>
          <p className="text-sm">
            The scanner sweeps 13F changes and Dataroma superinvestor moves once a
            day — or hit Scan Now to request one.
          </p>
        </div>
      )}

      {allItems.map((item) => (
        <InstitutionalFlowCard
          key={`${item.ticker}-${item.fund}-${item.filed_at}-${item.action}`}
          event={item}
        />
      ))}

      <div ref={loadMoreRef} className="h-8 text-center text-xs text-zinc-600">
        {isFetchingNextPage && "loading…"}
      </div>
    </div>
  );
}
