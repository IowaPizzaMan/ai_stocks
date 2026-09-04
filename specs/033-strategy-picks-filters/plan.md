# Implementation Plan: Combined Strategy Picks & Screener Filters in AI Chat

**Branch**: `033-strategy-picks-filters` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/033-strategy-picks-filters/spec.md`

## Summary

Two changes to the already-implemented AI Chat strategy-picks path (`032-weekly-strategy-picks`):
(1) remove its keyword pre-filter so intent detection runs on every question (FR-001), fixing
the reported failure where "give me 10 stocks to buy and 10 to short" wasn't recognized; and
(2) let a strategy-picks question also name free-form extra conditions (liked/disliked, sector,
financial trend, etc.) that narrow each strategy's candidate universe before ranking (FR-002–004),
reusing the exact same LLM-driven question-to-Mongo-pipeline mechanism the existing free-form
screener chat (`031-semantic-layer-chat`) already uses against the `screener` collection — not a
new, hardcoded condition parser. A user's per-ticker "liked"/"disliked" preference (already
captured by `PUT /stocks/{ticker}/sentiment` but not exposed to chat) becomes one new `screener`
field so it's queryable the same way any other screening signal is (FR-005). The two
already-implemented modules involved, `backend/semantic/chat.py` and
`backend/semantic/strategy_picks.py`, are extended rather than replaced; one small shared module
is extracted so both the free-form flow and the new condition-translation step call the identical
query-generation code (not two copies of it).

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner) — unchanged from 031/032. No frontend
change (spec's Assumptions: "no new user-facing controls").

**Primary Dependencies**: FastAPI, PyMongo (sync), `ollama` client — all already present, no new
dependency in either service.

**Storage**: MongoDB 7.x, database `stockai`. No new collection. One new field
(`liked_status`) on the existing `screener` collection (agent-runner writes, backend reads —
unchanged writer/reader split). Reads (no writes) `ticker_index.sentiment`, already written by
the existing sentiment endpoints.

**Testing**: pytest (backend, agent-runner) extending the exact existing test files this feature
touches: `agent-runner/tests/test_screener.py` (new `liked_status` derivation cases),
`backend/tests/test_screener_contract.py` (mirrored field-name assertion), a new
`backend/tests/test_condition_filter.py` (pure-function tests for the strip-display-stages
pipeline logic and the applied/failed/zero-match outcomes), and extensions to
`backend/tests/test_strategy_picks.py` / `test_chat_router.py` for the combined-condition and
no-keyword-recognition scenarios.

**Target Platform**: Local-first Docker Compose stack — unchanged.

**Project Type**: Web application (React frontend + FastAPI backend + agent-runner background
worker) — unchanged. This feature is backend-only; no frontend files change.

**Performance Goals**: A strategy-picks question with no extra condition keeps 032's ≤15s warm
budget (one fewer keyword-gate branch, same two Ollama calls it always made once the keyword
matched). A question with an extra condition adds one more Ollama call (condition translation)
— the spec's Assumptions section explicitly accepts this as a latency tradeoff, not a regression
to guard against (SC-001 isn't tightened by this feature). An ordinary screener question now
always pays for the intent-detection call it previously skipped — also an explicitly accepted
tradeoff (Edge Cases: "some added latency... not a regression to guard against").

**Constraints**: Same as 032 — local `qwen3:14b` only, LLM never chooses which tickers appear on
a list (FR-008 in 032, preserved here: the condition-translation call produces a *predicate*,
not a selection; ranking/limiting inside `strategy_signals` stays 100% deterministic Python,
same as before this feature). The condition-translation pipeline MUST run through the existing
`query_guard.validate_pipeline()` allowlist before execution — no new execution path that
bypasses it.

**Scale/Scope**: Same universe as `screener`/`strategy_signals` (032 Technical Context: ~65
tracked + ~556 breadth-only today, ~8,340 projected at 15x). The condition-translation query
executes an unlimited `$match` + ticker-only `$project` against `screener` — acceptable at this
scale per 031 research.md R8 (cache-resident collection).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| **I. Test-First & Comprehensive Coverage** | **PASS** | New pure logic (`condition_filter.py`'s pipeline-stripping and outcome classification, the extended `_rank_strategy`'s ticker-filter predicate) gets exhaustive pytest coverage in a new `test_condition_filter.py`, mirroring the existing test-file pattern. `agent-runner/tools/screener.py`'s `liked_status` derivation is covered in `test_screener.py` alongside its existing pure-function cases. |
| **II. Spec-Driven Development** | **PASS** | Full Spec Kit flow followed; spec + 3 clarifications recorded before this plan. |
| **III. Deterministic Core, LLM at the Edges** | **PASS, no new deviation** | This feature reuses 031's *already-recorded* LLM-generates-a-query pattern (031's Constitution Check already accepts this as the one deliberate deviation for the free-form flow) for the condition-translation step — it doesn't introduce a new one. Candidate *ranking and selection* inside `strategy_signals` remains 100% deterministic Python, unchanged from 032 (FR-008 there). The LLM's role stays: (a) classify intent + extract raw condition text, (b) translate condition text into a `screener` predicate, (c) narrate final results — never choose final tickers by itself. |
| **IV. Cache-Aware, Budget-Conscious Data Access** | **PASS** | Zero new external API calls. `liked_status` is copied from an already-written, already-cached field (`ticker_index.sentiment`) at the existing `screener_refresh` cadence. The condition query reads only the already-cached `screener` collection. |
| **V. Simplicity & Local-First Scope** | **PASS** | No new collection, service, queue, or timer. `screener_query.py`'s extraction is a refactor (code motion), not new infrastructure — it exists specifically to avoid a second, drifting copy of the query-generation logic (FR-004's own requirement). |
| **VI. Consistency Across Layers** | **PASS, same discipline as 031/032** | `liked_status` is added to **both** `semantic/schema.py`'s `SCREENER_SCHEMA` and `agent-runner/tools/screener.py`'s `compute_signals()`, kept in sync by the existing mirrored-field-name test (`backend/tests/test_screener_contract.py` / `agent-runner/tests/test_screener.py`) — no new collection constant needed since `screener`/`STRATEGY_SIGNALS` already exist in both `db.py` files. |

**Post-Phase-1 re-check**: still passing — see end of this document.

## Project Structure

### Documentation (this feature)

```text
specs/033-strategy-picks-filters/
├── plan.md              # This file
├── spec.md              # Feature specification (+ clarifications)
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── strategy-picks-filters-api.md   # Additive extension to 032's strategy-picks-api.md
└── tasks.md              # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
agent-runner/
├── tools/
│   └── screener.py               # compute_signals() + refresh_all()/refresh_one() +
│                                  #   liked_status derivation from ticker_index.sentiment
└── tests/
    └── test_screener.py          # + liked_status derivation cases

