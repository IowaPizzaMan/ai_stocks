// Spec: specs/021-stock-page-redesign (FR-002a) — candlestick panels so bar
// structure matches what the Strat rule engine reads (inside/outside bars,
// candle color). Recharts has no native candlestick: we draw one with a range
// Bar ([low, high]) plus a custom shape for the wick and open/close body.
import {
  Bar,
  Cell,
  ComposedChart,
  ReferenceArea,
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
import { PANEL_LABELS, sliceForDisplay, type Timeframe } from "../../lib/strat/displayWindow";

interface CandleDatum extends OHLCVBar {
  range: [number, number];
  rising: boolean;
}

/** Draws one candle: a thin high–low wick behind an open–close body.
 * Recharts types custom shapes as `(props: unknown) => Element`, so the cast
 * to the props we actually rely on happens here. */
function Candle(props: unknown) {
  const { x, y, width, height, payload } = (props ?? {}) as {
    x: number;
    y: number;
    width: number;
    height: number;
    payload: CandleDatum;
  };
  if (!payload || height <= 0) return <g />;

  const { open, close, high, low, rising } = payload;
  const color = rising ? CHART_DEFAULTS.bullishColor : CHART_DEFAULTS.bearishColor;
  const span = high - low;
  // y/height cover the [low, high] range, so price → pixel is linear within it
  const toY = (price: number) => (span === 0 ? y : y + ((high - price) / span) * height);

  const bodyTop = toY(Math.max(open, close));
  const bodyBottom = toY(Math.min(open, close));
  const bodyHeight = Math.max(bodyBottom - bodyTop, 1); // doji still gets a line
  const bodyWidth = Math.max(width * 0.6, 1);
  const bodyX = x + (width - bodyWidth) / 2;
  const centerX = x + width / 2;

  return (
    <g>
      <line x1={centerX} x2={centerX} y1={y} y2={y + height} stroke={color} strokeWidth={1} />
      <rect
        className="candle-body"
        x={bodyX}
        y={bodyTop}
        width={bodyWidth}
        height={bodyHeight}
        fill={color}
      />
    </g>
  );
}

/** Tooltip date wording matches the candle's period (FR-004/FR-005) so a
 * monthly candle reads as a month, not an arbitrary date inside it. */
function formatPeriod(date: string, tf: Timeframe): string {
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  if (tf === "Y") return String(d.getFullYear());
  if (tf === "M") return d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  if (tf === "W") return `Week of ${d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function CandlestickChart({
  bars,
  timeframe,
  height = 200,
  showBroadeningFormations = true,
}: {
  bars: OHLCVBar[];
  timeframe: Timeframe;
  height?: number;
  /** BF zones rendered on the old TFC panels; kept so the redesign doesn't
   * quietly drop a Strat signal the charts used to show. */
  showBroadeningFormations?: boolean;
}) {
  if (!bars.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950/40 text-xs text-zinc-600"
        style={{ height }}
      >
        no price data
      </div>
    );
  }

  const displayed = sliceForDisplay(bars, timeframe, false);
  const data: CandleDatum[] = displayed.map((b) => ({
    ...b,
    range: [b.low, b.high],
    rising: b.close >= b.open,
  }));
  // Detection runs on full history, then clips to what's on screen.
  const bfZones = showBroadeningFormations
    ? clipZonesToDisplayWindow(detectBroadeningFormations(bars), displayed)
    : [];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data}>
        <XAxis
          dataKey="date"
          tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          minTickGap={30}
          tickFormatter={(d: string) =>
            timeframe === "Y" ? String(new Date(`${d}T00:00:00`).getFullYear()) : d.slice(0, 7)
          }
        />
        <YAxis
          orientation="right"
          tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          domain={["dataMin", "dataMax"]}
          width={50}
        />
        {bfZones.map((z) => (
          <ReferenceArea
            key={`${z.start}-${z.end}-${z.high}`}
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

        <Bar dataKey="range" shape={Candle} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.date} />
          ))}
        </Bar>
        <Tooltip
          cursor={{ fill: "#ffffff08" }}
          contentStyle={{
            backgroundColor: "#09090b",
            border: "1px solid #27272a",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: "#a1a1aa" }}
          labelFormatter={(label: string) => formatPeriod(label, timeframe)}
          formatter={(_v, _n, item) => {
            const p = (item as unknown as { payload: CandleDatum }).payload;
            return [`O ${p.open}  H ${p.high}  L ${p.low}  C ${p.close}`, PANEL_LABELS[timeframe] ?? ""];
          }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
