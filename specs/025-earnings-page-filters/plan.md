# Implementation Plan: Earnings Page Readability & Filters

**Branch**: `025-earnings-page-filters` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-earnings-page-filters/spec.md`

## Summary

Rebuild the earnings page as a single auto-loading table: a date-windowed earnings
calendar that shows estimates for upcoming reports and actuals plus surprise for reports
already in. The manual scan disappears; filter state moves into URL search params; rows
sort by market cap descending and link to the stock detail page.

The enabling technical change is switching `GET /earnings/calendar` from Finnhub to FMP's
`stable/earnings-calendar`, which — unlike Finnhub's calendar — carries `epsActual` and
`revenueActual`, and accepts an arbitrary `from`/`to` window covering past dates. A live
probe (research.md D1) shows the documented truncation constraint that originally pushed
this endpoint to Finnhub no longer holds. Market cap, company name, and sector continue to
come from the cached Nasdaq screener universe, which also performs the ≥$500M noise screen.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 / React 18 (frontend)

**Primary Dependencies**: FastAPI, Pydantic v2, PyMongo (sync), `requests` — backend.
React 18 + Vite 5, TanStack Query v5, React Router v6, Tailwind v4, Axios — frontend.
No new dependencies in either service.

**Storage**: MongoDB 7.x, existing `earnings_cache` collection only (raw response cache,
4h TTL). No new collections, no persisted domain data (FR-026).

**Testing**: pytest + mongomock (backend, via existing `conftest` client fixture),
Vitest + React Testing Library (frontend).

**Target Platform**: Self-hosted Docker Compose stack, desktop browser.

**Project Type**: Web application — `backend/` (FastAPI) + `frontend/` (React SPA).

**Performance Goals**: Client-side filter changes render in <200ms with zero network
(SC-004, SC-009). Date window changes render in <2s (SC-004a). One provider request per
preset click (SC-009a).

**Constraints**: FMP daily soft cap of 250 calls shared across both services
(Constitution IV) — every new call site must route through `backend/fmp.py::fmp_get` and
fail soft on `FmpBudgetExceededError`. No frontend polling (Constitution V). Filter state
lives in URL search params (Constitution, Technology Stack Constraints).

**Scale/Scope**: A ±30-day window in peak season returns ~10–20k raw provider rows;
after the ≥$500M screen expect ~1–3k rows on the wire (research.md D5). The ±2-day
default is ~50–300 rows. Single user, no concurrency concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| **I. Test-First & Comprehensive Coverage** | Backend: router contract tests for the new `from`/`to` signature, surprise-derivation unit tests (the pure function is the highest-value deterministic surface here — negative EPS, zero estimate, missing actual, dedupe). Frontend: Vitest coverage for preset resolution, client-side filtering, ordering, and ticker links. Tests are written before the code they cover. | **PASS** |
| **II. Spec-Driven Development** | Feature originates from `specs/025-earnings-page-filters/spec.md`, clarified through 5 questions plus a follow-up control change. Component specs under `specs/component-specs/` need updating for the changed router and the replaced components — tracked as tasks. | **PASS** |
| **III. Deterministic Core, LLM at the Edges** | No LLM anywhere in this feature. Surprise math is a pure function computed server-side and fully unit-testable. | **PASS** |
| **IV. Cache-Aware, Budget-Conscious Data Access** | New FMP calls route through `backend/fmp.py::fmp_get` (budget-counted) and are cached 4h per window in `earnings_cache`. `FmpBudgetExceededError` degrades to stale cache with a staleness flag (FR-028), never a 5xx. **This feature also fixes an open KNOWN_ISSUES item**: `earnings_data.py::_fmp_get` currently bypasses the budget counter entirely. | **PASS — improves compliance** |
| **V. Simplicity & Local-First Scope** | Net code reduction: four frontend components removed, two added. No new infrastructure, collections, or dependencies. **Removing the scan UI also removes the app's only `refetchInterval` poll** (`useEarningsScan`), which the constitution explicitly disallows. | **PASS — improves compliance** |
| **VI. Consistency Across Layers** | `agent-runner/tools/earnings_calendar.py` mirrors `backend/earnings_data.py` by hand. This feature changes only the backend copy's calendar path; the agent-runner's scanner keeps its Finnhub path. Divergence is deliberate and documented (research.md D7) rather than silent, but it is real and must be recorded in KNOWN_ISSUES. | **PASS with noted seam** |

**Gate result: PASS.** No violations requiring justification; the Complexity Tracking table
below is therefore empty. Two principles are actively improved by this feature.

## Project Structure

### Documentation (this feature)

```text
specs/025-earnings-page-filters/
├── plan.md              # This file
├── research.md          # Phase 0 output — 8 decisions
├── data-model.md        # Phase 1 output — wire shapes, derivation rules
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   └── earnings-calendar.md   # GET /earnings/calendar request/response contract
├── checklists/
│   └── requirements.md  # From /speckit-specify + /speckit-clarify
└── tasks.md             # Created by /speckit-tasks — NOT by this command
```

### Source Code (repository root)

```text
backend/
├── earnings_data.py                 # MODIFY: calendar fetch → FMP stable/earnings-calendar
│                                    #   with from/to; join to screener universe; derive
│                                    #   surprise; route through fmp.fmp_get; sort by cap
├── routers/earnings.py              # MODIFY: GET /calendar takes from/to instead of days
└── tests/
    ├── test_earnings.py             # MODIFY: calendar contract tests for new signature
    └── test_earnings_data.py        # MODIFY: surprise derivation, dedupe, screen, order

