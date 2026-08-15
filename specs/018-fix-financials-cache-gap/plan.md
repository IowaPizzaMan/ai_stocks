# Implementation Plan: Fix Stale Empty Financials Cache

**Branch**: `018-fix-financials-cache-gap` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/018-fix-financials-cache-gap/spec.md`

## Summary

A financials fetch that hits a temporary FMP condition (402/403 "not covered on this plan", or the budget guard) currently caches its all-empty result exactly like a successful fetch, locking the emptiness in for the full 90-day window. Confirmed live: BSX got 402 on all seven statement types on 2026-08-09, and every analysis run since has served that empty cache. The fix adds a per-statement-type outcome marker (`confirmed` vs `unavailable`) to the `financials_cache` document; on a warm cache hit, any `unavailable` statement types (and, for legacy docs written before this fix, any empty ones) are re-fetched on that run, merged into the doc, and promoted to `confirmed` once FMP returns 200. Confirmed statement types keep the existing 90-day behavior untouched, and all failure handling stays fail-soft.

## Technical Context

**Language/Version**: Python 3.12 (agent-runner + backend Docker images)

**Primary Dependencies**: `requests` + `pymongo` in agent-runner (`tools/financials.py`, `tools/fmp_client.py`); FastAPI in backend (read-only consumer via `routers/stocks.py`)

**Storage**: MongoDB `financials_cache` collection (one doc per ticker: `{ticker, data, fetched_at}` → gains an `outcomes` map)

**Testing**: pytest + mongomock (`agent-runner/tests/test_financials.py`); backend contract tests in `backend/tests/test_routers.py` (no change expected — response shape is unchanged)

**Target Platform**: Self-hosted Docker Compose stack (Linux containers), single user

**Project Type**: Web service pair (backend API + agent-runner worker) sharing MongoDB

**Performance Goals**: No regression in analysis-run duration for tickers with fully confirmed cache (zero extra FMP calls, single Mongo read as today)

**Constraints**: FMP call volume for retries must stay inside the existing fmp_client throttle (`fmp_calls_per_minute`) and daily soft cap; retry adds at most 7 calls per manually-triggered analysis run per ticker (only for not-yet-confirmed statement types)

**Scale/Scope**: Single-user deployment, ticker universe ~tens of symbols; one collection touched, one tool function changed, one component spec updated

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| I. Test-First & Comprehensive Coverage | New behavior lands with updated `agent-runner/tests/test_financials.py` cases (outcome recording, per-key retry, legacy-doc self-correction, confirmed-empty not retried, fail-soft preserved). Backend router tests unaffected (shape unchanged) but re-run as regression. | PASS |
| II. Spec-Driven Development | Feature flows through Spec Kit (spec → clarify → this plan). `specs/component-specs/agent-runner/tools/financials.md` caching-logic section MUST be updated as part of implementation so the component spec stays authoritative. | PASS |
| III. Deterministic Core, LLM at the Edges | No LLM involvement anywhere in this change. | PASS (n/a) |
| IV. Cache-Aware, Budget-Conscious Data Access | Change strengthens the cache layer's correctness; retries route through the shared `fmp_client` throttle/budget guard and remain fail-soft ([] on 402/403/budget). No ad-hoc fetch paths added. | PASS |
| V. Simplicity & Local-First Scope | One additive field on an existing collection; no new infra, queues, or schedulers. Retry rides existing manually-triggered analysis runs (never cron). | PASS |
| VI. Consistency Across Layers | `financials_cache` is written by agent-runner and read by backend. The `outcomes` field is additive; backend continues to return `cached["data"]` unchanged, so no backend edit is required — but the contract doc records the new field so both services share one description of the collection. | PASS |

**Post-Phase-1 re-check**: design artifacts introduce no new violations — still PASS on all six principles. Complexity Tracking left empty (no justified violations).

## Project Structure

### Documentation (this feature)

```text
specs/018-fix-financials-cache-gap/
├── spec.md              # Feature spec (input)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── financials-cache.md   # Cache doc schema + get_financials behavior contract
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by this command)
```

### Source Code (repository root)

```text
agent-runner/
├── tools/
│   ├── financials.py        # get_financials(): outcome tracking + per-key retry (primary change)
│   └── fmp_client.py        # unchanged — retries reuse existing throttle/budget guard
└── tests/
    └── test_financials.py   # updated + new cases (primary test surface)

backend/
├── routers/
│   └── stocks.py            # /stocks/{ticker}/financials — expected unchanged (reads cached["data"])
└── tests/
    └── test_routers.py      # regression only; response shape unchanged

specs/component-specs/agent-runner/tools/
└── financials.md            # component spec caching-logic section updated to match
```

**Structure Decision**: All behavior change lives in `agent-runner/tools/financials.py` and its test file. Backend and frontend are untouched consumers — the fix works entirely by making the cache layer retry what it should never have considered settled.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
