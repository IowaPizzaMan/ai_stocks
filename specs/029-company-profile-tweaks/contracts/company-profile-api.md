# Contract: Company profile, peers & employee counts

**Story**: US2, US6, US7 (FR-005 – FR-017, FR-021, FR-021a)
**Research**: R1, R2, R4, R6, R7, R8, R12

---

## Provider fetch — `agent-runner/tools/company_profile.py` (new)

All three calls go through `tools.fmp_client.fmp_get` (Principle IV — throttle, soft-cap
guard, pull-cost metric attribution). No direct `requests` use.

| Function | FMP path | Window |
|---|---|---|
| `get_profile(ticker, db=None)` | `profile?symbol={t}` | none — every pull |
| `get_peers(ticker, db=None)` | `stock-peers?symbol={t}` | 90 days |
| `get_employee_counts(ticker, db=None)` | `historical-employee-count?symbol={t}` | 90 days |
| `refresh_company_info(ticker, mode="delta", db=None)` | orchestrates the three | `mode="full"` bypasses windows (FR-008b) |

`CACHE_DAYS = 90`, matching `tools/financials.py`.

### Degradation matrix (FR-006, FR-009, Principle IV)

| Condition | Behavior | `*_outcome` |
|---|---|---|
| 200 with payload | Store payload | `confirmed` |
| 200, empty payload | Store `[]`/`{}` — a real answer | `confirmed` |
| 402 / 403 (not entitled) | Keep prior stored payload, log at info | `unavailable` |
| `FmpBudgetExceededError` | Keep prior stored payload, log at warning | `unavailable` |
| Other `HTTPError` | Re-raise | — |

`unavailable` datasets are retried on the **next** pull regardless of the 90-day window
(R2 — the spec-018 lesson). A retry updates only its own payload/outcome and must not
slide the other datasets' `fetched_at`.

**`refresh_company_info` never raises on a provider failure.** A pull whose profile fetch
fails still completes its analysis; the affected surfaces render their unavailable states
(FR-009).

### Entitlement probe (R4)

Add to `fmp_client.PROBE_ENDPOINTS`:

```python
"stock_peers": "stock-peers?symbol=AAPL",
"employee_count": "historical-employee-count?symbol=AAPL",
```

(`profile` is already covered by the existing `company_info` family.)

### Crew integration

`refresh_company_info(ticker, mode=mode, db=db)` is registered as a prefetch job in
`Crew._prefetch`'s `jobs` dict so it is stage-recorded by `metrics.stage_recorder` and
parallelizable with the other prefetches. The tool writes `company_info` and updates
`ticker_index` itself; `Crew.run()`'s returned analyses document is **unchanged in shape**
— no `sector` is added to it (R5).

**Cost**: 3 FMP calls on a cold ticker, 1 on a warm one (profile only), 0 on a page view.

---

## Read endpoints

All four are **cache-only**. None may issue a provider call — a page view that costs FMP
budget violates Principle IV and SC-010.

### `GET /stocks/{ticker}/profile`

- **200** — profile found:

```jsonc
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "exchange": "NASDAQ",
  "exchange_full": "NASDAQ Global Select",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "country": "US",
  "currency": "USD",
  "website": "https://www.apple.com",
  "ceo": "Timothy D. Cook",
  "full_time_employees": 166000,
  "ipo_date": "1980-12-12",
  "description": "…",
  "logo_url": "https://images.financialmodelingprep.com/symbol/AAPL.png",  // null when default_image
  "market_cap": 4543533578600,
  "beta": 1.086,
  "last_dividend": 1.05,
  "range_low": 224.69,
  "range_high": 344.57,
  "average_volume": 53759263,
  "is_etf": false,
  "is_fund": false,
  "is_actively_trading": true,
  "fetched_at": "2026-08-22T14:03:00Z"
}
```

- **404** — no profile stored for this ticker. The frontend renders FR-009's "profile
  unavailable" state. **404, not an empty 200**: "we have never fetched this" and "this
  company has no data" are different conditions and the UI copy differs.

`price`, `change`, `change_percentage`, and `volume` are **deliberately not in the
response** (FR-011b) — they exist in Mongo for diagnostics but must not reach the UI,
where they could be rendered as a live price. `range_low`/`range_high` are split from the
provider's `"224.69-344.57"` string here, in the backend, so every consumer gets numbers.

