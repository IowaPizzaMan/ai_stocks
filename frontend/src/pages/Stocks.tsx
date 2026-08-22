// Spec: specs/component-specs/frontend/pages/Stocks.md
//
// Stock-specific only (renamed from "Feed" — specs/020-surface-macro-ui):
// filter bar and the analysis tile board. Market-breadth cards and macro
// context moved to the Macro page.
//
// specs/027-stocks-news-tab-ai-summary (research.md R1/R2): the page owns its
// own bounded, viewport-relative layout so the browser window itself never
// needs to scroll — only the active tab's content area does — and the grid
// no longer auto-fetches on scroll; loading more requires the explicit
// "Load more" control. This is scoped entirely to this page (no changes to
// App.tsx/Navbar.tsx/Sidebar.tsx), so every other route is unaffected.
import { useEffect } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import AnalysisTile from "../components/feed/AnalysisTile";
import FilterBar from "../components/feed/FilterBar";
import MarketNewsPanel from "../components/feed/MarketNewsPanel";
import PortfolioDigestPanel from "../components/feed/PortfolioDigestPanel";
import SkeletonTile from "../components/feed/SkeletonTile";
import TabBar from "../components/shared/TabBar";
import { groupBySignal } from "../lib/groupFeed";
import { useFeed } from "../hooks/useAnalysis";

const GROUP_LABEL: Record<string, string> = {
  bullish: "Bullish",
  neutral: "Neutral",
  bearish: "Bearish",
  unknown: "Unrecognized",
};

const SKELETON_BOARD_SIZE = 30;

// The Stocks page's own lightweight tab set (grid default / news),
// independent of the per-ticker detail page's tabs.
const TABS = [
  { id: "grid", label: "Stocks" },
  { id: "news", label: "News" },
];
const DEFAULT_TAB = "grid";

export default function Stocks() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  // Unknown/removed anchors fall back to the grid tab, mirroring StockDetail's
  // existing hash-tab convention (spec 021 FR-027).
  const hash = location.hash.replace("#", "");
  const activeTab = TABS.some((t) => t.id === hash) ? hash : DEFAULT_TAB;

  const filters = {
    ticker: searchParams.get("ticker") ?? undefined,
    signal: searchParams.get("signal") ?? undefined,
    sector: searchParams.get("sector") ?? undefined,
    conviction: searchParams.get("conviction") ?? undefined,
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

      {/* Non-shrinking header: filter bar + tab bar always stay in view —
          the browser window itself never needs to scroll for these. */}
      <div className="shrink-0 space-y-4">
        <FilterBar />
        <TabBar
          tabs={TABS}
          activeTab={activeTab}
          onSelect={(id) => navigate(`#${id}`, { replace: true })}
        />
      </div>

      {/* The only scrollable region on the page — grid or news, never both. */}
      <div data-scroll-region="true" className="min-h-0 flex-1 overflow-y-auto pt-4">
        {activeTab === "news" && <MarketNewsPanel />}

        {activeTab === "grid" && (
          // Grid (primary/left column) and the digest panel (second column)
          // render side-by-side, not stacked — spec 027 FR-007b, research.md R9.
          // On narrow viewports they wrap, with the grid column still first.
          <div className="flex flex-col gap-4 pb-4 lg:flex-row lg:items-start">
            <div data-grid-column="true" className="min-w-0 flex-1 space-y-4">
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

            <div data-digest-column="true" className="w-full shrink-0 lg:w-80">
              <PortfolioDigestPanel />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
