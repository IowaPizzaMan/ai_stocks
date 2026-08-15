# Implementation Plan: FMP Paid-Tier Migration & Admin Data Operations

**Branch**: `017-fmp-migration-admin` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-fmp-migration-admin/spec.md`

## Summary

Retire yfinance entirely and serve all its current data (price history, intraday chart bars, breadth-universe closes, earnings dates, delisting checks) from FMP's stable API, now that the subscription is paid. Rework the FMP budget guard from a 250/day counter into a configurable per-minute throttle. Add non-ticker "admin jobs" as a new `job_type` on the existing `work_queue` (no new queue), a backend admin router, and a frontend Admin page to trigger/monitor them.

The entitlement question is settled — the user verified their subscription directly (2026-08-15). **In**: insider trading + market-wide insider feed, senate/house congressional trading, ETF & fund holdings (**replacing the retired Dataroma superinvestor scraper**), market + per-ticker news (per-ticker fetched during each retrieval; market news shown on the Feed page pending a later redesign), company info, and the economics route (treasury curve, non-FRED indicators, releases calendar, market risk premium — FRED stays canonical for its existing 12 series). **Out**: 13F and transcripts (not entitled; will be sourced outside FMP as a future feature), crypto and forex. Adopted market-wide datasets surface in a new Market Overview experience with freshness badges and admin-pointing empty states. The automated entitlement probe remains as a verification tool for the still-ambiguous families (batch quotes, intraday resolutions, analyst grades). See [research.md](research.md) D1, D11–D14 and [fmp-gap-review.md](fmp-gap-review.md).

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner); TypeScript / React 18 + Vite 5 (frontend)

**Primary Dependencies**: FastAPI + Uvicorn, Pydantic v2 + pydantic-settings, PyMongo (sync), pandas, `requests` (FMP HTTP — already used by `tools/financials.py`); frontend: TanStack Query v5, Recharts, Tailwind v4, React Router v6, Axios via `lib/api.ts`. **Removed**: `yfinance` (both services' requirements).

**Storage**: MongoDB 7.x — existing collections (`price_history`, `work_queue`, `ticker_index`, financials caches) plus new market-wide collections (see [data-model.md](data-model.md)); TTL/cache discipline per constitution Principle IV.

**Testing**: pytest (backend + agent-runner; FMP HTTP faked, never live in tests), Vitest + React Testing Library (Admin page, Market Overview, hooks), ruff (repo-root `pyproject.toml` config)

**Target Platform**: Self-hosted Docker Compose (five services), single user, no auth

**Project Type**: Web application (backend + agent-runner + frontend)

**Performance Goals**: Breadth-universe refresh (~600 tickers) completes in ≤5 min under a 300 calls/min throttle in steady state (cache-first: only the missing trading days are fetched); admin job trigger reflects accepted/running status on the next page load or manual refresh; migrated price charts load in the same perceived time as today (cache-served).

**Constraints**: FMP paid-tier rate limit (Starter: 300 calls/min, 20GB/30-day bandwidth — verify via probe); Starter history depth is ~5 years, so existing Mongo history deeper than FMP's window MUST be preserved, never re-fetched; budget guard must be config-only revertible to free-tier limits (250/day); frontend never polls — fetch on navigation and manual refresh only; no cron — all triggering via `work_queue` or the two existing timer loops.

**Scale/Scope**: Single user; ticker universe ~600–1100 symbols (S&P 500 + NASDAQ-100 + watchlist); 8 yfinance call sites across 2 services to migrate; 1 new backend router + extensions to 2 existing; 2 new frontend pages + 2 extended; 10 admin jobs, ~8 new Mongo collections; 1 collector retired (Dataroma/Playwright).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | How this plan complies |
|---|-----------|--------|------------------------|
| I | Test-First & Comprehensive Coverage | ✅ PASS | Every migrated tool keeps/extends its existing pytest suite with FMP responses faked (existing pattern: `test_financials.py`); rule-engine skills are untouched (they consume stored bars, not providers). New admin router, job dispatch, and market-wide collectors get contract tests; Admin/MarketOverview pages get Vitest coverage. Migration explicitly re-runs the full existing suites as its regression gate (SC-003). |
| II | Spec-Driven Development | ✅ PASS | This feature runs the full Spec Kit pipeline; `specs/DATA_SOURCES.md` coverage map is updated as part of FR-007, and component specs are added/updated for changed tools/routers. |
| III | Deterministic Core, LLM at the Edges | ✅ PASS | No LLM in any new collector or the migration — and retiring the Dataroma scraper *removes* an LLM-dependent extraction path. Skills remain pure; they read the same stored bar shape post-migration. |
| IV | Cache-Aware, Budget-Conscious Data Access | ✅ PASS | All FMP calls stay behind the cache-first layer; the budget guard is *upgraded*, not removed — per-minute throttle + configurable soft daily cap, fail-soft (stale cache + log). Free-tier downgrade is an env change (FR-005/edge case). |
| V | Simplicity & Local-First Scope | ✅ PASS | Admin jobs reuse `work_queue` via a `job_type` discriminator — no second queue, no scheduler additions, no WebSockets; admin status is fetch-on-load + manual refresh. Admin is a nav area, not an auth boundary. Recurring/scheduled collection stays out of scope. |
| VI | Consistency Across Layers | ⚠️ PASS (watch) | `job_type` values, admin job names, and new collection/field names are shared vocabulary between `backend/` and `agent-runner/` — duplicated as small constants in both services per the no-shared-package rule. The contract files in [contracts/](contracts/) are the single written source of truth both must match. |

**Post-Phase-1 re-check**: ✅ PASS — the design artifacts introduce no new queue, no scheduler, no new datastore, no auth, and no shared package. The only cross-layer surface added is the `job_type` field and admin job names, pinned in [contracts/admin-jobs-api.md](contracts/admin-jobs-api.md).

## Project Structure

### Documentation (this feature)

```text
specs/017-fmp-migration-admin/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions D1–D10
├── data-model.md        # Phase 1 output — collections & entities
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   ├── admin-jobs-api.md      # Backend admin/job REST contract + work_queue job shape
│   ├── market-data-api.md     # Market-wide read endpoints for the frontend
│   └── fmp-migration-map.md   # Per-call-site yfinance → FMP endpoint mapping & fallbacks
├── fmp-gap-review.md    # Gap-review deliverable (FR-013) — seeded in Phase 1, finalized against probe output during implementation
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
agent-runner/
├── settings.py                  # + fmp rate-limit/budget settings (per-min, soft daily cap)
├── data_fetcher.py              # price/earnings/institutional/breadth sections → FMP
├── crew.py                      # yfinance existence check → FMP quote/profile check
├── queue_worker.py              # job_type dispatch: ticker_analysis (default) | admin job handlers
├── tools/
│   ├── fmp_client.py            # NEW — shared FMP HTTP client: throttle, budget guard, entitlement probe
│   ├── price.py                 # yfinance bars → FMP EOD + intraday chart endpoints
│   ├── breadth.py               # batched yf.download → FMP batch/looped EOD closes
│   ├── financials.py            # earnings block off yfinance → FMP; fmp_get moves to fmp_client
│   ├── earnings_calendar.py     # yfinance dates/prices → FMP earnings + EOD
│   ├── institutional.py         # holder-table live refresh dropped (13F not entitled); stored data read-only
│   ├── superinvestor.py         # RETIRED — no admin job, no new writes; stored data stays readable
│   ├── news.py                  # NEW — per-ticker stock news (retrieval flow) + market news collector
│   ├── company_info.py          # NEW — company-info route, per-ticker, 90-day refresh
│   └── market_wide.py           # NEW — market-wide collectors: sector perf, movers, economics, congress, insider feed, fund holdings
└── tests/                       # updated fakes (FMP shapes), + test_fmp_client.py, test_market_wide.py, test_news.py, queue dispatch tests