### `GET /stocks/{ticker}/peers`

- **200** — always, empty is valid:

```jsonc
{
  "ticker": "AAPL",
  "peers": [
    { "symbol": "GOOGL", "name": "Alphabet Inc.", "price": 333.84, "market_cap": 4040168831718 }
  ],
  "fetched_at": "2026-08-22T14:03:01Z"   // null if never fetched
}
```

Sorted market cap **descending**, nulls last, ties broken by symbol ascending (R8) — the
sort happens server-side so every client gets the same order.

### `GET /stocks/{ticker}/employee-count`

- **200** — always, empty is valid:

```jsonc
{
  "ticker": "AAPL",
  "records": [
    { "period_of_report": "2025-09-27", "filing_date": "2025-10-31",
      "form_type": "10-K", "employee_count": 166000, "source": "https://…" }
  ],
  "fetched_at": "2026-08-22T14:03:02Z"
}
```

Sorted by `period_of_report` **ascending** (oldest first) so the chart plots
chronologically without client-side sorting (FR-015).

### `GET /stocks/industries`

See [sector-and-industry.md](./sector-and-industry.md).

---

## Frontend contract

### `components/shared/CompanyLogo.tsx` (new, R6)

```tsx
<CompanyLogo ticker="AAPL" src={logoUrl} size="sm" | "md" | "lg" />
```

- `src` null/undefined → render the monogram fallback immediately, no network request.
- `onError` → swap to the same fallback. Never leave a broken image (FR-013).
- Fallback: the ticker's first 1–2 characters on a neutral `zinc` tile, same dimensions as
  the image so nothing shifts.
- `loading="lazy"`, fixed width/height attributes to reserve layout space.

Used by three surfaces with identical fallback behavior: `AnalysisTile` (`sm`, FR-021a),
`TilePreview` (`sm`, FR-021), `StockDetail` header (`lg`, FR-012).

### Logo source for grid surfaces

Tiles and hover cards read `logo_url` off the **feed response** (denormalized onto
`ticker_index`, see [data-model.md](../data-model.md) §2), not from a per-ticker profile
call. A 60-tile grid must not fire 60 profile requests.

This requires `AnalysisFeedItem` to carry `logo_url` and `name` — both come from
`ticker_index`, which `get_feed` already reads for the sentiment filter. See
[sector-and-industry.md](./sector-and-industry.md) for how the feed response is enriched.

### `CompanyProfileSection` (new)

Topmost section of the Overview tab (FR-010). Renders:

- Identity row: logo, name, ticker, exchange, sector, industry, country.
- Stats grid: price / change / change % / volume **from bars** (R7, FR-011a); market cap,
  beta, last dividend, 52-week range, average volume from the profile.
- Description, website link, CEO, employees, IPO date.
- `fetched_at` shown as "profile as of …" (FR-007).

Price derivation from `useStockPriceHistory`'s daily bars, already in the query cache:

```text
price   = bars[last].Close
change  = bars[last].Close − bars[last-1].Close
change% = change / bars[last-1].Close
volume  = bars[last].Volume
```

With fewer than 2 bars, render price alone and omit change (no `NaN`, no `0.00%`).

**ETF/fund handling** (edge case): when `is_etf` or `is_fund` is true, omit CEO,
employees, and industry rows rather than rendering blanks.

### `PeersSection` (new)

Table of symbol / name / price / market cap. Market cap abbreviated (`4.04T`, `166.0B`)
per FR-017; a null market cap renders `—`, never `0` (edge case). Each row links to
`/stock/{symbol}` (FR-014). Empty `peers` → "No peers published for this company."

### `EmployeeCountChart` (new, R12)

Recharts `LineChart`, X = `period_of_report`, Y = `employee_count` with a `166k`-style tick
formatter. Tooltip shows period, headcount, and `form_type`. A single record renders with
a visible `dot` so it is not an invisible line. Empty → "No reported employee history."

### Hooks

`hooks/useCompanyProfile.ts` exports `useCompanyProfile(ticker)`, `usePeers(ticker)`,
`useEmployeeCounts(ticker)` — TanStack Query, `refetchInterval: false` (constitution),
`staleTime` 1h to match `usePriceHistory`. `useCompanyProfile` must not treat 404 as an
error state to retry; it is a valid "no profile yet" answer.
