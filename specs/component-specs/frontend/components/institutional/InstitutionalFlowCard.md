# frontend/src/components/institutional/InstitutionalFlowCard.tsx

## Purpose
Card for one institutional flow event in the Institutional Flow feed. The event-feed analog of `AnalysisCard.md`, but represents a single fund move rather than a full AI analysis.

## Props
```typescript
interface InstitutionalFlowCardProps {
  event: InstitutionalFlowEvent
}
```

## Layout
```
┌─────────────────────────────────────────────────────┐
│ [New Position]  Pershing Square → GOOGL      2h ago  │
│                                                       │
│ Pershing Square opened a new $220M position in GOOGL │
│                                                       │
│ 1.2M shares · $220M · 8.4% of portfolio · 13F filing │
│ ●●●●● Notability 91                                  │
└─────────────────────────────────────────────────────┘
```

## Implementation

```tsx
import { useNavigate } from 'react-router-dom'
import { ActionBadge } from '@/components/institutional/ActionBadge'
import { formatRelative } from 'date-fns'

export function InstitutionalFlowCard({ event }: InstitutionalFlowCardProps) {
  const navigate = useNavigate()

  return (
    <article className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 hover:bg-slate-800/50 transition-all">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <ActionBadge action={event.action} />
          <span className="text-slate-300 text-sm">{event.fund}</span>
          <span className="text-slate-600">→</span>
          <button
            className="text-white font-bold hover:underline"
            onClick={() => navigate(`/stock/${event.ticker}`)}
          >
            {event.ticker}
          </button>
        </div>
        <span className="text-xs text-slate-500">
          {formatRelative(new Date(event.filed_at), new Date())}
        </span>
      </div>

      <p className="text-slate-300 text-sm leading-relaxed mb-3">{event.headline}</p>

      <div className="flex items-center gap-3 text-xs text-slate-500">
        {event.shares && <span>{event.shares.toLocaleString()} shares</span>}
        {event.value_usd && <span>${(event.value_usd / 1_000_000).toFixed(1)}M</span>}
        {event.pct_of_portfolio && <span>{event.pct_of_portfolio}% of portfolio</span>}
        <span className="uppercase tracking-wide">{event.source === '13F' ? '13F filing' : 'Dataroma'}</span>
      </div>

      <div className="mt-2">
        <NotabilityMeter score={event.notability_score} />
      </div>
    </article>
  )
}
```

### `ActionBadge` (sub-component, `components/institutional/ActionBadge.tsx`)
Small pill, colored by action: New Position (indigo), Add (green), Trim (amber), Exit (red). Config lives in `ACTION_CONFIG` (see `constants.md`).

### `NotabilityMeter` (sub-component)
Horizontal 5-dot meter (like `ConvictionMeter`) driven by `notability_score` bucketed into low/medium/high, plus the raw score as a tooltip.

## Key Details
- Only the ticker is clickable (navigates to `/stock/:ticker`) — the rest of the card is static, unlike `AnalysisCard` where the whole card navigates, since this card's primary subject is the fund/move, not the ticker
- Numbers formatted defensively — `shares`, `value_usd`, `pct_of_portfolio` are all optional (Dataroma-sourced moves sometimes lack exact share counts)

## Dependencies
- `react-router-dom`
- `date-fns`
- `ActionBadge`, `NotabilityMeter`
