# Quickstart: Remove Stocks from Watchlist and Stocks Page

Validation guide for the two removal flows once implemented. Assumes the standard local dev
setup (`docker-compose.yml` — `mongodb`, `backend`, `frontend`) or the equivalent local
processes; no new environment variables or services are introduced by this feature.

## Prerequisites

- Backend running with a Mongo instance reachable at `MONGO_URI` (docker-compose default:
  `mongodb://mongodb:27017`).
- At least one ticker with real stored data — the fastest way is to pull one through the
  existing flow: `POST /tickers/bulk` with `{"tickers": "AAPL"}`, then trigger analysis so
  `analyses`/`financials_cache`/etc. actually populate. A ticker with only a bare
  `ticker_index` row still proves the deletion mechanics but doesn't exercise the widened
  collection scope.
- Frontend dev server running (`npm run dev` in `frontend/`) or the built app served by the
  `frontend` container.

## Scenario 1 — Unpin from the watchlist (User Story 1)

1. Add a ticker to the watchlist: `POST /watchlist/AAPL`.
2. Load the app — confirm `AAPL` appears in the Sidebar watchlist.
3. Hover the `AAPL` row. **Expected**: an "x" control appears on that row only.
4. Click the "x". **Expected**: `AAPL` disappears from the Sidebar list immediately, no page
   reload.
5. Open AAPL's stock detail page (`/stock/AAPL`). **Expected**: prior analysis / fundamentals
   are still shown — nothing was deleted.
6. Verify at the data layer: `db.watchlist.findOne({ticker: "AAPL"})` → `null`.
   `db.analyses.findOne({ticker: "AAPL"})` → still present.

Failure-path check: stop the backend, retry step 4. **Expected**: the row reappears (or never
disappears) and an error message is shown, per FR-005/error-handling requirement — the UI
must not show AAPL as gone while the server still has it pinned.

## Scenario 2 — Delete from the Stocks page (User Story 2)

1. Ensure a ticker (e.g. `NVDA`) has been analyzed at least once, so
   `analyses`/`financials_cache`/`transcripts_cache`/etc. have real rows — see
   [data-model.md](data-model.md) for the full collection list to check.
2. Load the Stocks page. Confirm the `NVDA` tile is present.
3. Hover the tile. **Expected**: an "x" appears in the tile's corner.
4. Click the "x". **Expected**: an inline Confirm/Cancel popover opens naming `NVDA` and
   stating its data will be deleted; no deletion has happened yet.
5. Click **Cancel**. **Expected**: popover closes, tile remains, nothing deleted.
6. Repeat steps 3–4, then click **Confirm**. **Expected**: the tile disappears from the board
   without a full page reload.
7. Verify at the data layer — every collection in data-model.md's scope table should have no
   `NVDA` rows:
   ```js
   ["ticker_index", "analyses", "financials_cache", "watchlist", "institutional_flow",
    "transcripts_cache", "stock_news_cache", "institutional_cache",
    "beneficial_ownership_cache"].forEach(c =>
      print(c, db[c].countDocuments({ticker: "NVDA"})));   // expect 0 for all
   print("earnings_cache history", db.earnings_cache.countDocuments({type: "history", ticker: "NVDA"})); // expect 0
   print("earnings_cache market-wide survives", db.earnings_cache.countDocuments({type: "calendar"})); // expect unchanged, > 0 if it was populated before
   ```
8. Confirm `NVDA` is gone from listing surfaces: `GET /tickers` (not in `items`),
   `GET /stocks/search?q=NVDA` (empty), Sidebar watchlist (absent if it had been pinned).
9. Confirm re-addability: `POST /tickers/bulk` with `{"tickers": "NVDA"}` succeeds and
   creates a fresh `ticker_index` row with no restored history.

Failure-path check: stop the backend after step 4, click Confirm. **Expected**: tile remains
on the board, error message shown, and `db.ticker_index.findOne({ticker: "NVDA"})` still
exists.

## Scenario 3 — Keyboard/screen-reader reachability (User Story 3)

1. Using only the keyboard (Tab / Shift+Tab, no mouse), tab into the Sidebar watchlist list.
   **Expected**: focusing a watchlist row reveals its "x" exactly as hover does, and the
   control receives visible focus.
2. Press Enter/Space on the focused "x". **Expected**: same removal as a mouse click.
3. Repeat for a Stocks-page tile: tab to a tile, confirm its "x" becomes visible on focus,
   activate it, confirm the popover itself is reachable and its Confirm/Cancel buttons are
   tab-order-adjacent and keyboard-activatable.
4. With a screen reader (or by inspecting `aria-label` in devtools), confirm the watchlist
   control announces something like "Remove AAPL from watchlist" and the tile control
   announces something like "Delete NVDA and its data" — distinguishable wording per FR-016.

## Automated coverage (run instead of/alongside the manual walkthrough)

```bash
# Backend — extended delete_ticker collection-purge coverage
cd backend && python -m pytest tests/test_routers.py -k delete_ticker -v

# Frontend — hover/focus reveal, mutation wiring, confirm popover
cd frontend && npm test -- Sidebar AnalysisTile RemoveTickerConfirm
```

Both should be added as part of this feature's tasks (Constitution Principle I — test-first,
not "tested later").
