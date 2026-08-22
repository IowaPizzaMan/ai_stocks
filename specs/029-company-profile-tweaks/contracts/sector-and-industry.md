# Contract: Sector re-sourcing & the industry filter

**Story**: US5 (FR-024 – FR-027a), plus FR-018/FR-021a's feed-response needs
**Research**: R3, R5, R13

---

## Background: what is actually broken today

`analyses.sector` is **never written** (R5). `Crew.run()` builds its document from
`**synthesis`, and `portfolio_strategist.SCHEMA` has no `sector` property. So:

- `GET /sectors` matches `{"sector": {"$nin": [None, ""]}}` → matches nothing → the
  Sectors page's "No sector data yet" empty state is permanent.
- `GET /analysis/feed?sector=X` → always empty.
- This is the **first open bug in `KNOWN_ISSUES.md`**, which proposes this exact fix.

There is therefore **no migration**: no legacy values to preserve, no dual-read window, no
fallback path. The old field is simply not read any more.

---

## The single sector source (FR-026)

`ticker_index.sector` and `ticker_index.industry`, written by the profile fetch
(see [data-model.md](../data-model.md) §2).

| Consumer | Before | After |
|---|---|---|
| `GET /sectors` rollup | `analyses.sector` (always empty) | join `ticker_index` |
| `GET /sectors/{sector}` | `analyses.sector` | two-step via `ticker_index` |
| `GET /analysis/feed?sector=` | `analyses.sector` | two-step via `ticker_index` |
| `GET /analysis/sector/{sector}` | `analyses.sector` | two-step via `ticker_index` |
| `macro_worker` per-sector reads | `ticker_index.sector` (empty) | **unchanged code**, now populated |

The last row is the payoff of R3: `macro_worker.py:26` already does
`db[TICKER_INDEX].distinct("sector", …)` and starts working with no edit.

---

## Filter implementation — reuse 028's two-step, exactly

`backend/routers/analysis.py::get_feed` already resolves the `sentiment` filter by reading
matching tickers from `ticker_index` and constraining `analyses` with `$in`. Sector and
industry adopt the identical shape and join the same `ticker_conditions` list, so all
filters compose as AND (FR-025).

```python
if sector:
    matched = [d["ticker"] for d in db[TICKER_INDEX].find({"sector": sector}, {"_id": 0, "ticker": 1})]
    ticker_conditions.append({"ticker": {"$in": matched}})

if industry:
    matched = [d["ticker"] for d in db[TICKER_INDEX].find({"industry": industry}, {"_id": 0, "ticker": 1})]
    ticker_conditions.append({"ticker": {"$in": matched}})
```

**Critical invariant, inherited from 028** (`analysis.py:38-41` documents it): an empty
`matched` list MUST still append `$in: []` so the filter matches nothing. Skipping the
condition when nothing matches silently falls back to the **unfiltered** feed — the exact
bug 028 called out. A test must cover "filter by a sector no tracked ticker has → empty
feed, not the full feed."

`ticker_conditions` currently collapses to `filter.update(...)` for one condition and
`filter["$and"] = ...` for more. With up to four ticker-constraining conditions (search,
sentiment, sector, industry), keep that shape — it already generalizes.

---

## Feed response enrichment (needed by FR-021a)

Grid tiles and hover cards need `logo_url` and `name` per item without firing a request
per tile. `get_feed` already reads `ticker_index` for the sentiment filter; extend it to
attach, for the page's items only:

```jsonc
{ "ticker": "AAPL", "signal": "bullish", …, "name": "Apple Inc.", "logo_url": "https://…" }
```

One `ticker_index` query per feed page (`{"ticker": {"$in": page_tickers}}`), not per item.
`logo_url` is `null` when unknown — the frontend's `CompanyLogo` fallback covers it.

---

## `GET /sectors` — rollup after the switch

Same response shape as today (`sector`, `bullish_count`, `neutral_count`, `bearish_count`,
`ticker_count`, `top_ticker`), so `Sectors.tsx`'s `SectorSummary` type is unchanged.

Algorithm — keep the rollup in Python, per the module's existing design (R3):

1. Aggregate `analyses` → latest doc per ticker (existing `$sort`/`$group`/`$replaceRoot`
   pipeline, minus the `$match` on `sector`).
2. One `ticker_index` read for those tickers → `{ticker: (sector, industry)}`.
3. Bucket in Python. A ticker whose sector is missing/empty goes to the **`"Unclassified"`**
   bucket (FR-027) rather than being dropped.

**`"Unclassified"` is a reserved literal**, not a null. It sorts last regardless of
alphabetical order, and the UI pairs it with copy explaining these stocks await their next
pull (FR-027) — the `Sectors.tsx` card/row rendering needs a special case so it does not
read as a real sector named "Unclassified".

**FR-026a — rollup ↔ grid consistency**: because both the rollup and the feed filter read
`ticker_index.sector`, a sector counting N tickers and `/?sector=X` returning N items is
structurally guaranteed. The test asserts the counts match rather than asserting a
hard-coded number.

---

## `GET /stocks/industries` (new, R13)

```jsonc
{ "industries": ["Consumer Electronics", "Semiconductors", "Software - Infrastructure"] }
```

- Distinct non-null, non-empty `industry` values from `ticker_index`, restricted to
  tickers the user actually tracks (exclude `status: "removed_from_market"`).
- Sorted alphabetically.
- **200 with `[]`** before any profile exists — a valid day-one state, not an error.

FR-024's "no offered choice yields an empty grid" follows from sourcing the list from the
same collection the filter queries.

---

## Frontend

### `FilterBar` — industry `<select>` (R13)

A `<select>` rather than a pill row: industry is open-ended (FMP's taxonomy runs to ~150
values) and pills would wrap the bar into several lines.

- Options from `useIndustries()`, plus an "All industries" option mapping to no filter.
- Bound to the `industry` search param, `{ replace: true }`, same as every other filter.
- Follows the existing `setFilter` convention: selecting the active value clears it.
- Hidden entirely when the industries list is empty — an empty dropdown is a dead control.

**Watch the mount guard**: `FilterBar`'s debounced ticker effect is deliberately guarded
against firing a no-op navigation on mount, because `setSearchParams` navigates via a
hash-less relative URL and would clear the URL hash (`FilterBar.tsx:27-33`). That comment
references the Stocks page's `#news` anchor, which R9 removes — update the comment, but
**keep the guard**: `StockDetail` still uses hash tabs and the same `FilterBar` logic
pattern applies.

### `Sectors.tsx`

- `SectorRow` / `SectorCard` render the `"Unclassified"` bucket with distinct copy and
  pin it last.
- The existing "No sector data yet" empty state stays for the genuinely-empty case, but its
  copy ("pull some tickers from the feed first") is now finally **true** rather than
  permanently misleading.
