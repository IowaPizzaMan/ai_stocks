# Contracts: Watchlist Removal & Ticker Deletion

Both endpoints already exist and are unchanged in request/response shape. This document
records the contract this feature depends on (Story 1) and extends the *behaviour* of
(Story 2 — same shape, wider deletion scope), so frontend and backend work can proceed from
a shared, written-down interface instead of re-deriving it from source on each side.

## `DELETE /watchlist/{ticker}`

Non-destructive unpin. **No change in this feature** — consumed as-is by the new Sidebar "x"
control (User Story 1).

**Path params**: `ticker` (string) — case-insensitive, normalized to uppercase server-side.

**Success — 200**:
```json
{ "removed": "AAPL" }
```

**Not found — 404**:
```json
{ "detail": "AAPL not in watchlist." }
```
Frontend handling: per FR-019 (already-gone resolves to the same end state), the UI treats
this 404 the same as success — the row is already absent from the caller's intent, so no
error is surfaced to the user for this specific status code on this specific endpoint.

**Side effects**: deletes exactly one document from `watchlist`. Does not touch
`ticker_index`, `analyses`, or any other collection.

**Guarantees relied on by the frontend (FR-001–FR-005)**:
- Idempotent: calling twice in a row does not error the second time in a way that should
  block a "removed" UI state (handled per the 404 rule above).
- No side effect beyond the single `watchlist` document — safe to call from a lightweight
  hover control with no confirmation step.

---

## `DELETE /tickers/{ticker}`

Destructive full purge. **Behaviour extended by this feature** — request/response shape is
unchanged; the set of collections cleared server-side grows from 5 to 11 (see
[data-model.md](../data-model.md) for the authoritative list and exact filters per
collection).

**Path params**: `ticker` (string) — case-insensitive, normalized to uppercase server-side.

**Success — 200**:
```json
{ "deleted": "AAPL" }
```

**Not found — 404**:
```json
{ "detail": "Unknown ticker." }
```
Frontend handling: same idempotency treatment as the watchlist endpoint — a 404 here means
the ticker is already gone, so the tile should already not be rendering it; treat as
resolved, not as an error to surface (FR-019).

**Side effects (post-extension)**: `delete_one`/`delete_many` across the 11 collections
listed in data-model.md's scope table, keyed by `ticker` (or `{"type": "history", "ticker":
T}` for the mixed-scope `earnings_cache` collection specifically). All-or-nothing from the
caller's perspective per FR-011 — see Implementation Notes below for how that's achieved
without a Mongo multi-document transaction.

**Guarantees relied on by the frontend (FR-006–FR-013)**:
- A 200 response means the ticker is fully gone from every listing surface
  (`ticker_index` deleted) — the frontend need not separately verify `/tickers` or
  `/stocks/search` before dropping the tile from the board.
- A 200 response also implies any watchlist pin is gone — the frontend must invalidate the
  `["watchlist"]` query alongside the feed query on success (see
  [research.md](../research.md) item 4), rather than relying on a second round-trip.
- The deleted ticker can be re-added later via the existing `POST /tickers/bulk` or
  `POST /watchlist/{ticker}` flows, starting with a clean `ticker_index` row (FR-013).

### Implementation notes (not a contract change, but load-bearing for FR-011)

`mongomock`/MongoDB here run without multi-document ACID transactions configured in this
codebase (single-node, no replica set — Constitution V, no infra beyond what's needed). FR-011
("all-or-nothing from the user's perspective") is satisfied the same way the existing
5-collection version already satisfies it: delete `ticker_index` **first**. If any later
`delete_many` in the sequence raises, the ticker is already gone from every listing surface
(search, tile board, `/tickers`), so from the user's *perspective* the deletion took effect
completely even if a trailing cache collection technically still has an orphaned row —
that row is inert (nothing can look it up without a `ticker_index` entry driving the UI to
ask for it) and will be silently cleaned up the next time the same ticker is deleted again
or naturally expires under its collection's TTL where one exists. This mirrors the existing
handler's ordering and is not a new risk introduced by widening the collection list.

---

## Frontend hook contracts (new/reused)

### `useRemoveFromWatchlist()` — reused, unchanged

`frontend/src/hooks/useWatchlist.ts` (existing). `useMutation<{"removed": string}, unknown,
string>` wrapping `DELETE /watchlist/{ticker}`, invalidates `["watchlist"]` on success.

### `useDeleteTicker()` — new

Same shape as `useRemoveFromWatchlist`, wrapping `DELETE /tickers/{ticker}`:

```ts
useMutation({
  mutationFn: async (ticker: string) => {
    const { data } = await api.delete(`/tickers/${ticker.toUpperCase()}`);
    return data as { deleted: string };
  },
  onSuccess: () => {
    // useFeed keys on ["feed", filters] (useAnalysis.ts) — invalidate the whole
    // "feed" key space so every active filter combination refetches, not just
    // whichever filter happened to be active when the delete fired.
    queryClient.invalidateQueries({ queryKey: ["feed"] });
    queryClient.invalidateQueries({ queryKey: ["watchlist"] }); // drops any pin
  },
});
```
