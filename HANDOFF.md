# Handoff — Current State

> Updated 2026-08-02 on the GPU machine (RTX 4070 Ti Super, 16 GB). Phase 0 and
> Phase 1 are done. Delete or update this file when it goes stale.

## Where things stand

| Done | What |
|---|---|
| ✅ | Phase 0: stack up on this machine (`docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`), health/docs/frontend verified, `.env` populated with real keys |
| ✅ | Phase 1.1–1.6: full data layer — `tools/db.py`, `price.py`, `financials.py`, `macro.py`, `breadth.py`, plus real `seed_watchlist.py` / `backfill_financials.py`. 46 tests green (`agent-runner\.venv\Scripts\python -m pytest agent-runner\tests`) |
| ✅ | Live-verified: watchlist seeded (AAPL/MSFT/NVDA), financials 7/7 endpoints cached, 12 FRED series, NYMO/NAMO computed (−12.3/−11.0 neutral) |
| ✅ | `qwen2.5:14b` pulled and inference-verified on the GPU; agent-runner image rebuilt with the Phase 1 code |
| ✅ | Phase 2: all five skills implemented + tested (accumulation, gap_analysis, the_strat, market_flow, position_management). Rule specs live at `specs/*_rules.md`, `specs/the-strat-spec.md`, `specs/position_management_agent_spec.md` |
| ✅ | Phase 3: Crew MVP working **live** — queue worker + 3 agents (Technical, Fundamental, PortfolioStrategist) + market_flow as the recommendation sub-report. **CrewAI was dropped**: agents call Ollama directly with structured output (`llm.py::generate_json`, `format=json_schema`); all fetching/skill math is deterministic Python. Live AAPL run: 29.8s wall, 3 LLM calls, valid JSON first try, coherent narratives. 137 tests green |
| ✅ | Phase 4: API + Feed UI live. Backend routers (analysis/queue/watchlist/stocks + tickers admin) with mongomock-backed tests; Feed page (infinite scroll, filters, Pull/Run All controls, live queue chip), Stock Detail (Overview + AI Summary tabs, Pull button with queued/analyzing state), Sidebar watchlist. Vertical slice verified end-to-end: POST /queue/GOOGL → container analyzed it → appeared in /analysis/feed |
| ✅ | Phase 5: full 8-agent roster live (Macro/Insider/Institutional/Sentiment/Recommender added; NVDA full run = 54.7s), chunker/summarizer, backend price endpoint (`GET /stocks/{t}/price`, yfinance + 1h cache), PriceChart w/ MAs + broadening formations + volume/ROC panes, TFC grid, and all 7 Stock Detail tabs |
| ⬜ | Phase 6: Earnings Scanner — calendar tools, scanner + conversation agents, streaming chat endpoint, EarningsScan page |
| ⬜ | Phase 7: Institutional Flow — daily worker, flow scanner agent, Dataroma Playwright pipeline (superinvestor tool is already scrape-ready), flow feed page |

## Phase 5 sourcing notes (probed 2026-08-02)

- FMP insider + ALL 13F/institutional endpoints: 402/403 paid-tier → insider data
  comes from **Finnhub** (transactions + MSPR, both free), institutional from
  **yfinance holder tables** (top-10 w/ QoQ pctChange + ownership summary).
- Finnhub transcripts: 403 premium → SentimentAnalyst reads **company news +
  EPS surprises** instead; transcript path dormant in tools/sentiment.py.
- Dataroma/superinvestor: implemented (Playwright + LLM extraction), degrades to
  available:False when Playwright missing (it is in Docker, not the local venv).

Workflow agreement: **feature by feature, commit after each working chunk**. Phases in project-proposal.md §6.

## Hard-won API facts (do not rediscover)

- **FMP legacy `/api/v3` endpoints 403 on this key** (post-2025 account). Use the
  stable API: `https://financialmodelingprep.com/stable/` with query-style paths
  (`income-statement?symbol=AAPL&period=annual&limit=4`).
- **Quarterly statements 402 beyond ~4 periods** on the free tier (`limit=8`
  rejected) — `income_quarterly` uses `limit=4`.
- **Constituent endpoints (`sp500-constituent`, `nasdaq-constituent`) are 402
  paid-tier** — breadth's Wikipedia (S&P 500) / slickcharts (NASDAQ-100) scrape
  fallback is the de facto source. Works; always send a browser User-Agent.
- **pandas-ta is gone from PyPI** (0.3.x pulled; 0.4.x is a py3.12-only rewrite).
  Indicators are computed directly with pandas in `tools/price.py::compute_indicators`.
- `$NYMO`/`$NAMO` remain un-fetchable anywhere — computed locally per
  `specs/component-specs/agent-runner/tools/breadth.md`. Zone thresholds (±60)
  still need calibration against StockCharts.

## Dev environment on this machine

- Local venv: `agent-runner\.venv` (py3.11) with the data-layer deps + pytest +
  mongomock; crewai/playwright/ollama-py are NOT installed locally (Docker-only)
  — install them when Phase 3 needs to run outside the container.
- Tests: `agent-runner\.venv\Scripts\python -m pytest agent-runner\tests -q`
- Scripts run from repo root against the live Mongo container (port 27017):
  `agent-runner\.venv\Scripts\python scripts\seed_watchlist.py TICKER ...`

## Gotchas already hit (carried over + new)

- vitest must be v3 with vite 6; `defineConfig` imports from `"vitest/config"`.
- Tailwind v4 is CSS-first — no tailwind.config.ts on purpose.
- `backend/db.py` and `agent-runner/tools/db.py` intentionally duplicate
  collection-name constants — keep in sync by hand. Analyses sort/index on
  `timestamp` (backend's scaffold `created_at` index was fixed in Phase 1.1).
- All tool functions take an optional `db=` kwarg for injection — tests use
  mongomock, never a live Mongo.
