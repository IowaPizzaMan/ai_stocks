// Spec: specs/component-specs/frontend/pages/Stocks.md
//
// Stock-specific only (renamed from "Feed" — specs/020-surface-macro-ui):
// filter bar and the analysis tile board. Market-breadth cards and macro
// context moved to the Macro page.
//
// specs/027-stocks-news-tab-ai-summary (research.md R1/R2): the page owns its
// own bounded, viewport-relative layout so the browser window itself never
// needs to scroll — only the grid's own content area does — and the grid no
// longer auto-fetches on scroll; loading more requires the explicit "Load
// more" control.
//
// specs/029-company-profile-tweaks (US1, US3, research R9): the News tab
// moved to its own top-level route (see pages/News.tsx), so this page no
// longer has a tab bar at all — an old #news bookmark is just an ignored URL
// fragment now, which is how FR-004 is satisfied for free. The Portfolio
// Summary panel and its two-column layout are gone entirely (FR-018/FR-019);
// the grid is the page's only content, at full width.
//
// specs/037-stocks-conviction-and-activity US1 (contracts/feed-ordering.md):
// tiles within each signal group are ordered by conviction descending, then
// ticker ascending — a total order the server already applies, so
// groupBySignal() (lib/groupFeed.ts) must not re-sort. "Load more" only ever
// appends tiles that sort at-or-after the last one shown.
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import ActivityFeed from "../components/feed/ActivityFeed";
import AnalysisTile from "../components/feed/AnalysisTile";
import FilterBar from "../components/feed/FilterBar";
import SkeletonTile from "../components/feed/SkeletonTile";
import { groupBySignal } from "../lib/groupFeed";
import { useFeed } from "../hooks/useAnalysis";

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
    // 029-company-profile-tweaks US5 (FR-024/FR-025)
    industry: searchParams.get("industry") ?? undefined,
    // 028-dashboard-tweaks-batch US3 (FR-009)
    sentiment: (searchParams.get("sentiment") as "liked" | "disliked" | null) ?? undefined,
  };

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useFeed(filters);

  useEffect(() => {
    document.title = "StockAI — Stocks";
  }, []);

  const allItems = data?.pages.flatMap((p) => p.items) ?? [];
  const groups = groupBySignal(allItems);

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-7xl flex-col">
      <h1 className="sr-only">Analysis Feed</h1>

      {/* Non-shrinking header: the filter bar always stays in view — the
          browser window itself never needs to scroll for it. */}
      <div className="shrink-0 space-y-4">
        <FilterBar />
      </div>

      {/* The only scrollable region on the page. */}
      <div data-scroll-region="true" className="min-h-0 flex-1 overflow-y-auto pt-4">
        <div data-grid-column="true" className="min-w-0 space-y-4 pb-4">
          {/* specs/037-stocks-conviction-and-activity US3 (FR-015-FR-022) —
              lives inside the page's own scrollable region, not the fixed
              header, so the bounded viewport-relative layout is preserved;
              independent of the board's own loading/error state below. */}
          <ActivityFeed />

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

          {hasNextPage && (
            <div className="flex justify-center py-2">
              <button
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="rounded-lg border border-zinc-700 px-4 py-1.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
              >
                {isFetchingNextPage ? "loading…" : "Load more"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
