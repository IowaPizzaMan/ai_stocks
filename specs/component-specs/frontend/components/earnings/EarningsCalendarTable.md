# frontend/src/components/earnings/EarningsCalendarTable.tsx

## Purpose
Ranked table of earnings candidates from the scan. Not conversational — clicking a ticker (row or Analyze button) enqueues it directly into `work_queue` via `POST /earnings/analyze`. There is no intermediate chat step; the agentic crew picks the job up on its next poll. Sortable by score, date, avg move, or beat rate.

## Props
```typescript
interface EarningsCalendarTableProps {
  candidates: EarningsCandidate[]
  isLoading: boolean
  onAnalyzeTicker: (ticker: string) => void  // clicking a row or the Analyze button enqueues full analysis directly
}
```

## Row Click Behavior
Clicking anywhere on a row (not just the Analyze button) calls `onAnalyzeTicker(ticker)`, which posts to `/earnings/analyze` and enqueues the job immediately. Show a brief inline confirmation on the row (e.g. a "Queued" badge replacing the Actions button) rather than navigating away — the user stays on the calendar and can queue multiple tickers in a row.

## Columns
| Column | Content |
|---|---|
| Rank | # (1, 2, 3...) |
| Ticker | Bold + company name below in slate |
| Reports | Date + BMO/AMC badge |
| Score | Large number (0-100) with color: ≥70 green, 40-69 amber, <40 slate |
| Avg Move | ±X.X% with color (larger = more opportunity) |
| Beat Rate | X/8 format |
| EPS Revision | ↑ Up / → Flat / ↓ Down with color |
| Insider | 🔵 Cluster / 🟡 Single / — None |
| Accu. | 0-5 dots |
| Actions | [Analyze ▶] button, replaced by a "Queued" badge once enqueued |

## Score Color Coding
```typescript
const scoreColor = (score: number) =>
  score >= 70 ? 'text-green-400' :
  score >= 40 ? 'text-amber-400' :
  'text-slate-400'
```

## Sorting
Sort by any column header click. Default: score descending.

```typescript
const [sortKey, setSortKey] = useState<keyof EarningsCandidate>('score')
const [sortDir, setSortDir] = useState<'asc'|'desc'>('desc')
const sorted = [...candidates].sort((a, b) =>
  sortDir === 'desc' ? b[sortKey] - a[sortKey] : a[sortKey] - b[sortKey]
)
```

## Loading State
Show 5 skeleton rows while scan is running.

## Styling
- `bg-slate-900 border border-slate-800 rounded-xl overflow-hidden`
- Zebra striping: alternate rows `bg-slate-900` / `bg-slate-800/30`
- Hover: `hover:bg-slate-800/60 cursor-pointer`
- Sticky header row

## Dependencies
- `EarningsCandidateCard` (used in mobile/collapsed view, not table)
