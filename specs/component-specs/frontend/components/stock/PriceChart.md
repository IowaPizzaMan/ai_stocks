# frontend/src/components/stock/PriceChart.tsx

## Purpose
Interactive OHLCV price chart with volume bars overlaid. Supports 1D / 1W / 1M / 1Y / 5Y / MAX timeframe toggles, can auto-draw Strat broadening formation levels on top of price, and (in full/non-compact mode) stacks a dedicated volume pane and price/volume rate-of-change panes beneath it, all sharing the same x-axis and display window.

## Props
```typescript
interface PriceChartProps {
  ticker: string
  priceData: OHLCVBar[]           // fetched from analysis sub-report or a dedicated price endpoint
  defaultTimeframe?: Timeframe    // default '1Y' — lets callers (e.g. the TFC grid) preset each panel independently
  compact?: boolean               // smaller height + hides its own timeframe toggle row, for use inside a grid of charts
  signals?: {                     // optional: overlay signal timestamps on chart
    date: string
    type: 'bullish' | 'bearish'
    label: string
  }[]
  showBroadeningFormations?: boolean   // default true — overlay auto-detected BF levels per the-strat-spec.md
  showMovingAverages?: boolean          // default true — overlay the MAs used across the strategy specs, see below
  showVolumePane?: boolean              // default !compact — stacked VolumeChart beneath price, see VolumeChart.md
  showRateOfChangePanes?: boolean       // default !compact — stacked price + volume ROC panes, see RateOfChangeChart.md
  onTimeframeChange?: (tf: Timeframe) => void   // fires when the user clicks a toggle — lets a parent (e.g. StockDetail's deep-dive section) track which timeframe is active so it can feed the same value to StrategyInsightsPanel
}

type Timeframe = '1D' | '1W' | '1M' | '1Y' | '5Y' | 'MAX'
```

The compact panels inside `TFCChartGrid` deliberately default `showVolumePane`/`showRateOfChangePanes` off (via `compact`) to stay dense for the at-a-glance 4-chart TFC view. The full single chart on `StockDetail`'s "Deep dive" section (see `StockDetail.md` and `StrategyInsightsPanel.md`) is where these panes show by default.

## Implementation

Uses Recharts `ComposedChart` with two y-axes: one for price (line/area), one for volume (bar).

