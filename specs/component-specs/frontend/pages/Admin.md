# frontend/src/pages/Admin.tsx

## Purpose
URL: `/admin`. Management view over the full ticker registry (`ticker_index`, see `models/ticker.md`) — the same universe `POST /queue/all` (Run All) sweeps. This registry grows on its own over time (earnings calendar pulls, institutional flow scans, manual entry, watchlist adds), which means Run All naturally gets slower the longer the app runs. This page exists to keep that dataset intentionally small: disable or delete tickers the user doesn't care about, pull data for one ticker on demand, and mass-add many tickers at once via a paste box.

## Layout
```
Admin — Ticker Registry (128 total · 94 active · 12 disabled · 22 removed)

[ Mass Add ▾ ]
┌──────────────────────────────────────────────────┐
│ Paste tickers, separated by commas/spaces/lines   │
│                                                    │
│                                                    │
└──────────────────────────────────────────────────┘
[ Add Tickers ]

Filter: ( All ) ( Active ) ( Disabled ) ( Removed )     Search: [________]

TICKER   NAME              STATUS      LAST SEEN     [ Pull ]  [ Disable/Enable ]  [ Delete ]
AAPL     Apple Inc.        Active      2h ago        [▶]       [Disable]           [✕]
MSFT     Microsoft         Active      3h ago        [▶]       [Disable]           [✕]
ZNGA     Zynga Inc.        Disabled    4d ago        [▶]       [Enable]            [✕]
XYZ      —                 Removed     30d ago       [▶]       [Enable]            [✕]
...
```

## Implementation

```tsx
export function Admin() {
  const [filter, setFilter] = useState<TickerStatus | 'all'>('all')
  const [search, setSearch] = useState('')

  const { data, isLoading } = useTickers(filter === 'all' ? undefined : filter)
  const enqueue = useEnqueueTicker()
  const updateStatus = useUpdateTickerStatus()
  const deleteTicker = useDeleteTicker()

  const rows = (data?.items ?? []).filter(t =>
    !search || t.ticker.includes(search.toUpperCase()) || t.name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">
          Admin — Ticker Registry
          <span className="text-slate-500 font-normal text-lg ml-2">
            ({data?.total ?? 0} total · {data?.active_count ?? 0} active · {data?.disabled_count ?? 0} disabled · {data?.removed_count ?? 0} removed)
          </span>
        </h1>
      </div>

      <BulkAddPanel />

      <div className="flex items-center justify-between my-4">
        <StatusFilterTabs value={filter} onChange={setFilter} />
        <input
          className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-sm text-white"
          placeholder="Search ticker or name..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      <table className="w-full text-sm">
        <thead className="text-slate-500 text-xs uppercase">
          <tr>
            <th className="text-left py-2">Ticker</th>
            <th className="text-left py-2">Name</th>
            <th className="text-left py-2">Status</th>
            <th className="text-left py-2">Last Seen</th>
            <th className="text-right py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(item => (
            <AdminTickerRow
              key={item.ticker}
              item={item}
              onPull={() => enqueue.mutate(item.ticker)}
              onToggleStatus={() =>
                updateStatus.mutate({ ticker: item.ticker, status: item.status === 'disabled' ? 'active' : 'disabled' })
              }
              onDelete={() => deleteTicker.mutate(item.ticker)}
            />
          ))}
        </tbody>
      </table>

      {!isLoading && rows.length === 0 && (
        <p className="text-slate-500 text-sm py-8 text-center">No tickers match this filter.</p>
      )}
    </div>
  )
}
```

## `BulkAddPanel`
Collapsible panel (defaults open) containing the mass-add textarea. This is the primary way to seed a lot of tickers at once — the user pastes a watchlist export, a spreadsheet column, or a comma-separated list from anywhere.

