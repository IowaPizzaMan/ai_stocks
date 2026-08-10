# frontend/src/components/stock/TFCChartGrid.tsx

## Purpose
Replaces the single hero chart on `StockDetail` with 4 `PriceChart` panels shown at once, defaulted to **1D / 1W / 1M / 1Y**. This follows the Strat's rule to "always analyze at least 4 charts for any instrument" (`the-strat-spec.md` → "Time Frame Continuity (TFC)") — seeing all four side by side is what lets you read Time Frame Continuity (are the major participation groups confirming or in conflict?) at a glance, and each panel auto-draws its own broadening formation levels.

## Props
```typescript
interface TFCChartGridProps {
  ticker: string
  priceData: Record<Timeframe, OHLCVBar[]>   // pre-fetched per resolution, see PriceChart.md "Bar Resolution per Timeframe"
  signals?: PriceChartProps['signals']
}
```

## Layout
2×2 grid, each cell a `compact` `PriceChart` locked to its own default timeframe (user can still change an individual panel's timeframe via its own toggle if `compact` is turned off for that cell — default is toggles hidden to keep the grid dense):

```
┌─────────────────────────┬─────────────────────────┐
│  1D            ● green  │  1W            ● green  │
│  [compact PriceChart]   │  [compact PriceChart]   │
├─────────────────────────┼─────────────────────────┤
│  1M            ● red    │  1Y            ● green  │
│  [compact PriceChart]   │  [compact PriceChart]   │
└─────────────────────────┴─────────────────────────┘
        [TFC banner: "Conflict — 1M red vs. 1D/1W/1Y green"]
```

## Implementation
```tsx
import { PriceChart } from './PriceChart'
import { getTfcColor, getFullTfcState } from '@/lib/strat/tfc'

const PANELS: { tf: Timeframe; label: string }[] = [
  { tf: '1D', label: '1D' },
  { tf: '1W', label: '1W' },
  { tf: '1M', label: '1M' },
  { tf: '1Y', label: '1Y' },
]

export function TFCChartGrid({ ticker, priceData, signals }: TFCChartGridProps) {
  const colors = PANELS.map(p => ({ tf: p.tf, color: getTfcColor(priceData[p.tf]) }))
  const fullState = getFullTfcState(colors.map(c => c.color))   // 'bullish' | 'bearish' | 'conflict'

  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        {PANELS.map(({ tf, label }) => {
          const color = colors.find(c => c.tf === tf)!.color
          return (
            <div key={tf} className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-slate-400">{label}</span>
                <span className={`w-2 h-2 rounded-full ${color === 'green' ? 'bg-green-400' : 'bg-red-400'}`} />
              </div>
              <PriceChart
                ticker={ticker}
                priceData={priceData[tf]}
                defaultTimeframe={tf}
                compact
                signals={signals}
              />
            </div>
          )
        })}
      </div>

      <TfcBanner state={fullState} colors={colors} />
    </div>
  )
}
```

## TFC Color + Full TFC State
Per `the-strat-spec.md` → "TFC State": for each panel, compare the last sale to the **open of that timeframe's own current bar** — today's open for the Daily panel, this week's open for the Weekly panel — not the open of the oldest bar in whatever history window happens to be fetched. So this reads off the *last* bar in the resolution-matched series (the still-forming or most-recently-closed bar for that resolution), not the first:

```typescript
// lib/strat/tfc.ts
export function getTfcColor(bars: OHLCVBar[]): 'green' | 'red' {
  if (!bars.length) return 'green'
  const current = bars[bars.length - 1]   // today's daily bar / this week's weekly bar / etc.
  return current.close >= current.open ? 'green' : 'red'
}

export function getFullTfcState(colors: ('green' | 'red')[]): 'bullish' | 'bearish' | 'conflict' {
  if (colors.every(c => c === 'green')) return 'bullish'
  if (colors.every(c => c === 'red')) return 'bearish'
  return 'conflict'
}
```

## TFC Banner
Below the grid, a single-line readout of the Strat's "Full TFC" concept:

```tsx
function TfcBanner({ state, colors }: { state: 'bullish'|'bearish'|'conflict', colors: { tf: Timeframe, color: 'green'|'red' }[] }) {
  if (state !== 'conflict') {
    return (
      <div className={`mt-3 text-sm px-3 py-2 rounded-lg ${state === 'bullish' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
        Full TFC {state === 'bullish' ? 'Bullish' : 'Bearish'} — 1D, 1W, 1M, and 1Y all confirming.
      </div>
    )
  }
  const dissenting = colors.filter((c, _, arr) => c.color !== arr[0].color).map(c => c.tf)
  return (
    <div className="mt-3 text-sm px-3 py-2 rounded-lg bg-amber-500/10 text-amber-400">
      In Conflict — {dissenting.join(', ')} not confirming the others. Expect chop; be cautious per the Strat's TFC rules.
    </div>
  )
}
```

## Note on Strat Alignment
The Strat's canonical 4 major participation groups are Monthly / Weekly / Daily / 60-minute, not 1D/1W/1M/1Y. This grid renders 1D as daily candles and 1W as weekly candles (see `PriceChart.md` → "Bar Resolution per Timeframe"), so the panel labels read a little differently than the Strat's own terminology: the "1D" panel is really "the Daily participation group's chart" (many daily candles, not a single day), and "1W" is "the Weekly participation group's chart." That maps cleanly to 3 of the Strat's 4 groups (Daily, Weekly, Monthly via the 1M panel); the 60-minute group isn't represented here — add a 5th intraday panel later if that's needed.

The `Full TFC` banner text itself is driven by `tfcStatus` (`strat_result.tfc.status`), computed backend-side by `skills/the_strat.py` — see `the-strat-spec.md` → "TFC State" → "Implementation note (this app)". That computation covers **Weekly/Monthly/Quarterly/Yearly** — Daily is deliberately excluded from alignment (too noisy to flip "all participation groups agree" on its own), and Quarterly/Yearly (neither of which has its own panel here) are included. So the visible panels and the alignment groups aren't the same set in either direction: the "1D" panel shown here plays no part in the banner status at all, while Quarterly/Yearly can flip the banner to "In Conflict" with no panel of their own to point to.

Daily isn't dropped from the payload, though — `strat_result.daily_notable_candle` (non-null when Daily prints a hammer/shooter/outside bar/kicking/reversal) is a separate callout, independent of the alignment status; see `TechnicalsTab.md` for where that's meant to surface. If the panel/alignment mismatch is confusing in practice, either add Quarterly/Yearly panels, or drop the visual emphasis on the 1D panel's color dot (it's not part of the alignment check) and surface `daily_notable_candle` as its own line instead.

## Dependencies
- `PriceChart` (compact mode) — each panel inherits the full MA overlay (EMA 8/21/50/200, SMA 10/30/90) and broadening formation zones by default
- `lib/strat/tfc.ts`
- `lib/strat/broadeningFormations.ts` (via `PriceChart`)
- `lib/strat/movingAverages.ts` (via `PriceChart`)