```tsx
import { ComposedChart, Area, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea } from 'recharts'
import { CHART_DEFAULTS } from '@/lib/constants'
import { detectBroadeningFormations, clipZonesToDisplayWindow } from '@/lib/strat/broadeningFormations'
import { computeMovingAverages, MOVING_AVERAGES } from '@/lib/strat/movingAverages'
import { VolumeChart } from './VolumeChart'
import { RateOfChangeChart } from './RateOfChangeChart'

const TIMEFRAMES: Timeframe[] = ['1D', '1W', '1M', '1Y', '5Y', 'MAX']

export function PriceChart({
  ticker, priceData, defaultTimeframe = '1Y', compact = false, signals,
  showBroadeningFormations = true, showMovingAverages = true,
  showVolumePane = !compact, showRateOfChangePanes = !compact,
  onTimeframeChange,
}: PriceChartProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>(defaultTimeframe)

  const handleTimeframeClick = (tf: Timeframe) => {
    setTimeframe(tf)
    onTimeframeChange?.(tf)
  }

  // priceData already carries enough history at the right resolution to compute
  // a real 200-period MA (see "Bar Resolution per Timeframe" below) — MAs are
  // computed against that full history FIRST, then the result is trimmed down
  // to a clean number of candles for on-screen display.
  const withMAs = showMovingAverages ? computeMovingAverages(priceData) : priceData
  const filtered = sliceForDisplay(withMAs, timeframe, compact)

  // Same pattern as MAs: detect broadening formations against the FULL
  // 200-candle history, not just the trimmed display window — a BF that
  // formed 120 candles back is still "in force" as a support/resistance
  // level today even though its origin bar has scrolled off screen. Detection
  // runs on priceData (unsliced), then the resulting zones are clipped down
  // to the visible date range for rendering. See "Broadening Formations" below.
  const bfZones = showBroadeningFormations
    ? clipZonesToDisplayWindow(detectBroadeningFormations(priceData), filtered)
    : []

  return (
    <div>
      {!compact && (
        <div className="flex gap-2 mb-4">
          {TIMEFRAMES.map(tf => (
            <button
              key={tf}
              onClick={() => handleTimeframeClick(tf)}
              className={`text-xs px-3 py-1 rounded ${timeframe === tf ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
            >
              {tf}
            </button>
          ))}
        </div>
      )}

      <ResponsiveContainer width="100%" height={compact ? 180 : 300}>
        <ComposedChart data={filtered}>
          <XAxis dataKey="date" tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis yAxisId="price" orientation="right" tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 11 }} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
          <YAxis yAxisId="volume" orientation="left" hide />

          {/* Volume bars — behind price, lighter color */}
          <Bar yAxisId="volume" dataKey="volume" fill={CHART_DEFAULTS.volumeColor} opacity={0.5} />

          {/* Price area */}
          <Area
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke={CHART_DEFAULTS.accentColor}
            fill={`${CHART_DEFAULTS.accentColor}15`}
            strokeWidth={2}
            dot={false}
          />

          {/* Moving averages — every MA referenced across the strategy specs, see "Moving Averages" below */}
          {showMovingAverages && MOVING_AVERAGES.map(ma => (
            <Line
              key={ma.key}
              yAxisId="price"
              type="monotone"
              dataKey={ma.key}
              stroke={ma.color}
              strokeWidth={compact ? 1 : 1.5}
              strokeDasharray={ma.style === 'dashed' ? '4 3' : undefined}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          ))}

          {/* Broadening formation zones — most recent solid, prior ones faint (former BF levels act as S/R per the-strat-spec.md) */}
          {bfZones.map((z, i) => (
            <ReferenceArea
              key={`${z.start}-${z.end}`}
              yAxisId="price"
              x1={z.start} x2={z.end}
              y1={z.low} y2={z.high}
              fill={z.active ? CHART_DEFAULTS.bfActiveColor : CHART_DEFAULTS.bfPriorColor}
              fillOpacity={z.active ? 0.08 : 0.04}
              stroke={z.active ? CHART_DEFAULTS.bfActiveColor : CHART_DEFAULTS.bfPriorColor}
              strokeOpacity={z.active ? 0.5 : 0.25}
              strokeDasharray={z.active ? undefined : '2 3'}
            />
          ))}
          {bfZones.filter(z => z.active).map(z => (
            <React.Fragment key={`labels-${z.start}`}>
              <ReferenceLine yAxisId="price" y={z.high} stroke={CHART_DEFAULTS.bfActiveColor} strokeDasharray="3 3" label={{ value: 'BF High', position: 'right', fontSize: 10, fill: CHART_DEFAULTS.bfActiveColor }} />
              <ReferenceLine yAxisId="price" y={z.low} stroke={CHART_DEFAULTS.bfActiveColor} strokeDasharray="3 3" label={{ value: 'BF Low', position: 'right', fontSize: 10, fill: CHART_DEFAULTS.bfActiveColor }} />
            </React.Fragment>
          ))}

          {/* Signal markers */}
          {signals?.map(s => (
            <ReferenceLine key={s.date} x={s.date} yAxisId="price" stroke={s.type === 'bullish' ? CHART_DEFAULTS.bullishColor : CHART_DEFAULTS.bearishColor} strokeDasharray="3 3" />
          ))}

          <Tooltip
            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }}
            labelStyle={{ color: '#94a3b8' }}
            itemStyle={{ color: '#e2e8f0' }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Stacked sub-panes — share the same `filtered` series so dates line up under the price pane above */}
      {showVolumePane && (
        <div style={{ marginTop: 4 }}>
          <VolumeChart bars={filtered} compact={compact} />
        </div>
      )}
      {showRateOfChangePanes && (
        <div style={{ marginTop: 4, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <RateOfChangeChart bars={filtered} metric="price" compact={compact} />
          <RateOfChangeChart bars={filtered} metric="volume" compact={compact} />
        </div>
      )}
    </div>
  )
}
```

## Bar Resolution per Timeframe
`1D` shows daily candles and `1W` shows weekly candles — each timeframe renders candles at its own native resolution rather than everything being sliced off one daily series:

| Timeframe | Bar resolution |
|---|---|
| 1D | Daily candles |
| 1W | Weekly candles |
| 1M | Daily candles |
| 1Y | Daily candles |
| 5Y | Weekly candles |
| MAX | Monthly candles |

`useStockPriceHistory(ticker, timeframe)` requests the matching resolution from the price endpoint. Per timeframe, it must fetch at least enough history to compute a real 200-period MA at that resolution — not just enough to fill the visible window:

| Timeframe | Resolution | History fetched | Reason |
|---|---|---|---|
| 1D | Daily | Last 200 trading days | Needed so EMA 200 (daily) is a real 200-day average, not truncated |
| 1W | Weekly | Last 200 weeks (~4 years) | Same reasoning, one resolution up |
| 1M | Daily | Last 200 trading days | Shares the 1D fetch |
| 1Y | Daily | Last ~260 trading days | Covers a full year plus MA lookback |
| 5Y | Weekly | Last 260 weeks | Covers 5 years plus MA lookback |
| MAX | Monthly | All available | No cutoff |

## Display Windowing (history vs. what's shown)
Fetching 200 daily bars to seed the moving averages doesn't mean the chart should render 200 candles — that's cramped and unreadable. `computeMovingAverages` runs across the **full fetched history** first (so every MA value is accurate), then `sliceForDisplay` trims the result down to a clean number of candles sized for the panel:

```typescript
// lib/strat/displayWindow.ts
const DISPLAY_COUNT: Record<Timeframe, { full: number; compact: number }> = {
  '1D':  { full: 90,  compact: 60 },   // last ~90 daily candles, computed off 200
  '1W':  { full: 78,  compact: 52 },   // last ~78 weekly candles (~1.5yr / ~1yr), computed off 200 weeks
  '1M':  { full: 30,  compact: 21 },
  '1Y':  { full: 252, compact: 180 },
  '5Y':  { full: 260, compact: 156 },
  'MAX': { full: 240, compact: 120 },
}

