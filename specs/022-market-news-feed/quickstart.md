# Quickstart Validation: Market News Feed (022)

Checks that prove the feature works end to end. Contract: [market-news-endpoint.md](./contracts/market-news-endpoint.md); shapes: [data-model.md](./data-model.md).

## Prerequisites

- Docker Compose stack up: `docker compose up -d`
- `.env` has `FMP_API_KEY` (`news/stock-latest` verified entitled 2026-08-16)
- At least a couple of analyzed tickers so the stock grid has content above the panel

## Automated gates (must pass first)

```powershell
# Backend: endpoint caching, 20-cap, normalization, fail-soft, budget guard
cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_market_news.py tests/test_fmp_guard.py -q

# Full backend suite — the new router and settings field must not regress anything
cd backend; .\.venv\Scripts\python.exe -m pytest tests -q

# Frontend: panel rendering, 20-cap, states, page placement
cd frontend; npx vitest run

# Lint (constitution gate)
ruff check backend/
```

## Scenario 1 — The panel appears below the grid (US1)

1. Open `http://localhost:5173/` (Stocks page).
2. Scroll past the analysis grid to the bottom.
3. **Expect**: a market news section with 20 dated rows, newest first, each showing time, source, ticker badge, and headline.
4. Scroll further — **no additional articles load** and the list visibly ends (FR-003).
5. Click a headline → the original article opens in a **new tab**.
6. Click a ticker badge → navigates to that ticker's detail page.

> Note: the grid's own infinite-scroll sentinel sits above the panel, so scrolling down to the news also pages more stocks into the grid. That is pre-existing grid behavior, not a news bug.

## Scenario 2 — Fresh on visit, absent from history (US2)

1. `curl http://localhost:8000/market/news` → `articles` ≤ 20, `stale: false`, `as_of` populated.
2. Immediately re-run the same curl. **Expect**: identical `as_of` — served from cache, no new provider call.
3. Confirm the day's counter moved only once:
   `docker compose exec mongodb mongosh stockai --eval 'db.fmp_usage.find().sort({date:-1}).limit(1)'`
4. Confirm nothing leaked into analyses (FR-008):
   `docker compose exec mongodb mongosh stockai --eval 'db.analyses.findOne({}, {sub_reports:0})'` → no market-news fields.
   Also verify no ticker analysis gained articles: the market feed writes only to `market_news_cache`.
5. Leave the Stocks page open for several minutes — **expect no background refetching** (no polling, FR-010); check the browser network tab stays quiet.

## Scenario 3 — Filter independence (FR-001b)

1. On the Stocks page, apply a sector or signal filter that narrows the grid substantially.
2. **Expect**: the news panel is unchanged — same 20 market-wide articles.
3. Filter to a ticker with no news coverage. **Expect**: the panel still shows the full market list, not an empty one.

## Scenario 4 — Graceful degradation (US3)

> Covers what happens when a refresh *fails*. The hourly reuse behavior itself is Scenario 2 (US2).

1. **Provider failure**: stop outbound access or point `FMP_API_KEY` at an invalid value, restart the backend, and clear the cache:
   `docker compose exec mongodb mongosh stockai --eval 'db.market_news_cache.deleteMany({})'`
   Reload the Stocks page. **Expect**: the grid renders and works normally; the news panel shows a brief unavailable message; the page does **not** show an error state (FR-012).
2. **Stale fallback**: restore the key, load the page once (cache populates), then break the key again and force a cold read by aging the cache:
   `docker compose exec mongodb mongosh stockai --eval 'db.market_news_cache.updateOne({}, {$set:{fetched_at:new Date(Date.now()-2*3600*1000)}})'`
   `curl http://localhost:8000/market/news` → **`200`** with the previously cached articles and `stale: true` (FR-013).
3. **Budget guard**: set `FMP_DAILY_SOFT_CAP=1` in the backend env, restart, age the cache as above, and request twice. **Expect**: no crash, `stale: true`, and a soft-cap warning in the backend log. Restore the cap afterward.

## Scenario 5 — Per-ticker news unchanged (FR-014, no regression)

1. Open any analyzed ticker's detail page → **News** tab.
2. **Expect**: every article concerns that ticker; the sentiment timeline and AI summaries still render — spec 021 behavior is untouched by this feature.
