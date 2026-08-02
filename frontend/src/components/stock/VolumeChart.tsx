// Volume pane stacked beneath PriceChart — bars colored by candle direction,
// with a 20-bar volume SMA line (the relative-volume baseline).
import {
  Bar,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { OHLCVBar } from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";

export default function VolumeChart({ bars, compact = false }: { bars: OHLCVBar[]; compact?: boolean }) {
  const data = bars.map((b, i) => {
    const start = Math.max(0, i - 19);
    const window = bars.slice(start, i + 1);
    const volSma20 =
      i >= 19 ? window.reduce((a, x) => a + x.volume, 0) / window.length : null;
    return { ...b, volSma20 };
  });

  return (
    <ResponsiveContainer width="100%" height={compact ? 60 : 90}>
      <ComposedChart data={data}>
        <XAxis dataKey="date" hide />
        <YAxis
          orientation="right"
          tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }}
          tickLine={false}
          axisLine={false}
          width={50}
          tickFormatter={(v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(0)}M` : `${(v / 1e3).toFixed(0)}K`)}
        />
        <Bar dataKey="volume" isAnimationActive={false}>
          {data.map((b) => (
            <Cell
              key={b.date}
              fill={b.close >= b.open ? CHART_DEFAULTS.bullishColor : CHART_DEFAULTS.bearishColor}
              opacity={0.45}
            />
          ))}
        </Bar>
        <Line type="monotone" dataKey="volSma20" stroke="#facc15" strokeWidth={1} dot={false} connectNulls isAnimationActive={false} />
        <Tooltip
          contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 11 }}
          labelStyle={{ color: "#a1a1aa" }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
