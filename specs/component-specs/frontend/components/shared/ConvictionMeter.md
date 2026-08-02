# frontend/src/components/shared/ConvictionMeter.tsx

## Purpose
Visual indicator for conviction level (high/medium/low). Renders as three dots: filled dots = conviction level.

## Props
```typescript
interface ConvictionMeterProps {
  conviction: 'high' | 'medium' | 'low'
  label?: boolean  // show text label alongside dots, default false
}
```

## Implementation
```tsx
import { CONVICTION_CONFIG } from '@/lib/constants'

const LEVELS = { high: 3, medium: 2, low: 1 }

export function ConvictionMeter({ conviction, label = false }: ConvictionMeterProps) {
  const filled = LEVELS[conviction]
  const config = CONVICTION_CONFIG[conviction]
  return (
    <div className="flex items-center gap-1.5">
      {[1, 2, 3].map(i => (
        <span
          key={i}
          className={`w-2 h-2 rounded-full transition-colors ${i <= filled ? 'opacity-100' : 'opacity-20'}`}
          style={{ backgroundColor: config.dotColor }}
        />
      ))}
      {label && <span className="text-xs text-slate-400 ml-1">{config.label}</span>}
    </div>
  )
}
```
