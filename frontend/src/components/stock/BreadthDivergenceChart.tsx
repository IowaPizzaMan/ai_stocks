// Spec: specs/component-specs/frontend/components/stock/BreadthDivergenceChart.md
//
// Two stacked panes on one date axis: SPY closes over the McClellan oscillator.
// The oscillator pane carries both NYMO and NAMO as two lines on one shared
// ±60 scale (specs/026-macro-market-dashboard, Q2) so the two exchanges read
// as a comparison, not two separate boxes. The divergence is drawn, not just
// described — it's measured against NYMO only (market_flow_rules.md §4), so
// its swing anchors and dashed trend line sit on the NYMO line specifically.
// Ticker-independent by design (SPY + breadth only), so it also backs the
// market-flow feed card.
import { type ReactNode } from "react";
import {
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  BreadthPoint,
  Divergence,
  DivergenceAnchor,
  MarketBreadth,
  ResolvedDivergence,
  SpyPoint,
} from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";

const OSC_BAND = 60; // market_flow_rules.md §1 overbought/oversold boundary
const AXIS_WIDTH = 48; // identical on both panes so the date axes line up

const DIVERGENCE_COLOR = {
  bullish: CHART_DEFAULTS.bullishColor,
  bearish: CHART_DEFAULTS.warningColor,
  none: CHART_DEFAULTS.textColor,
} as const;

type Zone = "oversold" | "overbought";
interface ZoneBand {
  start: string;
  end: string;
  zone: Zone;
}

/** Contiguous runs where the oscillator closed beyond ±60 — the price pane
 *  tints these so the "opportunity zone" is visible against price. */
export function zoneBands(series: BreadthPoint[]): ZoneBand[] {
  const bands: ZoneBand[] = [];
  let open: ZoneBand | null = null;

  for (const point of series) {
    const zone: Zone | null =
      point.value <= -OSC_BAND ? "oversold" : point.value >= OSC_BAND ? "overbought" : null;
    if (open && open.zone === zone) {
      open.end = point.date;
      continue;
    }
    if (open) bands.push(open);
    open = zone ? { start: point.date, end: point.date, zone } : null;
  }
  if (open) bands.push(open);
  return bands;
}

/** One row per date across all three series so the panes share exact categories. */
export function mergeSeries(spy: SpyPoint[], nymo: BreadthPoint[], namo: BreadthPoint[]) {
  const closes = new Map(spy.map((p) => [p.date, p.close]));
  const nymoValues = new Map(nymo.map((p) => [p.date, p.value]));
  const namoValues = new Map(namo.map((p) => [p.date, p.value]));
  const dates = [...new Set([...closes.keys(), ...nymoValues.keys(), ...namoValues.keys()])].sort();
  return dates.map((date) => ({
    date,
    close: closes.get(date) ?? null,
    nymo: nymoValues.get(date) ?? null,
    namo: namoValues.get(date) ?? null,
  }));
}

/** Nearest charted session at or after `target`. The daily breadth run resolves
 *  divergences on whatever day it fires — including weekends and holidays,
 *  which have no bar — so requiring an exact match would silently drop those
 *  markers. Resolutions predating the window get none, rather than being
 *  pinned to the left edge where they'd read as having happened there.
 *  `dates` must be sorted ascending. */
export function snapToChartDate(dates: string[], target: string): string | null {
  if (!dates.length || target < dates[0]) return null;
  return dates.find((d) => d >= target) ?? dates[dates.length - 1];
}

