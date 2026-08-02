# frontend/src/components/queue/PullAllButton.tsx

## Purpose
"Run All" button (labeled "Pull All" in the UI) — enqueues every `active` ticker in the system-wide registry, not just the watchlist. That registry (`ticker_index`, see `models/ticker.md`) accumulates tickers from four sources: manual entry, watchlist add, earnings calendar pulls, and institutional flow scans. Clicking this button is the bulk "make sure everything gets (re-)analyzed" action; it doesn't change how tickers get discovered, just enqueues whatever's already in the system. Shows loading state while the request is in flight, then reflects the queue status.

## Props
None — reads from `useEnqueueAll()` and `useQueue()` directly.

## Implementation

```tsx
import { useEnqueueAll } from '@/hooks/useQueue'
import { useQueue } from '@/hooks/useQueue'

export function PullAllButton() {
  const enqueueAll = useEnqueueAll()
  const { data: queue } = useQueue()
  
  const isProcessing = (queue?.running_count ?? 0) > 0 || (queue?.pending_count ?? 0) > 0

  return (
    <button
      onClick={() => enqueueAll.mutate()}
      disabled={enqueueAll.isPending || isProcessing}
      className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm px-4 py-2 rounded-lg transition-colors"
    >
      {enqueueAll.isPending ? (
        <>
          <Spinner className="w-4 h-4" />
          Queuing...
        </>
      ) : isProcessing ? (
        <>
          <PulsingDot />
          {queue?.running_count} running · {queue?.pending_count} pending
        </>
      ) : (
        <>
          <RefreshIcon className="w-4 h-4" />
          Pull All
        </>
      )}
    </button>
  )
}
```

## States
| State | Display |
|---|---|
| Idle | "Pull All" with refresh icon |
| Mutating (HTTP in flight) | Spinner + "Queuing..." |
| Queue has items | Pulsing dot + "N running · M pending" |
| Disabled | Same as above, button disabled |

## On Success
`POST /queue/all` returns `{ enqueued, already_queued, universe_size }` (see `routers/queue.md`). On success, show a brief toast: "Queued N of {universe_size} tickers" — gives the user a sense of how large their system-wide universe has grown from earnings/institutional-flow discovery, not just what's in their watchlist.
