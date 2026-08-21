// Spec: specs/025-earnings-page-filters. Auto-loading, date-windowed earnings
// calendar — no manual scan trigger (FR-000). Date changes refetch the
// server; the size sliders and big-movers toggle filter client-side with
// zero additional requests (FR-027b).
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import EarningsFilterBar, {
  DEFAULT_MIN_EPS,
  DEFAULT_MIN_REV,
  getDefaultWindow,
} from "../components/earnings/EarningsFilterBar";
import EarningsTable from "../components/earnings/EarningsTable";
import { useAnalyzeTickers, useEarningsCalendar } from "../hooks/useEarningsScan";
import { filterEntries } from "../lib/earningsFilters";

export default function EarningsScan() {
  const [searchParams] = useSearchParams();
  const [queuedTickers, setQueuedTickers] = useState<Set<string>>(new Set());
  const analyze = useAnalyzeTickers();

  useEffect(() => {
    document.title = "StockAI — Earnings";
  }, []);

  const defaultWindow = getDefaultWindow();
  const from = searchParams.get("from") ?? defaultWindow.from;
  const to = searchParams.get("to") ?? defaultWindow.to;
  const minRev = Number(searchParams.get("min_rev") ?? DEFAULT_MIN_REV);
  const minEps = Number(searchParams.get("min_eps") ?? DEFAULT_MIN_EPS);
  const moversOnly = searchParams.get("movers") === "1";

  const calendar = useEarningsCalendar(from, to);

  const rawEntries = calendar.data?.entries ?? [];
  const filteredEntries = useMemo(
    () => filterEntries(rawEntries, { minRev, minEps, moversOnly }),
    [rawEntries, minRev, minEps, moversOnly],
  );

  const analyzeTicker = (ticker: string) => {
    analyze.mutate([ticker]);
    setQueuedTickers((prev) => new Set(prev).add(ticker));
  };

  const isInitialLoad = calendar.isLoading;
  const dateWindowEmpty = !calendar.isLoading && !calendar.isError && rawEntries.length === 0;
  const filtersEmptiedIt = !dateWindowEmpty && filteredEntries.length === 0 && rawEntries.length > 0;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <h1 className="text-xl font-semibold">Earnings</h1>

      <EarningsFilterBar
        visibleCount={filteredEntries.length}
        totalCount={rawEntries.length}
      />

      {calendar.data?.stale && (
        <p className="rounded-lg border border-amber-800 bg-amber-950/40 px-3 py-2 text-sm text-amber-400">
          Showing cached data — the earnings provider is temporarily unavailable
          {calendar.data.fetched_at ? ` (as of ${calendar.data.fetched_at})` : ""}.
        </p>
      )}

      {calendar.isError && (
        <p className="py-4 text-center text-sm text-red-400">
          Couldn't load the earnings calendar — is the backend running?
        </p>
      )}

      {!calendar.isError && (
        <>
          {calendar.isFetching && !isInitialLoad && (
            <p className="text-xs text-zinc-500">Updating window…</p>
          )}

          <EarningsTable
            entries={filteredEntries}
            isLoading={isInitialLoad}
            queuedTickers={queuedTickers}
            onQueueTicker={analyzeTicker}
          />

          {dateWindowEmpty && (
            <p className="py-8 text-center text-sm text-zinc-500">
              No companies report in this window — try a wider date range.
            </p>
          )}

          {filtersEmptiedIt && moversOnly && (
            <p className="py-8 text-center text-sm text-zinc-500">
              "Big movers only" is hiding every company in this window — turn it off to see
              the rest.
            </p>
          )}

          {filtersEmptiedIt && !moversOnly && (
            <p className="py-8 text-center text-sm text-zinc-500">
              No companies match the revenue/EPS floors — try lowering them.
            </p>
          )}
        </>
      )}
    </div>
  );
}
