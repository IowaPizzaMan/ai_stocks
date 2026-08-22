# Data Model: Company Profile, Peers & Navigation Tweaks

**Feature**: `029-company-profile-tweaks` | **Date**: 2026-08-22

Three changes: one collection populated for the first time, two scalars denormalized onto
an existing collection, and one collection removed.

---

## 1. `company_info` — populated (collection name already reserved)

Declared since spec 017 in both `backend/db.py:46` and `agent-runner/tools/db.py:51`,
never written to until now (R1). One document per ticker.

**Index** (add to `agent-runner/tools/db.py::ensure_indexes`):

```python
db[COMPANY_INFO].create_index([("ticker", ASCENDING)], unique=True)
```

**No TTL** — deliberate, same discipline as `price_history` and `stock_news_cache`.
Expiry would silently remove a ticker's sector and industry, dropping it out of the
Sectors rollup and the industry filter with no error anywhere (R1).

### Document shape

```jsonc
{
  "ticker": "AAPL",                      // unique key, uppercase

  // --- profile: refreshed every pull (FR-008) ---
  "profile": {
    "name": "Apple Inc.",
    "exchange": "NASDAQ",                 // FMP "exchange" (short form)
    "exchange_full": "NASDAQ Global Select",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "country": "US",
    "currency": "USD",
    "website": "https://www.apple.com",
    "ceo": "Timothy D. Cook",
    "full_time_employees": 166000,
    "ipo_date": "1980-12-12",
    "description": "Apple Inc. is a global technology corporation…",
    "image": "https://images.financialmodelingprep.com/symbol/AAPL.png",
    "default_image": false,               // true ⇒ treat as "no logo" (R6)
    "cik": "0000320193",
    "isin": "US0378331005",
    "cusip": "037833100",
    "phone": "(408) 996-1010",
    "address": "One Apple Park Way",
    "city": "Cupertino",
    "state": "CA",
    "zip": "95014",

    // displayed stats sourced from here (FR-011a)
    "market_cap": 4543533578600,
    "beta": 1.086,
    "last_dividend": 1.05,
    "range": "224.69-344.57",             // 52-week, provider's string form
    "average_volume": 53759263,

    // stored as fetched, NEVER displayed as the app's price (FR-011b, R7)
    "price": 309.35,
    "change": -1.95,
    "change_percentage": -0.62641,
    "volume": 42216056,

    "is_etf": false,
    "is_fund": false,
    "is_adr": true,
    "is_actively_trading": true
  },
  "profile_fetched_at": ISODate("2026-08-22T14:03:00Z"),
  "profile_outcome": "confirmed",         // confirmed | unavailable

  // --- peers: 90-day window (FR-008a) ---
  "peers": [
    { "symbol": "GOOGL", "name": "Alphabet Inc.", "price": 333.84, "market_cap": 4040168831718 }
  ],
  "peers_fetched_at": ISODate("2026-08-22T14:03:01Z"),
  "peers_outcome": "confirmed",

  // --- employee counts: 90-day window (FR-008a) ---
  "employee_counts": [
    {
      "period_of_report": "2025-09-27",
      "filing_date": "2025-10-31",
      "form_type": "10-K",
      "employee_count": 166000,
      "source": "https://www.sec.gov/Archives/edgar/…"
    }
  ],
  "employee_counts_fetched_at": ISODate("2026-08-22T14:03:02Z"),
  "employee_counts_outcome": "confirmed"
}
```

### Field notes

- **Naming**: provider `camelCase` is normalized to `snake_case` on write, matching how
  `tools/price_store.py` and `tools/congress.py` shape provider payloads. The exception is
  `range`, kept as the provider's `"low-high"` string and split for display — parsing it
  into two floats at write time would lose the provider's own formatting for the odd
  symbol that returns something non-numeric.
- **`default_image`**: FMP's own placeholder flag. `true` means skip the image request
  entirely and render the monogram fallback (R6) — do not fetch and hope.
- **`price`/`change`/`volume`**: retained for diagnostics only. FR-011b forbids displaying
  them as the stock's current price; the UI reads bars instead (R7).

