# frontend/src/components/layout/Navbar.tsx

## Purpose
Top navigation bar. Contains the logo, main nav links, global search, and a live queue indicator dot.

## Layout
```
[StockAI logo]   Feed | Institutional Flow | Sectors   [Search input ____________]   [●] Queue   [⚙ Admin]
```

## Props
None — reads from React Router location for active link state, and from `useQueue()` for the live indicator.

## Implementation Details

### Global Search
- Controlled input with debounce (300ms via `useDebouncedValue` or `setTimeout`)
- On input change, calls `searchStocks(q)` — renders a floating dropdown of results
- Each result shows: ticker, company name, signal badge
- Clicking a result navigates to `/stock/:ticker` and closes the dropdown
- Click-outside closes the dropdown (use `useRef` + `mousedown` listener)
- Keyboard navigation: arrow keys move through results, Enter selects, Escape closes

```typescript
const [query, setQuery] = useState('')
const [results, setResults] = useState<StockSearchResult[]>([])
const debouncedQuery = useDebounce(query, 300)

useEffect(() => {
  if (debouncedQuery.length < 1) { setResults([]); return }
  searchStocks(debouncedQuery).then(setResults)
}, [debouncedQuery])
```

### Queue Indicator
- Reads `useQueue()` — shows an animated pulse dot when `pending_count > 0` or `running_count > 0`
- Green pulse = running, amber pulse = pending, no dot = idle
- Clicking navigates to queue view or opens a queue popover

### Admin Link
- Small gear icon, far right, after the queue indicator — deliberately understated since it's a maintenance tool, not a primary nav destination
- Navigates to `/admin` (`pages/Admin.md`) — disable/delete tickers from the registry and mass-add new ones
- No badge/count on the icon itself; the Admin page header shows the registry breakdown once you're there

## Styling
- Fixed top, `z-50`, `bg-slate-950 border-b border-slate-800`
- Height: `h-14`
- Logo: bold, white, `text-lg`
- Nav links: `text-slate-400 hover:text-white` with active link `text-white`

## Dependencies
- `react-router-dom` (useNavigate, useLocation, Link)
- `useQueue` hook
- `searchStocks` API function

## Amendments

- **As actually shipped**, the nav bar is a plain link row (`{ to, label }[]` mapped to
  `NavLink`) — no global search dropdown, queue indicator, or Admin link exist in the real
  component; those describe an earlier, unimplemented design. Current links: Stocks (`/`),
  Macro, Institutional Flow, Sectors, Earnings.
- **specs/028-dashboard-tweaks-batch US4**: added `{ to: "/congress", label: "Congress" }`.
