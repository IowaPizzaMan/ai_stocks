# Implementation Plan: Company Profile, Peers & Navigation Tweaks

**Branch**: `029-company-profile-tweaks` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/029-company-profile-tweaks/spec.md`

## Summary

Seven tweaks, six of which hang off one new piece of data: a per-ticker company profile fetched from FMP's `profile`, `stock-peers`, and `historical-employee-count` endpoints and stored in the **already-reserved-but-unused** `company_info` collection. The profile's `sector` and `industry` are denormalized onto `ticker_index` (which already carries a `sector` field and is already the shared ticker contract between both services), which lets the Sectors rollup and the feed's sector/industry filters read them through the exact two-step pattern spec 028 established for the `sentiment` filter — no `$lookup`, no new join layer.

That single change also closes the **top open bug in [KNOWN_ISSUES.md](../../KNOWN_ISSUES.md)**: `Crew.run()` never sets `sector` on the analyses document, so `GET /sectors` rolls up nothing and the Sectors page's empty state is permanent. The known-issue entry proposes exactly this fix ("fetch/attach the ticker's sector … from an FMP profile call"). This plan implements it, and the implement phase moves that entry to the Fixed section.

The remaining work is subtractive or cosmetic: retire the portfolio-digest subsystem outright (9 source files + 5 test files + a collection), promote market news from a Stocks-page tab to its own route, and give the sector chart height plus legend toggling.

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner); TypeScript 5 / React 18 (frontend)

**Primary Dependencies**: FastAPI + Pydantic v2 + PyMongo (sync); React 18 + Vite 5 + TanStack Query v5 + Recharts + Tailwind v4; `requests` via the shared `tools/fmp_client.py`

**Storage**: MongoDB 7.x — reuses `company_info` (declared in both `db.py` files since spec 017, never written to) and `ticker_index`; drops `portfolio_digest_cache`

**Testing**: pytest (backend, agent-runner); Vitest + React Testing Library (frontend); `ruff` on both Python services

**Target Platform**: Local-first Docker Compose stack, single user, no auth

**Project Type**: Web application — three deployable services (`backend/`, `frontend/`, `agent-runner/`) plus MongoDB and Ollama

**Performance Goals**: Cold profile fetch adds 3 FMP calls per ticker; warm (within the 90-day window) adds 1. Page views add zero provider calls. No new polling anywhere.

**Constraints**: FMP paid Starter tier — 250 calls/**minute** (in-process token bucket in `fmp_client._throttle`), `fmp_daily_soft_cap` disabled by default. Every new call fail-softs to cache on 402/403/budget per Principle IV. Frontend never polls (`refetchInterval: false`).

**Scale/Scope**: One user, tens-to-low-hundreds of tracked tickers. ~14 files added, ~20 modified, ~14 deleted.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — still passing, see bottom of this section.*

| Principle | Assessment |
|---|---|
| **I. Test-First & Comprehensive Coverage** | PASS. New agent-runner tool (`company_profile.py`) gets a pytest suite with mocked `fmp_get`, covering cache-window hit/miss, 402/403 degradation, and budget-exceeded. New/changed backend endpoints get router tests. New/changed frontend components (tiles, hover card, profile section, peers, employee chart, legend toggle, industry filter) get Vitest coverage. Deleted surfaces get their tests deleted with them. No rule-engine skills are touched. |
| **II. Spec-Driven Development** | PASS. Spec + 5 clarifications precede this plan; contracts below are the traceable artifacts. Closes a documented KNOWN_ISSUES entry rather than silently patching around it. |
| **III. Deterministic Core, LLM at the Edges** | PASS, and net-positive. All three new datasets are pure provider reads with zero LLM involvement, and this feature *removes* an LLM job (`portfolio_digest`). No skill is modified. |
| **IV. Cache-Aware, Budget-Conscious Data Access** | PASS. Every call routes through `tools/fmp_client.fmp_get` (throttle + budget guard + metrics attribution). Peers/employees sit behind a 90-day window mirroring `financials.CACHE_DAYS`; profile refreshes per pull. All three degrade to stored data on `FmpBudgetExceededError` / 402 / 403 rather than failing the run. Read endpoints are cache-only — no provider call is ever issued from a page view. |
| **V. Simplicity & Local-First Scope** | PASS. Reuses an existing reserved collection instead of adding one; denormalizes two scalars onto `ticker_index` instead of introducing a join layer; adds no new job type, worker, scheduler, or polling. Net removes a subsystem. |
| **VI. Consistency Across Layers** | PASS. `COMPANY_INFO` is already declared identically in `backend/db.py:46` and `agent-runner/tools/db.py:51`. `ticker_index` gains `industry` alongside its existing `sector`, written by agent-runner and read by backend through the same contract. `PORTFOLIO_DIGEST_CACHE` is removed from both files in the same change. |

**Post-Phase-1 re-check**: No new violations. The Complexity Tracking table below is intentionally empty — no principle required a justified deviation.

## Project Structure

### Documentation (this feature)

```text
specs/029-company-profile-tweaks/
├── plan.md              # This file
├── spec.md              # Feature spec (5 clarifications resolved)
├── research.md          # Phase 0 — 14 decisions
├── data-model.md        # Phase 1 — company_info, ticker_index deltas, removals
├── quickstart.md        # Phase 1 — validation walkthrough + one-time mongosh step
├── checklists/
│   └── requirements.md  # Spec quality checklist (16/16)
├── contracts/
│   ├── company-profile-api.md      # profile/peers/employees: fetch, cache, endpoints
│   ├── sector-and-industry.md      # sector source switch + industry filter
│   └── portfolio-digest-removal.md # exact teardown inventory
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
agent-runner/
├── tools/
│   ├── company_profile.py          # NEW — profile/peers/employees fetch + cache
│   ├── db.py                       # MOD — index company_info; drop PORTFOLIO_DIGEST_CACHE
│   ├── fmp_client.py               # MOD — 2 new PROBE_ENDPOINTS families
│   ├── admin_jobs.py               # MOD — deregister portfolio_digest
│   └── portfolio.py                # DELETE
├── agents/portfolio_digest.py      # DELETE
├── crew.py                         # MOD — profile in _prefetch; sector/industry to ticker_index
└── tests/
    ├── test_company_profile.py     # NEW
    ├── test_portfolio_digest.py    # DELETE
    └── test_admin_jobs.py, test_queue_worker.py  # MOD

