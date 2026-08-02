// Raw pre-screened calendar (unscored). Each row has an explicit Queue button
// — the only way calendar tickers enter the work queue (the backend endpoint
// is read-only by design; see routers/earnings.py::get_calendar).
import type { EarningsCalendarEntry } from "../../api/types";

interface UpcomingEarningsTableProps {
  entries: EarningsCalendarEntry[];
  isLoading: boolean;
  queuedTickers: Set<string>;
  onQueueTicker: (ticker: string) => void;
}

export function formatCompact(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
  return `$${value.toFixed(0)}`;
}

export default function UpcomingEarningsTable({
  entries,
  isLoading,
  queuedTickers,
  onQueueTicker,
}: UpcomingEarningsTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-900 text-xs uppercase text-zinc-500">
          <tr>
            {["Ticker", "Reports", "EPS Est.", "Revenue Est.", "Mkt Cap", "Sector", ""].map(
              (label, i) => (
                <th key={i} className="px-3 py-2.5 font-medium">
                  {label}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {isLoading &&
            Array.from({ length: 6 }).map((_, i) => (
              <tr key={i} className="animate-pulse border-t border-zinc-800">
                {Array.from({ length: 7 }).map((_, j) => (
                  <td key={j} className="px-3 py-3">
                    <div className="h-4 w-full max-w-20 rounded bg-zinc-800" />
                  </td>
                ))}
              </tr>
            ))}

          {!isLoading && entries.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-8 text-center text-zinc-500">
                No companies above the cap floor reporting in this window.
              </td>
            </tr>
          )}

          {!isLoading &&
            entries.map((e, i) => {
              const queued = queuedTickers.has(e.ticker);
              return (
                <tr
                  key={e.ticker}
                  className={`border-t border-zinc-800 ${i % 2 === 1 ? "bg-zinc-800/20" : ""}`}
                >
                  <td className="px-3 py-2.5">
                    <span className="font-semibold">{e.ticker}</span>
                    <span className="block max-w-48 truncate text-xs text-zinc-500">
                      {e.company}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {e.report_date}
                    {e.report_time !== "unknown" && (
                      <span className="ml-1.5 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] uppercase text-zinc-400">
                        {e.report_time}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {e.eps_estimate !== null ? e.eps_estimate.toFixed(2) : "—"}
                  </td>
                  <td className="px-3 py-2.5">{formatCompact(e.revenue_estimate)}</td>
                  <td className="px-3 py-2.5">{formatCompact(e.market_cap)}</td>
                  <td className="px-3 py-2.5 text-zinc-400">{e.sector ?? "—"}</td>
                  <td className="px-3 py-2.5">
                    {queued ? (
                      <span className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-green-400">
                        Queued
                      </span>
                    ) : (
                      <button
                        onClick={() => onQueueTicker(e.ticker)}
                        className="rounded bg-indigo-600/20 px-2 py-1 text-xs text-indigo-300 hover:bg-indigo-600/40"
                      >
                        Queue ▶
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
        </tbody>
      </table>
    </div>
  );
}