export function sliceForDisplay<T>(bars: T[], tf: Timeframe, compact: boolean): T[] {
  const count = compact ? DISPLAY_COUNT[tf].compact : DISPLAY_COUNT[tf].full
  return bars.slice(-count)
}
```

These counts are starting points, not hard rules — tune per actual candle width / container size so it "looks clean" rather than sparse or crowded; a `ResizeObserver`-driven count (candle width target of ~6–8px) is a reasonable follow-up if the fixed numbers above don't read well at all screen sizes.

## Broadening Formations (auto-drawn)

Implements the Strat's broadening formation detection (`the-strat-spec.md` → "Broadening Formations (Detailed)" and "Pattern Identification Reference"). Logic lives in `lib/strat/broadeningFormations.ts` so it's shared across all `PriceChart` instances (including the TFC grid — see `TFCChartGrid.md`).

Same two-stage pattern as the moving averages: `detectBroadeningFormations` runs against the **full fetched history** (the same 200-candle lookback used for MAs, not the trimmed display window), then the resulting zones are clipped down to whatever date range is actually on screen. This matters because a BF that formed well outside the visible window is still a real, currently-in-force support/resistance level — the strat spec explicitly says "as time passes, if price doesn't reclaim the previous range... look for a new BF to form, then line up the former BF level" — so its lines should still show even if the candle that created it has scrolled off screen.

```typescript
// lib/strat/broadeningFormations.ts
type Bar = { date: string; open: number; high: number; low: number; close: number }
type BFZone = { start: string; end: string; high: number; low: number; active: boolean }

