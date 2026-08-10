// Feed filter bar + the Pull controls (ticker input, Pull, Run All, queue chip)
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useDebounce } from "../../hooks/useDebounce";
import { useEnqueueAll, useEnqueueTicker, useQueueStatus } from "../../hooks/useQueue";

const SIGNALS = ["bullish", "bearish", "neutral"];
const CONVICTIONS = ["high", "medium", "low"];

export default function FilterBar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [ticker, setTicker] = useState("");
  // Feed search — filters the feed in place as you type; distinct from the
  // Pull input, which enqueues a new analysis.
  const [search, setSearch] = useState(searchParams.get("ticker") ?? "");
  const debouncedSearch = useDebounce(search.trim());
  const enqueue = useEnqueueTicker();
  const enqueueAll = useEnqueueAll();
  const { data: queue } = useQueueStatus();

  const busyCount = (queue?.pending_count ?? 0) + (queue?.running_count ?? 0);

  useEffect(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (debouncedSearch) next.set("ticker", debouncedSearch);
        else next.delete("ticker");
        return next;
      },
      { replace: true },
    );
  }, [debouncedSearch, setSearchParams]);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (next.get(key) === value) next.delete(key);
    else next.set(key, value);
    setSearchParams(next, { replace: true });
  };

  const pull = () => {
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    enqueue.mutate(t);
    setTicker("");
  };

  return (
    <div className="sticky top-0 z-10 -mx-6 border-b border-zinc-800 bg-zinc-950/95 px-6 py-3 backdrop-blur">
      <div className="flex flex-wrap items-center gap-2">
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            pull();
          }}
        >
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Ticker…"
            className="w-28 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm uppercase placeholder:normal-case placeholder:text-zinc-600 focus:border-sky-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!ticker.trim() || enqueue.isPending}
            className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-sky-500 disabled:opacity-40"
          >
            Pull ▶
          </button>
        </form>
        <button
          onClick={() => enqueueAll.mutate()}
          disabled={enqueueAll.isPending}
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
        >
          Run All
        </button>
        {busyCount > 0 && (
          <span className="flex items-center gap-1.5 rounded-full bg-sky-500/10 px-2.5 py-1 text-xs text-sky-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
            {queue!.running_count > 0
              ? `analyzing ${queue!.running[0]?.ticker}${busyCount > 1 ? ` (+${busyCount - 1} queued)` : ""}`
              : `${busyCount} queued`}
          </span>
        )}

        <span className="mx-2 hidden h-5 w-px bg-zinc-800 sm:block" />

        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by ticker…"
          aria-label="Filter feed by ticker"
          className="w-36 rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs uppercase placeholder:normal-case placeholder:text-zinc-600 focus:border-sky-500 focus:outline-none"
        />

        {SIGNALS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter("signal", s)}
            className={`rounded-full border px-2.5 py-1 text-xs capitalize transition-colors ${
              searchParams.get("signal") === s
                ? "border-sky-500 bg-sky-500/10 text-sky-300"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {s}
          </button>
        ))}
        {CONVICTIONS.map((c) => (
          <button
            key={c}
            onClick={() => setFilter("conviction", c)}
            className={`rounded-full border px-2.5 py-1 text-xs capitalize transition-colors ${
              searchParams.get("conviction") === c
                ? "border-sky-500 bg-sky-500/10 text-sky-300"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {c} conv.
          </button>
        ))}
      </div>
    </div>
  );
}
