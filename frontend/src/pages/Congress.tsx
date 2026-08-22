// Congress trading disclosures — specs/028-dashboard-tweaks-batch US4.
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import CongressSummary from "../components/congress/CongressSummary";
import CongressTable from "../components/congress/CongressTable";
import { useCongressRefresh, useCongressSummary, useCongressTrades } from "../hooks/useCongress";
import { useDebounce } from "../hooks/useDebounce";
import { useQueueStatus } from "../hooks/useQueue";

export default function Congress() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [ticker, setTicker] = useState(searchParams.get("ticker") ?? "");
  const [politician, setPolitician] = useState(searchParams.get("politician") ?? "");
  const debouncedTicker = useDebounce(ticker.trim());
  const debouncedPolitician = useDebounce(politician.trim());

  useEffect(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (debouncedTicker) next.set("ticker", debouncedTicker);
        else next.delete("ticker");
        if (debouncedPolitician) next.set("politician", debouncedPolitician);
        else next.delete("politician");
        return next;
      },
      { replace: true },
    );
  }, [debouncedTicker, debouncedPolitician, setSearchParams]);

  const filters = {
    ticker: searchParams.get("ticker") ?? undefined,
    politician: searchParams.get("politician") ?? undefined,
  };

  const { data: summary, isLoading: summaryLoading } = useCongressSummary();
  const { data: trades, isLoading: tradesLoading, isError } = useCongressTrades(filters);
  const { data: queue } = useQueueStatus();
  const refresh = useCongressRefresh();

  const jobActive = [...(queue?.pending ?? []), ...(queue?.running ?? [])].some(
    (j) => j.job_type === "congress_trades_pull",
  );
  const busy = jobActive || refresh.isPending;

  useEffect(() => {
    document.title = "StockAI — Congress";
  }, []);

  const hasAnyData = (trades?.total ?? 0) > 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-white">Congress</h1>
        <button
          onClick={() => refresh.mutate()}
          disabled={busy}
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
        >
          {busy ? "refreshing…" : "Refresh"}
        </button>
      </div>

      {!summaryLoading && summary && (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Summary
          </h2>
          <CongressSummary data={summary} />
        </section>
      )}

      <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Filter by ticker…"
            aria-label="Filter by ticker"
            className="w-36 rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs uppercase placeholder:normal-case placeholder:text-zinc-600 focus:border-sky-500 focus:outline-none"
          />
          <input
            value={politician}
            onChange={(e) => setPolitician(e.target.value)}
            placeholder="Filter by member…"
            aria-label="Filter by member"
            className="w-48 rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs placeholder:text-zinc-600 focus:border-sky-500 focus:outline-none"
          />
        </div>

        {tradesLoading && (
          <p className="py-6 text-center text-sm text-zinc-600">loading disclosures…</p>
        )}

        {isError && (
          <p className="py-6 text-center text-sm text-zinc-600">
            Congress disclosures are unavailable right now.
          </p>
        )}

        {!tradesLoading && !isError && !hasAnyData && (filters.ticker || filters.politician) && (
          <p className="py-6 text-center text-sm text-zinc-600">
            No disclosures match the current filter.
          </p>
        )}

        {!tradesLoading && !isError && !hasAnyData && !filters.ticker && !filters.politician && (
          <p className="py-6 text-center text-sm text-zinc-600">
            No disclosures yet — click Refresh to pull recent Senate and House filings.
          </p>
        )}

        {!tradesLoading && !isError && hasAnyData && <CongressTable trades={trades!.items} />}
      </section>
    </div>
  );
}
