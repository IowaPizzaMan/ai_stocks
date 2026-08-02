# frontend/src/components/shared/SignalBadge.tsx

## Purpose
Pill badge displaying bullish/bearish/neutral signal with appropriate color. Used on every AnalysisCard, in the Sidebar, and in search results.

## Props
```typescript
interface SignalBadgeProps {
  signal: 'bullish' | 'bearish' | 'neutral'
  size?: 'sm' | 'md'   // default 'md'
}
```

## Implementation
```tsx
import { SIGNAL_CONFIG } from '@/lib/constants'

export function SignalBadge({ signal, size = 'md' }: SignalBadgeProps) {
  const config = SIGNAL_CONFIG[signal]
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-3 py-1'
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  )
}
```

## Visual
- Bullish: green pill `bg-green-500/15 text-green-400`
- Bearish: red pill `bg-red-500/15 text-red-400`
- Neutral: slate pill `bg-slate-500/15 text-slate-400`
