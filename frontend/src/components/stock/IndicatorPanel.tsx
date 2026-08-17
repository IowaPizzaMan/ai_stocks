// Spec: specs/021-stock-page-redesign US3 (FR-007, FR-008)
// One indicator rendered across its applicable timeframes so the same reading
// can be compared D→W→M→Y at a glance. MACD deliberately omits the yearly
// panel (see lib/indicators/macd.ts).
import {
  Area,
  Bar,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { OHLCVBar } from "../../api/types";
import { computeAtrPercent, ATR_WARMUP } from "../../lib/indicators/atrPercent";
import { computeMacd, MACD_WARMUP } from "../../lib/indicators/macd";
import {
  computeStochastic,
  OVERBOUGHT,
  OVERSOLD,
  STOCHASTIC_WARMUP,
} from "../../lib/indicators/stochastic";
import { computeZScore, ZSCORE_WARMUP } from "../../lib/indicators/zscore";
import { CHART_DEFAULTS } from "../../lib/constants";
import { PANEL_LABELS, PANEL_TIMEFRAMES, type Timeframe } from "../../lib/strat/displayWindow";

export type IndicatorKey = "macd" | "stochastic" | "atrPercent" | "zscore";

const META: Record<
  IndicatorKey,
  { title: string; blurb: string; warmup: number; timeframes: Timeframe[] }
> = {
  zscore: {
    title: "Z-score",
    blurb: "close vs its 20-period mean, in standard deviations",
    warmup: ZSCORE_WARMUP,
    timeframes: PANEL_TIMEFRAMES,
  },
  stochastic: {
    title: "Stochastic",
    blurb: "%K(14)/%D(3) — where price closed in its recent range",
    warmup: STOCHASTIC_WARMUP,
    timeframes: PANEL_TIMEFRAMES,
  },
  atrPercent: {
    title: "ATR %",
    blurb: "14-period average true range as a % of price",
    warmup: ATR_WARMUP,
    timeframes: PANEL_TIMEFRAMES,
  },
  macd: {
    title: "MACD",
    blurb: "12/26/9 — omitted on yearly, which would need ~35 years of history",
    warmup: MACD_WARMUP,
    // Yearly deliberately excluded (spec 021 clarification, 2026-08-16)
    timeframes: ["D", "W", "M"],
  },
};

const AXIS = { fill: CHART_DEFAULTS.textColor, fontSize: 9 };
const TOOLTIP_STYLE = {
  backgroundColor: "#09090b",
  border: "1px solid #27272a",
  borderRadius: 8,
  fontSize: 11,
};

function Insufficient({ warmup }: { warmup: number }) {
  return (
    <div className="flex h-[70px] items-center justify-center rounded bg-zinc-950/40 px-2 text-center text-[10px] leading-tight text-zinc-600">
      insufficient history — needs {warmup} bars
    </div>
  );
}

function IndicatorChart({
  indicator,
  bars,
}: {
  indicator: IndicatorKey;
  bars: OHLCVBar[];
}) {
  if (indicator === "macd") {
    const data = computeMacd(bars);
    return (
      <ResponsiveContainer width="100%" height={70}>
        <ComposedChart data={data}>
          <XAxis dataKey="date" hide />
          <YAxis orientation="right" tick={AXIS} tickLine={false} axisLine={false} width={38} />
          <ReferenceLine y={0} stroke={CHART_DEFAULTS.gridColor} />
          <Bar dataKey="histogram" fill={CHART_DEFAULTS.volumeColor} isAnimationActive={false} />
          <Line
            type="monotone"
            dataKey="macd"
            stroke={CHART_DEFAULTS.accentColor}
            strokeWidth={1.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="signal"
            stroke={CHART_DEFAULTS.warningColor}
            strokeWidth={1}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={{ color: "#a1a1aa" }}
            formatter={(v, n) => [typeof v === "number" ? v.toFixed(3) : "–", String(n)]}
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  if (indicator === "stochastic") {
    const data = computeStochastic(bars);
    return (
      <ResponsiveContainer width="100%" height={70}>
        <ComposedChart data={data}>
          <XAxis dataKey="date" hide />
          <YAxis
            orientation="right"
            domain={[0, 100]}
            ticks={[0, 50, 100]}
            tick={AXIS}
            tickLine={false}
            axisLine={false}
            width={38}
          />
          <ReferenceArea y1={OVERBOUGHT} y2={100} fill={CHART_DEFAULTS.bearishColor} fillOpacity={0.08} />
          <ReferenceArea y1={0} y2={OVERSOLD} fill={CHART_DEFAULTS.bullishColor} fillOpacity={0.08} />
          <Line
            type="monotone"
            dataKey="k"
            stroke={CHART_DEFAULTS.accentColor}
            strokeWidth={1.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="d"
            stroke={CHART_DEFAULTS.warningColor}
            strokeWidth={1}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={{ color: "#a1a1aa" }}
            formatter={(v, n) => [typeof v === "number" ? v.toFixed(1) : "–", String(n)]}
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  if (indicator === "atrPercent") {
    const data = computeAtrPercent(bars);
    return (
      <ResponsiveContainer width="100%" height={70}>
        <ComposedChart data={data}>
          <XAxis dataKey="date" hide />
          <YAxis orientation="right" tick={AXIS} tickLine={false} axisLine={false} width={38} />
          <Area
            type="monotone"
            dataKey="atrPct"
            stroke={CHART_DEFAULTS.bfActiveColor}
            fill={`${CHART_DEFAULTS.bfActiveColor}20`}
            strokeWidth={1.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={{ color: "#a1a1aa" }}
            formatter={(v) => [typeof v === "number" ? `${v.toFixed(2)}%` : "–", "ATR %"]}
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  const data = computeZScore(bars);
  return (
    <ResponsiveContainer width="100%" height={70}>
      <ComposedChart data={data}>
        <XAxis dataKey="date" hide />
        <YAxis orientation="right" tick={AXIS} tickLine={false} axisLine={false} width={38} />
        <ReferenceLine y={0} stroke={CHART_DEFAULTS.gridColor} />
        <ReferenceLine y={2} stroke={CHART_DEFAULTS.bearishColor} strokeDasharray="2 3" strokeOpacity={0.5} />
        <ReferenceLine y={-2} stroke={CHART_DEFAULTS.bullishColor} strokeDasharray="2 3" strokeOpacity={0.5} />
        <Line
          type="monotone"
          dataKey="zscore"
          stroke={CHART_DEFAULTS.accentColor}
          strokeWidth={1.5}
          dot={false}
          connectNulls
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          labelStyle={{ color: "#a1a1aa" }}
          formatter={(v) => [typeof v === "number" ? v.toFixed(2) : "–", "z-score"]}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export default function IndicatorPanel({
  indicator,
  priceData,
}: {
  indicator: IndicatorKey;
  priceData: Partial<Record<Timeframe, OHLCVBar[]>>;
}) {
  const meta = META[indicator];

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-2">
        <h3 className="text-sm font-medium text-zinc-200">{meta.title}</h3>
        <span className="text-[11px] text-zinc-500">{meta.blurb}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {meta.timeframes.map((tf) => {
          const bars = priceData[tf] ?? [];
          return (
            <div key={tf}>
              <p className="mb-0.5 text-[10px] uppercase tracking-wide text-zinc-600">
                {PANEL_LABELS[tf]}
              </p>
              {bars.length >= meta.warmup ? (
                <IndicatorChart indicator={indicator} bars={bars} />
              ) : (
                <Insufficient warmup={meta.warmup} />
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
