# frontend/src/components/queue/QueueStatus.tsx

## Purpose
Live queue status display — shows what's currently running, what's pending, and when the last run completed. Placed in the header area or a dedicated status bar.

## Props
None — reads from `useQueue()` with 10-second polling.

## Implementation

```tsx
import { useQueue } from '@/hooks/useQueue'

export function QueueStatus() {
  const { data: queue, isLoading } = useQueue()

  if (isLoading || !queue) return null
  if (queue.running_count === 0 && queue.pending_count === 0) {
    return <span className="text-xs text-slate-500">Queue idle</span>
  }

  return (
    <div className="flex items-center gap-3 text-xs">
      {queue.running_count > 0 && (
        <div className="flex items-center gap-1.5 text-green-400">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          {queue.running[0]?.ticker} analyzing...
        </div>
      )}
      {queue.pending_count > 0 && (
        <span className="text-slate-400">{queue.pending_count} pending</span>
      )}
    </div>
  )
}
```

## Key Behaviors
- Polls every 10 seconds (via `useQueue`'s `refetchInterval`)
- When a ticker is running, shows that ticker's name with an animated green dot
- When idle, shows subtle "Queue idle" text or nothing
- Visible in the Navbar area so the user always knows what's happening
