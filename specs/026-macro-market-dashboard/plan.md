# Implementation Plan: Macro Market Dashboard

**Branch**: `026-macro-market-dashboard` | **Date**: 2026-08-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/026-macro-market-dashboard/spec.md`

## Summary

Rebuild `/macro` as a market-wide dashboard: de-duplicate the breadth chart, drop the sector cards, and add three new sections (yield curve + spreads, economic calendar, indicator backdrop).

The data half of this feature is largely **already designed but never built**. Spec `017-fmp-migration-admin` reserved an `economics_pull` admin job — `job_type`, `dataset_meta` name, `stale_minutes`, and all four target collections (`treasury_rates`, `economic_calendar_events`, `economic_indicators`, `market_risk_premium`) exist as constants in both services' `db.py`, with document shapes pinned in that feature's data-model. No writer was ever implemented. This plan implements that handler rather than inventing a parallel path.

Approach in one line: an agent-runner daily worker fills the four collections (one-time 2-year Treasury backfill, then incremental), `backend/routers/market.py` gains read-only endpoints that shape and compute over what was cached, and the Macro page consumes them alongside a reworked breadth chart.

## Technical Context

**Language/Version**: Python 3.12 (backend + agent-runner), TypeScript 5.x / React 18 (frontend)

**Primary Dependencies**: FastAPI, PyMongo (sync), pydantic-settings, requests, pytest, mongomock · React 18 + Vite 5, TanStack Query v5, Recharts, Tailwind v4, Vitest + React Testing Library

**Storage**: MongoDB 7.x — four collections already named in `backend/db.py` and `agent-runner/tools/db.py`; `treasury_rates` is a **maintained store** (no TTL, like `price_history` from 024), the rest are refreshed-in-place caches

**Testing**: pytest with `mongomock` (backend router contracts, agent-runner tool behavior); Vitest + RTL (page, components, hooks)

**Target Platform**: Self-hosted Docker Compose stack, single user, no auth

**Project Type**: Web application — `backend/` (FastAPI read layer) + `agent-runner/` (data pulls) + `frontend/` (React SPA)

**Performance Goals**: First meaningful content < 2s on warm cache (SC-007); all four sections served from Mongo with no provider call on the request path

**Constraints**: Zero external calls on page load (FR-030); FMP daily soft cap shared with every other consumer (constitution IV); no polling anywhere in the frontend (constitution V); page usable at 1280px without horizontal scroll (SC-008)

**Scale/Scope**: ~500 Treasury snapshots (2y daily), ~150 calendar events per refresh window, ~6 indicator series, 1 risk-premium row. One page, 4 new endpoints, 1 new worker, ~6 new frontend components.

## Constitution Check

*GATE: evaluated before Phase 0, re-evaluated after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| **I. Test-First & Comprehensive Coverage** | Every new router endpoint gets a contract test; every pure function (spread math, curve alignment, event classification, backfill windowing) gets a unit test; page and chart get Vitest coverage | **PASS** — pure-function surface is deliberately wide (see data-model §6) so the deterministic parts are fully testable |
| **II. Spec-Driven Development** | Feature originates from `spec.md`, clarified in 5 questions. Conflicts with an earlier spec are amended, not bypassed | **PASS with recorded amendment** — see Complexity Tracking; `017` data-model note requires an edit |
| **III. Deterministic Core, LLM at the Edges** | No LLM call anywhere in this feature. Spread/inversion/surprise classification are pure functions over stored numbers | **PASS** |
| **IV. Cache-Aware, Budget-Conscious Data Access** | All FMP access via `agent-runner/tools/fmp_client.fmp_get` (throttle + soft cap + fail-soft). Backfill is one-time and guarded. Daily incremental is 1 call. Read path never calls a provider | **PASS** — steady-state ~7–9 calls/day (indicators are one call per series, not batchable); one-time backfill ~8 calls |
| **V. Simplicity & Local-First Scope** | No new service, no scheduler, no queue. Reuses the existing `work_queue` admin-job registry and `main.py`'s daily-timer loop | **PASS** |
| **VI. Consistency Across Layers** | Collection-name constants already exist in both `db.py` files. Job vocabulary reused verbatim from `017/contracts/admin-jobs-api.md` | **PASS** — no new duplicated constants introduced beyond what 017 already pinned |
| **Technology Stack Constraints** | Nothing added outside the pinned stack | **PASS** — Recharts for the curve, no new charting or date library |

**Post-Phase-1 re-evaluation**: unchanged. The design added no new infrastructure, no new dependency, and no LLM surface. The single recorded deviation is the `017` FR-016 amendment below.

## Project Structure

### Documentation (this feature)

```text
specs/026-macro-market-dashboard/
├── plan.md              # This file
├── research.md          # Phase 0 — 9 decisions, incl. 3 provider limits verified live
├── data-model.md        # Phase 1 — 4 collections + derived read shapes + pure-function surface
├── quickstart.md        # Phase 1 — validation guide
├── contracts/
│   └── macro-api.md     # Phase 1 — 4 endpoint contracts + frontend consumption rules
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # Phase 2 — NOT created by /speckit-plan
```

### Source Code (repository root)

```text
agent-runner/
├── economics_worker.py                 # NEW — daily timer, mirrors breadth_worker.py
├── main.py                             # EDIT — add run_daily_economics_if_due to the loop
├── settings.py                         # EDIT — economics_refresh_hour_utc
├── tools/
│   ├── economics.py                    # NEW — the four pulls + backfill windowing
│   ├── admin_jobs.py                   # EDIT — register economics_pull handler/dataset/stale
│   └── db.py                           # EDIT — indexes for the four collections
└── tests/
    └── test_economics.py               # NEW — pull, backfill, gap-healing, fail-soft

