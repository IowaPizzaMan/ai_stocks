// Top Traded Stocks — specs/028-dashboard-tweaks-batch US6 (FR-022, FR-023, FR-024).
// Rendered below the ticker grid on the Stocks page, inside the grid column.
import { Link } from "react-router-dom";
import { useMostActives, useMostActivesRefresh } from "../../hooks/useMostActives";
import { useQueueStatus } from "../../hooks/useQueue";
import { formatDate } from "../../lib/time";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      {children}
    </section>
  );
}

function formatChangePct(pct: number | null): string {
  if (pct === null) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export default function MostActivesPanel() {
  const { data, isLoading, isError } = useMostActives();
  const { data: queue } = useQueueStatus();
  const refresh = useMostActivesRefresh();

  const jobActive = [...(queue?.pending ?? []), ...(queue?.running ?? [])].some(
    (j) => j.job_type === "market_movers_pull",
  );
  const busy = jobActive || refresh.isPending;

  if (isLoading) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">loading top traded stocks…</p>
      </Shell>
    );
  }

  if (isError) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">
          Top traded stocks are unavailable right now.
        </p>
      </Shell>
    );
  }

  const items = data?.items ?? [];

  return (
    <Shell>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Top Traded Stocks
        </h2>
        <div className="flex items-center gap-2">
          {data?.date && (
            <span className="text-xs text-zinc-600">
              session {formatDate(data.date) || data.date}
            </span>
          )}
          <button
            onClick={() => refresh.mutate()}
            disabled={busy}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
          >
            {busy ? "refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="py-6 text-center text-sm text-zinc-600">
          No data yet — click Refresh to pull today's most-active stocks.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-500">
                <th className="pb-2 pr-3">Ticker</th>
                <th className="pb-2 pr-3">Company</th>
                <th className="pb-2 pr-3 text-right">Price</th>
                <th className="pb-2 text-right">Change</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.ticker} className="border-t border-zinc-800">
                  <td className="py-1.5 pr-3" data-ticker={item.ticker}>
                    <Link to={`/stock/${item.ticker}`} className="font-medium text-sky-400 hover:underline">
                      {item.ticker}
                    </Link>
                  </td>
                  <td className="py-1.5 pr-3 truncate text-zinc-400">{item.company ?? "—"}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums text-zinc-300">
                    {item.price !== null ? item.price.toFixed(2) : "—"}
                  </td>
                  <td
                    className={`py-1.5 text-right tabular-nums ${
                      (item.change_pct ?? 0) > 0
                        ? "text-emerald-400"
                        : (item.change_pct ?? 0) < 0
                          ? "text-red-400"
                          : "text-zinc-400"
                    }`}
                  >
                    {formatChangePct(item.change_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Shell>
  );
}
