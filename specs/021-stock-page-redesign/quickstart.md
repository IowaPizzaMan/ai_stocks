# Quickstart Validation: Stock Page Redesign (021)

Runnable checks proving the feature end-to-end. Contracts: [price-endpoint.md](./contracts/price-endpoint.md), [analysis-subreports.md](./contracts/analysis-subreports.md); shapes: [data-model.md](./data-model.md).

## Prerequisites

- Docker Compose stack up: `docker compose up -d` (mongodb, backend, frontend, agent-runner, ollama)
- `.env` has `FMP_API_KEY` (news/insider-stats/beneficial-ownership verified entitled 2026-08-16) and Finnhub key
- A ticker with long history and news flow (AAPL) registered in `ticker_index`

## Automated gates (must pass before manual checks)

```powershell
# Backend: yearly resolution + existing price tests
cd backend; python -m pytest tests/test_price.py -q

# Agent-runner: news tool, keyword/timeline math, insider stats, beneficial ownership, changes diff
cd agent-runner; python -m pytest tests/ -q

# Lint (constitution gate)
ruff check backend/; ruff check agent-runner/ scripts/

# Frontend: indicators, prose formatter, candlestick, tab default, per-tab empty states
cd frontend; npx vitest run
```

## Scenario 1 — Charts tab default with corrected aggregation (US1, US2)

1. Open `http://localhost:5173/stocks/AAPL` (no hash).
2. **Expect**: Charts tab active; four candlestick panels (D/W/M/Y); Price ROC + Volume ROC below; indicator grid below that; no Deep Dive section anywhere; no charts above the tab bar.
3. `curl "http://localhost:8000/stocks/AAPL/price?resolution=yearly"` → ≤ 15 bars, one per year.
4. Count candles: monthly ≈ 36, yearly 10–15. Hover a monthly candle → tooltip shows that month's OHLC.
5. Short-history check: open a recent IPO ticker → monthly/yearly panels render available periods; no errors.

## Scenario 2 — Indicators per timeframe (US3)

1. On AAPL Charts tab, verify z-score, stochastic, and ATR% rows each show four timeframe panels; verify the MACD row shows only three panels (daily, weekly, monthly) — no yearly MACD panel at all.
2. Stochastic values within 0–100 with 80/20 zones shaded.
3. Monthly MACD on a ticker with under 3 years of history shows the "insufficient history" state — expected behavior, not a bug.

## Scenario 3 — Pull-time news pipeline (US5, US8)

1. Click **Pull ▶** on AAPL; wait for the analysis to land.
2. In Mongo: `db.analyses.findOne({ticker:"AAPL"}, {sub_reports:{news:1}, changes_since_last:1})` → `news.articles` spans a full 30 days (hundreds of articles on a mega-cap) with `bullish_count`/`bearish_count`; 15 newest have `ai_summary`; `timeline` ascending; `trend` populated; `stance.reasoning` cites a headline; `days_covered`/`window_days` present.
3. News tab: timeline chart on top covering the month, 25 articles listed with a "Show 25 more" button, as-of label = pull date.
4. Ticker with no coverage → News tab shows the empty state.
5. AI Summary: News Stance section present; **no** breadth/market-timing chart; caveats still render; after a second pull, "what changed" note appears (or states no material change).

## Scenario 4 — Insider & Institutional visuals (US7)

1. AAPL Insider tab: quarterly acquired-vs-disposed bars + buy/sell ratio trend + net-direction verdict above the existing 90-day table.
2. OWL Institutional tab: beneficial-ownership filings listed (filer, date, % of class) with stake-direction verdict; cached 13F summary still shown with its staleness label.
3. Confirm logs show **no** calls to `institutional-ownership/latest` (not entitled).

## Scenario 5 — Readability & removals (US4)

1. Overview: verdict renders as short paragraphs/bullets with emphasized levels/percentages; **no** Position Management section (but `position_management` still present in the Mongo document).
2. AI Summary narratives use the same formatting.
3. Old links: `/stocks/AAPL#overview` shows Overview; `/stocks/AAPL#bogus` falls back to Charts.

## Scenario 6 — Sentiment at a glance (US6)

1. Sentiment tab: headline gauge + the same timeline chart as the News tab in the first screenful; tone evidence / keyword pills / earnings-surprise below.

## Budget guard check (FR-026)

1. Temporarily set `FMP_DAILY_SOFT_CAP=1` in agent-runner env; pull a ticker.
2. **Expect**: run completes; news/insider/institutional sections serve stale cache with prior as-of dates; log shows the soft-cap warning; no crash. Restore the cap afterward.
