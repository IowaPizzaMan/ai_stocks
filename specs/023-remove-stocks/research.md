# Research: Remove Stocks from Watchlist and Stocks Page

No items in Technical Context were marked `NEEDS CLARIFICATION` — the spec's two
clarification markers (confirmation weight, re-discovery behaviour) were already resolved
before planning. The research below is inventory work needed to size FR-009's "all data
scoped to the ticker" requirement correctly, plus a survey of existing patterns to reuse
rather than reinvent.

## 1. What does "all stored data for a ticker" actually cover?

**Decision**: Extend `delete_ticker` (`backend/routers/stocks.py`) to purge 11 collections
total instead of the 5 it currently touches. Full inventory and exact filters are in
[data-model.md](data-model.md) §"Deletion scope by collection".

**Rationale**: `backend/db.py` and `agent-runner/tools/db.py` declare ~35 collection
constants combined. Grepping every read/write site (not just the constant declarations,
which include a few names — `CONGRESS_TRADES`, `FUND_HOLDINGS`, `STOCK_NEWS`, `COMPANY_INFO`
— that are declared but never actually written anywhere in the current codebase) shows only
11 collections are genuinely keyed by an individual ticker. The rest are market-wide,
sector-wide, or scan-run-scoped caches that don't belong to any single stock. Deleting a
ticker must clear the first group and must leave the second group alone — over-deleting a
shared cache (e.g. `earnings_cache`'s market-wide `calendar`/`universe` docs) would force an
unrelated re-fetch for every other tracked ticker, which conflicts with Constitution
Principle IV (budget-conscious data access).

**Alternatives considered**:
- *Leave the endpoint as-is (5 collections)* — rejected: fails FR-009 outright; stale
  `transcripts_cache`, `earnings_cache` history, `stock_news_cache`,
  `institutional_cache`, and `beneficial_ownership_cache` rows would survive a "delete" and
  the ticker's history would still be reconstructable from cache, contradicting the user's
  explicit ask.
- *Add a generic "delete everywhere this ticker appears" sweep across all collections* —
  rejected: over-broad and fragile. It would need a special case for every
  mixed-scope collection anyway (`earnings_cache`'s `type` discriminator,
  `market_flow_events`' plural `tickers` array), so an explicit per-collection list is no
  more code and is auditable at a glance.

## 2. Confirm-popover pattern: is there an existing component to reuse?

**Decision**: Build one small new component (`RemoveTickerConfirm.tsx`), not a
dialog/modal library.

**Rationale**: Grepping `frontend/src/components` for existing confirm/popover patterns
(`Popover`, `confirm`, `useState.*confirm`) found none — this is the first destructive
confirmation UI in the app. `EarningsCandidateCard.tsx` has a close-on-outside-click modal
pattern (`onClick={(e) => e.stopPropagation()}` on the panel, close button with
`aria-label`) that's a reasonable structural reference for stopPropagation + aria-label
conventions, but it's a full detail panel, not a small inline popover, so it isn't reused
directly. Constitution Principle V (no new infra ahead of demonstrated need) rules out
pulling in a dialog library (e.g. Radix) for one small in-place confirm — Tailwind + a
`useState` boolean + a fixed-position absolute div, matching the pattern `AnalysisTile.tsx`
already uses for its hover preview (`previewOpen` state, `absolute z-20` positioning), is
sufficient.

**Alternatives considered**:
- *`window.confirm()`* — rejected: can't name the ticker with rich formatting, can't be
  styled to match FR-016 ("visually distinguishable from the reversible unpin"), and blocks
  the JS thread, which is worse for keyboard/screen-reader flow (User Story 3) than an
  in-page focusable popover.
- *Browser-native `<dialog>` element* — rejected as unnecessary for a two-button confirm;
  reserved as a future option if the app ever needs a heavier modal.

## 3. Wiring the watchlist "x" — is there already a mutation to call?

**Decision**: Reuse `useRemoveFromWatchlist()` from `frontend/src/hooks/useWatchlist.ts`
as-is. No backend change needed for User Story 1.

**Rationale**: `DELETE /watchlist/{ticker}` (`backend/routers/watchlist.py`) already exists,
already returns 404 on a missing ticker (satisfies FR-019's "already gone" edge case at the
API level — the frontend only needs to treat 404 as a no-op success, not surface it as an
error), and the hook already invalidates the `["watchlist"]` query key on success (satisfies
FR-004's "no full reload" requirement, since `Sidebar.tsx` and the (currently stub)
`Watchlist.tsx` page both read that query). This endpoint and hook are unused by any current
UI — this feature is purely "add the missing button."

**Alternatives considered**: None — the existing contract fully satisfies FR-001–FR-005;
there is no reason to add a second code path.

## 4. Wiring the Stocks-page "x" — request shape for the destructive path

**Decision**: New `useDeleteTicker()` hook wrapping `DELETE /tickers/{ticker}`
(`backend/routers/stocks.py::delete_ticker`), following the exact `useMutation` +
`invalidateQueries` shape already used by `useRemoveFromWatchlist`. On success, invalidate
both the feed query key (so the tile disappears — see `useFeed` in
`frontend/src/hooks/useAnalysis.ts`) and `["watchlist"]` (since deletion also clears any
watchlist pin per FR-009, and the Sidebar must not show a ghost entry).

**Rationale**: The endpoint's request/response contract (`{"deleted": ticker}` on success,
404 with `HTTPException` detail on unknown ticker) already matches the pattern the frontend
uses elsewhere (`api/client.ts` axios instance, error surfaced via the mutation's `isError`/
`error` state). No new backend endpoint needed — only its body (collection purge scope) needs
extending, per research item 1.

**Alternatives considered**: *Optimistic update (remove tile before server confirms)* —
rejected for the destructive path specifically: FR-008/FR-011 require the UI to stay
consistent with actual server state for a destructive, irreversible action; optimistic
removal risks showing "gone" for a delete that then fails, contradicting SC-005. (Optimistic
update is fine and unnecessary to avoid for the non-destructive watchlist unpin, but that
path already works via the existing hook's invalidate-on-success behaviour, which is
effectively instant at local-network latency.)

## 5. Keyboard/focus-reveal pattern (User Story 3)

**Decision**: Reuse Tailwind's `group` + `group-hover` / `:focus-within` pattern already
established for revealing secondary UI on hover elsewhere in the codebase
(`EarningsCandidateCard.tsx`, `Sectors.tsx` hover reveals), extended with `focus-within:`
so keyboard tabbing into the row/tile reveals the control identically to a mouse hover, per
FR-015/Acceptance Scenario 1 of User Story 3. The remove control itself is a real `<button>`
with `aria-label` (e.g. `Remove ${ticker} from watchlist` / `Delete ${ticker} and its data`),
not a styled `<div>`, so it's natively tab-reachable and screen-reader-announced without
extra ARIA roles.

**Rationale**: Matches existing accessibility conventions already in the codebase (
`AnalysisTile.tsx`'s `buildAriaLabel` helper, `EarningsCandidateCard.tsx`'s
`aria-label="Close"`), so no new interaction pattern is introduced — only extended to two
more locations.

**Alternatives considered**: *Always-visible remove control (no hover/focus gating)* —
rejected: contradicts the user's explicit request ("when you hover... I want to see an
'x'") and would add visual noise to a dense tile board; hover/focus-reveal already has
precedent in `AnalysisTile.tsx`'s preview panel.