backend/
├── db.py                               # EDIT — indexes only (names already present)
├── routers/
│   └── market.py                       # EDIT — 4 new read-only endpoints
└── tests/
    └── test_market_economics.py        # NEW — contract tests for the 4 endpoints

frontend/src/
├── pages/
│   ├── Macro.tsx                       # REWRITE — 4 sections, sector grid removed
│   └── Macro.test.tsx                  # REWRITE — sector assertions replaced
├── hooks/
│   └── useEconomics.ts                 # NEW — 4 queries, staleTime 1 day, no polling
├── components/macro/                   # NEW directory
│   ├── YieldCurveChart.tsx             # curve + prior-period overlays
│   ├── SpreadTiles.tsx                 # 3 spreads: value, change, inverted, sparkline
│   ├── EconomicCalendarPanel.tsx       # upcoming + recently reported
│   ├── IndicatorTiles.tsx              # 4 tiles + risk premium, lagging marker
│   └── *.test.tsx                      # one per component
├── components/feed/
│   └── MarketFlowCard.tsx              # EDIT — event becomes optional (FR-002a)
├── components/stock/
│   └── BreadthDivergenceChart.tsx      # EDIT — NAMO as 2nd line, toggle removed
└── lib/
    ├── yieldCurve.ts                   # NEW — pure: spread math, curve alignment
    └── yieldCurve.test.ts              # NEW
```

**Structure Decision**: Existing three-service web-application layout, unchanged. The only new directory is `frontend/src/components/macro/`, which follows the established per-page component-folder convention (`components/earnings/`, `components/feed/`, `components/stock/`). The agent-runner writes, the backend reads and shapes, the frontend renders — the same seam `routers/market.py` already documents for breadth.

## Complexity Tracking

> One recorded deviation. Everything else fits existing patterns.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Amending `specs/017-fmp-migration-admin/data-model.md`'s `economic_indicators` constraint ("only series NOT in `tools/macro.py` DEFAULT_INDICATORS") | Spec 026 Q4 selected FMP `economic-indicators` as the **single** source for the growth / inflation / employment / policy-rate tiles. Those four overlap FRED series that 017 deliberately excluded from this collection to avoid duplication. Storing them is required for FR-024 | Leaving 017's restriction intact would mean either (a) silently violating it, which constitution II forbids, or (b) sourcing the tiles from FRED, which contradicts the user's explicit and reaffirmed Q4 decision. The amendment is a one-line scope widening of an unimplemented collection — no data migration, no consumer affected, since nothing writes or reads it today. FRED's `tools/macro.py` path is left completely untouched and continues to serve the sector macro worker |

**Note on divergence**: after this change, GDP/CPI/unemployment/fed-funds exist in *two* places — FRED via `macro_cache` (consumed by the sector macro worker) and FMP via `economic_indicators` (consumed by this page). This is a real, accepted cost of the Q4 decision. It is bounded by keeping the two consumers strictly separate — no code blends them, and the Macro page reads only `economic_indicators` (spec Assumptions, "The indicator tiles use one source, not two"). Recorded here so it is a known seam rather than a latent inconsistency under constitution VI.
