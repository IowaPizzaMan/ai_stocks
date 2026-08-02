# frontend/src/components/shared/MetricCard.tsx

## Purpose
Single metric tile (label + value + trend arrow) that colors itself based on where the value sits within that metric's typical range — a heat scale from ice blue (low) to red (high), so a whole grid of ratios reads at a glance. Used by `FundamentalsTab`'s Key Ratio Cards grid, and any other metrics grid going forward (institutional, macro, insider dashboards can adopt the same component).

## Props
```typescript
interface MetricCardProps {
  metricKey: MetricKey        // e.g. 'pe_ttm', 'debt_equity' — looks up the range + formatter
  label: string                // display label, e.g. "P/E (TTM)"
  value: number | null
  trend?: 'up' | 'down' | 'flat'   // vs prior year, optional
}
```

## Color Scale
Value is normalized to its position within `METRIC_RANGES[metricKey]` (0 = low end, 1 = high end), then bucketed into 5 bands. This is a pure magnitude scale — low raw value is always ice blue and high raw value is always red for that metric, independent of whether "high" happens to be fundamentally good or bad for that particular ratio. That keeps the read consistent across a grid where some metrics are "lower is cheaper" (P/E, EV/EBITDA, Debt/Equity) and others are "higher is stronger" (Gross Margin, ROE/ROIC, FCF Yield) — the color always just says "this number is toward the hot/high end of its normal range," and the label tells you what that means.

```typescript
// lib/constants.ts
export const METRIC_RANGES: Record<MetricKey, { min: number; max: number; format: 'ratio' | 'pct' | 'x' }> = {
  pe_ttm:       { min: 5,   max: 60,  format: 'x' },      // <8 ice blue, >45 red
  ev_ebitda:    { min: 4,   max: 30,  format: 'x' },
  fcf_yield:    { min: -5,  max: 15,  format: 'pct' },
  debt_equity:  { min: 0,   max: 3,   format: 'x' },
  gross_margin: { min: 10,  max: 80,  format: 'pct' },
  roe_roic:     { min: -10, max: 40,  format: 'pct' },
}

const BANDS = [
  { max: 0.20, bg: 'bg-sky-500/15',   text: 'text-sky-300',   border: 'border-sky-500/30' },   // ice blue — low end
  { max: 0.40, bg: 'bg-cyan-500/10',  text: 'text-cyan-300',  border: 'border-cyan-500/20' },
  { max: 0.60, bg: 'bg-slate-800',    text: 'text-slate-300', border: 'border-slate-700' },     // neutral — mid range
  { max: 0.80, bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30' },
  { max: 1.01, bg: 'bg-red-500/15',   text: 'text-red-400',   border: 'border-red-500/30' },    // hot — high end
]

export function getMetricBand(metricKey: MetricKey, value: number | null) {
  if (value == null) return BANDS[2]   // no data → neutral
  const { min, max } = METRIC_RANGES[metricKey]
  const pct = Math.min(Math.max((value - min) / (max - min), 0), 1)
  return BANDS.find(b => pct <= b.max)!
}
```

## Implementation
```tsx
import { METRIC_RANGES, getMetricBand } from '@/lib/constants'

export function MetricCard({ metricKey, label, value, trend }: MetricCardProps) {
  const band = getMetricBand(metricKey, value)
  const { format } = METRIC_RANGES[metricKey]
  const formatted = value == null
    ? '—'
    : format === 'pct' ? `${value.toFixed(1)}%`
    : format === 'x'   ? `${value.toFixed(1)}x`
    : value.toFixed(2)

  return (
    <div className={`rounded-xl border p-4 transition-colors ${band.bg} ${band.border}`}>
      <div className="text-xs text-slate-400 mb-1">{label}</div>
      <div className={`flex items-baseline gap-2`}>
        <span className={`text-2xl font-semibold ${band.text}`}>{formatted}</span>
        {trend && trend !== 'flat' && (
          <TrendArrow direction={trend} className="text-xs opacity-70" />
        )}
      </div>
    </div>
  )
}
```

## Notes
- Ranges in `METRIC_RANGES` are starting points (rough market-wide bounds) — tune per-sector later if a card reads wrong for e.g. utilities vs. growth tech, where "normal" P/E differs a lot.
- `value == null` (no data) renders the neutral slate band rather than defaulting to either extreme.
- Same band function can back a legend/key if useful: ice blue → cyan → slate → amber → red, left to right.

## Dependencies
- `lib/constants.ts` (`METRIC_RANGES`, `getMetricBand`, `MetricKey` type)
- `TrendArrow` (existing shared icon component)
