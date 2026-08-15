# frontend/src/components/feed/AnalysisTile.tsx

## Purpose
The compact unit of the Feed's checkerboard grid (feature 019). Replaces `AnalysisCard` — see
`AnalysisCard.md` for what it displaced. A tile shows only a stock's ticker, a signal-colored
fill, and 1–3 conviction dots, so dozens can fit on one screen at once.

## Props
```typescript
interface AnalysisTileProps {
  analysis: AnalysisFeedItem
}
```

## Face content (and nothing else)
- **Ticker** — the only visible text. Tickers over 5 characters (GOOGL, BRK.B) render at a
  smaller font size rather than truncating, so nothing is ever cut off ambiguously.
- **Fill color** — encodes `analysis.signal`, matching the app's existing `SignalBadge`
  palette: emerald (bullish), red (bearish), zinc (neutral). An unrecognized or missing
  signal renders a conspicuous dashed-border, no-fill fallback — it is never silently shown
  as neutral.
- **Conviction dots** — 1, 2, or 3 filled dots for low/medium/high conviction (same mapping as
  `ConvictionMeter`), rendered in a neutral tone so they read against any of the three fill
  colors. Missing/unrecognized conviction renders zero filled dots, not a misleading count.

## Accessibility
Because signal and conviction are conveyed primarily by color and small dots, the full state
is available as text via `aria-label`:
`"{ticker} — {signal}, {conviction} conviction ({n} of 3), analyzed {relative time}"`, with
graceful degradation when a field is missing (`"unknown signal"`, `"no conviction data"`). The
dot row itself is `aria-hidden` — it's decorative once the label carries the value.

## Implementation sketch
```tsx
const FILL: Record<Signal, string> = {
  bullish: "border-emerald-500/30 bg-emerald-500/15 text-emerald-400",
  bearish: "border-red-500/30 bg-red-500/15 text-red-400",
  neutral: "border-zinc-500/30 bg-zinc-500/15 text-zinc-300",
}
const FALLBACK_FILL = "border-dashed border-zinc-700 bg-transparent text-zinc-500"

export default function AnalysisTile({ analysis }: AnalysisTileProps) {
  const fillClass = isKnownSignal(analysis.signal) ? FILL[analysis.signal] : FALLBACK_FILL
  const level = convictionLevel(analysis.conviction) // high→3, medium→2, low→1, else→0

  return (
    <div className={`flex h-14 flex-col items-center justify-center gap-1 rounded-md border ${fillClass}`}
         aria-label={buildAriaLabel(analysis)}>
      <span>{analysis.ticker}</span>
      <span aria-hidden="true" className="flex gap-1">
        {[1, 2, 3].map(i => <span key={i} data-filled={i <= level} />)}
      </span>
    </div>
  )
}
```

## Interaction (added in feature 019's User Story 2)
- Click/tap, or Enter while focused, navigates to `/stock/{ticker}` — same destination
  `AnalysisCard` used.
- Hover or keyboard focus reveals `TilePreview`, a popover carrying the detail that no longer
  fits on the tile face: signal label, conviction with label, recency, the summary snippet,
  and an add-to-watchlist button. See the "TilePreview" section below.
- The tile itself remains focusable (keyboard users reach both navigation and the preview's
  watchlist button without a mouse).

## TilePreview

### Purpose
Rich hover/focus popover anchored to an `AnalysisTile`, carrying everything the old
`AnalysisCard` displayed on its face that no longer fits a compact tile.

### Props
```typescript
interface TilePreviewProps {
  analysis: AnalysisFeedItem
}
```

### Content
- `SignalBadge` (signal as text)
- `ConvictionMeter` with `label` (conviction as text, not just dots)
- Relative time, plus the "data as of" absolute date when available
- Line-clamped `analysis.summary`
- A "+ Watchlist" button wired to `useAddToWatchlist`

### Behavior
- Shown on the tile's `mouseenter`/`focus-within`, hidden on `mouseleave`/`blur`.
- The watchlist button calls `e.stopPropagation()` so clicking it does not trigger the tile's
  navigate-on-click.
- Flips its placement near grid edges so it's never clipped by the viewport.
- Not required on touch devices (no hover): tapping a tile navigates directly; watchlist-add
  remains available from the stock detail page.

## Dependencies
- `SignalBadge`, `ConvictionMeter` (shared, unmodified)
- `useAddToWatchlist` (`hooks/useWatchlist.ts`, unmodified)
- `lib/time.ts` (`relativeTime`, `formatDate`)
- `react-router-dom` (navigation)