function classifyBar(bar: Bar, prev: Bar): '1' | '2U' | '2D' | '3' {
  const higherHigh = bar.high > prev.high
  const lowerLow = bar.low < prev.low
  if (higherHigh && lowerLow) return '3'
  if (higherHigh) return '2U'
  if (lowerLow) return '2D'
  return '1'
}

/**
 * Every Outside Bar (3) IS a broadening formation (the-strat-spec.md, "Key Rules").
 * Walk the series, open a zone at each Outside Bar using its high/low, then
 * expand that zone's high/low as later bars extend it (new higher high or
 * lower low while it's still the active BF). Per the spec, redraw backward
 * from the most recent extremes whenever TFC changes (i.e. the running
 * bar's close-vs-open color flips), which starts a new zone and demotes the
 * old one to a "prior" zone (former BF levels become support/resistance).
 */
export function detectBroadeningFormations(bars: Bar[]): BFZone[] {
  const zones: BFZone[] = []
  let current: BFZone | null = null
  let lastTfcColor: 'green' | 'red' | null = null

  for (let i = 1; i < bars.length; i++) {
    const bar = bars[i]
    const prev = bars[i - 1]
    const type = classifyBar(bar, prev)
    const tfcColor = bar.close >= bar.open ? 'green' : 'red'

    if (type === '3') {
      if (current) { current.active = false; zones.push(current) }
      current = { start: bar.date, end: bar.date, high: bar.high, low: bar.low, active: true }
    } else if (current) {
      // Zone keeps expanding while price extends it in either direction
      if (bar.high > current.high) current.high = bar.high
      if (bar.low < current.low) current.low = bar.low
      current.end = bar.date
    }

    // TFC change (color flip) → close out and start fresh, drawn backward from
    // the most recent high/low per "Drawing Broadening Formations" in the spec
    if (current && lastTfcColor && tfcColor !== lastTfcColor) {
      current.end = bar.date
      zones.push({ ...current, active: false })
      current = { start: bar.date, end: bar.date, high: bar.high, low: bar.low, active: true }
    }
    lastTfcColor = tfcColor
  }

  if (current) zones.push(current)
  // Keep the most recent handful of zones only — older ones clutter the chart
  return zones.slice(-4)
}

/**
 * Detection ran on the full 200-candle history; the chart itself only shows
 * `filtered` (the display-windowed slice). Clip each zone's x-range down to
 * the visible date span so ReferenceArea/ReferenceLine don't try to draw
 * outside the chart's own x-domain:
 * - Zones that end before the visible window starts are dropped (fully
 *   scrolled off, no longer relevant to show).
 * - Zones that started before the window are clamped to start at the
 *   window's first visible date (the level still applies, just draw it from
 *   the left edge rather than off-screen).
 * - The active zone's right edge is extended to the window's last visible
 *   date — it's still open/in force, so it should run to "now."
 */
