# Research: Market News Feed (022)

All Technical Context unknowns resolved. Decisions D1–D7.

## D1 — The per-symbol route was already correct

**Decision**: Make no change to per-ticker news; record it as a no-regression requirement (FR-014) only.

**Rationale**: The user's premise was that the initially-supplied route fetched all stocks. Verified two ways: [`agent-runner/tools/news.py:129`](../../agent-runner/tools/news.py) builds `news/stock?symbols={ticker}`, and a live call for AAPL returned only AAPL-tagged articles. The route is per-symbol and already scoped correctly, so this feature is purely additive.

**Alternatives considered**: Changing the per-ticker source (rejected — it would break working, spec-021-tested behavior to fix a problem that does not exist).

## D2 — Market-wide source endpoint

**Decision**: `stable/news/stock-latest`.

**Rationale**: Probed live 2026-08-16 — HTTP 200, and each article carries a `symbol`, which is what makes the ticker link in FR-005 possible. The user confirmed this over the alternatives during clarification.

**Alternatives considered**: `news/general-latest` (HTTP 200, entitled, but no `symbol` field so no ticker click-through — kept in the spec's Data Sources as a documented fallback); `news/press-releases-latest` (**HTTP 402, not entitled** — out of scope); aggregating per-symbol calls across tracked tickers (rejected in clarification: costs one call per ticker and surfaces nothing new).

**Observed shape** (drives data-model.md): `{symbol, publishedDate, publisher, site, title, text, image, url}` — identical to the per-symbol route's shape, so normalization can follow the same field mapping already proven in `tools/news.py`.

## D3 — Budget guard: the backend has none

**Decision**: Add `backend/fmp.py` with a `fmp_get()` that increments the shared daily counter and raises a soft-cap error, and route `/market/news` through it. Mirror `agent-runner/tools/fmp_client.py`'s contract exactly: same `fmp_usage` collection, same UTC `%Y-%m-%d` day bucket, same `fmp_daily_soft_cap` setting name, `0` meaning disabled.

**Rationale**: Constitution Principle IV requires a fail-soft budget guard on rate-limited providers. The agent-runner has one; the backend does not — `routers/price.py` and `earnings_data.py::_fmp_get` both call FMP with bare `requests.get` and never increment the counter, so agent-runner's guard currently under-counts the day's true spend. This feature adds a **user-triggered** FMP path, which is precisely the kind that can burn quota through ordinary navigation, so shipping it unguarded would make the gap materially worse. Sharing the counter (Principle VI) means both services throttle against the same number.

**Alternatives considered**: Match the existing unguarded backend pattern (rejected — knowingly adds a third violation of a hard constraint); import agent-runner's client (rejected — the two services deliberately do not share a package, per Principle V); fix all three call sites now (rejected as scope creep into two working paths; recorded in `KNOWN_ISSUES.md` and reported to the user instead).

## D4 — Cache shape and refresh

**Decision**: A single-document `market_news_cache` collection keyed by a constant `key: "stock-latest"`, holding the normalized articles plus `fetched_at`. Freshness is decided **in code** by comparing `fetched_at` against a 60-minute window — the same pattern `routers/price.py` already uses — with **no TTL index**. The endpoint reads the document; when it is missing or older than the window it fetches, normalizes, upserts, and returns.

**Rationale**: The user chose a ~60-minute reuse window (clarification). A TTL index was the first instinct (it matches `MACRO_CACHE`), but it is **incompatible with FR-013**: a TTL index physically deletes the expired document, which is exactly the copy the "serve stale articles when the budget is exhausted" fallback needs. Timestamp comparison expires the data logically while keeping the fallback copy on disk, satisfying both requirements. One document, because the payload is market-wide and small (20 displayed articles), so per-article documents would add query complexity for nothing.

**Alternatives considered**: TTL index (rejected on the FR-013 conflict above — this is the correction that matters most in this file); TTL index plus a separate "last known good" document (rejected — two documents to keep consistent for no benefit over one timestamp check); caching in the frontend only (rejected — a browser refresh would bypass it and hit FMP every time, defeating FR-011).

**Interaction with the frontend cache**: TanStack Query's `staleTime` is set to the same 60 minutes so in-session navigation does not even reach the backend; the server-side TTL is what protects the budget across reloads and restarts.

## D5 — Where the panel lives

**Decision**: A `MarketNewsPanel` component in `frontend/src/components/feed/`, rendered by `Stocks.tsx` after the grouped signal sections and after the existing infinite-scroll sentinel.

**Rationale**: `components/feed/` already holds the Stocks-page building blocks (`AnalysisTile`, `FilterBar`, `SkeletonTile`), so the panel belongs beside them. Rendering after the load-more sentinel keeps the grid's own infinite scroll intact (spec Assumptions) while placing news at the page's end, matching "below the stock grid".

**Alternatives considered**: A new `components/news/` directory (rejected — one component does not warrant a directory); placing the panel between the filter bar and the grid (rejected — contradicts the request).

**Note on scroll interaction**: the grid's `useIntersectionObserver` sentinel sits above the panel, so scrolling to the news will page the grid in as a side effect. Acceptable and pre-existing behavior; called out in quickstart so it is not mistaken for a bug.

## D6 — Panel independence from page filters and from failure

**Decision**: `useMarketNews()` takes no filter arguments and its query key carries no filter state, so grid filters cannot affect it (FR-001b). The panel renders its own loading, empty, and error states locally and is not gated on the feed query's status, so a news failure cannot blank the grid (FR-012).

**Rationale**: Directly implements two clarified requirements. Keeping the query key filter-free is what makes filter-independence structural rather than a convention someone can forget.

**Alternatives considered**: Passing filters through and ignoring them (rejected — invites accidental coupling later).

## D7 — Article display and ticker links

**Decision**: Each row shows publish time, source, ticker badge (when `symbol` is present), and headline linking out with `target="_blank" rel="noreferrer"`. The ticker badge routes internally to `/stocks/{symbol}`. Provider `image` is **not** rendered in v1.

**Rationale**: Matches the existing `NewsTab` row treatment from spec 021, so the two news surfaces look like one system. Skipping images keeps 20 rows scannable and avoids 20 external image requests on the app's home page (the strict-CSP/self-hosted context makes remote images a needless dependency). Articles with no `symbol` still render (spec edge case) — they simply omit the badge.

**Alternatives considered**: Thumbnail per row (rejected for v1 — visual weight and 20 extra network fetches on the landing page); reusing `NewsTab` wholesale (rejected — it is built around the per-ticker `NewsReport` shape with timelines and AI summaries, none of which apply here).
