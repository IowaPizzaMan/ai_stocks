// Spec: specs/021-stock-page-redesign US7 (FR-016, FR-017)
// Quarterly insider flow from FMP's statistics endpoint. These aggregates count
// all Form 4 activity, so the verdict here is explicitly labeled as covering
// awards/exercises too — the open-market-only read stays on the 90-day table.
import {
  Bar,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { InsiderQuarterStats } from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";

function verdict(stats: InsiderQuarterStats[]): { label: string; className: string } {
  const recent = stats.slice(0, 4);
  const acquired = recent.reduce((a, s) => a + (s.total_acquired || 0), 0);
  const disposed = recent.reduce((a, s) => a + (s.total_disposed || 0), 0);
  if (!acquired && !disposed) {
    return { label: "no reported activity", className: "border-zinc-700 bg-zinc-800 text-zinc-400" };
  }
  if (acquired > disposed) {
    return {
      label: "net acquired over the last 4 quarters",
      className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
    };
  }
  if (disposed > acquired) {
    return {
      label: "net disposed over the last 4 quarters",
      className: "border-red-500/30 bg-red-500/10 text-red-400",
    };
  }
  return { label: "balanced", className: "border-amber-500/30 bg-amber-500/10 text-amber-400" };
}

export default function InsiderFlowCharts({ stats }: { stats?: InsiderQuarterStats[] }) {
  if (!stats?.length) {
    return (
      <p className="py-6 text-center text-sm text-zinc-600">
        No quarterly insider statistics available — pull a fresh analysis to fetch them.
      </p>
    );
  }

  // Oldest → newest so the trend reads left to right.
  const data = [...stats]
    .sort((a, b) => a.year - b.year || a.quarter - b.quarter)
    .map((s) => ({
      period: `${s.year} Q${s.quarter}`,
      acquired: s.total_acquired,
      disposed: -s.total_disposed,
      ratio: s.acquired_disposed_ratio,
    }));
  const v = verdict(stats);

  return (
    <div className="space-y-4">
      <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs ${v.className}`}>
        {v.label}
      </span>

      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-zinc-600">
          shares acquired vs disposed by quarter (all Form 4 activity)
        </p>
        <ResponsiveContainer width="100%" height={180}>
          <ComposedChart data={data} stackOffset="sign">
            <XAxis
              dataKey="period"
              tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={54}
              tickFormatter={(v: number) => `${Math.round(Math.abs(v) / 1000)}k`}
            />
            <ReferenceLine y={0} stroke={CHART_DEFAULTS.gridColor} />
            <Bar dataKey="acquired" name="acquired" fill={CHART_DEFAULTS.bullishColor} fillOpacity={0.75} isAnimationActive={false} />
            <Bar dataKey="disposed" name="disposed" fill={CHART_DEFAULTS.bearishColor} fillOpacity={0.75} isAnimationActive={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: "#a1a1aa" }}
              formatter={(val, n) => [Math.abs(Number(val)).toLocaleString(), String(n)]}
            />
            <Legend wrapperStyle={{ fontSize: 10, color: CHART_DEFAULTS.textColor }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-zinc-600">
          acquired / disposed ratio (above 1 = more buying than selling)
        </p>
        <ResponsiveContainer width="100%" height={110}>
          <ComposedChart data={data}>
            <XAxis dataKey="period" tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }} tickLine={false} axisLine={false} width={40} />
            <ReferenceLine y={1} stroke={CHART_DEFAULTS.gridColor} strokeDasharray="3 3" />
            <Line
              type="monotone"
              dataKey="ratio"
              name="ratio"
              stroke={CHART_DEFAULTS.accentColor}
              strokeWidth={2}
              dot={{ r: 2 }}
              isAnimationActive={false}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: "#a1a1aa" }}
              formatter={(val) => [Number(val).toFixed(3), "ratio"]}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
