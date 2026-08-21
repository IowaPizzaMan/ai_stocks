# Implementation Plan: Delta-Only Data Pulls

**Branch**: `024-delta-data-pulls` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-delta-data-pulls/spec.md`

## Summary

Make delta retrieval the default for per-stock pulls, with an operator-triggered full
refresh as the only way to rebuild stored data.

The technical approach rests on one structural change: a **`price_history` collection
holding a single daily OHLCV series per ticker**, shared by both containers and
extended incrementally. That one move satisfies four requirements at once — local
resampling for every chart resolution (SC-004), natural deduplication of the repeated
in-pull download (SC-003), atomic single-document swap on full refresh (FR-030), and
elimination of the interleaving hazard between containers (FR-031). News gains a
coverage envelope on its existing document; insider transactions gain a date bound.

One finding reframes the goal and is called out here rather than buried: **a bounded
FMP price request costs the same single API call as an unbounded one.** Delta fetching
for prices saves transfer and parse time, not request count. The measurable wins are
eliminating the duplicate history download, collapsing four chart-resolution fetches to
zero, and reducing news paging. Whether that reaches SC-001's 50% depends on how much
of pull wall-time is HTTP and pandas versus sequential LLM calls — which is precisely
why the spec ranks US1 (measurement) above the delta work, and why this plan builds it
first.

## Technical Context

**Language/Version**: Python 3.12 (backend + agent-runner), TypeScript 5 / React 18 (frontend)

**Primary Dependencies**: FastAPI, Pydantic v2, PyMongo (sync), pandas, requests; React 18 + Vite 5, TanStack Query v5, Tailwind v4

**Storage**: MongoDB 7.x — new `price_history` and `pull_metrics` collections; modified `stock_news_cache` and `work_queue`; retired `price_cache`

**Testing**: pytest (both services), Vitest + React Testing Library (frontend), ruff as lint gate

**Target Platform**: Docker Compose, single-user self-hosted local stack

**Project Type**: Web application — two Python services + React frontend + MongoDB

**Performance Goals**: SC-001 repeat pull ≥50% faster (target, pending US1 measurement); SC-002 ≥80% less data transferred on a repeat pull; SC-003 zero duplicate in-pull retrievals; SC-004 zero downloads on chart-resolution switching

**Constraints**: FMP daily soft cap must never be exceeded and must fail soft (Principle IV); provider request count per pull must not increase (FR-022); no polling in the frontend; no shared Python package between services (Principle V)

**Scale/Scope**: Single user; ~10²–10³ tickers in `ticker_index`; ~15y × ~250 bars ≈ 3,800 rows per series (~450 KB, well inside the 16 MB document limit)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment | Verdict |
|---|---|---|
| **I. Test-First & Comprehensive Coverage** | Merge and coverage logic is written as pure functions over plain data and tested exhaustively via a case table shared by both services. Router contract tests for `mode`, the upgrade rule, and the metrics endpoint. Vitest for the refresh control and cost panel. Edge cases enumerated in research D12. | ✅ PASS |
| **II. Spec-Driven Development** | Full pipeline: spec → clarify (5 questions) → plan. Requirements traced by FR/SC id throughout every artifact. | ✅ PASS |
| **III. Deterministic Core, LLM at the Edges** | No LLM involvement anywhere in this feature. Skills receive byte-identical inputs — `get_series` returns the same DataFrame shape `fetch_eod_history` does today (FR-020), so `_resample`, `_slice_period`, and `compute_indicators` are untouched. | ✅ PASS |
| **IV. Cache-Aware, Budget-Conscious Data Access** | Every provider call still routes through the budget-guarded client; `FmpBudgetExceededError` handling is unchanged and full refresh gets no exemption (FR-027, clarification Q3). FR-022 forbids any increase in requests per pull. **Net improvement**: rewriting `backend/routers/price.py` onto `backend/fmp.py::fmp_get` closes half of a logged `KNOWN_ISSUES.md` budget-bypass entry. | ✅ PASS (improves) |
| **V. Simplicity & Local-First Scope** | No new services, queues, schedulers, or shared packages. Two new collections, one modified endpoint, one new endpoint, one new button, one collapsible panel. Explicitly rejected: per-bar documents, time-series collections, a new admin route, automatic drift detection (clarification Q4/Q5). | ✅ PASS |
| **VI. Consistency Across Layers** | The known tension: the store accessor is duplicated across containers. Follows the established house pattern (`db.py` constants, `backend/fmp.py`, `backend/earnings_data.py`) and is actively defended — both services run the *same* merge case table, so divergence fails a test instead of corrupting data silently. | ✅ PASS |

**Post-Phase-1 re-check**: No gate changed. The Phase 1 design *strengthened* Principle
IV (one bypass call site removed) and Principle VI (shared case table promoted from
convention to an enforced test). No entries in Complexity Tracking.

**Note on a deliberate correctness trade**: the spec knowingly accepts silent
post-split drift, with the operator's full refresh as the only remedy (clarification
Q4/Q5). This is a recorded, user-made decision, not an oversight — the constitution
requires such risks to be documented rather than left as tribal knowledge, which the
spec's Assumptions section and the `KNOWN_ISSUES.md` step in `quickstart.md` do.

## Project Structure

### Documentation (this feature)

```text
specs/024-delta-data-pulls/
├── plan.md                       # This file
├── spec.md                       # Feature spec (clarified 2026-08-17)
├── research.md                   # Phase 0 — D0..D12
├── data-model.md                 # Phase 1 — collections, validation, transitions
├── quickstart.md                 # Phase 1 — 9 validation scenarios + migration
├── contracts/
│   ├── queue-pull-mode.md        # Phase 1 — API + UI contract (US1, US5)
│   └── price-store.md            # Phase 1 — store accessor contract (US2)
├── checklists/
│   └── requirements.md           # Spec quality checklist (16/16)
└── tasks.md                      # Phase 2 — NOT created by /speckit-plan
```

### Source Code (repository root)

```text
agent-runner/
├── tools/
│   ├── price_store.py            # NEW — store accessor + pure merge/coverage fns
│   ├── metrics.py                # NEW — stage_recorder, threading.local attribution
│   ├── price.py                  # MOD — 3 fetch_eod_history sites → store
│   ├── news.py                   # MOD — delta window + coverage envelope
│   ├── insider.py                # MOD — date-bounded transaction fetch
│   ├── fmp_client.py             # MOD — `start` param; per-stage request/byte tally
│   ├── finnhub_client.py         # MOD — per-stage request/byte tally
│   └── db.py                     # MOD — PRICE_HISTORY, PULL_METRICS + indexes
├── crew.py                       # MOD — refresh once, mode plumbing, stage recording
├── queue_worker.py               # MOD — read job.mode, write pull_metrics
└── tests/
    ├── test_price_store.py       # NEW — shared merge case table
    ├── test_metrics.py           # NEW — attribution under parallel prefetch
    └── test_news.py, test_insider.py, test_crew.py   # MOD