backend/
├── routers/
│   ├── admin.py                 # NEW — GET /admin/jobs, POST /admin/jobs/{name}/run, run history
│   ├── market.py                # + read endpoints: sector perf, movers, economics, congress, insider feed, fund holdings, market news
│   ├── stocks.py                # + GET /stocks/{ticker}/news
│   └── price.py                 # yfinance chart bars → FMP intraday/EOD (via cache layer)
├── db.py                        # + new collection name constants (mirrored in agent-runner/tools/db.py)
└── tests/                       # test_admin_router.py, updated test_price.py fakes

frontend/src/
├── pages/
│   ├── Admin.tsx                # NEW — job list, trigger buttons, run status/history
│   ├── MarketOverview.tsx       # NEW — sector perf, movers, economics, congress, insider feed, fund holdings visuals
│   ├── Feed.tsx                 # + market-news section (full redesign deferred — future feature)
│   └── StockDetail.tsx          # + per-ticker news list; company-info fields in header
├── hooks/
│   ├── useAdminJobs.ts          # NEW — list/trigger/status (no polling)
│   └── useMarketOverview.ts     # NEW
├── components/market/           # NEW — visual treatments per dataset (freshness badge, empty state)
└── App/router + nav             # Admin + Market Overview routes and nav entries

specs/
├── DATA_SOURCES.md              # coverage map rewritten post-migration (FR-007)
└── component-specs/             # new/updated specs for changed components
```

**Structure Decision**: Existing three-service web-app layout is kept exactly; no new services, packages, or top-level directories. New code lands in the established per-service homes (`tools/` for agent-runner collectors, `routers/` for backend endpoints, `pages/`+`hooks/` for frontend). The only new shared *vocabulary* (job types, collection names) is duplicated constants per Principle V/VI, pinned by the contracts.

## Complexity Tracking

No constitution violations to justify. The closest call — whether admin jobs justify a separate queue or scheduler — was resolved by extending `work_queue` with a `job_type` field and keeping all triggering manual, which stays inside existing infrastructure.