function formatChange(pct: number | null): string {
  if (pct == null) return "pending";
  return `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

/** ▲/▼ glyph marking where a past divergence resolved, with the follow-through
 *  in a native SVG tooltip — how the signal has actually paid off recently. */
function ResolutionMarker({
  cx,
  cy,
  entry,
}: {
  cx?: number;
  cy?: number;
  entry: ResolvedDivergence;
}) {
  const bullish = entry.type === "bullish";
  return (
    <text
      x={cx}
      y={cy}
      textAnchor="middle"
      dominantBaseline="middle"
      fontSize={10}
      fill={DIVERGENCE_COLOR[entry.type]}
      opacity={0.85}
    >
      {bullish ? "▲" : "▼"}
      <title>
        {`${entry.type} divergence resolved ${entry.resolved}` +
          ` (anchors ${entry.anchor_dates.join(" → ") || "n/a"})` +
          ` · SPY next 5d ${formatChange(entry.spy_change_5d)},` +
          ` 10d ${formatChange(entry.spy_change_10d)}`}
      </title>
    </text>
  );
}

/** The divergence overlay for one pane: the dashed swing-to-swing trend line
 *  plus its two anchor dots.
 *
 *  Returned as a flat array rather than a component — recharts discovers
 *  ReferenceLine/ReferenceDot by walking its own children, and anything nested
 *  inside a custom component is invisible to it (renders nothing at all). */
function divergenceOverlay(
  points: DivergenceAnchor[],
  yAxisId: string,
  color: string,
): ReactNode[] {
  if (points.length < 2) return [];
  return [
    <ReferenceLine
      key={`${yAxisId}-trend`}
      yAxisId={yAxisId}
      stroke={color}
      strokeWidth={1.5}
      strokeDasharray="5 3"
      ifOverflow="extendDomain"
      segment={[
        { x: points[0].date, y: points[0].value },
        { x: points[1].date, y: points[1].value },
      ]}
    />,
    ...points.map((p) => (
      <ReferenceDot
        key={`${yAxisId}-${p.date}`}
        yAxisId={yAxisId}
        x={p.date}
        y={p.value}
        r={3.5}
        fill={color}
        stroke="#09090b"
        strokeWidth={1}
        ifOverflow="extendDomain"
      />
    )),
  ];
}

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

export default function BreadthDivergenceChart({
  breadth,
  compact = false,
}: {
  breadth: MarketBreadth;
  compact?: boolean;
}) {
  const divergence: Divergence = breadth.divergence;

  if (!breadth.nymo.length || !breadth.spy.length) {
    return (
      <div className="flex h-28 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-xs text-zinc-600">
        no breadth data yet — the agent-runner computes it once a day
      </div>
    );
  }

  const data = mergeSeries(breadth.spy, breadth.nymo, breadth.namo);
  // Zone shading tracks NYMO — the primary signal (market_flow_rules.md §4)
  // and the series divergences are actually measured against.
  const bands = zoneBands(breadth.nymo);
  const color = DIVERGENCE_COLOR[divergence.type];
  const showDivergence = divergence.type !== "none";
  const closeByDate = new Map(breadth.spy.map((p) => [p.date, p.close]));
  // A marker can only sit on a date the axis has a category for, so snap each
  // resolution to the nearest charted session.
  const chartDates = [...closeByDate.keys()];
  const markers = compact
    ? []
    : breadth.divergence_history
        .map((entry) => ({ entry, date: snapToChartDate(chartDates, entry.resolved) }))
        .filter((m): m is { entry: ResolvedDivergence; date: string } => m.date !== null);

  return (
    <div>
      {!compact && (
        <p className="mb-1 text-[10px] uppercase tracking-wide text-zinc-600">
          SPY vs NYMO / NAMO
        </p>
      )}

      <ResponsiveContainer width="100%" height={compact ? 80 : 130}>
        <ComposedChart data={data} margin={{ top: 6, right: 0, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" hide />
          <YAxis
            yAxisId="price"
            orientation="right"
            domain={["auto", "auto"]}
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            width={AXIS_WIDTH}
          />

          {bands.map((b) => (
            <ReferenceArea
              key={`${b.zone}-${b.start}`}
              yAxisId="price"
              x1={b.start}
              x2={b.end}
              fill={
                b.zone === "oversold"
                  ? CHART_DEFAULTS.bullishColor
                  : CHART_DEFAULTS.warningColor
              }
              fillOpacity={0.07}
            />
          ))}

          <Line
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke={CHART_DEFAULTS.accentColor}
            strokeWidth={1.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
            name="SPY"
          />

          {showDivergence && divergenceOverlay(divergence.price_points, "price", color)}

          {markers.map(({ entry, date }) => (
            <ReferenceDot
              key={`marker-${entry.resolved}`}
              yAxisId="price"
              x={date}
              y={closeByDate.get(date)}
              shape={<ResolutionMarker entry={entry} />}
            />
          ))}

          <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [`$${Number(v).toFixed(2)}`, "SPY"]} />
        </ComposedChart>
      </ResponsiveContainer>

      <ResponsiveContainer width="100%" height={compact ? 70 : 110}>
        <ComposedChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="date"
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            minTickGap={40}
          />
          <YAxis
            yAxisId="osc"
            orientation="right"
            // Auto-fit the readings rather than always framing ±60: a typical
            // divergence is a few points of slope, and a fixed ±60 frame
            // flattens it into a straight line. The zone guides below come
            // into range on their own as the oscillator approaches them.
            domain={[
              (min: number) => Math.floor(min - 5),
              (max: number) => Math.ceil(max + 5),
            ]}
            tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            width={AXIS_WIDTH}
          />

          <ReferenceLine yAxisId="osc" y={0} stroke={CHART_DEFAULTS.gridColor} />
          <ReferenceLine
            yAxisId="osc"
            y={OSC_BAND}
            stroke={CHART_DEFAULTS.warningColor}
            strokeOpacity={0.35}
            strokeDasharray="2 3"
            label={{ value: "overbought", position: "insideTopLeft", fontSize: 8,
                     fill: CHART_DEFAULTS.warningColor, opacity: 0.7 }}
          />
          <ReferenceLine
            yAxisId="osc"
            y={-OSC_BAND}
            stroke={CHART_DEFAULTS.bullishColor}
            strokeOpacity={0.35}
            strokeDasharray="2 3"
            label={{ value: "oversold", position: "insideBottomLeft", fontSize: 8,
                     fill: CHART_DEFAULTS.bullishColor, opacity: 0.7 }}
          />

          <Line
            yAxisId="osc"
            type="monotone"
            dataKey="nymo"
            stroke={CHART_DEFAULTS.bfActiveColor}
            strokeWidth={1.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
            name="NYMO"
          />
          <Line
            yAxisId="osc"
            type="monotone"
            dataKey="namo"
            stroke={CHART_DEFAULTS.bfPriorColor}
            strokeWidth={1.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
            name="NAMO"
          />

          {showDivergence && divergenceOverlay(divergence.osc_points, "osc", color)}

          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(v, name) => [Number(v).toFixed(1), name as string]}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {divergence.type !== "none" && (
        <p className="mt-1 text-[11px]" style={{ color }}>
          {divergence.type === "bullish" ? "▲" : "▼"} {divergence.type} divergence —{" "}
          {divergence.description}
          {divergence.price_points.length === 2 && (
            <>
              {" "}
              (SPY {divergence.price_points[0].value} on {divergence.price_points[0].date} →{" "}
              {divergence.price_points[1].value} on {divergence.price_points[1].date}; NYMO{" "}
              {divergence.osc_points[0]?.value} → {divergence.osc_points[1]?.value})
            </>
          )}
        </p>
      )}
      {!compact && markers.length > 0 && (
        <p className="mt-0.5 text-[10px] text-zinc-600">
          ▲/▼ mark where past divergences resolved — hover for SPY's follow-through.
        </p>
      )}
    </div>
  );
}
