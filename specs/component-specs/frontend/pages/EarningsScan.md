# frontend/src/pages/EarningsScan.tsx

## Purpose
URL: `/earnings`. Not conversational. A single-pane scan results view: run a scan, get a ranked table, click a ticker to queue it for the agentic crew. No chat interface, no LLM in the ticker-selection loop.

## Layout
```
┌─────────────────────────────────────────────────────────────┐
│  Earnings Scanner                    [Scan controls ▼]      │
├─────────────────────────────────────────────────────────────┤
│  [ScanControls]                                              │
│  [EarningsCalendarTable]  ← click a row or [Analyze ▶] to    │
│                              enqueue that ticker directly     │
└─────────────────────────────────────────────────────────────┘
```

Single-pane layout: full-width table. Optional `EarningsCandidateCard` panel/modal opens for a candidate on demand to show score breakdown before queuing.

## State

```typescript
const [scanId, setScanId]         = useState<string | null>(null)
const [scanStatus, setScanStatus] = useState<'idle'|'running'|'complete'|'failed'>('idle')
const [candidates, setCandidates] = useState<EarningsCandidate[]>([])
const [queuedTickers, setQueuedTickers] = useState<Set<string>>(new Set())
```

## Key Behaviors

### 1. Trigger Scan
"Scan" button in `ScanControls` → `POST /earnings/scan` → receives `scan_id` → starts polling `GET /earnings/scan/{scan_id}` every 3 seconds until `status === "complete"`. On complete: populate candidates table.

```typescript
const triggerScan = async () => {
  setScanStatus('running')
  const { scan_id } = await api.post('/earnings/scan', { days_ahead: daysAhead }).then(r => r.data)
  setScanId(scan_id)
  const poll = setInterval(async () => {
    const result = await api.get(`/earnings/scan/${scan_id}`).then(r => r.data)
    if (result.status === 'complete') {
      clearInterval(poll)
      setScanStatus('complete')
      setCandidates(result.candidates)
    } else if (result.status === 'failed') {
      clearInterval(poll)
      setScanStatus('failed')
    }
  }, 3000)
}
```

### 2. Click ticker → enqueue directly
Clicking a row (or its Analyze button) in `EarningsCalendarTable` calls `onAnalyzeTicker(ticker)`, which posts straight to `/earnings/analyze` and marks the ticker as queued. No intermediate confirmation step, no chat round-trip.

```typescript
const analyzeTicker = async (ticker: string) => {
  await api.post('/earnings/analyze', { tickers: [ticker] })
  setQueuedTickers(prev => new Set(prev).add(ticker))
}
```

The row shows a "Queued" badge in place of the Analyze button once `queuedTickers.has(ticker)` is true. `queue_worker.py` (component-specs/agent-runner/queue_worker.md) picks the job up on its next poll cycle — the crew runs asynchronously from here on.

### 3. Optional detail card
Clicking a "details" affordance (separate from the row's queue action) opens `EarningsCandidateCard` with the full score breakdown. Its own `onAnalyze` button enqueues via the same direct path as above.

## Running State UX
While scan is running (30–60s):
- Table shows a skeleton loader
- Progress indicator (spinner or animated dots) with label "Scanning {n} companies reporting in the next {days} days..."

## Sub-components

### `ScanControls` (see its own spec)
### `EarningsCalendarTable` (see its own spec — row click enqueues directly, no chat)
### `EarningsCandidateCard` (optional detail panel, see its own spec)

## Dependencies
- `useEarningsScan` hook (new)
- `EarningsCalendarTable`, `EarningsCandidateCard`, `ScanControls`
