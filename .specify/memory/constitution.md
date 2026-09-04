<!--
Sync Impact Report
Version change: 1.0.1 → 1.1.0 (existing guidance materially expanded)
Modified principles:
  - VI. Consistency Across Layers: extended to cover the semantic layer. The principle
    previously governed only backend/ ↔ agent-runner/ agreement on shared concepts. It now
    also governs the third view of that same data — the schema the chat AI is shown in
    backend/semantic/schema.py. A collection can be written correctly and read correctly
    while the model is told about a field that isn't there (queries match nothing) or not
    told about one that is (the field is invisible to chat); neither failure raises, both
    surface days later as a bad chat answer. specs/031-semantic-layer-chat already built
    the mirrored field-vocabulary test for `screener` to close exactly this gap, and
    specs/035-chat-and-news-upgrade needed the same construction again for `news_articles`
    — promoting the pattern from per-feature convention to a stated requirement.
Modified sections: none beyond Principle VI
Added sections: none
Removed sections: none
Deferred/TODO items: none
Templates requiring follow-up: none checked against yet; re-check plan/spec/tasks templates on next amendment
-->

# StockAI Constitution

## Core Principles

### I. Test-First & Comprehensive Coverage (NON-NEGOTIABLE)
Every feature MUST ship with tests before it is considered done. The five rule-engine
skills (`the_strat`, `accumulation`, `gap_analysis`, `market_flow`, `position_management`)
are pure functions with no LLM calls inside them — they MUST have exhaustive pytest suites
that verify their behavior against the corresponding rule spec, since they are the
highest-value, fully-deterministic test surface in the system. Backend routers and
agent-runner tools MUST have integration tests covering their contracts (request/response
shapes, MongoDB read/write behavior). Frontend components and hooks MUST have Vitest +
React Testing Library coverage for user-facing logic (filtering, pagination, mutations).
A pull request that adds behavior without a corresponding test is incomplete, not "tested
later."

**Rationale**: This is a solo, local-first project with no staging environment and an LLM
in the loop — tests are the primary defense against silent regressions, and the deterministic
skills layer is specifically designed to be fully verifiable without needing the LLM to
cooperate.

### II. Spec-Driven Development
Non-trivial features originate from a spec (`specs/SPEC.md`, `specs/component-specs/`, or a
Spec Kit feature spec under `specs/NNN-*/`) before implementation begins. The Spec Kit
workflow (`/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement`) is the default path for anything beyond a trivial fix. Code should be
traceable back to a requirement; when implementation reveals the spec is wrong or
incomplete, the spec is updated, not silently bypassed.

**Rationale**: The existing `specs/` tree is already the project's source of truth
(60+ component specs, 5 rule specs, architecture diagram); this principle keeps that
investment authoritative instead of letting code and specs drift apart.

### III. Deterministic Core, LLM at the Edges
The rule-engine skills compute; the LLM interprets. Skills MUST remain pure,
deterministic `skill.run(ticker, data) -> dict` functions with no model calls inside them.
Agents may read skill output and reason over it, but MUST NOT reimplement or override a
skill's computed result with LLM judgment. Chunk-and-summarize (via Ollama) prepares data
for agents; it does not replace the skills' math.

**Rationale**: Small local models (7B–14B) are unreliable at arithmetic and rule-following
under tool-calling pressure. Keeping the analytics deterministic and LLM-free is what makes
Principle I's exhaustive skill testing possible and keeps the system's core outputs
auditable independent of model quality.

