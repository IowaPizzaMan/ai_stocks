// Sector ETF comparison chart — specs/028-dashboard-tweaks-batch US5
// (FR-019, FR-020, FR-020a, FR-020b, FR-021). Percentage-change comparison
// across all 11 sector ETFs (clarification Q2) — a shared dollar axis would
// stack them as parallel bands (XLK ~$250 vs XLRE ~$40) and hide who is
// actually leading or lagging.
import { useState } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useSearchParams } from "react-router-dom";
import type { SectorEtfSeries, SectorEtfWindow } from "../../api/types";
import { useSectorEtfSeries, useSectorEtfSeriesRefresh } from "../../hooks/useSectorEtfSeries";
import { useQueueStatus } from "../../hooks/useQueue";
import { rebaseToPercent } from "../../lib/rebaseToPercent";

// specs/029-company-profile-tweaks US4 (FR-028): 440px vs. the previous 280
// — eleven series over a ~30% range at 280px gave ~8px of separation between
// adjacent lines, below where a line stays followable across crossings
// (research R10).
const CHART_HEIGHT = 440;

const WINDOWS: { value: SectorEtfWindow; label: string }[] = [
  { value: "1m", label: "1M" },
  { value: "3m", label: "3M" },
  { value: "6m", label: "6M" },
  { value: "1y", label: "1Y" },
];

// 11 distinguishable hues (Tailwind -400 shades) — never the only
// differentiator, the legend always pairs each with its ticker/sector name.
const TICKER_COLORS: Record<string, string> = {
  XLC: "#38bdf8", // sky-400
  XLY: "#f87171", // red-400
  XLP: "#34d399", // emerald-400
  XLE: "#fbbf24", // amber-400
  XLF: "#a78bfa", // violet-400
  XLI: "#fb923c", // orange-400
  XLV: "#22d3ee", // cyan-400
  XLB: "#f472b6", // pink-400
  XLRE: "#a3e635", // lime-400
  XLK: "#60a5fa", // blue-400
  XLU: "#c084fc", // purple-400
};

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: "#09090b",
    border: "1px solid #27272a",
    borderRadius: 8,
    fontSize: 11,
  },
  labelStyle: { color: "#a1a1aa" },
  itemStyle: { color: "#e4e4e7" },
};

/** Merges each series' rebased points into one date-aligned array Recharts
 * can plot as multiple lines — a union of every date across all series, with
 * each line's Line using connectNulls to bridge a series' own gaps. */
function mergeForChart(series: SectorEtfSeries[]): Record<string, number | string>[] {
  const byDate = new Map<string, Record<string, number | string>>();
  for (const s of series) {
    for (const point of rebaseToPercent(s.bars)) {
      const row = byDate.get(point.date) ?? { date: point.date };
      row[s.ticker] = point.pct;
      byDate.set(point.date, row);
    }
  }
  return Array.from(byDate.values()).sort((a, b) => (a.date as string).localeCompare(b.date as string));
}

