# frontend/src/components/stock/RateOfChangeChart.tsx

## Purpose
Momentum oscillator pane — percentage rate of change over a lookback period, for either price or volume. Not derived from a specific numbered rule in the strategy specs (none of them define a formal ROC calculation); it's a standard supporting indicator that gives a numeric readout of the momentum the Strat only classifies qualitatively (momentum vs. retracement, per `the-strat-spec.md` → "Inside Bars (Detailed)"). Sits beneath `PriceChart` (and beneath `VolumeChart`, if shown) sharing the same x-axis/timeframe.

## Props
```typescript
interface RateOfChangeChartProps {
  bars: OHLCVBar[]
  metric: 'price' | 'volume'
  period?: number        // lookback bars, default 10
  compact?: boolean      // default false
}
```

## Calculation
```typescript
// lib/strat/rateOfChange.ts
export function computeROC(bars: OHLCVBar[], metric: 'price' | 'volume', period = 10): (number | null)[] {
  const values = bars.map(b => metric === 'price' ? b.close : b.volume)
  return values.map((v, i) => {
    if (i < period) return null
    const prior = values[i - period]
    if (!prior) return null
    return ((v - prior) / prior) * 100
  })
}
```

## Implementation
```tsx
import { ComposedChart, Area, ReferenceLine, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { CHART_DEFAULTS } from '@/lib/constants'
import { computeROC } from '@/lib/strat/rateOfChange'

export function RateOfChangeChart({ bars, metric, period = 10, compact = false }: RateOfChangeChartProps) {
  const roc = computeROC(bars, metric, period)
  const data = bars.map((b, i) => ({ date: b.date, roc: roc[i] }))
  const label = metric === 'price' ? `Price ROC (${period})` : `Volume ROC (${period})`

  return (
    <div>
      {!compact && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>{label}</div>}
      <ResponsiveContainer width="100%" height={compact ? 60 : 90}>
        <ComposedChart data={data}>
          {!compact && <XAxis dataKey="date" tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }} tickLine={false} axisLine={false} />}
          {!compact && <YAxis tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }} tickLine={false} axisLine={false} width={40} />}
          <ReferenceLine y={0} stroke={CHART_DEFAULTS.textColor} strokeOpacity={0.4} />
          <Area
            type="monotone"
            dataKey="roc"
            stroke={metric === 'price' ? CHART_DEFAULTS.accentColor : CHART_DEFAULTS.volumeColor}
            fill={(d: any) => (d.roc >= 0 ? CHART_DEFAULTS.bullishColor : CHART_DEFAULTS.bearishColor)}
            fillOpacity={0.15}
            dot={false}
          />
          {!compact && (
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }}
              formatter={(v: number) => [`${v?.toFixed(1)}%`, label]}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
```

Note: Recharts' `Area` doesn't natively split fill color above/below a threshold from a single series — if a true two-tone fill is wanted (green above zero, red below), use two overlaid `Area`s each clipped with a `<defs>` `linearGradient`/`clipPath` at the zero crossing, or fall back to a single-tone line with the zero `ReferenceLine` doing the visual work (simpler, matches the mockup). Start with the simple version; revisit if the two-tone fill is worth the complexity.

## Dependencies
- `recharts`
- `lib/strat/rateOfChange.ts`
