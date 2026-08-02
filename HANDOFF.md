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
| ✅ | Phase 2: all five skills implemented + tested (accumulation, gap_analysis, the_strat, market_flow, position_management) — 113 tests green. Rule specs live at `specs/*_rules.md`, `specs/the-strat-spec.md`, `specs/position_management_agent_spec.md` |
| ⬜ | Phase 3: Crew MVP — `work_queue` + `queue_worker` + 3-agent crew (Technical, Fundamental, PortfolioStrategist) writing to `analyses`. The riskiest bet: CrewAI ↔ Ollama tool-calling on a 14B model. Local venv does NOT have crewai/ollama-py — test inside the container or install them locally |

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