backend/
├── semantic/
│   ├── schema.py                 # + liked_status field description
│   ├── screener_query.py         # NEW — QUERY_SCHEMA/build_system_prompt/criteria_from_pipeline/
│   │                              #   generate_pipeline, extracted from chat.py (pure code motion)
│   ├── chat.py                   # imports screener_query instead of owning it; calls
│   │                              #   strategy_picks.detect() unconditionally (FR-001)
│   ├── condition_filter.py       # NEW — translate_conditions(): condition text -> ticker set
│   ├── strategy_picks.py         # INTENT_SCHEMA + extra_conditions; looks_like_strategy_picks()
│   │                              #   removed; _rank_strategy()/compute_picks() take ticker_filter;
│   │                              #   response gains condition_requested/condition_applied/condition_note
│   └── market_flow_filter.py     # UNCHANGED — independent filter, still applied after ranking
├── db.py                         # + liked_status index on SCREENER
└── tests/
    ├── test_screener_contract.py # + liked_status in the mirrored field-name set
    ├── test_condition_filter.py  # NEW
    ├── test_strategy_picks.py    # + combined-condition, zero-match, unrecognized-condition cases
    └── test_chat_router.py       # + no-keyword-recognition, condition-response-shape cases

frontend/                          # UNCHANGED — no new user-facing controls (spec Assumptions)
```

**Structure Decision**: No new service, collection, or route. Extends 031/032's existing
three-service layout by (a) adding one field to an existing collection, (b) extracting one
already-existing chunk of query-generation code into a small shared module so it has exactly one
implementation instead of becoming two once `strategy_picks.py` needs it too, and (c) extending
032's intent schema and response shape additively. `backend/routers/chat.py` itself is unchanged
— same route, same request shape, response gains three optional fields nested under the already-
additive `strategy_picks` object.

## Design Overview

**Write path** (agent-runner, existing `screener_refresh` job, unchanged cadence): the existing
per-ticker loop in `refresh_all()`/`refresh_one()` already reads `ticker_index` for the tracked-
ticker set / `is_tracked` flag; it's extended to also read that same document's `sentiment` field
and pass it through `compute_signals(..., liked_status=...)` into the flat `screener` document —
one additional field, no new read, no new cadence.

**Read path** (backend, per chat question):
1. `chat.answer_question()` calls `strategy_picks.detect()` on **every** question (FR-001 —
   `looks_like_strategy_picks()` removed). Extended `INTENT_SCHEMA` also returns
   `extra_conditions: string[] | null` in the same call.
2. If `is_strategy_picks` is false, control falls through to the existing free-form flow
   unchanged (FR-009) — that flow now imports its query-generation pieces from the new
   `screener_query.py` instead of owning them locally, but produces byte-identical behavior.
3. If true and `extra_conditions` is non-empty: `condition_filter.translate_conditions()` makes
   one more Ollama call reusing `screener_query`'s exact schema/prompt, validates the result
   through the existing `query_guard`, strips display-oriented stages, and executes an unlimited
   ticker-only `$match` against `screener` (research.md R4) — producing either a ticker set
   (possibly empty — FR-006) or an "unable to apply" result (FR-007), plus plain-language
   criteria for FR-008.
4. `strategy_picks.compute_picks()` (unchanged Market Flow step) now also threads the resulting
   `ticker_filter` into each `_rank_strategy()` call's Mongo predicate, narrowing the
   `strategy_signals` candidate set *before* the existing sort/limit — so a filtered-out stock
   never occupies a slot a qualifying one should have (FR-003).
5. `narrate()`'s prompt gains the condition's plain-language criteria/failure note so the
   generated prose discloses what was applied or why something couldn't be (FR-007/008),
   unchanged narration call shape otherwise.

**Why extract `screener_query.py` instead of duplicating**: `strategy_picks.py` cannot import
from `chat.py` (which already imports `strategy_picks` — that would be a cycle). FR-004 requires
condition translation to use "the same general question-to-query mechanism," not a matching
reimplementation, so the shared logic needs a home neither existing module owns. See
research.md R3.

**Why the condition query strips `$sort`/`$limit`/`$project`**: `query_guard`'s default/hard
limits exist to bound rows *displayed* to the user in the free-form flow; reusing them for a
ticker-membership check would silently truncate the qualifying set and violate FR-003's "never
displaces a candidate that does meet every condition." See research.md R4.

## Complexity Tracking

*No entries — the Constitution Check above shows no unjustified violations. The one LLM-generates-
a-query pattern this feature relies on (the condition-translation call) is not a new deviation
from Principle III; it reuses 031's already-recorded and already-accepted exception rather than
introducing a second one.*

## Post-Phase-1 Constitution Re-Check

Unchanged from the table above after completing Phase 0 (research.md) and Phase 1
(data-model.md, contracts/, quickstart.md): no new collection, service, dependency, or LLM
responsibility beyond what's recorded there — one new `screener` field, one code-motion module,
one new small module, additive schema/response fields. Still **PASS** on all six principles.
