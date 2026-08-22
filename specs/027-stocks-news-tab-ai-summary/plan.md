# Implementation Plan: Stocks Page News Tab and Cross-Stock AI Summary

**Branch**: `027-stocks-news-tab-ai-summary` | **Date**: 2026-08-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-stocks-news-tab-ai-summary/spec.md`

## Summary

Reorganize the Stocks page into a tabbed layout: the filter bar + stock grid stay on
the default tab, the market-wide news list (spec 022) moves to a new **News** tab,
and the grid's scroll-triggered auto-fetch is replaced with a bounded, internally
scrollable panel plus an explicit "Load more" control so the browser window itself
never has to scroll. The default tab also gains a **cross-stock AI summary** panel
that synthesizes every tracked stock's existing AI analysis (conviction-prioritized,
capped at 25 for LLM context budget) into an overview and specific per-stock guidance,
with a manual regenerate control. The digest panel renders **beside** the grid as a
second column (grid in the primary/left position), not stacked above or below it
(clarified 2026-08-22, FR-007b).

Technical approach: the frontend changes are page-local (new tabs + bounded-layout
wrapper in `Stocks.tsx`, a manual "Load more" button replacing
`useIntersectionObserver`, a new digest panel) with zero changes to `App.tsx` or any
other route. The regeneration step reuses `work_queue`'s existing (currently
unexercised) non-ticker `job_type` dispatch path in `agent-runner/queue_worker.py` —
no new queue, service, or scheduler — backed by a new agent
(`agents/portfolio_digest.py`) that condenses and synthesizes `analyses` documents the
same way `portfolio_strategist.py` already condenses one ticker's sub-reports. Results
persist in a new singleton `portfolio_digest_cache` document that independently tracks
last-success and last-failure, so a failed regeneration never blanks the panel.

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner), TypeScript / React 18 + Vite 5 (frontend)

**Primary Dependencies**: FastAPI, PyMongo (sync), TanStack Query v5, Ollama via `llm.generate_json` (agent-runner) — no new dependencies

**Storage**: MongoDB 7.x — existing `analyses`, `work_queue`; new singleton `portfolio_digest_cache`

**Testing**: pytest (backend routers + agent-runner tools/agents/queue dispatch), Vitest + React Testing Library (frontend)

**Target Platform**: Self-hosted Docker Compose (single user, local-first)

**Project Type**: Web application (backend + frontend + agent-runner workers)

**Performance Goals**: Digest regeneration is a single Ollama call over ≤25 condensed stock entries — same order of magnitude as one ticker's `portfolio_strategist` call, not a per-stock loop; grid/tab UI changes are pure client-side reorganization with no new network calls beyond the existing paginated feed

**Constraints**: No frontend polling beyond the existing sanctioned `useQueueStatus` busy-loop (Constitution Tech Stack Constraints); no changes to `App.tsx`'s shared shell (R1); Ollama `num_ctx=8192` bounds the digest's input cap (R5); market news content/behavior (20-cap, ~60-min reuse) must be byte-for-byte unchanged by the relocation (FR-002)

**Scale/Scope**: 1 user; 2 new Stocks-page tabs; digest input capped at 25 of however many tickers are tracked (typically dozens, not thousands)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First & Comprehensive Coverage | PASS | New deterministic surfaces (condense-and-rank-by-conviction, cap-at-25, stale derivation) each get pytest suites; the digest agent's schema-validated LLM call follows the same test shape as `portfolio_strategist`'s. Frontend tab switching, bounded-layout markup, and digest panel states get Vitest+RTL coverage. Contract file above defines the assertable shapes. |
| II. Spec-Driven Development | PASS | Spec 027 clarified (3 Qs: filter independence, cap-priority order, digest panel placement) before planning; all three answers are load-bearing in this plan (R5, R8, R9). |
| III. Deterministic Core, LLM at the Edges | PASS | Condensing `analyses` documents, sorting/capping by conviction, and computing `stale` are pure functions; the LLM (`portfolio_digest` agent) only writes the overview narrative and per-stock notes — it does not override any stock's stored signal/conviction. |
| IV. Cache-Aware, Budget-Conscious Data Access | PASS | The digest makes zero new external provider calls — it only reads already-cached `analyses` documents and calls the local Ollama runtime, which has no daily-budget concept. No FMP/Finnhub/etc. calls are added by this feature. |
| V. Simplicity & Local-First Scope | PASS | No new service, queue, or scheduler — reuses `work_queue`'s existing non-ticker `job_type` dispatch branch (R4). No new npm/pip dependency. `App.tsx`'s shared shell is untouched (R1); the bounded-layout change is scoped to one page. |
| VI. Consistency Across Layers | PASS | `PORTFOLIO_DIGEST_CACHE` collection name and the digest document shape are defined once in `contracts/portfolio-digest-api.md` and `data-model.md`; both `backend/db.py` and `agent-runner/tools/db.py` declare the same constant per existing convention. Tab pattern reuses `StockDetail.tsx`'s hash-routing convention instead of inventing a second one. |

**Post-Phase-1 re-check (2026-08-21)**: All six principles still PASS after Phase 0/1
design — no new infrastructure was introduced, the LLM stayed confined to narrative
synthesis, and the one new external-facing behavior (a regenerate button) drives
already-existing job-queue plumbing rather than new plumbing. No Complexity Tracking
entries needed.

**Post-clarification re-check (2026-08-22)**: FR-007b (digest panel placed beside the
grid rather than stacked above it, R9) is a pure layout change inside the same
page-local, already-planned component tree — it introduces no new infrastructure,
dependency, or data flow, so all six principles remain PASS. Only `Stocks.tsx`'s
internal markup (R1's `flex-1 overflow-y-auto` body) and its Vitest coverage need to
change; the digest panel component, its hooks, and the backend/agent-runner work are
unaffected.

## Project Structure

### Documentation (this feature)

```text
specs/027-stocks-news-tab-ai-summary/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── portfolio-digest-api.md   # GET /portfolio/digest, POST /portfolio/digest/regenerate, admin-job handler
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/
├── db.py                            # + PORTFOLIO_DIGEST_CACHE constant
├── routers/
│   └── portfolio.py                 # NEW: GET /portfolio/digest, POST /portfolio/digest/regenerate
└── tests/test_portfolio.py          # NEW