backend/
├── routers/
│   ├── stocks.py                   # MOD — /profile, /peers, /employee-count, /industries
│   ├── analysis.py                 # MOD — feed sector filter re-sourced; industry param
│   ├── sectors.py                  # MOD — rollup joins ticker_index
│   ├── portfolio.py                # DELETE
│   └── main.py                     # MOD — drop portfolio router
├── db.py                           # MOD — drop PORTFOLIO_DIGEST_CACHE
└── tests/
    ├── test_company_profile.py     # NEW
    ├── test_portfolio.py           # DELETE
    └── test_sectors.py, test_routers.py  # MOD

frontend/src/
├── pages/
│   ├── News.tsx                    # NEW — market news as its own route
│   ├── Stocks.tsx                  # MOD — tabs + digest panel removed, grid full width
│   ├── Sectors.tsx                 # MOD (chart height lives in SectorEtfChart)
│   └── StockDetail.tsx             # MOD — logo by ticker; Overview gains 3 sections
├── components/
│   ├── stock/CompanyProfileSection.tsx   # NEW
│   ├── stock/PeersSection.tsx            # NEW
│   ├── stock/EmployeeCountChart.tsx      # NEW
│   ├── shared/CompanyLogo.tsx            # NEW — img + onError fallback, one place
│   ├── feed/AnalysisTile.tsx             # MOD — logo chip beside ticker
│   ├── feed/TilePreview.tsx              # MOD — full summary + logo + name
│   ├── feed/FilterBar.tsx                # MOD — industry <select>
│   ├── feed/PortfolioDigestPanel.tsx     # DELETE
│   ├── layout/Navbar.tsx                 # MOD — News link
│   └── sectors/SectorEtfChart.tsx        # MOD — height + legend toggle
├── hooks/
│   ├── useCompanyProfile.ts        # NEW — profile, peers, employees
│   ├── useIndustries.ts            # NEW
│   ├── usePortfolioDigest.ts       # DELETE
│   └── usePortfolioDigestRegenerate.ts   # DELETE
├── lib/filterHighlights.ts         # DELETE (digest-only helper)
└── api/types.ts                    # MOD — profile types in, digest types out
```

**Structure Decision**: Existing three-service web-app layout, unchanged. No new service, package, or shared module — `backend/` and `agent-runner/` continue to duplicate the small `COMPANY_INFO` constant by hand per Principle V/VI rather than introducing a shared package.

## Phase 0 — Research

See [research.md](./research.md). Fourteen decisions; the load-bearing ones:

- **R1** — Reuse `company_info`, don't add a collection. It has been declared in both services since spec 017 and never written to; it was reserved for exactly this payload.
- **R3** — Denormalize `sector`/`industry` onto `ticker_index` rather than joining `company_info` at query time. This is what makes the sector rollup and both filters cheap, and it reuses 028's proven two-step filter pattern.
- **R5** — `analyses.sector` is dead on arrival today (nothing writes it). The switch therefore has no migration risk and repairs a permanent empty state.
- **R7** — The profile section's price/change/volume come from bars already fetched on the stock page; no new endpoint, and one price on the page (FR-011a/b).
- **R11** — Recharts `<Line hide>` excludes a series from Y-domain computation, so legend toggling satisfies FR-030 with no manual domain math.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — `company_info` document shape and its three independent freshness markers; the two `ticker_index` field additions; the full removal inventory.
- [contracts/company-profile-api.md](./contracts/company-profile-api.md) — fetch/cache semantics, degradation matrix, and the four read endpoints.
- [contracts/sector-and-industry.md](./contracts/sector-and-industry.md) — sector re-sourcing, the unclassified bucket, the industry filter, and the rollup↔grid consistency guarantee (FR-026a).
- [contracts/portfolio-digest-removal.md](./contracts/portfolio-digest-removal.md) — exact file-by-file teardown, plus the one-time collection drop.
- [quickstart.md](./quickstart.md) — end-to-end validation, including the day-one "everything unclassified" state and the mongosh drop.

## Complexity Tracking

No constitutional violations to justify — this section is intentionally empty.