// specs/029-company-profile-tweaks US4 (FR-029): real <button> elements so
// legend entries are keyboard-focusable and activatable — Recharts' default
// legend renders plain <li>s, which aren't (research R11).
function ClickableLegend({
  series,
  hidden,
  onToggle,
}: {
  series: SectorEtfSeries[];
  hidden: Set<string>;
  onToggle: (ticker: string) => void;
}) {
  return (
    <ul className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1">
      {series.map((s) => {
        const isHidden = hidden.has(s.ticker);
        return (
          <li key={s.ticker}>
            <button
              type="button"
              aria-pressed={isHidden}
              onClick={() => onToggle(s.ticker)}
              className={`flex items-center gap-1 text-[10px] transition-opacity ${
                isHidden ? "text-zinc-600 opacity-50 line-through" : "text-zinc-300"
              }`}
            >
              <span
                className="inline-block h-2 w-2 rounded-sm"
                style={{ backgroundColor: TICKER_COLORS[s.ticker] ?? "#71717a" }}
              />
              {s.ticker}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default function SectorEtfChart() {
  const [searchParams, setSearchParams] = useSearchParams();
  const window = (searchParams.get("window") as SectorEtfWindow | null) ?? "6m";
  // Within-visit UI state, deliberately not URL-encoded (spec Assumptions) —
  // survives a window change (FR-031) because it's component state, not tied
  // to the query key the window param drives.
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const { data, isLoading, isError } = useSectorEtfSeries(window);
  const { data: queue } = useQueueStatus();
  const refresh = useSectorEtfSeriesRefresh();

  const toggleSeries = (ticker: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  };

  const jobActive = [...(queue?.pending ?? []), ...(queue?.running ?? [])].some(
    (j) => j.job_type === "sector_etf_pull",
  );
  const busy = jobActive || refresh.isPending;

  const setWindow = (value: SectorEtfWindow) => {
    const next = new URLSearchParams(searchParams);
    next.set("window", value);
    setSearchParams(next, { replace: true });
  };

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Sector Momentum
        </h2>
        <div className="flex items-center gap-2">
          <div className="flex overflow-hidden rounded-lg border border-zinc-700">
            {WINDOWS.map((w) => (
              <button
                key={w.value}
                onClick={() => setWindow(w.value)}
                className={`px-2.5 py-1 text-xs transition-colors ${
                  window === w.value
                    ? "bg-sky-500/10 text-sky-300"
                    : "text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => refresh.mutate()}
            disabled={busy}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
          >
            {busy ? "refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {isLoading && (
        <p className="py-6 text-center text-sm text-zinc-600">loading sector chart…</p>
      )}

      {isError && (
        <p className="py-6 text-center text-sm text-zinc-600">
          Sector chart is unavailable right now.
        </p>
      )}

      {!isLoading && !isError && (!data || data.series.every((s) => s.bars.length === 0)) && (
        <p className="py-6 text-center text-sm text-zinc-600">
          No data yet — click Refresh to pull the sector ETFs' price history.
        </p>
      )}

      {!isLoading && !isError && data && data.series.some((s) => s.bars.length > 0) && (
        <>
          {hidden.size >= data.series.length ? (
            // FR-032 — distinct from "no data": the series exist, they're
            // just all toggled off. ClickableLegend still renders below so
            // the user can bring them back.
            <div
              style={{ height: CHART_HEIGHT }}
              className="flex items-center justify-center text-sm text-zinc-600"
            >
              All series hidden — click a ticker below to show it again.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
              <LineChart data={mergeForChart(data.series)} margin={{ top: 6, right: 16, bottom: 0, left: 0 }}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#71717a", fontSize: 9 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                  tick={{ fill: "#71717a", fontSize: 9 }}
                  tickLine={false}
                  axisLine={false}
                  width={44}
                  domain={["auto", "auto"]}
                />
                <ReferenceLine y={0} stroke="#3f3f46" />
                {data.series.map((s) => (
                  <Line
                    key={s.ticker}
                    type="monotone"
                    dataKey={s.ticker}
                    name={s.ticker}
                    stroke={TICKER_COLORS[s.ticker] ?? "#71717a"}
                    strokeWidth={1.5}
                    dot={false}
                    connectNulls
                    isAnimationActive={false}
                    hide={hidden.has(s.ticker)}
                  />
                ))}
                <Tooltip
                  {...TOOLTIP_STYLE}
                  formatter={(v, name) => [`${Number(v).toFixed(2)}%`, name as string]}
                />
              </LineChart>
            </ResponsiveContainer>
          )}

          <ClickableLegend series={data.series} hidden={hidden} onToggle={toggleSeries} />

          {data.series.some((s) => s.partial) && (
            <p className="mt-2 text-xs text-zinc-600">
              Limited history: {data.series.filter((s) => s.partial).map((s) => s.ticker).join(", ")}
            </p>
          )}
        </>
      )}
    </section>
  );
}