agent-runner/
├── tools/
│   ├── db.py                        # + PORTFOLIO_DIGEST_CACHE constant (kept in sync with backend/db.py)
│   ├── portfolio.py                 # NEW: gather analyses, condense, sort/cap by conviction
│   └── admin_jobs.py                # + JOB_HANDLERS["portfolio_digest"] = run_portfolio_digest
├── agents/
│   └── portfolio_digest.py          # NEW: LLM synthesis over condensed multi-stock input (mirrors portfolio_strategist's shape)
├── queue_worker.py                  # unchanged — _run_admin_job branch already dispatches by job_type
└── tests/
    ├── test_portfolio_digest.py     # NEW: condense/cap/rank logic + agent schema
    ├── test_admin_jobs.py           # NEW: handler success/empty/failure paths
    └── test_queue_worker.py         # + dispatch test for job_type="portfolio_digest"

frontend/
├── src/
│   ├── api/types.ts                 # + PortfolioDigestResponse, PortfolioDigestHighlight; QueueJob.ticker → optional, + job_type
│   ├── hooks/
│   │   ├── usePortfolioDigest.ts    # NEW: GET /portfolio/digest (no polling, no filter args — R8)
│   │   ├── useQueue.ts              # useQueueStatus's drain-invalidate list + ["portfolio-digest"]
│   │   └── usePortfolioDigestRegenerate.ts  # NEW: POST /portfolio/digest/regenerate mutation
│   ├── components/
│   │   ├── shared/TabBar.tsx        # NEW: extracted from StockDetail's hash-tab nav, reused by both pages
│   │   └── feed/
│   │       ├── PortfolioDigestPanel.tsx  # NEW: overview + highlights + regenerate button + empty/stale/busy states
│   │       └── MarketNewsPanel.tsx  # unchanged component, now rendered inside the News tab instead of inline
│   └── pages/
│       ├── Stocks.tsx               # tabs (grid/news), bounded layout (R1), manual Load-more (R2), digest panel beside grid as a second column (R9)
│       └── StockDetail.tsx          # tab nav markup swapped for the extracted TabBar (no behavior change)
└── src/**/*.test.{ts,tsx}           # Vitest coverage per Principle I
```

**Structure Decision**: Existing three-service web layout (`backend/`, `frontend/`,
`agent-runner/`) is kept; the feature only adds modules inside each service and one
new router. No shared packages (Principle V) — the digest document shape is kept
aligned across `backend/db.py` and `agent-runner/tools/db.py` by hand, per the same
convention already used for every other collection constant (Principle VI).

## Complexity Tracking

No constitution violations — table intentionally empty.
