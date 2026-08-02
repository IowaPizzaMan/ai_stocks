# frontend/src/components/stock/VolumeChart.tsx

## Purpose
Standalone volume pane — bars colored by day direction, with the Volume SMA 20 overlay (`agent-runner/tools/price.md`), and accumulation-spike days highlighted per `accumulation_volume_rules.md` Rule 3 (up day, volume ≥ 1.5x the 20-day average). Meant to sit directly beneath a `PriceChart` sharing the same x-axis/timeframe, not as a standalone page section.

## Props
```typescript
interface VolumeChartProps {
  bars: OHLCVBar[]        // same resolution + display window as the PriceChart above it
  compact?: boolean       // default false — shorter height, no axis labels
}
```

## Implementation
```tsx
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Line, ComposedChart } from 'recharts'
import { CHART_DEFAULTS } from '@/lib/constants'

function volumeSma20(bars: OHLCVBar[]): (number | null)[] {
  return bars.map((_, i) => {
    if (i + 1 < 20) return null
    const slice = bars.slice(i + 1 - 20, i + 1)
    return slice.reduce((a, b) => a + b.volume, 0) / 20
  })
}

export function VolumeChart({ bars, compact = false }: VolumeChartProps) {
  const avg20 = volumeSma20(bars)
  const data = bars.map((b, i) => ({ ...b, avgVol: avg20[i] }))

  return (
    <ResponsiveContainer width="100%" height={compact ? 70 : 100}>
      <ComposedChart data={data}>
        {!compact && <XAxis dataKey="date" tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }} tickLine={false} axisLine={false} />}
        {!compact && <YAxis tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }} tickLine={false} axisLine={false} width={40} />}

        <Bar dataKey="volume">
          {data.map((d, i) => {
            const isUpDay = d.close >= d.open
            const isSpike = d.avgVol != null && d.volume >= 1.5 * d.avgVol && isUpDay
            const fill = isSpike ? CHART_DEFAULTS.accumulationColor
              : isUpDay ? CHART_DEFAULTS.bullishColor
              : CHART_DEFAULTS.bearishColor
            return <Cell key={i} fill={fill} opacity={isSpike ? 0.9 : 0.45} />
          })}
        </Bar>

        <Line type="monotone" dataKey="avgVol" stroke={CHART_DEFAULTS.textColor} strokeWidth={1} dot={false} strokeDasharray="3 3" />

        {!compact && (
          <Tooltip
            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }}
            labelStyle={{ color: '#94a3b8' }}
            formatter={(v: number, name: string) => [v.toLocaleString(), name === 'avgVol' ? '20d avg' : 'Volume']}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  )
}
```

## Visual Rule
- Regular up day: `bullishColor` (dim)
- Regular down day: `bearishColor` (dim)
- Accumulation spike day (up day, volume ≥ 1.5x 20-day avg): a distinct brighter `accumulationColor` (e.g. teal) at full opacity, so institutional-buying days visibly pop out of the bar chart — this is the same threshold `StrategyInsightsPanel` uses to count "how many spike days in the last 20."

## Dependencies
- `recharts`
- `CHART_DEFAULTS.accumulationColor` (new token, teal — distinct from bullish green so a "regular up day" and an "accumulation day" don't read as the same thing)
