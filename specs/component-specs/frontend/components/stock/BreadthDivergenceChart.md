# frontend/src/components/stock/BreadthDivergenceChart.tsx

## Purpose
Visualizes SPY-vs-NYMO divergence — the signal the Market Timing section already
*describes* in prose ("bearish divergence between SPY's price action and the
NYMO"). Requested by Neal 2026-08-09: when the RecommenderAgent calls out a
divergence, show it, don't just say it.

Rendered inside the **Market Timing** section of the AI Summary tab
(`StockDetail.tsx` → `AISummaryTab`) whenever divergence data is available;
always shows the two aligned panes even when no divergence is flagged, so the
user can eyeball the relationship themselves.

## Layout
Two stacked panes sharing one date axis (last ~30 trading days):

```
┌──────────────────────────────────────────────┐
│ SPY (close)                        ● HH      │   ← price pane
│        ╱╲      ╱╲__________________╱         │     swing points marked,
│  ─────╱  ╲____╱      trend line ──────►      │     divergence line drawn
├──────────────────────────────────────────────┤
│ NYMO                                         │   ← oscillator pane
│   ╱╲     ╱╲                                  │
│  ╱  ╲___╱  ╲______ ● LH                      │     opposite-slope line =
│ ─────────────────────────── 0 line           │     the divergence
│         trend line ──►                       │
└──────────────────────────────────────────────┘
  ⚠ Bearish divergence: SPY higher high (652.10 on 08-07)
    vs NYMO lower high (+18.4 vs +31.2 on 07-28)
```

- **Price pane:** SPY daily closes as a line. The two swing points that anchor
  the divergence (e.g., the two highs for a bearish divergence) get dot
  markers connected by a dashed trend line.
- **Oscillator pane:** NYMO as a line (or histogram-style area around 0), with
  a zero line and shaded overbought/oversold bands at ±60. The corresponding
  two NYMO swing points get dots + a dashed trend line — sloping the
  *opposite* direction from the price line. The two opposite-sloping dashed
  lines ARE the visual; make them prominent (amber for bearish, emerald for
  bullish).
- **Caption:** one line under the chart restating the divergence with the
  actual dates/values, colored to match (amber/emerald). Hidden when
  `divergence.type === "none"`.
- Optional NAMO toggle: small `NYMO | NAMO` switch above the oscillator pane
  (NYMO default, per `market_flow_rules.md` §4).
- Compact: ~280px tall total; same dark styling as the other stock charts
  (`border-zinc-800 bg-zinc-900`).

## Data contract

New backend endpoint **`GET /market/breadth`** (serves `breadth_cache` — no
new computation; the agent-runner already stores daily oscillator values and
SPY closes per `tools/breadth.md`):

```json
{
  "spy":  [{ "date": "2026-07-01", "close": 634.2 }, ...],
  "nymo": [{ "date": "2026-07-01", "value": -12.4 }, ...],
  "namo": [{ "date": "2026-07-01", "value": -8.1 }, ...],
  "divergence": {
    "type": "bearish",              // "bullish" | "bearish" | "none"
    "description": "SPY higher high vs NYMO lower high",
    "price_points": [{ "date": "2026-07-28", "value": 648.3 },
                     { "date": "2026-08-07", "value": 652.1 }],
    "osc_points":   [{ "date": "2026-07-28", "value": 31.2 },
                     { "date": "2026-08-07", "value": 18.4 }]
  },
  "divergence_history": [
    { "type": "bullish", "resolved": "2026-06-12",
      "anchor_dates": ["2026-06-02", "2026-06-11"],
      "spy_change_5d": 2.1, "spy_change_10d": 3.4 },
    ...
  ],
  "method": "computed_ratio_adjusted"
}
```

`divergence_history` backs the ▲/▼ resolution markers. **Built in its own
`breadth_divergences` collection**, not inside `breadth_cache` as this spec
first said — `breadth_cache` is strictly one doc per (exchange, date) and
mixing a second doc shape into it would break every reader. The daily breadth
run opens a doc when a divergence appears and stamps `resolved` when it goes
away (it can't be recomputed from a 60-day window), with forward SPY % changes
filled in as the sessions complete. SPY closes *are* stored on the nyse
`breadth_cache` rows as `spy_close`, since the divergence read is SPY vs NYMO
and they share a date key.

Requires `tools/breadth.py::detect_divergence` to return the **anchor points**
(dates + values of the two swing highs/lows on each series), not just
type/description — the frontend draws the trend lines from these rather than
re-detecting swings client-side. See `agent-runner/tools/breadth.md`.

## Props
```tsx
{
  breadth: MarketBreadth        // the /market/breadth payload
  oscillator?: "nymo" | "namo"  // default "nymo"
  compact?: boolean             // feed-thumbnail mode: shorter, no markers
}
```

## Implementation notes (learned while building)

- **Never wrap `ReferenceLine`/`ReferenceDot` in a custom component.** Recharts
  discovers them by walking its own children; anything nested inside a
  component of yours is invisible to it and renders *nothing*, silently. Helper
  functions returning arrays of elements are fine — components are not.
- The oscillator pane uses an **auto domain**, not a fixed ±60 frame. A typical
  divergence is a few points of slope; framing ±60 always flattens it into a
  straight line and defeats the whole chart. The zone guides come into range on
  their own as the oscillator approaches them.
- Marker dates are **snapped to the nearest charted session**
  (`snapToChartDate`). The daily run resolves divergences on whatever day it
  fires, including weekends and holidays, which have no bar — requiring an exact
  date match silently drops those markers (caught live on Juneteenth 2026).
- Both panes need identical `YAxis width` and margins, or the date axes drift
  apart and the two trend lines stop being comparable.

## Additional requirements (committed 2026-08-09)

### Divergence history markers
Small ▲/▼ glyphs on the price pane wherever *past* divergences resolved
(▲ = bullish divergence, ▼ = bearish), so the user learns how reliable the
signal has actually been for this regime. Requires the backend payload to
carry a `divergence_history` list (see Data contract) — each past divergence's
resolution date + type — persisted in `breadth_cache` as the daily breadth run
detects them, since they can't be recomputed from the 30-day window alone.
Tooltip on hover: type, anchor dates, and what SPY did over the following
5/10 sessions.

### Zone shading on the price pane
Tint the price pane's background on days where NYMO closed beyond ±60 —
subtle emerald band for ≤ -60 (oversold "opportunity zone"), subtle amber for
≥ +60 (overbought). Ties the `market_flow_rules.md` §1 zone concept to price
visually. Frontend-only; derived from the `nymo` history already in the
payload.

### Market-flow feed card
Divergences are market-wide but currently surface only inside a per-stock
analysis. Emit a feed event when the daily breadth run detects a **new**
divergence (transition from `none`/other-type — not re-fired while the same
divergence persists): category `market_flow`, no ticker, headline like
"Bearish SPY/NYMO divergence detected", body = the description + anchor
values, and a compact thumbnail render of this chart (the component in a
`compact` mode: smaller height, no toggle, caption only). Emission belongs in
the agent-runner's daily breadth pass, alongside where `breadth_cache` is
written; events land in `market_flow_events`, served by
`GET /market/flow-events`.

**Placement:** pinned above the analysis cards on the Feed page, not
interleaved. They're ticker-less, so a chronological slot in a per-ticker feed
would bury them, and merging a second doc shape into the feed's pagination
would complicate `/analysis/feed` for no benefit. They're hidden once the user
applies any filter (a market-wide card is noise when narrowed to one ticker)
and age out after 14 days.

### Reusability (design constraint)
The component is ticker-independent — props are SPY + breadth data only, no
ticker context. Keep it that way: no per-stock imports, no route coupling, so
it can drop unchanged into a future Market/Admin dashboard page and the feed
card thumbnail.

## Dependencies
- `GET /market/breadth` (new backend route; reads `breadth_cache`)
- Same lightweight charting approach as `PriceChart`/`RateOfChangeChart`
