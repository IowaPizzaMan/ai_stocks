# Contract: Like / Dislike (stock sentiment)

**Story**: US3 (FR-005, FR-006, FR-006a, FR-007, FR-008, FR-009, FR-010)
**Research**: R11

Stored as a nullable `sentiment` field on the existing `ticker_index` document. No new
collection.

---

## `PUT /stocks/{ticker}/sentiment`

Sets or toggles the tag. Ticker is upper-cased by the endpoint.

**Request**

```jsonc
{ "sentiment": "liked" }     // "liked" | "disliked"
```

**Responses**

- **200** `{ "ticker": "NVDA", "sentiment": "liked" }` — tag set.
- **200** `{ "ticker": "NVDA", "sentiment": null }` — **toggle-off**: the requested value
  equalled the stored value, so the tag was cleared (FR-008).
- **404** `{ "detail": "NVDA is not tracked." }` — no `ticker_index` row. Enforces FR-006a
  at the API, not just by hiding the control.
- **422** — `sentiment` not one of the two allowed values.

**Toggle semantics** (FR-007, FR-008): a single field holds the state, so setting
`disliked` over `liked` replaces it — the two can never coexist. Sending the value already
stored clears it. This keeps the UI a pair of idempotent buttons with no separate "clear"
call.

`sentiment_at` is set alongside on write and unset on clear.

## `DELETE /stocks/{ticker}/sentiment`

Unconditionally clears the tag.

- **200** `{ "ticker": "NVDA", "sentiment": null }`
- **404** — not tracked.

Provided so the frontend never has to know the current value to clear it.

---

## `GET /stocks/{ticker}` — added field

The existing ticker record response gains:

```jsonc
{ "ticker": "NVDA", "status": "active", "sentiment": "liked", /* … */ }
```

`sentiment` is `null` when untagged. This is what the detail page reads to render button
state, and its **presence in the record is also what proves the ticker is tracked** — the
same request answers both questions (R11).

---

## `GET /analysis/feed?sentiment=liked` — new filter (FR-009)

New optional query param on the existing feed endpoint: `liked` | `disliked`.

**Implementation** (R11): two steps, not a `$lookup`.

1. Resolve tagged tickers: `db[TICKER_INDEX].find({"sentiment": value}, {"ticker": 1})`.
2. Constrain the existing `analyses` query: `filter["ticker"] = {"$in": tickers}`.

**Rules**
- Combines with every existing filter (ticker, signal, sector, conviction) via AND.
- An empty tagged set yields `{"items": [], "total": 0}` — **not** an unfiltered feed. This
  is the one way this filter can go badly wrong, so it gets an explicit test.
- Interaction with the existing `ticker` substring filter: both apply; `$in` narrows the
  candidate set and the regex still matches within it.

**Assertions**
- `?sentiment=liked` returns only tagged tickers.
- `?sentiment=liked&signal=bearish` intersects correctly.
- Zero tagged tickers returns empty, never everything.
- Untracked/untagged tickers never appear.

---

## Frontend

### `SentimentButtons.tsx` (FR-005, FR-006, FR-006a)

Rendered in `StockDetail.tsx`'s header block, immediately after the `<h1>{symbol}</h1>`
and before the signal/conviction badges.

| Condition | Rendering |
|---|---|
| Ticker record exists (tracked) | Thumbs-up and thumbs-down buttons |
| No ticker record (untracked) | **Nothing rendered at all** — not a disabled control (FR-006a; spec Assumptions) |
| `sentiment === "liked"` | Thumbs-up shown active; thumbs-down inactive |
| `sentiment === "disliked"` | Thumbs-down shown active; thumbs-up inactive |
| `sentiment === null` | Both inactive |

Both buttons carry an `aria-label` (`Like NVDA` / `Dislike NVDA`) and
`aria-pressed` reflecting active state, so the control is operable and assertable without
relying on icon rendering.

Active state must be conveyed by more than color alone (fill/outline change), consistent
with the project's existing status-color practice.

### `useSentiment.ts`

Mutations for set and clear. On success, invalidate:
- `["ticker-record", symbol]` — refreshes button state
- `["feed"]` — so a tagged stock appears/disappears under an active sentiment filter
  immediately (SC-003)

Optimistic update is **not** used: the toggle-off semantics mean the server decides the
resulting state, and guessing it client-side would flicker on the toggle case.

### `FilterBar.tsx` (FR-009)

Two buttons appended after the conviction group, following the identical
`setFilter("sentiment", value)` toggle pattern already used for signal and conviction
(mutually exclusive with each other — selecting `disliked` replaces `liked`, since they
share one search param).

Labels: `liked` / `disliked`.

`Stocks.tsx` adds `sentiment: searchParams.get("sentiment") ?? undefined` to the filters
object passed to `useFeed`.

**Assertions**
- Buttons hidden for an untracked ticker; shown for a tracked one.
- Clicking thumbs-up on an untagged stock marks it liked.
- Clicking thumbs-up again clears it.
- Clicking thumbs-down on a liked stock makes it disliked and not liked.
- `aria-pressed` tracks state.
- Selecting the `liked` filter chip sets `?sentiment=liked`; selecting it again clears it.
