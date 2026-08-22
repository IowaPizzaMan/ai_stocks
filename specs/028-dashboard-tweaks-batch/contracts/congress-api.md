# Contract: Congress disclosures

**Story**: US4 (FR-011 … FR-018, FR-016a, FR-016b)
**Research**: R4, R7, R8, R10

New router `backend/routers/congress.py` (prefix `/congress`), superseding spec 017's
provisional `GET /market/congress-trades` sketch — that path had no implementation and no
consumer (R10). A supersession note is added to
`specs/017-fmp-migration-admin/contracts/market-data-api.md` rather than leaving the two
contracts silently contradictory.

---

## Pull job: `congress_trades_pull`

Registered in `agent-runner/tools/admin_jobs.py::JOB_HANDLERS`, handler in
`agent-runner/tools/congress.py`. Dataset name `congress_trades`, `stale_minutes: 15`
(both already pinned by 017's registry).

**Behavior**
1. `fmp_get("senate-latest")` and `fmp_get("house-latest")` — 2 calls total.
2. Normalize each row to the `congress_trades` schema (see [data-model](../data-model.md)).
3. Upsert on `trade_id` — re-runs are idempotent.
4. Return the number of rows written.

**Fail-soft** (Principle IV): each chamber is fetched independently inside its own
try/except for `FmpBudgetExceededError` and `requests` errors, following
`tools/economics.py`'s per-sub-pull isolation. One chamber failing must not lose the
other's rows. If **both** fail, the handler raises so the job records `failed`.

**Field mapping** (R7 — confirmed against a live response). Both chambers share the same
core fields; full table in [data-model.md](../data-model.md). The three that change
behavior:

- `politician` is derived: `firstName + " " + lastName`, falling back to `office`. The
  provider has no single name field.
- `person_id` comes from `senateId` — a **person** id (bioguide, `B001236`), repeated
  across all of that member's rows. It is **not** a per-trade id.
- `transaction_type` arrives as `"Purchase"` / `"Sale"`, capitalised — not `buy`/`sell`.
  Stored verbatim; normalised only at read time.

**`trade_id` is a composite hash and must include `transaction_type` and `owner`.** The
provider supplies no per-trade identifier, and a member can file a Purchase and a Sale of
the same ticker on the same date, or hold the same trade Joint and Self. Omitting either
field from the hash makes those rows collide and silently overwrite one another.

**Normalizer tolerance**: exact JSON casing is still unconfirmed, so each field is read
from a small candidate key set, and any row yielding neither a ticker nor a politician is
**skipped with a warning log** rather than raising. Capturing the fixture is now a
verification step, not a discovery step.

`ticker` is stored `null` — never `""` — when absent, so FR-018's link suppression is a
null check. `asset_type` (`"Stock"`) is the more reliable equity discriminator and
`asset_description` identifies a row when `ticker` is null.

---

## `POST /congress/refresh`

Enqueues `congress_trades_pull`. Mirrors `portfolio.py::regenerate_digest` exactly (R4).

- **200** `{ "status": "enqueued", "job_id": "…" }`
- **200** `{ "status": "already_queued", "job_id": "<existing>" }` — a `pending|running`
  job of this type already exists.

---

## `GET /congress/trades`

Cache read only — never calls a provider.

**Query params**

| Param | Type | Notes |
|---|---|---|
| `ticker` | string, optional | case-insensitive **substring**, matching the feed's convention (FR-013) |
| `politician` | string, optional | matches `person_id` exactly when the value looks like a bioguide id, otherwise case-insensitive substring on `politician` (FR-014) |
| `chamber` | `senate` \| `house`, optional | |
| `limit` | int, default 100, max 500 | |

All params combine with AND.

The `person_id` path is what makes the person filter reliable: it is stable per member, so
a member filing under varying name spellings still resolves to one person — the spec's
Edge Case accepting that limitation no longer applies (R7).

**Response** — always 200; an empty collection is a valid empty state, not an error
(matching `market.py::get_market_news` and `portfolio.py::get_digest`):

```jsonc
{
  "items": [
    {
      "trade_id": "…",
      "chamber": "senate",
      "person_id": "B001236",
      "politician": "John Boozman",
      "district": "AR",
      "owner": "Joint",                   // often null
      "ticker": "AVGO",                   // null for non-equity disclosures
      "asset_description": "Broadcom Inc",
      "asset_type": "Stock",
      "transaction_type": "Purchase",     // provider casing, verbatim
      "amount_range": "$1,001 - $15,000",
      "transaction_date": "2025-04-08",
      "disclosure_date": "2026-08-20",
      "link": "https://efdsearch.senate.gov/search/view/ptr/…"
    }
  ],
  "total": 128,
  "as_of": "2026-08-22T09:00:00Z"    // max collected_at; null when empty
}
```

Note the sample's real dates: disclosed 2026-08-20 for a trade made 2025-04-08 — a
16-month filing lag. This is exactly why the summary window filters `disclosure_date`
rather than `transaction_date` (R8); a transaction-date window would have hidden this row
entirely.

Sorted by `disclosure_date` descending — what became public most recently.

---

## `GET /congress/summary`

Computed per request from stored rows. **Pure arithmetic — no LLM** (Principle III, R8).

```jsonc
{
  "window_days": 90,
  "most_bought": [
    { "ticker": "NVDA", "buy_count": 7 },
    { "ticker": "AAPL", "buy_count": 4 }
  ],
  "high_dollar": [
    {
      "trade_id": "…", "politician": "Jane Doe", "ticker": "NVDA",
      "transaction_type": "Purchase", "amount_range": "$250,001 - $500,000",
      "disclosure_date": "2026-08-14"
    }
  ],
  "high_dollar_threshold": "$100,001",
  "as_of": "2026-08-22T09:00:00Z"
}
```

Both lists are empty arrays when nothing qualifies — the frontend renders FR-016b's
explicit "none in this window" message rather than hiding the section.

### `rank_most_bought(rows, now, days=90) -> list[dict]` (FR-015)

- Include rows whose `disclosure_date` is within `days` of `now` **and** whose
  `transaction_type` indicates a purchase.
- Group by `ticker`; ignore rows with a null ticker.
- Sort by `buy_count` descending, then `ticker` ascending — the tiebreak makes output
  stable and therefore assertable.

**Buy predicate**: the provider sends `"Purchase"` / `"Sale"` (capitalised), so the test is
case-insensitive on `"purchase"`. It must **not** be a substring test for `"buy"` (never
appears) and must **not** treat the partial-sale variants these filings commonly use —
`"Sale (Full)"`, `"Sale (Partial)"` — as anything but sales. An `is_purchase(t)` helper
holds this rule in one tested place rather than inline at both call sites.

**Window is on `disclosure_date`, not `transaction_date`** (R8): disclosures are routinely
filed weeks late, so a transaction-date window would hide newly-disclosed older trades —
exactly the ones worth surfacing.

### `high_dollar(rows, now, days=90, threshold=100_001) -> list[dict]` (FR-016)

- Same window and date field.
- Parse `amount_range`'s bounds; include the row when its **upper bound ≥ threshold**.
- **Never compute a midpoint, average, or point estimate** (FR-016a).
- A row whose `amount_range` is absent or unparseable returns `None` from the parser and
  is excluded — it still appears in the main table, just never flagged.
- Sort by `disclosure_date` descending.

### Bracket parser

`parse_amount_bounds(s) -> tuple[int, int] | None`

Extracts numeric bounds from the disclosed string, tolerating `$`, thousands separators,
and either hyphen or en-dash separators. Open-ended forms (`"Over $1,000,000"`) yield a
lower bound with the upper bound equal to it, which still passes a `≥` test correctly.
Returns `None` for anything unparseable — never raises, never guesses.

**Assertions**: each standard bracket, including the real `"$1,001 - $15,000"` form; the
exact `$100,001` boundary (inclusive); the bracket immediately below it (excluded);
open-ended "over" form; en-dash and hyphen; absent; garbage string; null ticker excluded
from ranking; count tiebreak ordering; a row just inside and just outside the 90-day
window; `is_purchase` over `"Purchase"`, `"Sale"`, `"Sale (Full)"`, `"Sale (Partial)"`,
mixed case, and null.

---

## Frontend

### Nav (FR-011)

`Navbar.tsx` gains `{ to: "/congress", label: "Congress" }`. `App.tsx` registers
`<Route path="/congress" element={<Congress />} />`.

### `Congress.tsx`

Summary section above the table. Two filter inputs (ticker, politician), both debounced
and written to URL search params via the project's standard pattern — `useDebounce` and
`setSearchParams`, as `FilterBar.tsx` already does. A Refresh button posts to
`/congress/refresh`.

Empty collection → an empty state naming the Refresh button, mirroring the digest panel's
"click Regenerate" state.

### `CongressTable.tsx` (FR-017, FR-018)

Columns: chamber, politician, ticker, asset description, type, amount range, transaction
date, disclosure date.

- `ticker` non-null → `<Link to={`/stock/${ticker}`}>` (singular — R1).
- `ticker` null → plain text (e.g. `—`), **no link element at all**, so there is nothing
  clickable to mislead. `asset_description` carries the identity in that case, which is why
  it earns a column.
- Both dates are shown. Given filing lags of a year or more are normal in this data
  (see the sample above), collapsing them into one date would actively mislead.

### `CongressSummary.tsx` (FR-015, FR-016, FR-016b)

Most-bought list with counts; high-dollar list showing the bracket **as text, never a
number**. Each renders its own explicit empty message when its array is empty.

**Assertions**
- Ticker filter narrows rows; politician filter narrows rows; both together intersect.
- A null-ticker row renders without a link.
- Clicking a ticker navigates to `/stock/<TICKER>`.
- Empty `high_dollar` renders the "none in this window" message, not a hidden section.
- Amount is rendered verbatim as the bracket string.
