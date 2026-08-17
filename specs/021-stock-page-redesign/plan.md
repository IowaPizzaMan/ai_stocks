# Implementation Plan: Stock Page Redesign

**Branch**: `021-stock-page-redesign` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-stock-page-redesign/spec.md`

## Summary

Reorganize the stock detail page around a default **Charts** tab (candlestick D/W/M/Y charts with corrected monthly/yearly aggregation, ROC panels, and per-timeframe MACD / z-score / stochastic / ATR% indicators), add a **News** tab fed by FMP stock news with deterministic bullish/bearish keyword timelines and LLM article summaries generated at pull time, upgrade the Insider and Institutional tabs with FMP-backed flow visuals, reformat long-form prose, and refresh the AI Summary tab (drop the breadth chart, add a news stance and a "what changed" note).

Technical approach: backend gains a `yearly` price resolution (pandas resample of full EOD history); the frontend computes display indicators in a Vitest-tested `lib/indicators` module (same pattern as existing MAs/ROC); candlesticks render via a Recharts custom `Bar` shape; all new external data (news, insider statistics, beneficial ownership) flows through `agent-runner/tools/fmp_client.fmp_get` into new cache collections during a pull, landing as new/extended sub-reports on the analysis document — no new services, no polling, no page-load LLM calls.

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner), TypeScript / React 18 + Vite 5 (frontend)

**Primary Dependencies**: FastAPI, PyMongo (sync), pandas, Recharts, TanStack Query v5, Ollama via `llm.generate_json` (agent-runner)

**Storage**: MongoDB 7.x — existing `analyses`, `price_cache`, `fmp_call_log`; new `stock_news_cache`, `beneficial_ownership_cache`; extended insider data rides the analysis document

**Testing**: pytest (backend routers + agent-runner tools/agents), Vitest + React Testing Library (frontend)

**Target Platform**: Self-hosted Docker Compose (single user, local-first)

**Project Type**: Web application (backend + frontend + agent-runner workers)

**Performance Goals**: Charts tab interactive < 2s on cached data (SC-001); pull-time news processing bounded (≤ 50 articles fetched, ≤ 15 LLM-summarized)

**Constraints**: FMP daily soft cap honored via `fmp_client` (fail-soft to stale cache, FR-026); `institutional-ownership/latest` NOT entitled (402, verified 2026-08-16) — institutional visuals derive from `acquisition-of-beneficial-ownership` (entitled) + cached 13F snapshot; no frontend polling (`refetchInterval: false`); no new npm chart library (Recharts only)

**Scale/Scope**: 1 user; ~8 tabs on one page; 4 timeframes × 4 indicators; ≤ 50 news articles per ticker per pull

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First & Comprehensive Coverage | PASS | New deterministic surfaces (yearly resample, keyword tally, insider stats shaping, indicator math, prose formatter, tab default) each get pytest/Vitest suites; contracts below define the assertable shapes. |
| II. Spec-Driven Development | PASS | Spec 021 clarified (4 Qs) before planning; entitlement discovery written back into spec Data Sources / FR-013. |
| III. Deterministic Core, LLM at the Edges | PASS | Keyword counts, timeline aggregation, net-direction verdicts, and "what changed" diffs are pure Python functions; the LLM only writes article summaries and the news stance. No skill outputs are overridden. |
| IV. Cache-Aware, Budget-Conscious Data Access | PASS | All new FMP calls go through `fmp_client.fmp_get` (throttle + soft cap + `FmpBudgetExceededError` → stale cache). New caches carry `fetched_at`; UI shows as-of dates. The un-entitled endpoint is never called. |
| V. Simplicity & Local-First Scope | PASS | No new services, queues, or packages. News data rides the analysis document (no new frontend fetch path beyond what exists). Indicators computed client-side like existing MAs/ROC — no new backend indicator endpoints. |
| VI. Consistency Across Layers | PASS | New sub-report field names defined once in contracts/analysis-subreports.md; backend serves the analysis document unchanged; frontend types.ts mirrors the contract. |

**Post-Phase-1 re-check (2026-08-16)**: All six principles still PASS — design added no new infrastructure, kept LLM usage at the summary/stance edge, and every new external call routes through the budget-guarded client. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/021-stock-page-redesign/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── price-endpoint.md        # yearly resolution + bar shape
│   └── analysis-subreports.md   # news / insider / institutional / changes_since_last
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/
├── routers/price.py                 # + "yearly" resolution (resample YE, 15y slice)
└── tests/test_price.py              # + yearly resample/window tests

agent-runner/
├── tools/
│   ├── news.py                      # NEW: FMP stock news fetch + per-article keyword tally + timeline
│   ├── insider.py                   # + FMP insider-trading/statistics quarterly stats
│   ├── institutional.py             # + beneficial-ownership fetch; net-direction from entitled sources
│   └── db.py                        # + STOCK_NEWS_CACHE, BENEFICIAL_OWNERSHIP_CACHE names/TTL
├── agents/
│   ├── news_analyst.py              # NEW: article summaries + news stance (LLM, structured output)
│   └── sentiment_analyst.py         # receives news keyword timeline context (shared tally source)
├── crew.py                          # prefetch news/beneficial-ownership; news sub-report; changes_since_last diff
└── tests/                           # pytest for all of the above

frontend/
├── src/
│   ├── lib/
│   │   ├── indicators/              # NEW: macd.ts, stochastic.ts, atrPercent.ts, zscore.ts (+ tests)
│   │   └── prose.ts                 # NEW: sentence-split + key-term emphasis helper (+ tests)
│   ├── components/stock/
│   │   ├── CandlestickChart.tsx     # NEW: Recharts custom-shape candles
│   │   ├── ChartsTab.tsx            # NEW: 4 candle charts + ROC + indicator grid
│   │   ├── IndicatorPanel.tsx       # NEW: one indicator × 4 timeframes row
│   │   ├── NewsTab.tsx              # NEW: timeline chart + article summary list
│   │   ├── SentimentTimeline.tsx    # NEW: shared bullish/bearish timeline chart
│   │   ├── InsiderFlowCharts.tsx    # NEW: quarterly acquired/disposed + ratio trend
│   │   ├── InstitutionalFlowVisuals.tsx  # NEW: beneficial-ownership stakes + net verdict
│   │   ├── FormattedProse.tsx       # NEW: readable long-form text renderer
│   │   ├── tabs.tsx                 # Insider/Institutional/Sentiment tab upgrades
│   │   └── PriceChart.tsx           # candle mode wiring (or superseded inside ChartsTab)
│   ├── pages/StockDetail.tsx        # tab list/order/default, Deep Dive & PM removal, AISummary refresh
│   ├── lib/strat/displayWindow.ts   # D/W/M/Y resolution + window mapping (M→monthly, Y→yearly)
│   └── api/types.ts                 # NewsReport, insider/institutional extensions, changes_since_last
└── src/**/*.test.{ts,tsx}           # Vitest coverage per Principle I
```

**Structure Decision**: Existing three-service web layout (`backend/`, `frontend/`, `agent-runner/`) is kept; the feature only adds modules inside each service. No shared packages (Principle V) — the sub-report contract doc keeps the two Python services and the frontend types aligned (Principle VI).

## Complexity Tracking

No constitution violations — table intentionally empty.
