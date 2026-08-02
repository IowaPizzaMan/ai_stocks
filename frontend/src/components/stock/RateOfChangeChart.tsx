// Rate-of-change pane: bar-over-bar % change for price or volume.
import {
  Bar,
  Cell,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { OHLCVBar } from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";

export default function RateOfChangeChart({
  bars,
  metric,
}: {
  bars: OHLCVBar[];
  metric: "price" | "volume";
}) {
  const data = bars.map((b, i) => {
    if (i === 0) return { date: b.date, roc: 0 };
    const prev = metric === "price" ? bars[i - 1].close : bars[i - 1].volume;
    const cur = metric === "price" ? b.close : b.volume;
    return { date: b.date, roc: prev ? ((cur - prev) / prev) * 100 : 0 };
  });

  return (
    <div>
      <p className="mb-0.5 text-[10px] uppercase tracking-wide text-zinc-600">{metric} ROC %</p>
      <ResponsiveContainer width="100%" height={60}>
        <ComposedChart data={data}>
          <XAxis dataKey="date" hide />
          <YAxis
            orientation="right"
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <ReferenceLine y={0} stroke={CHART_DEFAULTS.gridColor} />
          <Bar dataKey="roc" isAnimationActive={false}>
            {data.map((d) => (
              <Cell
                key={d.date}
                fill={d.roc >= 0 ? CHART_DEFAULTS.bullishColor : CHART_DEFAULTS.bearishColor}
                opacity={0.5}
              />
            ))}
          </Bar>
          <Tooltip
            contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 11 }}
            labelStyle={{ color: "#a1a1aa" }}
            formatter={(v) => [`${Number(v).toFixed(2)}%`, "ROC"]}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
