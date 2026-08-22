// Replaces UpcomingEarningsTable + EarningsCalendarTable: one table, always
// ordered by market cap (server-sorted — this component never re-sorts,
// FR-019), showing actuals/surprise for anything already reported.
// spec: specs/025-earnings-page-filters
import { Link } from "react-router-dom";
import type { EarningsCalendarEntry } from "../../api/types";

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
  return `$${value.toFixed(0)}`;
}

function formatEps(value: number | null): string {
  return value === null ? "—" : value.toFixed(2);
}

interface SurpriseProps {
  pct: number | null;
  beat: boolean | null;
}

/** Beat/miss must be distinguishable at a glance without relying on the sign
 * character alone (FR-012) — color AND an explicit label/icon. A null
 * surprise (missing/zero estimate) always renders as unavailable, never 0%
 * or a beat (FR-011). */
function Surprise({ pct, beat }: SurpriseProps) {
  if (pct === null || beat === null) {
    return <span data-testid="surprise-unavailable" className="text-zinc-600">—</span>;
  }
  if (beat) {
    return (
      <span data-testid="surprise-beat" className="text-emerald-400">
        ▲ +{pct.toFixed(1)}%
      </span>
    );
  }
  return (
    <span data-testid="surprise-miss" className="text-red-400">
      ▼ {pct.toFixed(1)}%
    </span>
  );
}

interface EarningsTableProps {
  entries: EarningsCalendarEntry[];
  isLoading: boolean;
  queuedTickers: Set<string>;
  onQueueTicker: (ticker: string) => void;
}

export default function EarningsTable({
  entries,
  isLoading,
  queuedTickers,
  onQueueTicker,
}: EarningsTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-900 text-xs uppercase text-zinc-500">
          <tr>
            {["Ticker", "Reports", "EPS (Est. / Actual)", "Surprise", "Revenue (Est. / Actual)",
              "Surprise", "Mkt Cap", "Last Updated", ""].map((label, i) => (
              <th key={i} className="px-3 py-2.5 font-medium">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading &&
            Array.from({ length: 6 }).map((_, i) => (
              <tr key={i} className="animate-pulse border-t border-zinc-800">
                {Array.from({ length: 9 }).map((_, j) => (
                  <td key={j} className="px-3 py-3">
                    <div className="h-4 w-full max-w-20 rounded bg-zinc-800" />
                  </td>
                ))}
              </tr>
            ))}

          {!isLoading &&
            entries.map((e, i) => {
              const queued = queuedTickers.has(e.ticker);
              const isUpcoming = e.reporting_state === "upcoming";
              const isAwaiting = e.reporting_state === "awaiting";

              return (
                <tr
                  key={e.ticker}
                  data-testid="earnings-row"
                  data-reporting-state={e.reporting_state}
                  className={`border-t border-zinc-800 ${i % 2 === 1 ? "bg-zinc-800/20" : ""}`}
                >
                  <td className="px-3 py-2.5">
                    <Link
                      to={`/stock/${e.ticker}`}
                      className="font-semibold text-indigo-300 underline decoration-indigo-700 hover:text-indigo-200"
                    >
                      {e.ticker}
                    </Link>
                    <span className="block max-w-48 truncate text-xs text-zinc-500">{e.company}</span>
                  </td>

                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {e.report_date}
                    {isAwaiting && (
                      <span
                        data-testid="awaiting-badge"
                        className="ml-1.5 rounded bg-amber-900/40 px-1.5 py-0.5 text-[10px] uppercase text-amber-400"
                      >
                        Awaiting results
                      </span>
                    )}
                  </td>

                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {formatEps(e.eps_estimate)}
                    {" / "}
                    {isUpcoming ? <span className="text-zinc-600">—</span> : formatEps(e.eps_actual)}
                  </td>
                  <td className="px-3 py-2.5">
                    {isUpcoming ? (
                      <span className="text-zinc-600">—</span>
                    ) : (
                      <Surprise pct={e.eps_surprise_pct} beat={e.beat} />
                    )}
                  </td>

                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {formatCompact(e.revenue_estimate)}
                    {" / "}
                    {isUpcoming ? <span className="text-zinc-600">—</span> : formatCompact(e.revenue_actual)}
                  </td>
                  <td className="px-3 py-2.5">
                    {isUpcoming ? (
                      <span className="text-zinc-600">—</span>
                    ) : (
                      <Surprise
                        pct={e.revenue_surprise_pct}
                        beat={e.revenue_surprise_pct === null ? null : e.revenue_surprise_pct > 0}
                      />
                    )}
                  </td>

                  <td className="px-3 py-2.5">{formatCompact(e.market_cap)}</td>
                  <td className="px-3 py-2.5 text-xs text-zinc-500">{e.last_updated}</td>

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
