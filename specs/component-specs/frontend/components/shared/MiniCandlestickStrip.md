# frontend/src/components/shared/MiniCandlestickStrip.tsx

## Purpose
Tiny inline candlestick strip (typically 5 candles) showing the actual price action around wherever a signal fired. Used by `StrategyInsightsPanel` so each narrative insight ("down gap closed back above the 30-day SMA") comes with a literal picture of the candles that made it true, not just the sentence. None of the other charts in the app draw real candlesticks (`PriceChart` uses a smoothed area for density reasons) — this is the one place actual OHLC bodies/wicks render, because at 5 candles there's room and the shape of the bar is the point.

## Props
```typescript
interface MiniCandlestickStripProps {
  bars: OHLCVBar[]           // small window, see getSignalWindow below — typically 5 bars
  highlightDate?: string     // the trigger bar's date — drawn with an accent outline + tone color
  tone?: 'bullish' | 'bearish' | 'warning' | 'neutral'   // outline/highlight color, matches the parent insight's tone
  width?: number              // default 100
  height?: number             // default 44
}
```

## Signal Window Extraction
Centers the strip on the bar that actually triggered the signal — 2 bars of context before and after where available. If the trigger is the most recent bar (signal just fired, no "after" bars exist yet), the window instead ends at the trigger so it doesn't reach into future data that doesn't exist.

```typescript
// lib/strat/signalWindow.ts
export function getSignalWindow(bars: OHLCVBar[], triggerDate: string, size = 5): { bars: OHLCVBar[]; triggerDate: string } | null {
  const idx = bars.findIndex(b => b.date === triggerDate)
  if (idx === -1) return null
  const half = Math.floor(size / 2)
  const isLatest = idx >= bars.length - 1
  const start = isLatest ? Math.max(0, idx - size + 1) : Math.max(0, idx - half)
  const end = isLatest ? idx + 1 : Math.min(bars.length, start + size)
  return { bars: bars.slice(start, end), triggerDate }
}
```

## Implementation
Plain SVG, no charting library — at 5 bars this is simpler hand-drawn than wiring up a candlestick series in Recharts (which has no native candlestick primitive anyway).

```tsx
const TONE_COLOR = { bullish: '#4ade80', bearish: '#f87171', warning: '#fbbf24', neutral: '#a78bfa' } as const

export function MiniCandlestickStrip({ bars, highlightDate, tone = 'neutral', width = 100, height = 44 }: MiniCandlestickStripProps) {
  if (!bars.length) return null
  const highs = bars.map(b => b.high), lows = bars.map(b => b.low)
  const max = Math.max(...highs), min = Math.min(...lows)
  const pad = (max - min) * 0.1 || 1
  const lo = min - pad, hi = max + pad
  const slot = width / bars.length
  const bodyWidth = slot * 0.55

  const y = (v: number) => height - ((v - lo) / (hi - lo)) * height

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {bars.map((b, i) => {
        const cx = i * slot + slot / 2
        const isUp = b.close >= b.open
        const bodyTop = y(Math.max(b.open, b.close))
        const bodyBottom = y(Math.min(b.open, b.close))
        const isTrigger = b.date === highlightDate
        const color = isUp ? '#4ade80' : '#f87171'
        return (
          <g key={b.date}>
            {isTrigger && (
              <rect x={cx - slot / 2 + 1} y={0} width={slot - 2} height={height} fill={TONE_COLOR[tone]} opacity={0.12} rx={2} />
            )}
            <line x1={cx} x2={cx} y1={y(b.high)} y2={y(b.low)} stroke={color} strokeWidth={1} />
            <rect
              x={cx - bodyWidth / 2}
              y={bodyTop}
              width={bodyWidth}
              height={Math.max(bodyBottom - bodyTop, 1)}
              fill={color}
              stroke={isTrigger ? TONE_COLOR[tone] : 'none'}
              strokeWidth={isTrigger ? 1.5 : 0}
            />
          </g>
        )
      })}
    </svg>
  )
}
```

## Dependencies
- `lib/strat/signalWindow.ts` (`getSignalWindow`)
