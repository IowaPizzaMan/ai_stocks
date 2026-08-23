# Implementation Plan: Semantic Layer Chat Assistant

**Branch**: `031-semantic-layer-chat` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/031-semantic-layer-chat/spec.md`

## Summary

Add a **Chat** tab where the user asks plain-English questions and a local LLM answers them by
generating a MongoDB query against a **flat, pre-computed `screener` collection** — one document
per ticker holding deterministic screening signals (20-day range position and z-score, weekly
change, financial-trend direction, FCF-vs-debt). The worker computes and stores those signals on
the existing refresh cycle; the backend owns the semantic layer, generates and validates the
query, executes it read-only, and returns an answer plus the criteria actually applied.

The design is driven by one measured finding (research.md R1): `qwen3:14b` produces a **valid,
correct** query against a flat pre-computed collection, and **invalid MongoDB** against the raw
nested collections. Pre-computation is therefore load-bearing, not an optimization — and it is
also what keeps chat fast at 15x scale, since questions touch a ~17 MB indexed collection rather
than the ~1 GB `price_history`.

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner); TypeScript + React 18 (frontend)

**Primary Dependencies**: FastAPI, Uvicorn, Pydantic v2, PyMongo (sync), pandas;
**new to `backend/`**: `ollama>=0.4` (backend has no LLM capability today — research.md R10);
frontend: React Router v6, TanStack Query v5, Axios

**Storage**: MongoDB 7.x, database `stockai`. One new collection: `screener`.

**Testing**: pytest + mongomock (backend, agent-runner); Vitest + React Testing Library
(frontend, with `vi.mock` on the axios module — no MSW)

**Target Platform**: Local-first Docker Compose stack (mongodb, backend, frontend, agent-runner,
ollama). Single user, no auth.

**Project Type**: Web application (React frontend + FastAPI backend + polling worker)

**Performance Goals**: SC-001 — answer within 10s for most questions. Measured: ~5–8s warm,
~16s cold. Requires Ollama `keep_alive` + pre-warm at backend startup.

**Constraints**: Local `qwen3:14b` only (9.3 GB, the sole installed model); no external LLM
calls; MongoDB auth is **not** enabled (research.md R6); frontend must not poll (Principle V).

**Scale/Scope**: Today 65 tracked tickers / 556 price docs / 84 MB. At 15x: ~975 tickers /
~8,340 price docs / ~1.3 GB, with `screener` at ~17 MB. Fits in cache; no redesign needed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| **I. Test-First & Comprehensive Coverage** | **PASS** | Signal computation is pure `f(bars, financials) -> dict` — exactly the exhaustively-testable surface Principle I targets. Query validation (the read-only allowlist) is pure and must have adversarial tests. Golden-question suite covers generation quality. |
| **II. Spec-Driven Development** | **PASS** | Full Spec Kit flow followed; spec + clarifications complete. |
| **III. Deterministic Core, LLM at the Edges** | **DEVIATION — justified below** | Query *construction* is model-generated. All arithmetic remains deterministic and pre-computed. See Complexity Tracking. |
| **IV. Cache-Aware, Budget-Conscious Data Access** | **PASS** | Signals are derived from already-cached `price_history` / `financials_cache`. **Zero new external API calls.** Chat never contacts a provider. |
| **V. Simplicity & Local-First Scope** | **PASS** | No shared package (per clarification Q4 → option C). No new queue, scheduler, or WebSocket. Streaming deferred. MongoDB auth deliberately *not* enabled to avoid a breaking infra change. |
| **VI. Consistency Across Layers** | **PASS, with a required discipline** | `SCREENER` constant must be added to **both** `backend/db.py` and `agent-runner/tools/db.py` with matching `ensure_indexes` entries, per the hand-sync convention at `backend/db.py:13`. |

**Post-Phase-1 re-check**: still passing. The Phase 1 design added no new infrastructure; the
one deviation (III) is unchanged in scope and remains mitigated as described.

### Two decisions that need the user's explicit sign-off

1. **FR-012 "structurally enforced" read-only.** MongoDB auth is disabled repo-wide
   (research.md R6). The plan enforces read-only with a **stage allowlist in application code**,
   which cannot be bypassed by prompt content but is not a database-level guarantee. Enabling
   auth + a `read`-role user is a breaking change to local dev and both services' config.
   **Planned: allowlist now, auth as a follow-up.** Flagging because the spec's wording implies
   more than will be delivered.
2. **`transcripts_cache` keep vs delete.** The user asked to delete unused collections. This one
   has 0 documents and no writer, but it is referenced (index bootstrap, cleanup-on-ticker-delete,
   and an asserting test) and corresponds to planned feature `specs/007-earnings-transcripts/`.
   **Planned: keep**, per the spec's own carve-out for reserved features. Only
   `portfolio_digest_cache` is deleted.

## Project Structure

### Documentation (this feature)

```text
specs/031-semantic-layer-chat/
├── plan.md              # This file
├── spec.md              # Feature specification (+ clarifications)
├── research.md          # Phase 0 output — measured findings
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── chat-api.md
│   └── screener-collection.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── requirements.txt              # + ollama>=0.4
├── settings.py                   # + chat tuning (keep_alive, timeout, limits)
├── db.py                         # + SCREENER constant, + ensure_indexes entry
├── llm.py                        # NEW — port of agent-runner/llm.py (+ timeouts)
├── semantic/                     # NEW — the semantic layer (backend-only, per Q4=C)
│   ├── schema.py                 #   semantic layer description fed to the model
│   ├── query_guard.py            #   read-only stage allowlist + limit/maxTimeMS injection
│   └── chat.py                   #   orchestration: generate → validate → execute → explain
├── routers/
│   └── chat.py                   # NEW — POST /chat
└── tests/
    ├── test_semantic_schema.py   # NEW
    ├── test_query_guard.py       # NEW — adversarial ($out/$merge/$function/$where)
    └── test_chat_router.py       # NEW

