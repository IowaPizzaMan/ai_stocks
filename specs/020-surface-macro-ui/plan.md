# Implementation Plan: Decouple Macro Analysis From Ticker Research and Surface It in the UI

**Branch**: `020-surface-macro-ui` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-surface-macro-ui/spec.md`

## Summary

Macro analysis (economy-wide: inflation, rates, yield curve, sector rotation) currently runs inside every per-ticker crew run, feeds the portfolio strategist's verdict, and is stored in each analysis's `sub_reports.macro` — yet no UI surface ever displays it. This feature (1) removes the macro analyst from the per-ticker pipeline entirely (prefetch, agent call, sub-report, and strategist input), (2) stands up an independent macro worker in the agent-runner's existing poll loop that refreshes one macro read per active sector at most weekly (reusing the existing `macro_analysis_cache` per-sector collection), (3) adds a `GET /market/macro` backend endpoint serving those reads, and (4) reworks the frontend navigation: "Feed" becomes "Stocks" (URL unchanged, breadth cards removed), and a new top-level "Macro" page hosts the market-breadth (NYMO/NAMO) divergence cards plus every sector's macro read.

## Technical Context

**Language/Version**: Python 3.12 (backend + agent-runner), TypeScript / React 18 + Vite 5 (frontend)

**Primary Dependencies**: FastAPI + PyMongo (backend), direct-Ollama structured output via `agent-runner/llm.py` (macro analyst LLM calls), TanStack Query v5 + React Router v6 + Tailwind v4 (frontend)

**Storage**: MongoDB 7.x — existing collections only: `macro_analysis_cache` (per-sector reads, unique index on `sector`), `macro_cache` (FRED series, 24h TTL), `breadth_cache` / `breadth_divergences` / `market_flow_events` (unchanged), `ticker_index` (sector universe source)

**Testing**: pytest + mongomock (agent-runner, backend), Vitest + React Testing Library (frontend); `ruff check` on both Python services

**Target Platform**: Self-hosted Docker Compose stack (single user, local-first)

**Project Type**: Web application — three services touched: `agent-runner/` (pipeline + worker), `backend/` (one new endpoint), `frontend/` (nav rename, page removal/addition)

**Performance Goals**: Per-ticker analysis drops one LLM call (~7 structured-output calls instead of 8) and two prefetch fetches; macro worker adds at most ~11 LLM calls per week total (one per active sector), amortized across the week

**Constraints**: No new external data fetches (FRED data already cached 24h in `macro_cache`); no polling in the frontend (`refetchInterval: false`); no new infrastructure beyond the existing agent-runner poll loop; FMP/Finnhub budgets untouched (macro uses FRED only)

**Scale/Scope**: ~11 GICS sectors max in `ticker_index`; single user; 3 user stories, ~10 functional requirements

## Constitution Check

*GATE: evaluated against Constitution v1.0.1 before Phase 0; re-checked after Phase 1 design.*

| Principle | Verdict | Notes |
|---|---|---|
| I. Test-First & Comprehensive Coverage | PASS | Plan includes: agent-runner tests for the sector-based macro analyst and the new worker's due/refresh logic (mongomock, fake LLM); backend tests for `GET /market/macro`; frontend Vitest for the renamed Stocks page (breadth cards gone, filtering intact) and the new Macro page (sector cards, breadth cards, empty state). Existing `test_crew.py` assertions updated, not deleted — they now pin the *absence* of macro. |
| II. Spec-Driven Development | PASS | This plan traces to `specs/020-surface-macro-ui/spec.md` (clarified twice). Affected component specs (`crew.md`, `macro_analyst.md`, `main.md`, `Feed.md`, `Navbar.md`, `market.py` router spec) get updated as part of implementation so specs don't drift (recorded as tasks). |
| III. Deterministic Core, LLM at the Edges | PASS | No skill logic changes. The macro analyst remains an LLM interpretation layer over cached FRED data; breadth/divergence math untouched. Removing macro from the strategist's inputs is a prompt/input change, not LLM override of computed results. |
| IV. Cache-Aware, Budget-Conscious Data Access | PASS | Macro worker reads FRED via the existing `get_macro_data`/`get_yield_curve_status` cached tools (24h TTL respected) and writes the existing 7-day per-sector `macro_analysis_cache`. Zero new external API surface; FMP/Finnhub budgets unaffected. |
| V. Simplicity & Local-First Scope | PASS | The worker joins the existing single-process poll loop in `main.py` exactly like `breadth_worker` — no cron, no scheduler, no queue. Frontend gains one route + one page; no new state management. No shared-package extraction. |
| VI. Consistency Across Layers | PASS (action required) | `MACRO_ANALYSIS_CACHE = "macro_analysis_cache"` exists only in `agent-runner/tools/db.py` today; the backend must add the same constant with the same collection name and document shape to `backend/db.py`. Recorded as an explicit task. |

**Post-Phase-1 re-check**: PASS — design artifacts introduce no new collections, no new infrastructure, no deviation from the stack constraints.

## Project Structure

### Documentation (this feature)

```text
specs/020-surface-macro-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── macro-api.md     # GET /market/macro contract
│   └── macro-worker.md  # Worker scheduling/refresh contract + crew removal contract
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
agent-runner/
├── agents/
│   ├── macro_analyst.py         # MODIFIED: sector-based run() (no ticker param); cache logic stays
│   └── portfolio_strategist.py  # MODIFIED: drop macro weighting language from SYSTEM/prompt
├── crew.py                      # MODIFIED: remove macro prefetch jobs, macro_analyst call, sub_reports["macro"]
├── macro_worker.py              # NEW: run_macro_refresh_if_due() — per-sector weekly refresh in the poll loop
├── main.py                      # MODIFIED: call macro_worker each tick (alongside breadth worker)
└── tests/
    ├── test_crew.py                 # MODIFIED: 7 sub-reports, 7 LLM calls, no macro key
    ├── test_macro_analyst_cache.py  # MODIFIED: sector-based signature
    ├── test_phase5_agents.py        # MODIFIED: macro test drops ticker arg
    └── test_macro_worker.py         # NEW: due-scheduling + stale-sector refresh (mongomock, fake LLM)

backend/
├── db.py                        # MODIFIED: add MACRO_ANALYSIS_CACHE constant (Principle VI)
├── routers/market.py            # MODIFIED: add GET /market/macro
└── tests/test_market.py         # MODIFIED: /market/macro coverage

frontend/src/
├── App.tsx                      # MODIFIED: /macro route; Feed import → Stocks
├── components/layout/Navbar.tsx # MODIFIED: "Feed"→"Stocks", add "Macro" link
├── pages/
│   ├── Stocks.tsx               # RENAMED from Feed.tsx: breadth/flow cards removed, title "Stocks"
│   ├── Stocks.test.tsx          # RENAMED from Feed.test.tsx: updated assertions
│   ├── Macro.tsx                # NEW: breadth cards + per-sector macro read cards + empty state
│   └── Macro.test.tsx           # NEW
├── hooks/useMacro.ts            # NEW: useMacroReads() → GET /market/macro
└── api/types.ts                 # MODIFIED: SectorMacroRead type; MacroReport reused
```

**Structure Decision**: Web-app layout (existing `backend/` + `frontend/` + `agent-runner/` trio). No new top-level directories; the macro worker follows the established `breadth_worker.py` sibling-module pattern, and the Macro page follows the existing `pages/` + `hooks/` + `api/types.ts` pattern.

## Complexity Tracking

No constitution violations — table not required.
