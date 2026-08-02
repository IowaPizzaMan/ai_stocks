// Spec: specs/component-specs/frontend/components/stock/PriceChart.md
import { Fragment, useState } from "react";
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
import { CHART_DEFAULTS } from "../../lib/constants";
import {
  clipZonesToDisplayWindow,
  detectBroadeningFormations,
} from "../../lib/strat/broadeningFormations";
import { sliceForDisplay, type Timeframe } from "../../lib/strat/displayWindow";
import { computeMovingAverages, MOVING_AVERAGES } from "../../lib/strat/movingAverages";
import RateOfChangeChart from "./RateOfChangeChart";
import VolumeChart from "./VolumeChart";

const TIMEFRAMES: Timeframe[] = ["1D", "1W", "1M", "1Y", "5Y", "MAX"];

interface SignalMarker {
  date: string;
  type: "bullish" | "bearish";
  label: string;
}

interface PriceChartProps {
  priceData: OHLCVBar[];
  defaultTimeframe?: Timeframe;
  compact?: boolean;
  signals?: SignalMarker[];
  showBroadeningFormations?: boolean;
  showMovingAverages?: boolean;
  showVolumePane?: boolean;
  showRateOfChangePanes?: boolean;
  onTimeframeChange?: (tf: Timeframe) => void;
}

export default function PriceChart({
  priceData,
  defaultTimeframe = "1Y",
  compact = false,
  signals,
  showBroadeningFormations = true,
  showMovingAverages = true,
  showVolumePane,
  showRateOfChangePanes,
  onTimeframeChange,
}: PriceChartProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>(defaultTimeframe);
  const volumePane = showVolumePane ?? !compact;
  const rocPanes = showRateOfChangePanes ?? !compact;

  if (!priceData.length) {
    return (
      <div className={`flex items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 text-xs text-zinc-600 ${compact ? "h-44" : "h-72"}`}>
        no price data
      </div>
    );
  }

  // MAs + BF detection run on FULL history; display slicing happens after
  const withMAs = showMovingAverages ? computeMovingAverages(priceData) : priceData;
  const filtered = sliceForDisplay(withMAs, timeframe, compact);
  const bfZones = showBroadeningFormations
    ? clipZonesToDisplayWindow(detectBroadeningFormations(priceData), filtered as OHLCVBar[])
    : [];

  const handleTimeframe = (tf: Timeframe) => {
    setTimeframe(tf);
    onTimeframeChange?.(tf);
  };

  return (
    <div>
      {!compact && (
        <div className="mb-3 flex gap-1.5">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => handleTimeframe(tf)}
              className={`rounded px-3 py-1 text-xs transition-colors ${
                timeframe === tf
                  ? "bg-sky-600 text-white"
                  : "text-zinc-400 hover:bg-zinc-800 hover:text-white"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      )}

      <ResponsiveContainer width="100%" height={compact ? 180 : 300}>
        <ComposedChart data={filtered}>
          <XAxis
            dataKey="date"
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            minTickGap={40}
          />
          <YAxis
            yAxisId="price"
            orientation="right"
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            domain={["auto", "auto"]}
            width={50}
          />
          <YAxis yAxisId="volume" orientation="left" hide />

          <Bar yAxisId="volume" dataKey="volume" fill={CHART_DEFAULTS.volumeColor} opacity={0.5} isAnimationActive={false} />

          <Area
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke={CHART_DEFAULTS.accentColor}
            fill={`${CHART_DEFAULTS.accentColor}15`}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />

          {showMovingAverages &&
            MOVING_AVERAGES.map((ma) => (
              <Line
                key={ma.key}
                yAxisId="price"
                type="monotone"
                dataKey={ma.key}
                stroke={ma.color}
                strokeWidth={compact ? 1 : 1.5}
                strokeDasharray={ma.style === "dashed" ? "4 3" : undefined}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            ))}

          {bfZones.map((z) => (
            <ReferenceArea
              key={`${z.start}-${z.end}-${z.high}`}
              yAxisId="price"
              x1={z.start}
              x2={z.end}
              y1={z.low}
              y2={z.high}
              fill={z.active ? CHART_DEFAULTS.bfActiveColor : CHART_DEFAULTS.bfPriorColor}
              fillOpacity={z.active ? 0.08 : 0.04}
              stroke={z.active ? CHART_DEFAULTS.bfActiveColor : CHART_DEFAULTS.bfPriorColor}
              strokeOpacity={z.active ? 0.5 : 0.25}
              strokeDasharray={z.active ? undefined : "2 3"}
            />
          ))}
          {!compact &&
            bfZones
              .filter((z) => z.active)
              .map((z) => (
                <Fragment key={`labels-${z.start}-${z.high}`}>
                  <ReferenceLine
                    yAxisId="price"
                    y={z.high}
                    stroke={CHART_DEFAULTS.bfActiveColor}
                    strokeDasharray="3 3"
                    label={{ value: "BF High", position: "right", fontSize: 9, fill: CHART_DEFAULTS.bfActiveColor }}
                  />
                  <ReferenceLine
                    yAxisId="price"
                    y={z.low}
                    stroke={CHART_DEFAULTS.bfActiveColor}
                    strokeDasharray="3 3"
                    label={{ value: "BF Low", position: "right", fontSize: 9, fill: CHART_DEFAULTS.bfActiveColor }}
                  />
                </Fragment>
              ))}

          {signals?.map((s) => (
            <ReferenceLine
              key={s.date}
              x={s.date}
              yAxisId="price"
              stroke={s.type === "bullish" ? CHART_DEFAULTS.bullishColor : CHART_DEFAULTS.bearishColor}
              strokeDasharray="3 3"
            />
          ))}

          <Tooltip
            contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#a1a1aa" }}
            itemStyle={{ color: "#e4e4e7" }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {!compact && showMovingAverages && (
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-zinc-500">
          {MOVING_AVERAGES.map((ma) => (
            <span key={ma.key} className="flex items-center gap-1">
              <span className="inline-block h-0.5 w-3" style={{ backgroundColor: ma.color }} />
              {ma.type.toUpperCase()} {ma.period}
            </span>
          ))}
        </div>
      )}

      {volumePane && (
        <div className="mt-1">
          <VolumeChart bars={filtered as OHLCVBar[]} compact={compact} />
        </div>
      )}
      {rocPanes && (
        <div className="mt-1 grid grid-cols-2 gap-2">
          <RateOfChangeChart bars={filtered as OHLCVBar[]} metric="price" />
          <RateOfChangeChart bars={filtered as OHLCVBar[]} metric="volume" />
        </div>
      )}
    </div>
  );
}