backend/
├── price_store.py                # NEW — hand-synced mirror of the agent-runner module
├── routers/
│   ├── price.py                  # MOD — read stored series, resample locally
│   ├── queue.py                  # MOD — `mode` param + pending-job upgrade rule
│   └── stocks.py                 # MOD — GET /stocks/{ticker}/pull-metrics
├── db.py                         # MOD — PRICE_HISTORY, PULL_METRICS
└── tests/
    ├── test_price_store.py       # NEW — same case table as agent-runner
    └── test_price.py, test_routers.py                # MOD

frontend/src/
├── components/stock/
│   ├── FullRefreshButton.tsx     # NEW — confirm-then-refresh (US5)
│   └── PullCostPanel.tsx         # NEW — collapsible stage breakdown (US1)
├── hooks/
│   ├── useQueue.ts               # MOD — mode-aware enqueue mutation
│   └── usePullMetrics.ts         # NEW
├── pages/StockDetail.tsx         # MOD — mount both components
└── api/types.ts                  # MOD — PullMetrics, EnqueueResponse.mode
```

**Structure Decision**: Existing three-part layout (`backend/`, `agent-runner/`,
`frontend/`) is unchanged — no new top-level directories. The one structural addition is
the duplicated `price_store` module, one copy per Python service, which is the house
pattern for cross-container shared logic under Principle V (research D4).

## Implementation Sequence

Ordered so each step is independently verifiable, matching the spec's story priorities.

| Step | Story | Delivers | Verified by |
|---|---|---|---|
| 1 | US1 (P1) | `metrics.py`, client instrumentation, `pull_metrics`, endpoint, cost panel | Scenario 1 |
| 2 | US2 (P2) | `price_store` ×2 + shared case table; agent-runner call sites | Scenarios 3, 4 |
| 3 | US2 (P2) | Backend price endpoint onto the store; retire `price_cache` | Scenario 2 |
| 4 | US5 (P2) | `mode` plumbing, upgrade rule, refresh button | Scenarios 6, 7, 8, 9 |
| 5 | US3 (P3) | News delta window + coverage envelope; drop TTL | Scenario 5 |
| 6 | US4 (P4) | Insider date-bounded fetch | pytest |

Steps 2–4 ship together as the default-path switch: **US5 gates US2 going live**. Delta
must not become the default until the operator has a way to undo it (spec, US5 "Why
this priority").

Step 1 first is not ceremony. If it shows fetch time is a small fraction of pull
wall-time, SC-001's target gets restated against the fetch portion before steps 2–6 are
built out — that is the measurement doing its job, and it is cheaper to learn now.

## Complexity Tracking

> No constitutional violations. Table intentionally empty.

The one candidate — duplicating `price_store` across containers — is not a violation:
Principle V explicitly prescribes duplication over a shared package, and Principle VI's
consistency requirement is met by the shared test case table rather than by shared code.
