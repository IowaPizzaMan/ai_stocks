# Implementation Plan: Remove Stocks from Watchlist and Stocks Page

**Branch**: `023-remove-stocks` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/023-remove-stocks/spec.md`

## Summary

Add a hover/focus-revealed "x" control to (a) each Sidebar watchlist entry, wired to the
already-existing but unused `useRemoveFromWatchlist` hook and `DELETE /watchlist/{ticker}`
endpoint (non-destructive unpin), and (b) each Stocks-page `AnalysisTile`, wired through a
new inline confirm popover to the existing `DELETE /tickers/{ticker}` endpoint (destructive
purge). The backend deletion endpoint's scope is incomplete against FR-009 — it purges 5 of
11 ticker-scoped collections — so it must be extended to also clear `transcripts_cache`,
`earnings_cache` (history-type docs only), `stock_news_cache`, `institutional_cache`, and
`beneficial_ownership_cache`. No new libraries, no schema/migration changes, no new backend
endpoints — this is UI affordances plus closing a data-scope gap on an existing endpoint.

## Technical Context

**Language/Version**: Python 3.12 (backend, FastAPI), TypeScript 5.6 / React 18 (frontend)

**Primary Dependencies**: FastAPI, PyMongo, Pydantic (backend, already in use for both
touched routers); React, @tanstack/react-query, axios, react-router-dom, Tailwind CSS
(frontend, already in use for both touched components) — no new dependencies

**Storage**: MongoDB — 11 existing ticker-scoped collections (see [data-model.md](data-model.md)),
no schema changes, no new collections, no migration

**Testing**: pytest + httpx + mongomock (backend router tests, `backend/tests/test_routers.py`);
Vitest + React Testing Library (frontend component tests, e.g. `AnalysisTile.test.tsx`,
`Stocks.test.tsx`)

**Target Platform**: Existing self-hosted Docker Compose web app (backend API container +
Vite/React SPA), no deployment changes

**Project Type**: Web application (existing `backend/` + `frontend/` split)

**Performance Goals**: Interactive UI feedback (hover reveal, in-flight state) within the
same frame budget as existing tile/sidebar interactions — no new performance target, this is
UI-scale work

**Constraints**: Single-user, local-first, no auth (Constitution V); deletion must not call
any external data-source API (Constitution IV — this is a pure Mongo purge, no FMP/Finnhub
calls, so no budget-guard interaction); `backend/` and `agent-runner/` collection names must
stay in sync per Constitution VI (already true — this feature only reads existing constants
from `backend/db.py`, doesn't add new ones)

**Scale/Scope**: 2 frontend components modified (`Sidebar.tsx`, `AnalysisTile.tsx`) + 1 new
small confirm-popover component; 1 backend endpoint extended (`delete_ticker` in
`backend/routers/stocks.py`); no new endpoints, no new pages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First & Comprehensive Coverage** — PASS (with obligation). Frontend hook/mutation
  logic and hover-reveal/confirm-popover behaviour need Vitest + RTL coverage; the extended
  `delete_ticker` endpoint needs a pytest case per newly-purged collection. Tracked as
  required tasks in Phase 2, not optional.
- **II. Spec-Driven Development** — PASS. Originates from `specs/023-remove-stocks/spec.md`,
  which has no remaining `[NEEDS CLARIFICATION]` markers.
- **III. Deterministic Core, LLM at the Edges** — N/A. No rule-engine skill or LLM call is
  touched by this feature.
- **IV. Cache-Aware, Budget-Conscious Data Access** — PASS. Deletion is a local Mongo purge
  only; it never calls an external provider, so there is no FMP/Finnhub budget to guard.
  `earnings_cache` deletion is scoped to `{"type": "history", "ticker": T}` specifically so it
  does **not** touch the market-wide `calendar`/`universe` cache docs that share the
  collection — accidentally purging those would force an unnecessary re-fetch for every
  other tracked ticker.
- **V. Simplicity & Local-First Scope** — PASS. No new infrastructure, no new library (the
  confirm popover is a small local component, not a modal/dialog dependency), no polling
  added. Reuses the existing `useMutation`/`react-query` invalidation pattern already used by
  `useWatchlist.ts`.
- **VI. Consistency Across Layers** — PASS. The five collections being added to the delete
  scope are all read via `backend/db.py` constants that already mirror
  `agent-runner/tools/db.py` 1:1; no new constant is introduced on either side.

No violations. Complexity Tracking table not needed.

**Post-Phase 1 re-check**: Design artifacts (research.md, data-model.md, contracts/,
quickstart.md) introduced no new dependency, collection, endpoint, or infrastructure beyond
what's assessed above — the widened `delete_ticker` scope is additional `delete_many` calls
against collections already declared in `backend/db.py`, and the confirm popover is a local
component with no new library. All six gates still PASS unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/023-remove-stocks/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── watchlist-and-ticker-deletion.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── routers/
│   ├── watchlist.py         # DELETE /watchlist/{ticker} — already correct, no change
│   └── stocks.py            # DELETE /tickers/{ticker} — extend collection purge scope
├── db.py                    # collection name constants — already has all needed constants
└── tests/
    └── test_routers.py      # extend delete_ticker test coverage

frontend/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   └── Sidebar.tsx          # add hover/focus "x" per watchlist entry
│   │   ├── feed/
│   │   │   ├── AnalysisTile.tsx     # add hover/focus "x" per tile
│   │   │   └── RemoveTickerConfirm.tsx  # new: inline Confirm/Cancel popover
│   │   └── shared/                  # (if a shared hover-reveal-button pattern emerges)
│   ├── hooks/
│   │   ├── useWatchlist.ts          # useRemoveFromWatchlist — already exists, wire it up
│   │   └── useStocks.ts             # new (or add to existing hook file): useDeleteTicker
│   └── api/
│       └── types.ts                  # no new types needed — deletion returns {deleted: string}
└── src/components/feed/AnalysisTile.test.tsx  # extend with remove-control coverage
```

**Structure Decision**: Existing `backend/` + `frontend/` web-application split (Option 2).
No new top-level directories. Both user-facing changes are additive edits to existing
components (`Sidebar.tsx`, `AnalysisTile.tsx`) plus one new small presentational component
for the confirm popover; the backend change is additive lines inside the existing
`delete_ticker` handler, not a new endpoint.

## Complexity Tracking

*No Constitution Check violations — table not needed.*
