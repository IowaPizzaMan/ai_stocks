// Spec: specs/021-stock-page-redesign US5/US6 (FR-019, FR-020)
// One shared chart rendered on both the News and Sentiment tabs: bullish vs
// bearish language per date, with the net line making the drift obvious.
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
import type { NewsTrend, TimelinePoint } from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";

const TREND_STYLES: Record<NewsTrend, { label: string; className: string }> = {
  bullish: {
    label: "trending bullish",
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  },
  bearish: {
    label: "trending bearish",
    className: "border-red-500/30 bg-red-500/10 text-red-400",
  },
  mixed: {
    label: "mixed",
    className: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  },
};

export default function SentimentTimeline({
  timeline,
  trend,
  height = 180,
}: {
  timeline: TimelinePoint[];
  trend?: NewsTrend;
  height?: number;
}) {
  if (!timeline?.length) {
    return (
      <p className="py-6 text-center text-sm text-zinc-600">
        No dated news language to chart yet.
      </p>
    );
  }

  // Bearish plots downward so the two sides read as one net picture rather
  // than two stacks the eye has to subtract.
  const data = timeline.map((p) => ({
    ...p,
    bearishDown: -p.bearish,
    net: p.bullish - p.bearish,
  }));
  const style = trend ? TREND_STYLES[trend] : undefined;

  return (
    <div>
      {style && (
        <div className="mb-2 flex items-center gap-2">
          <span className={`rounded-full border px-2.5 py-0.5 text-xs ${style.className}`}>
            {style.label}
          </span>
          <span className="text-xs text-zinc-600">
            {timeline.reduce((a, p) => a + p.article_count, 0)} articles across {timeline.length}{" "}
            {timeline.length === 1 ? "day" : "days"}
          </span>
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} stackOffset="sign">
          <XAxis
            dataKey="date"
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            minTickGap={25}
          />
          <YAxis
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            width={32}
            tickFormatter={(v: number) => String(Math.abs(v))}
          />
          <ReferenceLine y={0} stroke={CHART_DEFAULTS.gridColor} />
          <Bar
            dataKey="bullish"
            name="bullish terms"
            fill={CHART_DEFAULTS.bullishColor}
            fillOpacity={0.75}
            isAnimationActive={false}
          />
          <Bar
            dataKey="bearishDown"
            name="bearish terms"
            fill={CHART_DEFAULTS.bearishColor}
            fillOpacity={0.75}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="net"
            name="net tone"
            stroke={CHART_DEFAULTS.accentColor}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#09090b",
              border: "1px solid #27272a",
              borderRadius: 8,
              fontSize: 11,
            }}
            labelStyle={{ color: "#a1a1aa" }}
            formatter={(v, n) => [Math.abs(Number(v)), String(n)]}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: CHART_DEFAULTS.textColor }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
