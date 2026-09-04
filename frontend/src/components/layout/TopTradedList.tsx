// Compact Top Traded Stocks list for the main sidebar — specs/035-chat-and-news-upgrade
// US6 (FR-021, FR-023). Moved here from the Stocks page's MostActivesPanel,
// which owned a wide 4-column table sized for the main content column; this
// variant is sized for the sidebar's w-56 width (ticker + change% only).
import { Link } from "react-router-dom";
import { useMostActives, useMostActivesRefresh } from "../../hooks/useMostActives";
import { useQueueStatus } from "../../hooks/useQueue";

function formatChangePct(pct: number | null): string {
  if (pct === null) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export default function TopTradedList() {
  const { data, isLoading, isError } = useMostActives();
  const { data: queue } = useQueueStatus();
  const refresh = useMostActivesRefresh();

  const jobActive = [...(queue?.pending ?? []), ...(queue?.running ?? [])].some(
    (j) => j.job_type === "market_movers_pull",
  );
  const busy = jobActive || refresh.isPending;

  const items = data?.items ?? [];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="font-medium text-zinc-300">Top Traded Stocks</p>
        <button
          onClick={() => refresh.mutate()}
          disabled={busy}
          aria-label="Refresh top traded stocks"
          className="text-xs text-zinc-500 transition-colors hover:text-zinc-300 disabled:opacity-40"
        >
          {busy ? "…" : "refresh"}
        </button>
      </div>

      {isLoading && <p className="text-xs text-zinc-600">loading…</p>}
      {isError && <p className="text-xs text-zinc-600">unavailable right now.</p>}
      {!isLoading && !isError && items.length === 0 && (
        <p className="text-xs text-zinc-600">No top traded stocks yet.</p>
      )}

      <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto">
        {items.map((item) => (
          <li key={item.ticker}>
            <Link
              to={`/stock/${item.ticker}`}
              className="flex items-center justify-between rounded-md px-2 py-1.5 transition-colors hover:bg-zinc-900 hover:text-zinc-200"
            >
              <span className="font-medium">{item.ticker}</span>
              <span
                className={`tabular-nums ${
                  (item.change_pct ?? 0) > 0
                    ? "text-emerald-400"
                    : (item.change_pct ?? 0) < 0
                      ? "text-red-400"
                      : "text-zinc-400"
                }`}
              >
                {formatChangePct(item.change_pct)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
