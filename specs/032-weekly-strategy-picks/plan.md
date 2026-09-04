# Implementation Plan: Weekly Strategy Buy/Short Picks in AI Chat

**Branch**: `032-weekly-strategy-picks` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/032-weekly-strategy-picks/spec.md`

## Summary

Add a second recognized intent to the existing AI Chat: "per my trading strategies, what should I
buy/short this week and at what price." Two of the system's rule-engine skills — **The Strat**
(`skills/the_strat.py`) and **Gap Analysis** (`skills/gap_analysis.py`) — are extended to run
across the **full ticker universe** on a new background refresh job (mirroring spec 031's
`screener` pattern exactly), writing one flat document per ticker into a new precomputed
`strategy_signals` collection: direction, a rule-derived entry/short price, and a strength score.
**Market Flow** cannot do the same (its own rule spec: "NYMO alone is not a stock picker" — it
reads one market-wide breadth value, not a per-ticker one), so per the spec's Clarifications it
is instead applied as a read-time filter/caveat, using the market-wide NYMO reading already
cached in `breadth_cache` by the existing `breadth_worker`. At ask-time, chat detects the intent,
runs a **deterministic** ranked query against `strategy_signals` (LLM never chooses which stocks
appear — FR-008), applies the Market Flow filter, and asks the LLM only to narrate the computed
lists into prose — the same "generate → validate/compute → narrate" shape as 031's existing
`answer_question()`, reusing its two-Ollama-calls, single-request/response pattern (no new
async/job-polling plumbing needed: the existing chat UI's "thinking…" indicator during a normal
`useMutation` call already satisfies the spec's Clarifications on response timing).

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner); TypeScript + React 18 (frontend) — unchanged from 031.

**Primary Dependencies**: FastAPI, PyMongo (sync), `ollama` client (backend, already added by 031), pandas (agent-runner, already used by `skills/the_strat.py` / `skills/gap_analysis.py`). No new dependency in either service.

**Storage**: MongoDB 7.x, database `stockai`. One new collection: `strategy_signals` (agent-runner writes, backend reads — same split as 031's `screener`). Reads (no writes) from two existing collections: `price_history` (via `tools/price.py::get_price_history()`, already resamples weekly/monthly/quarterly/yearly locally — zero new external calls) and `breadth_cache`/`breadth_meta` (already refreshed daily by `breadth_worker`, both already registered in `backend/db.py`).

**Testing**: pytest (backend, agent-runner) — extends the exact 031 pattern: pure-function tests for the new agent-runner signal module (mirrors `agent-runner/tests/test_screener.py`), a schema-mirror contract test (mirrors `backend/tests/test_screener_contract.py` / `test_db_constants.py`), router/integration tests (mirrors `backend/tests/test_chat_router.py`). Vitest + RTL for the frontend list rendering.

**Target Platform**: Local-first Docker Compose stack (mongodb, backend, frontend, agent-runner, ollama). Single user, no auth — unchanged.

**Project Type**: Web application (React frontend + FastAPI backend + agent-runner background worker) — unchanged from 031.

**Performance Goals**: Chat responses for a strategy-picks question complete within a single request/response (no polling), same shape as 031's SC-001 (~10s warm target) but budgeted slightly higher — **≤15s warm** — since the response composes two per-strategy lists instead of one flat table. All the heavy per-ticker computation (The Strat / Gap Analysis pattern detection across the full universe) happens ahead of time in the background refresh job, not inside the request.

**Constraints**: Local `qwen3:14b` only, via the same pre-warmed Ollama client as 031 — no new model. `strategy_signals` refresh MUST go through `work_queue` (registered in agent-runner's `JOB_HANDLERS`, like `screener_refresh`), not a new timer loop — `breadth_worker`'s own timer is documented in the codebase as "the one deliberate exception" to Constitution Principle V, not a pattern to extend. The LLM MUST NOT decide which tickers appear on a list (FR-008) — its only roles are (a) parsing the question's direction/count/named-strategy into structured parameters and (b) narrating the deterministically-computed lists into prose, mirroring 031's two-call shape but with a narrower first-call responsibility than 031's (031's first call *builds the query*; this one only *extracts parameters* — selection stays 100% deterministic Python either way).

**Scale/Scope**: Same universe as `screener` — today ~65 tracked + ~556 breadth-only tickers (556 `price_history` docs), 15x projected to ~8,340. `strategy_signals` at that scale is comparable in size to `screener` (~17 MB at 15x) — no redesign needed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| **I. Test-First & Comprehensive Coverage** | **PASS** | New signal derivation (`tools/strategy_signals.py`) is a pure `f(ticker, price_data) -> dict` built entirely from already-pure, already-tested `skills/the_strat.py` / `skills/gap_analysis.py` — exhaustive pytest coverage required, mirroring `test_screener.py`. The Market Flow filter (backend-side threshold classification) is also pure and needs adversarial tests (boundary NYMO values). |
| **II. Spec-Driven Development** | **PASS** | Full Spec Kit flow followed; spec + clarifications complete, including the Market Flow scope change discovered during this planning phase. |
| **III. Deterministic Core, LLM at the Edges** | **PASS** (cleaner than 031's deviation) | Candidate selection and ranking are 100% deterministic Python queries against `strategy_signals` (FR-008). The LLM's two touchpoints are narrower than 031's: parsing free-text into `{direction, count, named_strategy}` parameters (not building a query that itself decides matches), and narrating an already-final list into prose. Skills remain pure with no model calls inside them. |
| **IV. Cache-Aware, Budget-Conscious Data Access** | **PASS** | Zero new external API calls. Multi-timeframe price data comes from `get_price_history()`'s local pandas resample of the already-cached `price_history` doc (`refresh="none"`). The Market Flow filter reads the already-cached `breadth_cache`/`breadth_meta` (refreshed once/day by the existing `breadth_worker`) rather than calling `get_market_breadth()` fresh. |
| **V. Simplicity & Local-First Scope** | **PASS** | `strategy_signals` refresh is a new `work_queue` admin job (`JOB_HANDLERS["strategy_signals_refresh"]`), the established pattern `screener_refresh` already uses — not a new timer loop, not a new queue. No WebSocket, no frontend polling: the existing `useMutation`-based chat UI (with its already-implemented "thinking…" indicator) is reused unchanged for timing. |
| **VI. Consistency Across Layers** | **PASS, with the same required discipline 031 established** | New `STRATEGY_SIGNALS = "strategy_signals"` constant + matching indexes MUST be added to **both** `backend/db.py` and `agent-runner/tools/db.py`, and covered by a contract-mirror test alongside the existing `test_db_constants.py` / `test_screener_contract.py`. |

**Post-Phase-1 re-check**: still passing — see end of this document.

### One discovery from this planning phase, not from spec.md's original scope

The spec's Clarifications section already documents that Market Flow was found, during this
planning phase, to be unable to independently rank a ticker universe (its own rule spec: "NYMO
alone is not a stock picker") and was rescoped from a 3rd independent list to a shared
filter/caveat (FR-017–FR-019). No further undisclosed deviations were found while researching
Phase 0/1 below.

## Project Structure

### Documentation (this feature)

```text
specs/032-weekly-strategy-picks/
├── plan.md              # This file
├── spec.md              # Feature specification (+ clarifications)
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── strategy-picks-api.md   # Additive extension to 031's chat-api.md
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
agent-runner/
├── skills/
│   ├── the_strat.py              # UNCHANGED (already pure, already covers direction+trigger price)
│   └── gap_analysis.py           # + one new field per gap: pre-gap reversal/entry level (small, additive)
├── tools/
│   ├── db.py                     # + STRATEGY_SIGNALS constant (mirror of backend/db.py)
│   └── strategy_signals.py       # NEW — pure signal derivation + upsert, mirrors screener.py's shape
├── tools/admin_jobs.py           # + JOB_HANDLERS["strategy_signals_refresh"]
└── tests/
    ├── test_strategy_signals.py  # NEW — exhaustive pure-function tests (Principle I)
    └── test_gap_analysis.py      # + tests for the new reversal-level field