frontend/src/
├── pages/EarningsScan.tsx           # REWRITE → auto-loading single-table page
├── hooks/useEarningsScan.ts         # MODIFY: new useEarningsCalendar(from,to); drop the
│                                    #   polling scan hook; keep useAnalyzeTickers
├── api/types.ts                     # MODIFY: EarningsCalendarEntry gains actuals/surprise
└── components/earnings/
    ├── EarningsFilterBar.tsx        # NEW: presets, custom dates, sliders, toggle
    ├── EarningsFilterBar.test.tsx   # NEW
    ├── EarningsTable.tsx            # NEW: replaces UpcomingEarningsTable
    ├── EarningsTable.test.tsx       # NEW
    ├── UpcomingEarningsTable.tsx    # DELETE (+ its test)
    ├── EarningsCalendarTable.tsx    # DELETE (+ its test) — scored-candidate table
    ├── EarningsCandidateCard.tsx    # DELETE — scan detail modal
    └── ScanControls.tsx             # DELETE — manual trigger

specs/component-specs/               # MODIFY: backend/routers/earnings.md and the
                                     #   frontend earnings component specs
KNOWN_ISSUES.md                      # MODIFY: retire the stale FMP truncation constraint;
                                     #   close the budget-bypass item; log the new seam
```

**Structure Decision**: Existing two-service web layout (`backend/` + `frontend/`), no new
directories. The change is concentrated in one backend module, one router, one page, and
the `components/earnings/` folder. `agent-runner/` is untouched.

## Phase 0 — Research

See [research.md](./research.md). Eight decisions, all `NEEDS CLARIFICATION` resolved:

| # | Decision |
|---|---|
| D1 | Source actuals from FMP `stable/earnings-calendar` — the documented ~15-row truncation no longer reproduces (789 and 2,347 rows returned on live probe) |
| D2 | Change endpoint signature to `from`/`to` rather than adding a parallel endpoint |
| D3 | Compute surprise server-side as a pure function; never store it |
| D4 | **Drop the bmo/amc column** — FMP's calendar has no time-of-day field |
| D5 | Screen against the cached Nasdaq universe before serialization to bound payload |
| D6 | Cache per exact window in `earnings_cache`, 4h TTL, budget-guarded |
| D7 | Leave `agent-runner`'s Finnhub calendar path alone; document the seam |
| D8 | Filter state in URL search params; only the date window reaches the server |

## Phase 1 — Design & Contracts

- **[data-model.md](./data-model.md)** — wire shape for `EarningsCalendarEntry` with
  actuals and derived surprise, the reporting-state enum, derivation rules (including the
  negative-EPS and zero-estimate cases), dedupe rule, and ordering guarantee.
- **[contracts/earnings-calendar.md](./contracts/earnings-calendar.md)** — request and
  response contract for `GET /earnings/calendar`, validation rules, error and degraded
  responses, and the full list of breaking changes for the frontend.
- **[quickstart.md](./quickstart.md)** — how to run and validate the feature end to end,
  mapped to the spec's success criteria.

### Post-Design Constitution Re-check

Re-evaluated after Phase 1. **Still PASS.** The design added no storage, no dependency, and
no service. Two items to carry into `/speckit-tasks`:

1. **Dead code after the scan UI is removed.** `POST /earnings/scan`, `GET /earnings/scan/{id}`,
   `earnings_scan_worker.py`, and `agents/earnings_scanner.py` survive with no caller. The
   spec explicitly scopes their deletion out, so they stay — but leaving unreachable code
   undocumented would violate the workflow rule on recording open questions. Log in
   KNOWN_ISSUES rather than expanding scope.
2. **`EarningsScanDoc` and the scored-candidate types** in `api/types.ts` become unused on
   the frontend once the scan UI goes. Remove the now-unreferenced frontend types; leave
   backend shapes intact for the dormant endpoints.

## Complexity Tracking

No constitution violations — table intentionally empty.

## Risks

| Risk | Mitigation |
|---|---|
| FMP re-imposes truncation on `earnings-calendar`, or the key's entitlement changes | Row counts are asserted in the quickstart validation; the 4h cache limits blast radius; degraded responses already surface staleness to the user (FR-028) |
| A ±30-day window in peak season returns a large payload | Screen against the universe server-side before serialization (D5); measure in quickstart step 6 and revisit only if it proves slow |
| Losing the bmo/amc marker (D4) is more disruptive than expected | Recorded as a deliberate tradeoff in research.md and reflected back into the spec's Key Entities; re-adding means a per-symbol `earnings` call or keeping Finnhub, both rejected for now |
| Universe cache miss forces a 25k-row Nasdaq download on first request of the day | Pre-existing behavior, unchanged by this feature; the 24h universe cache already absorbs it |