agent-runner/
├── tools/
│   ├── db.py                     # + SCREENER constant (mirror of backend/db.py)
│   └── screener.py               # NEW — pure signal computation + upsert
├── screener_worker.py            # NEW — refresh loop (or admin job handler)
└── tests/
    └── test_screener.py          # NEW — exhaustive pure-function tests (Principle I)

frontend/src/
├── components/layout/Navbar.tsx  # + { to: "/chat", label: "Chat" }
├── App.tsx                       # + import + <Route path="/chat" />
├── api/types.ts                  # + chat request/response types
├── hooks/useChat.ts              # NEW — useMutation (no polling)
└── pages/
    ├── Chat.tsx                  # NEW
    └── Chat.test.tsx             # NEW
```

**Structure Decision**: Web-application layout, using the repo's existing three-service split.
The semantic layer lives **only** in `backend/semantic/` per clarification Q4 (option C) — no
shared package, no constitution amendment. `agent-runner` gains only a pure signal-computation
module and its refresh trigger; it does not import the semantic layer.

## Design Overview

**Write path** (worker, on the existing refresh cycle):
`price_history` + `financials_cache` + `company_info` → pure `compute_signals()` → upsert one
flat document per ticker into `screener`.

**Read path** (backend, per question):
question + capped conversation context → `schema.py` description → Ollama with
`format=<JSON Schema>` (constrained decoding guarantees parseable output, research.md R10) →
`query_guard.validate()` (allowlist, inject `$limit` + `maxTimeMS`) → execute read-only →
result rows + criteria → second Ollama call for prose → response carrying answer, plain-language
criteria, match counts, and the raw query.

**Why two LLM calls rather than one**: generation and interpretation have different needs —
generation wants `temperature: 0` and constrained decoding; interpretation wants prose. Measured
cost of the second call is only ~3.1s warm (research.md R2).

## Complexity Tracking

> Filled because the Constitution Check records one deviation.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Principle III** — query construction is LLM-generated rather than deterministic code | The user explicitly chose text-to-query over a curated function library (clarification Q1 → B). It is what makes open-ended questions possible without enumerating every screen in advance. | A curated deterministic function library (Q1 option A) was **recommended and explicitly declined by the user**. Recording it here as the constitution requires, not relitigating it. |

**Scope of the deviation, stated precisely.** Principle III's binding requirements are that
rule-engine skills stay pure and that agents must not *override a skill's computed result with
LLM judgment*. Both still hold: every number the user sees is computed by deterministic Python
(FR-010) and the model never recomputes or overrides one. What genuinely changes is that query
*construction* — previously always hand-written — is now model-generated. That is a real
expansion of LLM responsibility, and Principle III's stated rationale ("small local models are
unreliable at arithmetic and rule-following") applies partially: arithmetic is fully protected,
rule-following is not.

**Mitigations already designed in:**
- All arithmetic pre-computed deterministically and exhaustively tested (FR-010, Principle I).
- Constrained decoding (`format=<schema>`) removes malformed-output failures entirely.
- Read-only stage allowlist sits between model and driver (FR-012).
- `$limit` + `maxTimeMS` bound every query's cost (FR-016).
- Every answer is auditable: criteria + counts always shown, raw query on demand (FR-013/014).
- A golden-question regression suite is the primary defense against semantically-wrong queries —
  this is the deviation's main residual risk and the suite is a required deliverable, not optional.
