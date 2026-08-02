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
1. **Signal** — pill toggle group: All | Bullish | Bearish | Neutral
2. **Conviction** — pill toggle group: All | High | Medium | Low
3. **Sector** — dropdown select from SECTORS constant
4. **Date range** — "Last 24h / 7d / 30d / All" quick-select buttons
5. **Clear** — "Clear filters" text button (only visible when any filter is active)

## URL Sync
Filters are stored as URL search params so state survives refresh and can be shared:
```typescript
import { useSearchParams } from 'react-router-dom'

const [searchParams, setSearchParams] = useSearchParams()
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

## Styling
- Horizontal flex row, `gap-3`, `py-3`
- Toggle pills: `border border-slate-700 rounded-full px-3 py-1 text-sm`
- Active pill: `bg-indigo-600 border-indigo-600 text-white`
- Inactive pill: `text-slate-400 hover:text-white hover:border-slate-500`
- Sticky below Navbar on scroll (`sticky top-14 z-40 bg-slate-950 border-b border-slate-800`)

## Dependencies
- `react-router-dom` (useSearchParams)
- `SECTORS`, `SIGNAL_FILTERS`, `CONVICTION_FILTERS` from constants