```tsx
function BulkAddPanel() {
  const [text, setText] = useState('')
  const bulkAdd = useBulkAddTickers()
  const [result, setResult] = useState<BulkAddResponse | null>(null)

  const count = text.split(/[\s,]+/).filter(Boolean).length

  const handleSubmit = () => {
    bulkAdd.mutate(text, {
      onSuccess: (res) => {
        setResult(res)
        setText('')
      }
    })
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 mb-2">
      <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 block">
        Mass Add Tickers
      </label>
      <textarea
        className="w-full h-24 bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm text-white font-mono resize-y"
        placeholder="AAPL, MSFT, NVDA&#10;TSLA GOOGL&#10;... paste as many as you want, any separator works"
        value={text}
        onChange={e => setText(e.target.value)}
      />
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs text-slate-500">{count > 0 ? `${count} ticker${count === 1 ? '' : 's'} detected` : ''}</span>
        <button
          onClick={handleSubmit}
          disabled={bulkAdd.isPending || count === 0}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-1.5 rounded-lg"
        >
          {bulkAdd.isPending ? 'Adding...' : `Add Tickers`}
        </button>
      </div>
      {result && (
        <p className="text-xs text-slate-400 mt-2">
          Added {result.added.length}
          {result.already_existed.length > 0 && ` · ${result.already_existed.length} already tracked`}
          {result.invalid.length > 0 && ` · ${result.invalid.length} invalid (${result.invalid.join(', ')})`}
        </p>
      )}
    </div>
  )
}
```

## `AdminTickerRow`
One row per ticker in the registry.
- **Ticker / Name** — plain text; ticker links to `/stock/:ticker`.
- **Status** — `TickerStatusBadge`. Since this table is mostly `active` and `disabled` rows the user put there on purpose, it's fine for the badge to render for every status here (unlike Watchlist/Sidebar, don't suppress it for `active` — actually, keep the shared component's default behavior of showing nothing for `active`, since the row order/filter already communicates status).
- **Last Seen** — relative time from `last_seen_at`.
- **Pull (▶)** — calls `useEnqueueTicker()` for that one ticker, same as everywhere else in the app. Works regardless of status (mirrors the reactivation behavior already documented in `routers/queue.md`).
- **Disable / Enable** — toggles `disabled` via `useUpdateTickerStatus()`. Label flips based on current status. Disabled only applies to `active`/`disabled` tickers; for a `removed_from_market` row this button reads "Enable" too (reactivates it, matching the semantics `PATCH` shares with the queue re-activation path).
- **Delete (✕)** — destructive. Confirm via `window.confirm(`Permanently delete ${ticker} and all of its cached data?`)` before calling `useDeleteTicker()`. No undo.

```tsx
function AdminTickerRow({ item, onPull, onToggleStatus, onDelete }: AdminTickerRowProps) {
  const isDisabledOrRemoved = item.status !== 'active'

  return (
    <tr className={`border-t border-slate-800 ${isDisabledOrRemoved ? 'opacity-60' : ''}`}>
      <td className="py-2 font-medium">
        <Link to={`/stock/${item.ticker}`} className="text-white hover:text-indigo-400">{item.ticker}</Link>
      </td>
      <td className="py-2 text-slate-400">{item.name ?? '—'}</td>
      <td className="py-2"><TickerStatusBadge status={item.status} /></td>
      <td className="py-2 text-slate-500">{formatRelativeTime(item.last_seen_at)}</td>
      <td className="py-2 text-right space-x-2">
        <button onClick={onPull} title="Fetch data for this ticker" className="text-slate-400 hover:text-white">▶</button>
        <button onClick={onToggleStatus} className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded border border-slate-700">
          {item.status === 'active' ? 'Disable' : 'Enable'}
        </button>
        <button
          onClick={() => window.confirm(`Permanently delete ${item.ticker} and all of its cached data?`) && onDelete()}
          title="Delete permanently"
          className="text-slate-500 hover:text-red-400"
        >✕</button>
      </td>
    </tr>
  )
}
```

## `StatusFilterTabs`
Simple tab row: All / Active / Disabled / Removed. Sets the `status` query param passed to `useTickers()`.

## Disable vs. Delete
- **Disable** — reversible, keeps all cached data (analyses, financials), just excludes the ticker from `POST /queue/all`. Use this for "I don't want this analyzed right now but might later."
- **Delete** — irreversible, wipes the registry entry and every cached document tied to it. Use this to actually free up space / shrink the dataset. See `DELETE /tickers/{ticker}` in `routers/stocks.md` for exactly what gets removed.

## Dependencies
- `useTickers`, `useUpdateTickerStatus`, `useDeleteTicker`, `useBulkAddTickers` (`hooks/useTickers.md`)
- `useEnqueueTicker` (`hooks/useQueue.md`)
- `TickerStatusBadge` (`components/shared/TickerStatusBadge.md`)
- `react-router-dom` (`Link`)

## Nav
Linked from `Navbar.md` — add an "Admin" link (e.g. a small gear icon on the right side of the nav, near the queue indicator) so it's reachable but not competing with the primary Feed/Institutional Flow/Sectors links.
