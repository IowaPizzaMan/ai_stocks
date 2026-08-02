# frontend/src/components/earnings/EarningsCandidateCard.tsx

## Purpose
Expanded card view for a single earnings candidate — shows the full score breakdown. Used when the user wants to see details on a specific company before deciding whether to queue it. Can be shown as a panel or modal. `onAnalyze` enqueues the ticker directly into `work_queue`, same as the table row click — no chat involved.

## Props
```typescript
interface EarningsCandidateCardProps {
  candidate: EarningsCandidate
  onAnalyze: (ticker: string) => void  // enqueues full analysis directly
  onClose: () => void
}
```

## Layout
```
┌────────────────────────────────────────────────┐
│  NVDA  NVIDIA Corporation      Score: 87  [×]  │
│  Reports: Wednesday Jan 22, after market close  │
├────────────────────────────────────────────────┤
│  Score Breakdown                               │
│  ─────────────                                 │
│  Avg move     ±9.2%  ████████░░  22/25 pts     │
│  Beat rate    7/8    ████████░░  18/20 pts      │
│  EPS revision  ↑ Up  ██████████  20/20 pts     │
│  Insider      Cluster ████████░  20/20 pts     │
│  Accumulation  4/5   ███████░░░  12/15 pts     │
├────────────────────────────────────────────────┤
│  Post-earnings move history (last 8 quarters)  │
│  [Mini bar chart: +12.1%, -3.2%, +8.4%, ...]  │
├────────────────────────────────────────────────┤
│  [Analyze This Stock ▶]                        │
└────────────────────────────────────────────────┘
```

## Post-Earnings Move History Chart
Small Recharts `BarChart` showing each quarter's move_pct — green bars for positive, red for negative. Lets the user immediately see volatility pattern.

```tsx
<BarChart data={candidate.quarters} width={340} height={80}>
  <Bar dataKey="move_pct"
    fill="#22c55e"
    cell={(entry) => <Cell fill={entry.move_pct >= 0 ? '#22c55e' : '#ef4444'} />}
  />
  <ReferenceLine y={0} stroke="#475569" />
</BarChart>
```

## Score Bar Component (inline)
```tsx
function ScoreBar({ value, max, pts }: { value: number, max: number, pts: number }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-800 rounded-full">
        <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-400 w-14 text-right">{pts} pts</span>
    </div>
  )
}
```