backend/
├── db.py                         # + STRATEGY_SIGNALS constant, + ensure_indexes entry
├── semantic/
│   ├── strategy_picks.py         # NEW — intent parse -> deterministic query -> Market Flow filter -> narrate
│   ├── market_flow_filter.py     # NEW — small pure port of skills/market_flow.py::classify_level (hand-dup precedent, like llm.py)
│   └── chat.py                   # + dispatch: strategy-picks intent checked before the existing free-form flow
├── routers/chat.py                # UNCHANGED (same POST /chat; response payload gains an optional field)
└── tests/
    ├── test_strategy_picks.py    # NEW
    ├── test_market_flow_filter.py # NEW — boundary/threshold tests
    ├── test_db_constants.py      # + STRATEGY_SIGNALS mirror assertion
    └── test_chat_router.py       # + strategy-picks request/response cases

frontend/src/
├── api/types.ts                  # + StrategyPicksResponse fields (optional, additive)
└── pages/
    ├── Chat.tsx                  # + per-strategy list rendering when the response carries strategy_picks
    └── Chat.test.tsx             # + rendering cases
```

**Structure Decision**: Extends 031's existing three-service layout without adding a new service,
queue, or scheduler. Precomputation follows 031's `screener` pattern exactly (a new agent-runner
module + a new `work_queue` admin job writing one collection agent-runner owns); the read path
follows 031's `chat.py` pattern exactly (a new backend module the router dispatches into
alongside the existing free-form flow). The only genuinely new piece of infrastructure is one
MongoDB collection (`strategy_signals`); everything else is composition of already-existing
pieces (`get_price_history()`, `breadth_cache`, the `ollama` client, the chat UI's existing
"thinking…" indicator).

## Design Overview

**Write path** (agent-runner, new `work_queue` admin job `strategy_signals_refresh`, same cadence
class as `screener_refresh`):
`price_history` (full universe, same union `screener.refresh_all()` already iterates) →
`get_price_history()` (local pandas resample, no new API calls) → `skills/the_strat.run()` +
`skills/gap_analysis.run()` (both already pure, already tested) → `tools/strategy_signals.py`
derives, per ticker, a `the_strat` block and a `gap_analysis` block (`direction`, `entry_price`,
`strength`) per the rules in [data-model.md](./data-model.md) → upsert one flat document per
ticker into `strategy_signals` (single writer — no `replace_one` collision with `screener`,
which stays completely untouched by this feature).

**Read path** (backend, per chat question):
`chat.answer_question()` first calls `strategy_picks.detect(question, history)` — one small
Ollama call (`temperature: 0`, constrained JSON schema, mirroring 031's query-generation call but
producing `{is_strategy_picks, direction, count, named_strategy}` instead of a Mongo pipeline). If
`is_strategy_picks` is false, control falls through unchanged to 031's existing free-form flow
(FR-011). If true: deterministic Python queries `strategy_signals` twice (once per strategy),
sorted by `strength` descending with ticker as the tie-break, limited to `count` (default 10);
`market_flow_filter.py` reads the latest `breadth_cache` row and applies FR-017's inclusion
filter/caveat to each candidate; the assembled structured result (never altered by the LLM) is
handed to one `generate_text()` call for prose narration, exactly like 031's answer-interpretation
step. The response carries the existing `answer` field plus a new optional `strategy_picks`
object — additive, so 031's existing response consumers are unaffected.

**Why a new collection instead of extending `screener`**: `screener`'s `refresh_all()`/
`refresh_one()` do a full-document `replace_one` (031 data-model.md explicitly warns about this
exact hazard for `price_history`'s two writers). A second job writing extra fields onto the same
documents would have them silently wiped on the next `screener_refresh` cycle. A dedicated
single-writer collection avoids that landmine entirely and keeps `screener`'s "flat, LLM-queryable"
purpose (031 research.md R1) uncontaminated by fields no free-form query is meant to touch.

## Complexity Tracking

*No entries — the Constitution Check above shows no unjustified violations. Principle III, which
required a documented deviation for 031, is fully satisfied (not merely mitigated) by this
feature's design: selection and ranking never touch the LLM.*

## Post-Phase-1 Constitution Re-Check

Unchanged from the table above after completing Phase 0 (research.md) and Phase 1
(data-model.md, contracts/, quickstart.md) design: no new collection, dependency, service, or
LLM responsibility was introduced beyond what's recorded there. Still **PASS** on all six
principles.