export function clipZonesToDisplayWindow(zones: BFZone[], visibleBars: Bar[]): BFZone[] {
  if (!visibleBars.length) return []
  const windowStart = visibleBars[0].date
  const windowEnd = visibleBars[visibleBars.length - 1].date

  return zones
    .filter(z => z.end >= windowStart)
    .map(z => ({
      ...z,
      start: z.start < windowStart ? windowStart : z.start,
      end: z.active ? windowEnd : (z.end > windowEnd ? windowEnd : z.end),
    }))
}
```

`CHART_DEFAULTS.bfActiveColor` / `bfPriorColor` should be visually distinct from the bullish/bearish signal colors already in use (e.g. violet for the active BF, dim slate for prior ones) so the three overlays (signals, BF zones, price) don't compete.

## Moving Averages (auto-overlaid)

Every moving average referenced anywhere in the strategy specs, pulled together so they show on every `PriceChart` instance rather than living in one place:

| MA | Source spec | Why it's there |
|---|---|---|
| EMA 8 | `agent-runner/tools/price.md` — `get_technical_indicators` | Short-term trend, feeds `TechnicalAnalyst` |
| EMA 21 | same | Short/medium trend |
| EMA 50 | same | Medium trend, golden/death cross with EMA 200 |
| EMA 200 | same | Long-term trend line |
| SMA 10 | `gap_analysis_rules.md` → "Moving Average Rules" | Gap-vs-SMA classification (Section 6) |
| SMA 30 | same | The key line in the rulebook — "down gap above 30-day SMA" is called the strongest LONG signal; also referenced in `market_flow_rules.md`'s NYMO/gap scoring |
| SMA 90 | same | Third leg of the 3-SMA gap framework |
| Volume SMA 20 | `agent-runner/tools/price.md` | Relative volume baseline — plotted on the **volume** axis, not price, since it's a volume MA not a price MA |

```typescript
// lib/strat/movingAverages.ts
export const MOVING_AVERAGES = [
  { key: 'ema8',   period: 8,   type: 'ema', color: '#f472b6', style: 'solid' },
  { key: 'ema21',  period: 21,  type: 'ema', color: '#facc15', style: 'solid' },
  { key: 'ema50',  period: 50,  type: 'ema', color: '#38bdf8', style: 'solid' },
  { key: 'ema200', period: 200, type: 'ema', color: '#a78bfa', style: 'solid' },
  { key: 'sma10',  period: 10,  type: 'sma', color: '#4ade80', style: 'dashed' },
  { key: 'sma30',  period: 30,  type: 'sma', color: '#fb923c', style: 'dashed' },
  { key: 'sma90',  period: 90,  type: 'sma', color: '#f87171', style: 'dashed' },
] as const

function sma(values: number[], period: number, i: number): number | null {
  if (i + 1 < period) return null
  const slice = values.slice(i + 1 - period, i + 1)
  return slice.reduce((a, b) => a + b, 0) / period
}

function ema(values: number[], period: number, i: number, prevEma: number | null): number | null {
  if (i + 1 < period) return null
  if (prevEma == null) return sma(values, period, i)   // seed with SMA
  const k = 2 / (period + 1)
  return values[i] * k + prevEma * (1 - k)
}

/**
 * Computes all 7 MAs against the full fetched history for whatever resolution
 * `bars` is already in (daily for 1D/1M/1Y, weekly for 1W/5Y, monthly for MAX —
 * see "Bar Resolution per Timeframe"). Since `priceData` is fetched with at
 * least 200 bars of lookback at that resolution, a 200-period EMA is a real
 * 200-bar average, not truncated. Display trimming happens separately, after
 * this — see `sliceForDisplay` in "Display Windowing" below.
 */
export function computeMovingAverages(bars: OHLCVBar[]): (OHLCVBar & Record<string, number | null>)[] {
  const closes = bars.map(b => b.close)
  const out = bars.map(b => ({ ...b } as OHLCVBar & Record<string, number | null>))
  for (const ma of MOVING_AVERAGES) {
    let prev: number | null = null
    for (let i = 0; i < bars.length; i++) {
      const v = ma.type === 'ema' ? ema(closes, ma.period, i, prev) : sma(closes, ma.period, i)
      out[i][ma.key] = v
      if (ma.type === 'ema') prev = v ?? prev
    }
  }
  return out
}
```

## MA Legend
Small legend row under the chart (or a corner overlay) mapping color → MA, since 7 lines on one chart gets busy — EMAs solid, SMAs dashed per `MOVING_AVERAGES[].style` above, so the two families are visually distinguishable even before reading the legend. Consider letting users toggle individual MAs on/off via the legend (click to hide/show that `dataKey`), since not everyone wants all 7 at once, but the default per this request is all on.

## Dependencies
- `recharts`
- `lib/strat/broadeningFormations.ts` (`detectBroadeningFormations`, `clipZonesToDisplayWindow`)
- `lib/strat/movingAverages.ts`
- `lib/strat/displayWindow.ts` (`sliceForDisplay`)
- `VolumeChart` (`VolumeChart.md`)
- `RateOfChangeChart` (`RateOfChangeChart.md`)
