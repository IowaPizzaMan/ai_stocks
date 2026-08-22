# frontend/src/pages/Congress.tsx

**Added by**: specs/028-dashboard-tweaks-batch US4
**Contract**: specs/028-dashboard-tweaks-batch/contracts/congress-api.md

## Purpose

URL: `/congress`. Recent Senate and House trading disclosures (FMP `senate-latest` /
`house-latest`), with a computed buying-activity summary, filters by ticker and by
lawmaker, and ticker navigation into the stock detail page. Nav entry: "Congress"
(`layout/Navbar.tsx`), after Earnings.

## Layout

```
[Congress]                                              [Refresh]
──────────────────────────────────────────────────────────────────
Summary
  Most bought — last 90 days      High-dollar trades (≥ $100,001)
  NVDA        7 buys              NVDA   $250,001 - $500,000
  AAPL        4 buys              ...
──────────────────────────────────────────────────────────────────
[Filter by ticker…] [Filter by member…]

Chamber  Politician     Ticker  Asset          Type      Amount            Traded      Disclosed
senate   John Boozman   AVGO    Broadcom Inc   Purchase  $1,001 - $15,000  2025-04-08  2026-08-20
...
```

## Implementation

Reads/writes `ticker`/`politician` filters via `useSearchParams`, debounced
(`useDebounce`, same guarded-effect pattern `FilterBar.tsx` uses so a no-op keystroke
doesn't fire a redundant navigation). Renders `CongressSummary` (above) and
`CongressTable` (below) as separate components — see their own component specs.

```tsx
const [searchParams, setSearchParams] = useSearchParams();
const [ticker, setTicker] = useState(searchParams.get("ticker") ?? "");
const [politician, setPolitician] = useState(searchParams.get("politician") ?? "");
const debouncedTicker = useDebounce(ticker.trim());
const debouncedPolitician = useDebounce(politician.trim());

useEffect(() => {
  setSearchParams((prev) => {
    const next = new URLSearchParams(prev);
    debouncedTicker ? next.set("ticker", debouncedTicker) : next.delete("ticker");
    debouncedPolitician ? next.set("politician", debouncedPolitician) : next.delete("politician");
    return next;
  }, { replace: true });
}, [debouncedTicker, debouncedPolitician, setSearchParams]);

const { data: summary } = useCongressSummary();
const { data: trades, isLoading, isError } = useCongressTrades({
  ticker: searchParams.get("ticker") ?? undefined,
  politician: searchParams.get("politician") ?? undefined,
});
const refresh = useCongressRefresh();
```

## Key Details

- **Two distinct empty states**, matching the Portfolio Summary panel's precedent
  (specs/028 US2): "No disclosures match the current filter" when a filter narrowed the
  set to zero, vs. "No disclosures yet — click Refresh" when nothing has ever been pulled
  and no filter is active.
- The politician filter accepts either a name substring (e.g. "Boozman") or a
  bioguide-id-shaped value (e.g. "B001236", matched via `^[A-Za-z]\d{6}$`) — the latter
  matches `person_id` exactly, resolving a lawmaker filed under varying name spellings.
- Summary math (`most_bought`/`high_dollar`) is pure arithmetic computed server-side over
  a rolling 90-day window on `disclosure_date` (never `transaction_date` — disclosures
  routinely lag by months). No LLM involvement (Principle III).
- `Refresh` enqueues `congress_trades_pull` via `POST /congress/refresh`, deduped like
  every other refresh control in this batch; busy state reads `useQueueStatus` for
  `job_type === "congress_trades_pull"`.
- Page title: `document.title = "StockAI — Congress"`.

## Dependencies

- `useCongressTrades`, `useCongressSummary`, `useCongressRefresh` (`hooks/useCongress.ts`)
- `useDebounce`, `useQueueStatus`
- `CongressTable`, `CongressSummary` (`components/congress/`)
- `react-router-dom` (useSearchParams)