### Freshness rules

| Dataset | Refresh trigger | Window |
|---|---|---|
| `profile` | Every analysis pull (FR-008) | none — always refetched |
| `peers` | Analysis pull, if `peers_fetched_at` older than 90d (FR-008a) | 90 days |
| `employee_counts` | Analysis pull, if `employee_counts_fetched_at` older than 90d | 90 days |
| any, `*_outcome == "unavailable"` | Retried on the **next** pull regardless of window | — |

The last row is the spec-018 lesson (R2): a 402/403/budget degradation must not be frozen
in place for 90 days. A retry that promotes `unavailable → confirmed` updates only that
dataset's payload and outcome; it must **not** slide the other datasets' `fetched_at`.

A **full refresh** (`mode="full"`) bypasses the windows entirely and refetches all three
(FR-008b).

### Write path

`agent-runner/tools/company_profile.py` writes this document itself at fetch time — inside
the tool, not from `Crew.run()`'s return value. A profile therefore persists even if a
later LLM stage in the same pull raises, which is the same durability property
`financials.get_financials` has.

---

## 2. `ticker_index` — two field additions (denormalized)

Per R3. Written by the same profile fetch, in the same transaction-free upsert as the
`company_info` write.

| Field | Status | Purpose |
|---|---|---|
| `sector` | **exists already** (`register_ticker`, `db.py:183`) — now actually populated | Sectors rollup, feed sector filter, `macro_worker`'s `distinct("sector")` |
| `industry` | **new** | Stocks page industry filter (FR-024/FR-025) |
| `name` | exists | Refreshed from the profile (better than the registry's guess) |
| `logo_url` | **new** | Lets tiles and hover cards render logos from the feed response without a per-ticker profile fetch (FR-021/FR-021a) |

`logo_url` is `null` when `default_image` is true or no profile exists.

**No new index required** — `ticker_index` already has a unique index on `ticker` and an
index on `status`. The filter path resolves tickers by `sector`/`industry` and then
constrains `analyses` by `$in`, so these fields are read in a single small collection scan,
not used as a sort key.

**Consumers that start working with no code change**: `macro_worker.py:26` already reads
`db[TICKER_INDEX].distinct("sector", {"sector": {"$nin": [None, ""]}, …})`. Once profiles
land, it begins producing real per-sector macro reads instead of nothing.

---

## 3. `analyses.sector` — removed from the contract

Not a migration: **nothing writes this field today** (R5 — `portfolio_strategist.SCHEMA`
has no `sector`, and no other agent supplies one). There is no legacy data to move.

- `backend/routers/sectors.py::get_sectors` stops matching on `analyses.sector` and joins
  `ticker_index` instead.
- `backend/routers/analysis.py::get_feed`'s `sector` param stops filtering
  `analyses.sector` and adopts the two-step ticker resolution.
- `GET /analysis/sector/{sector}` likewise.

---

## 4. `portfolio_digest_cache` — removed

Singleton document collection introduced by 027. Per FR-019 and clarification 1: stop
writing, delete records, remove the collection and its constant from both `db.py` files.
Runtime code never drops collections, so the drop is a documented one-time mongosh step
(R14) — see [quickstart.md](./quickstart.md). Full file inventory in
[contracts/portfolio-digest-removal.md](./contracts/portfolio-digest-removal.md).

---

## Entity relationships

```text
ticker_index (1) ──── (0..1) company_info      both keyed by `ticker`
      │                        │
      │ sector, industry       │ peers[] → symbols that may or may not
      │ (denormalized)         │           exist in ticker_index (R8)
      ▼                        ▼
  feed filters &          Overview tab sections
  Sectors rollup          (profile / peers / employees)

analyses (1 per ticker) ──── joined to ticker_index by `ticker` for the
                             Sectors rollup and the sector/industry filters
```

A peer symbol is deliberately **not** a foreign key — peers routinely reference companies
the user does not track, and `/stock/{symbol}` already renders that untracked state (R8).
