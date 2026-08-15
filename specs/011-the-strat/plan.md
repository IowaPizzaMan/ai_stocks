# Implementation Plan: The Strat Price-Action Rule Engine

**Branch**: `011-the-strat` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-the-strat/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

`agent-runner/skills/the_strat.py` already implements a subset of this spec — bar
classification (FR-001/002), hammer/shooter detection (FR-004/005), kicking patterns
(FR-007), 2-1-2 and 2-2 reversals and 2-bar/1-bar Rev Strat (part of FR-014/015/016),
and Full Time Frame Continuity with the app's daily-excluded/quarterly-yearly-included
scope adjustment (FR-022/023/030/031). It is wired into `crew.py`'s per-ticker
pipeline and consumed by `agents/technical_analyst.py`, with an existing pytest suite
(`agent-runner/tests/test_the_strat.py`).

This plan extends that module (not a greenfield build) to close the remaining gaps:
outside-bar subtypes (FR-003), momentum/regular signal distinction (FR-006),
universal-truth tagging (FR-009), inside-bar momentum/retracement + Mother Bar quality
+ multi-inside-bar flags (FR-010–012), the two missing canonical reversals —
Failed-2-Goes-3 and 3-1-2 — plus Soft Rev Strat (FR-014/018), cross-timeframe
combinations and measured-move projection (FR-019–021), "in control" TFC
determination and natural-buyer/seller correlation (FR-024/025), Broadening
Formation fractal/reclaim/support-resistance tracking (FR-026–029), the pre-trade
checklist synthesis (FR-032–035), entry/stop-placement computation for every signal
type (FR-036–039), and the VIX-ETN instrument-class rule set (FR-040–042). All
additions are pure functions consistent with the existing module's style — no new
services, no new persistence.

## Technical Context

**Language/Version**: Python 3.11/3.12 (matches `agent-runner/.venv`, already running this module)

**Primary Dependencies**: `pandas` (already used); no new dependencies — no bid/ask
or intraday feed is available (see Constraints), so no real-time market-data client
is added

**Storage**: N/A for this feature. `agent-runner` uses MongoDB for job/results
persistence (`tools/db.py`), but `the_strat.py` is and remains a pure, stateless
function library — each call recomputes from the full OHLC window `tools/price.py`
already returns, matching every sibling skill (`market_flow.py`, `gap_analysis.py`,
`accumulation.py`, `position_management.py`). See research.md for the explicit
stateless-vs-persisted decision on "in force" signal tracking and Broadening
Formation levels.

**Testing**: pytest, run from `agent-runner/` (`pytest tests/test_the_strat.py`);
existing suite extended in place, no new test framework

**Target Platform**: `agent-runner` background worker service (Docker, per
`docker-compose.yml`); invoked synchronously inside `crew.py`'s per-ticker pipeline,
same as today

**Project Type**: Single-service extension — Python library module inside an
existing monorepo (`backend/` FastAPI + `agent-runner/` worker + `frontend/` React),
following the existing `skills/` rule-engine pattern (Option 1 below)

**Performance Goals**: No new performance target beyond the existing per-ticker
`crew.py` pipeline (the_strat.run() already executes synchronously per ticker per
scheduled analysis run); added computation is pure in-memory logic over a data
window already in hand, no new I/O

**Constraints**: This app has no intraday or live bid/ask feed — only daily-and-up
OHLC pulled from `yfinance` via `tools/price.py::get_price_history()` (per
spec.md Assumptions and FR-030). This directly affects FR-037/FR-039 (stop rules
that reference "the bid"/"the offer" in the source methodology); see research.md
for the documented proxy decision. 60-minute TFC, the Flip, Uncoupling, and Sideways
30 remain explicitly out of scope per FR-030.

**Scale/Scope**: Same invocation scale as today — one `the_strat.run()` call per
ticker per analysis job processed by `queue_worker.py`; no batch/bulk mode required.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still the unfilled template (placeholder
principle names/descriptions, no ratified version) — there are no concrete
principles to gate this plan against. No violations to record; no gate failures.
Recommend running `/speckit-constitution` separately to establish real principles,
but this is not a blocker for planning or implementing this feature.

## Project Structure

### Documentation (this feature)

```text
specs/011-the-strat/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
# Option 1: Single project — existing agent-runner skill module, extended in place
agent-runner/
├── skills/
│   └── the_strat.py         # EXTEND: existing module (bar/pattern/TFC logic today;
│                             #   add outside-bar subtypes, stop/level-of-defense,
│                             #   BF tracking, checklist synthesis, VIX-ETN rules)
├── tools/
│   └── price.py              # UNCHANGED interface; crew.py may pass an optional
│                             #   correlated-ticker price history for FR-025
├── agents/
│   └── technical_analyst.py  # Consumes the_strat.run() output as `strat` context;
│                             #   prompt updated (out of code-scope for this plan,
│                             #   flagged for /speckit-tasks) to narrate new fields
├── crew.py                   # Existing call site: `the_strat.run(ticker, price_history)`;
│                             #   additive only — no signature break
└── tests/
    └── test_the_strat.py     # EXTEND: existing pytest suite, one test group per
                              #   new FR area

specs/component-specs/agent-runner/
├── tools/price.md            # Existing component spec — update if correlated-ticker
│                             #   fetch is added
└── agents/technical_analyst.md  # Existing component spec — update for new strat
                              #   output fields technical_analyst should narrate
```

**Structure Decision**: This is an in-place extension of one existing module
(`agent-runner/skills/the_strat.py`) inside the monorepo's existing worker service,
following the same pure-function `skills/` pattern already used by
`market_flow.py`, `gap_analysis.py`, `accumulation.py`, and `position_management.py`.
No new service, package, or directory is introduced; Option 1 (single project) is
the only structure in use here, so Options 2/3 from the template are not applicable.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations recorded — table intentionally omitted.
