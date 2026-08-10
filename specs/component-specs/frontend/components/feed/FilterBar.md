# frontend/src/components/feed/FilterBar.tsx

## Purpose
Horizontal filter bar above the analysis feed. Controls which analyses are shown by signal, conviction, sector, and date range. Filter state lives in URL search params (bookmarkable/shareable).

## Props
```typescript
interface FilterBarProps {
  onChange: (filters: FeedFilters) => void
  activeFilters: FeedFilters
}
```

## Filter Controls
1. **Ticker search** — text input, filters the feed to matching tickers as the user types (debounced ~300ms via `useDebouncedValue`, no submit/Enter needed). Client-side substring match against `ticker`/company name on already-loaded pages plus a `ticker` query param passed through to `GET /analysis/feed` so pagination stays correct once the user has typed enough to narrow results server-side. Distinct from the Navbar's global search (`Navbar.md`) — that one jumps straight to a stock's detail page from anywhere in the app; this one filters the feed in place without navigating away.
2. **Signal** — pill toggle group: All | Bullish | Bearish | Neutral
3. **Conviction** — pill toggle group: All | High | Medium | Low
4. **Sector** — dropdown select from SECTORS constant
5. **Date range** — "Last 24h / 7d / 30d / All" quick-select buttons
6. **Strategy filters** — see "Strategy Filters (Phase 2)" below
7. **Clear** — "Clear filters" text button (only visible when any filter is active)

## URL Sync
Filters are stored as URL search params so state survives refresh and can be shared:
```typescript
import { useSearchParams } from 'react-router-dom'

const [searchParams, setSearchParams] = useSearchParams()
const ticker = searchParams.get('ticker') || ''
const signal = searchParams.get('signal') || ''
const conviction = searchParams.get('conviction') || ''
// etc.

const updateFilter = (key: string, value: string) => {
  setSearchParams(prev => {
    if (!value) prev.delete(key)
    else prev.set(key, value)
    return prev
  })
}
```
The ticker search input calls `updateFilter('ticker', value)` on the debounced value, same mechanism as the other pill/dropdown filters — it isn't a special case, just debounced before it hits the URL so every keystroke doesn't rewrite history.

## Strategy Filters (Phase 2)
Trading-strategy-flavored filters, beyond the structural signal/conviction/sector/date filters above. **Which specific strategies ship first is still undecided** — captured here so the filter bar's shape is spec'd even though the backend scoring behind each one isn't yet:
- **Institutional activity** — "Institutions buying" / "Institutions selling" toggle, sourced from the same recent-13F/superinvestor-move data that backs the Institutional Flow feed (`InstitutionalFlow.md`) — a ticker qualifies if it has a recent buy-side or sell-side flow event.
- **YTD performance** — "Positive on year" / "Negative on year" toggle, sourced from price data (YTD % change from the first trading day of the calendar year).
- **"Earning Money"** (quality-company screen) — placeholder name for a profitability/quality filter; likely backed by `FundamentalsTab`'s margin and returns fields (e.g. positive `netProfitMargin` and `returnOnInvestedCapital` above some floor) once that data is reliably available per ticker. Exact thresholds TBD.
- **"Stonk"** (high-beta screen) — placeholder name for a volatility filter; likely backed by `beta` from yfinance `.get_info()` (see `DATA_SOURCES.md`) above some threshold. Exact threshold TBD.

These map to new optional query params on `GET /analysis/feed` and new optional fields on `AnalysisFeedItem` — see `backend/models/analysis.md` and `backend/routers/analysis.md`. Render as an additional pill/toggle group once the backing fields exist; until then this section documents intent, not a buildable contract.

## Styling
- Horizontal flex row, `gap-3`, `py-3`
- Toggle pills: `border border-slate-700 rounded-full px-3 py-1 text-sm`
- Active pill: `bg-indigo-600 border-indigo-600 text-white`
- Inactive pill: `text-slate-400 hover:text-white hover:border-slate-500`
- Sticky below Navbar on scroll (`sticky top-14 z-40 bg-slate-950 border-b border-slate-800`)

## Dependencies
- `react-router-dom` (useSearchParams)
- `SECTORS`, `SIGNAL_FILTERS`, `CONVICTION_FILTERS` from constants
