# frontend/src/components/earnings/EarningsTable.tsx

**Added by specs/025-earnings-page-filters.** Replaces `UpcomingEarningsTable.tsx` (the old
read-only calendar table) and `EarningsCalendarTable.tsx` (the removed scored-candidate
table) with one table.

## Purpose
Renders whatever rows it's given, in the order it's given them — it never sorts or filters.
Ordering (`market_cap` descending) is guaranteed server-side
(`backend/earnings_data.py::_screen_and_build`, FR-019); filtering is applied by the parent
page via `lib/earningsFilters.ts` before rows reach this component. This split keeps the
"always sorted by market cap, non-overridable" guarantee in exactly one place.

## Props
```typescript
interface EarningsTableProps {
  entries: EarningsCalendarEntry[];
  isLoading: boolean;
  queuedTickers: Set<string>;
  onQueueTicker: (ticker: string) => void;
}
```

## Columns
Ticker (linked) · Reports · EPS Est./Actual · EPS Surprise · Revenue Est./Actual · Revenue
Surprise · Mkt Cap · Last Updated · Queue action.

## `reporting_state` rendering (FR-013)
| State | Actual/surprise columns | Notes |
|---|---|---|
| `upcoming` | explicit "—" placeholder | Never `0`, never blank (FR-014) |
| `reported` | actual value + `Surprise` | Beat/miss shown by color **and** an arrow/label, never sign character alone (FR-012) |
| `awaiting` | "—" plus an amber "Awaiting results" badge on the Reports cell | Must never render with the miss treatment — a past date with no actuals yet is common, not a bad result (spec Edge Cases) |

A `null` surprise (missing/zero estimate — see `_surprise_pct` in
`backend/earnings_data.py`) always renders as unavailable (`—`, `text-zinc-600`), never as
`0%` or a beat (FR-011).

## Ticker link (FR-022–024)
The ticker symbol is a `react-router-dom` `<Link to={/stock/${ticker}}>`, a sibling of the
row's Queue button — not nested inside it, and not sharing a click handler. Clicking either
one only fires that one's action.

## Dependencies
- `react-router-dom` (`Link`)
- `api/types.ts` (`EarningsCalendarEntry`)