### IV. Cache-Aware, Budget-Conscious Data Access
All external data-source calls (yfinance, FMP, Finnhub, FRED, Quiver, Dataroma) MUST go
through the cache-first data layer (`data_fetcher.py` and its cache collections), not direct
ad-hoc calls from agents or routers. Cache TTLs (90-day financials, 24h macro, permanent
transcripts) MUST be respected. Providers with hard rate limits (e.g. FMP's 250/day) MUST
have a budget guard that fails soft — serve stale cache and log — rather than exhausting the
day's quota.

**Rationale**: The project runs on free/low-tier API plans; an unguarded fetch path can take
the whole app down for a day. This was already identified as a top risk in
`project-proposal.md` and is treated as a hard constraint, not a suggestion.

### V. Simplicity & Local-First Scope
Build for the actual deployment target: a single user, self-hosted Docker Compose stack, no
cloud hosting, no auth, no multi-tenancy, no billing. Do not add infrastructure (queues
beyond `work_queue`, schedulers beyond the existing poll/timer loops, WebSocket live
updates, shared internal packages) ahead of a demonstrated need — `backend/` and
`agent-runner/` deliberately duplicate small shared constants rather than adding a
shared-package build step. All analysis triggering flows through `work_queue`, never cron;
the frontend never polls — it fetches on navigation and manual triggers only. Scope may
expand over time, but each expansion should be a deliberate amendment, not scope creep.

**Rationale**: Matches the explicit "what I'd explicitly not build yet" list in
`project-proposal.md` and keeps a one-person project from accreting operational complexity
it doesn't need yet.

### VI. Consistency Across Layers
Where `backend/` and `agent-runner/` both touch the same concepts (ticker registration
semantics, MongoDB collection/field names, status enums), they MUST stay semantically
consistent even though they ship as separate Docker images with separate dependency trees.
`ticker_index` is the single universe of tickers; both services read/write it through the
same contract. Divergence between the two services' understanding of shared data is a bug,
not an acceptable seam.

This extends to the **semantic layer** — the description of a collection the chat AI is
shown in `backend/semantic/schema.py`. That schema is a third view of the same data,
alongside the writer's and the reader's, and it MUST agree with what is actually written.
Concretely, any collection the chat AI can query (`query_guard.READABLE_COLLECTIONS`)
MUST have a field-vocabulary contract test mirrored verbatim in both services — one
asserting the writer produces exactly that set of fields, one asserting the schema
describes exactly that set — as `screener` does today via
`backend/tests/test_screener_contract.py` and `agent-runner/tests/test_screener.py`.
Admitting a collection to `READABLE_COLLECTIONS` without that mirrored test is incomplete,
and every field in the schema MUST carry a type and a description written well enough for
the model to use the field correctly.

**Rationale**: The two services can't share a Python package by design (Principle V), so
consistency has to be actively maintained rather than enforced by the compiler/import
system — this principle exists so that tradeoff doesn't quietly rot into data corruption.
The semantic-layer extension covers a failure mode the original wording missed: a
collection can be written correctly *and* read correctly while the model is told about a
field that doesn't exist (queries silently match nothing) or not told about one that does
(the field is invisible to chat). Neither raises an exception. Both surface days later as
a bad chat answer, which is the hardest kind of bug to trace back to its cause — and the
LLM cannot be trusted to notice the discrepancy itself, since inventing a plausible field
is exactly what Principle III assumes it will do.

## Technology Stack Constraints

The stack below is a constraint, not just a default — deviating from it (swapping a
framework, adding a new datastore, introducing async Mongo, etc.) requires either an
explicit justification recorded in the relevant `plan.md` or a constitution amendment if the
change is project-wide.

- **Backend / Agent Runner**: Python 3.12, FastAPI + Uvicorn, Pydantic v2, PyMongo (sync),
  CrewAI, Ollama (local LLM runtime), pandas + pandas-ta, Playwright (Dataroma only), pytest,
  ruff (lint + format).
- **Frontend**: React 18 + Vite 5 + TypeScript, Tailwind CSS v4, TanStack Query v5
  (`refetchInterval: false` everywhere — no polling), Recharts, Framer Motion, React Router
  v6, Axios via a single `lib/api.ts`, filter state in URL search params, Vitest + React
  Testing Library.
- **Infrastructure**: Docker Compose with five services (`mongodb`, `backend`, `frontend`,
  `agent-runner`, `ollama`), MongoDB 7.x with TTL indexes on cache collections, `.env` /
  `.env.example` via `pydantic-settings`.

## Development Workflow & Quality Gates

- Features flow through the Spec Kit pipeline (Principle II) before code is written, except
  for trivial fixes (typos, config tweaks, dependency bumps).
- Tests (Principle I) and `ruff` MUST pass before a change is considered mergeable. `ruff` is
  a pinned dependency in both `backend/requirements.txt` and `agent-runner/requirements.txt`
  (each service installs it into its own venv, per Principle V), governed by the single
  `ruff` config in the repo-root `pyproject.toml` (config, not runtime code, is shared even
  though the two services' dependencies are not). Run `ruff check backend/` /
  `ruff check agent-runner/ scripts/` before considering a change to either service done.
  Hooks (lint, test) MUST NOT be skipped (`--no-verify`) to force a merge; a failing gate
  means the change or the test is wrong, not that the gate should be bypassed.
- Pull requests/commits SHOULD reference the spec or feature directory they implement
  (e.g. `specs/016-dedupe-analysis-feed/`) so behavior stays traceable to a requirement.
- Risks and open questions uncovered during implementation are recorded (in the plan, spec,
  or `project-proposal.md`'s Risks section) rather than left as undocumented tribal
  knowledge.

## Governance

This constitution supersedes ad-hoc practice for anything it addresses. When a principle and
a convenience conflict, the principle wins unless the constitution is amended.

**Amendment procedure**: Amendments are made via `/speckit-constitution`, editing this file
directly, or an equivalent explicit review. Every amendment MUST update the Sync Impact
Report at the top of this file and bump the version per the policy below.

**Versioning policy** (semantic versioning applied to governance):
- **MAJOR** — a principle is removed or redefined in a backward-incompatible way.
- **MINOR** — a new principle or section is added, or existing guidance is materially
  expanded.
- **PATCH** — wording, typo, or clarification changes with no semantic effect.

**Compliance review**: Non-trivial plans and PRs should be checked against the Core
Principles above (test coverage, spec traceability, deterministic-skills boundary, cache/
budget discipline, scope discipline, cross-layer consistency). This project is expected to
evolve — principles that stop fitting reality should be amended openly rather than quietly
ignored.

**Version**: 1.1.0 | **Ratified**: 2026-08-15 | **Last Amended**: 2026-08-25
