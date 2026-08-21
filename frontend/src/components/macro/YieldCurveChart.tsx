// Spec: specs/026-macro-market-dashboard/contracts/macro-api.md,
//       specs/026-macro-market-dashboard/data-model.md §6
//
// The Treasury yield curve for the latest session, with month-ago/year-ago
// overlays. GET /market/treasury-curve already aligns current/month_ago/
// year_ago per maturity — this just draws it. A log-scale X axis is used
// deliberately: months run 1..360, and a linear axis would crush the entire
// short end (1M..2Y) into the first few pixels of the chart. `months` (not
// an evenly-spaced maturity category) is what makes the curve's actual shape
// — not just its ranking — visible.
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TreasuryCurve } from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";
import { formatYield, hasOverlay } from "../../lib/yieldCurve";

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

export default function YieldCurveChart({ data }: { data: TreasuryCurve }) {
  if (!data.session || data.curve.length === 0) {
    return (
      <div className="flex h-28 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-xs text-zinc-600">
        no yield curve data yet — the agent-runner computes it once a day
      </div>
    );
  }

  const showMonthAgo = hasOverlay(data.curve, "month_ago");
  const showYearAgo = hasOverlay(data.curve, "year_ago");
  const maturityByMonths = new Map(data.curve.map((p) => [p.months, p.maturity]));
  const monthTicks = data.curve.map((p) => p.months);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-wide text-zinc-600">Treasury yield curve</p>
        <span className="text-xs text-zinc-500">session {data.session}</span>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data.curve} margin={{ top: 6, right: 16, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="months"
            type="number"
            scale="log"
            domain={[1, 360]}
            ticks={monthTicks}
            tickFormatter={(months: number) => maturityByMonths.get(months) ?? ""}
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            width={40}
            domain={["auto", "auto"]}
          />

          <Line
            type="monotone"
            dataKey="current"
            stroke={CHART_DEFAULTS.accentColor}
            strokeWidth={2}
            dot={{ r: 2 }}
            connectNulls
            isAnimationActive={false}
            name="Current"
          />
          {showMonthAgo && (
            <Line
              type="monotone"
              dataKey="month_ago"
              stroke={CHART_DEFAULTS.bfActiveColor}
              strokeWidth={1.5}
              strokeDasharray="5 3"
              dot={false}
              connectNulls
              isAnimationActive={false}
              name="1 month ago"
            />
          )}
          {showYearAgo && (
            <Line
              type="monotone"
              dataKey="year_ago"
              stroke={CHART_DEFAULTS.bfPriorColor}
              strokeWidth={1.5}
              strokeDasharray="2 2"
              dot={false}
              connectNulls
              isAnimationActive={false}
              name="1 year ago"
            />
          )}

          <Legend wrapperStyle={{ fontSize: 10 }} formatter={(value) => value} />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(v, name) => [formatYield(Number(v)), name as string]}
            labelFormatter={(months: number) => maturityByMonths.get(months) ?? months}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
