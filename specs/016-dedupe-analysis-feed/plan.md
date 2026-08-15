# Implementation Plan: Deduplicate Analysis Feed & Storage

**Branch**: `016-dedupe-analysis-feed` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-dedupe-analysis-feed/spec.md`

## Summary

The `analyses` MongoDB collection currently gets a new document on every completed
analysis run, so a re-analyzed ticker accumulates one document per run. This shows up as
duplicate cards in the Feed and stale history lingering after re-analysis. The fix is at
the root: change the single write point (`agent-runner/queue_worker.py:72`) from
`insert_one` to an upsert keyed on `ticker`, using the existing (currently unused for this
collection) `write_db(..., upsert_key=...)` helper. Once storage guarantees at most one
document per ticker, the Feed's existing plain query is already correct — no read-side
aggregation is needed. The per-ticker lookup endpoint (`GET /analysis/{ticker}`) collapses
from a history list to a single object, matching the new invariant and removing the
never-fully-built "history timeline" data plumbing. A new one-time script
(`scripts/dedupe_analyses.py`, modeled on the existing `scripts/backfill_financials.py`)
collapses pre-existing duplicates, after which a new unique index on `ticker` enforces the
invariant at the database level as defense-in-depth. See `research.md` for the full decision
record (D1–D7).

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner), TypeScript (frontend, React 18 + Vite 5)

**Primary Dependencies**: FastAPI + PyMongo (backend router change), PyMongo + existing
`write_db`/`ensure_indexes` helpers (agent-runner write-path and index change), TanStack
Query v5 (frontend hook change) — no new dependencies of any kind.

**Storage**: MongoDB 7.x, collection `analyses` — this feature changes its cardinality
invariant (≤1 doc per ticker) and adds one unique index; see `data-model.md`.

**Testing**: pytest + mongomock (backend and agent-runner, matching existing
`backend/tests/test_routers.py` and `agent-runner/tests/test_queue_worker.py` conventions —
see `research.md` D7); Vitest + React Testing Library only if `StockDetail.tsx`'s existing
test coverage touches the `analyses?.[0]` logic being simplified (to be confirmed against
current frontend test files during implementation).

**Target Platform**: Existing Docker Compose stack (`mongodb`, `backend`, `agent-runner`,
`frontend`) — no platform change.

**Project Type**: Web application (existing `backend/` + `agent-runner/` + `frontend/`
structure) plus one new one-time operator script under `scripts/`.

**Performance Goals**: SC-004 — Feed page-load/filtering stays under 1s perceived load.
Satisfied automatically: removing duplicate documents shrinks the collection and the Feed
query is unchanged (no new aggregation added, per `research.md` D2), so this is a net
performance improvement, not a risk.

**Constraints**: One-time cleanup (FR-006/FR-007) must be safe to re-run with no further
effect after the first successful run. Unique index creation must not crash service startup
if run before cleanup completes (`research.md` D6, fail-soft).

**Scale/Scope**: Single-user, local-first deployment (Constitution Principle V) — no scale
concerns; the change touches one write call site, one read endpoint, one new script, two
`ensure_indexes()` copies, and their direct frontend/test consumers.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First & Comprehensive Coverage** — PASS. `research.md` D7 commits to extending
  existing pytest/mongomock coverage (`test_queue_worker.py`, `test_routers.py`) plus a new
  test for the dedupe script, matching existing conventions; no behavior ships untested.
- **II. Spec-Driven Development** — PASS. This plan traces directly to `spec.md`'s FR-001
  through FR-008; the stale "Analysis History Timeline" spec section
  (`specs/component-specs/frontend/components/stock/AISummaryTab.md`) is flagged for removal
  rather than left to drift from reality (`research.md` D4).
- **III. Deterministic Core, LLM at the Edges** — PASS/N/A. No rule-engine skill or LLM-facing
  code is touched; this is pure storage/API plumbing.
- **IV. Cache-Aware, Budget-Conscious Data Access** — PASS/N/A. No external data-source
  fetch path is touched. The fail-soft posture used for unique-index creation
  (`research.md` D6) explicitly mirrors this principle's "fail soft, log, don't crash"
  pattern, applied to an index-bootstrap failure instead of a data fetch.
- **V. Simplicity & Local-First Scope** — PASS. Explicitly chose *not* to add a `$group`
  aggregation to the Feed once the write-path fix makes it unnecessary (`research.md` D2),
  and reused the existing `scripts/` one-off-script pattern rather than introducing a
  migrations framework (`research.md` D5) — both are direct applications of this principle.
- **VI. Consistency Across Layers** — PASS, with an explicit obligation: `ensure_indexes()`
  is duplicated between `agent-runner/tools/db.py` and `backend/db.py` (their own header
  comments already flag "keep in sync"), and this feature's new unique index must be added
  to **both** copies identically (`data-model.md` Index changes, `research.md` D6) —
  tracked so it isn't missed during /speckit-tasks.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/016-dedupe-analysis-feed/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output — decisions D1-D7
├── data-model.md         # Phase 1 output — Analysis invariant + index changes
├── quickstart.md         # Phase 1 output — manual + automated validation steps
├── contracts/             # Phase 1 output
│   ├── analysis_ticker_endpoint.md   # GET /analysis/{ticker}: list -> single object
│   ├── analysis_write_path.md         # queue_worker insert -> upsert
│   └── dedupe_analyses_script.md      # new scripts/dedupe_analyses.py
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Existing structure, no new top-level directories. Files touched by this feature:

```text
agent-runner/
├── queue_worker.py        # write path: insert_one -> write_db(upsert_key="ticker")
├── tools/db.py             # ensure_indexes(): + unique index on analyses.ticker (fail-soft)
└── tests/test_queue_worker.py   # + re-run-same-ticker upsert assertion

backend/
├── db.py                    # ensure_indexes(): + unique index on analyses.ticker (fail-soft, kept in sync with agent-runner copy)
├── routers/analysis.py     # GET /analysis/{ticker}: find().limit() -> find_one()
└── tests/test_routers.py   # test_ticker_history rewritten for single-object response

frontend/
├── src/hooks/useAnalysis.ts        # useTickerAnalysis: Analysis[] -> Analysis | null
└── src/pages/StockDetail.tsx       # drop analyses?.[0] indirection

scripts/
└── dedupe_analyses.py       # NEW — one-time cleanup, see contracts/dedupe_analyses_script.md

specs/component-specs/frontend/components/stock/
└── AISummaryTab.md          # remove stale "Analysis History Timeline" section (never built)
```

No `backend/routers/sectors.py` or `analysis.py`'s `get_sector_analyses` changes — out of
scope, unaffected in behavior per spec (`research.md` D2).

**Structure Decision**: Existing web-application layout (`backend/` + `agent-runner/` +
`frontend/`, each with its own `tests/`) is unchanged. This feature adds exactly one new
file (`scripts/dedupe_analyses.py`) alongside the existing `scripts/backfill_financials.py`
precedent, and otherwise modifies files in place — no new modules, packages, or directories.

## Complexity Tracking

*No violations — table not needed.*
