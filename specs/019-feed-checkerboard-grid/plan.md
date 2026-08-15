# Implementation Plan: Feed Checkerboard Grid

**Branch**: `019-feed-checkerboard-grid` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-feed-checkerboard-grid/spec.md`

## Summary

Replace the Feed page's single-column large-card list with a dense, responsive multi-column grid of compact tiles. Each tile shows only the ticker, a signal-colored fill (emerald = bullish, red = bearish, zinc = neutral — the app's existing convention), and 1–3 conviction dots. Tiles are grouped by signal (bullish → neutral → bearish, newest-first within each group), click through to the stock detail page, and expose a rich hover preview (signal label, conviction, recency, summary snippet, add-to-watchlist). This is a **frontend-only** change: the existing `/analysis/feed` endpoint, its filters, its one-entry-per-ticker dedupe, and its newest-first pagination are reused unchanged; grouping happens client-side over loaded pages.

## Technical Context

**Language/Version**: TypeScript ~5.x on React 18 (existing frontend; no version changes)

**Primary Dependencies**: Vite 5, Tailwind CSS v4, TanStack Query v5 (`useInfiniteQuery`, `refetchInterval: false`), React Router v6, Axios via `lib/api.ts`. No new dependencies — the grid is CSS Grid via Tailwind utilities; the hover preview is a positioned popover built with existing primitives (no popper/floating-ui library).

**Storage**: N/A (reads existing `/analysis/feed` API; no schema or backend changes)

**Testing**: Vitest + React Testing Library (existing frontend test setup, e.g. `frontend/src/components/**/**.test.tsx`)

**Target Platform**: Self-hosted web app (Docker Compose `frontend` service); desktop-first with responsive reflow down to mobile widths

**Project Type**: Web application — this feature touches `frontend/` only

**Performance Goals**: ≥30 tiles visible without scrolling at 1920×1080 (SC-001); grid renders a 60-item page without perceptible jank; no new network chatter (fetch on navigation + infinite scroll only, per constitution)

**Constraints**: No polling (`refetchInterval: false` everywhere); filter state stays in URL search params; color must not be the sole signal carrier (accessible names + hover preview); `SkeletonCard` is shared with InstitutionalFlow and must not be modified — a new `SkeletonTile` is added instead

**Scale/Scope**: One page redesign; 1 modified page, ~3 new components, 1 deleted component (`AnalysisCard`, Feed-only), 1 pure grouping helper, component-spec updates, and new Vitest suites. Universe is dozens-to-hundreds of tickers (single user)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Assessment | Status |
|---|-----------|------------|--------|
| I | Test-First & Comprehensive Coverage | Frontend user-facing logic gets Vitest + RTL coverage: tile rendering (color per signal, dot count per conviction, fallbacks), pure `groupBySignal` helper (exhaustive — it's deterministic), hover preview content/actions, Feed page states (loading/error/empty/filtered). No rule-engine skills touched. | PASS |
| II | Spec-Driven Development | This plan traces to `specs/019-feed-checkerboard-grid/spec.md` (clarified). Component specs in `specs/component-specs/frontend/` will be updated (Feed.md rewritten; AnalysisTile.md added; AnalysisCard.md marked replaced) so the spec tree stays authoritative. | PASS |
| III | Deterministic Core, LLM at the Edges | No skills or agents touched; pure presentation of already-computed signal/conviction. Grouping logic is a pure function. | PASS |
| IV | Cache-Aware, Budget-Conscious Data Access | No new external data calls; reuses the existing feed endpoint. Page size rises 20→60 per request against our own MongoDB-backed API — no third-party quota impact. | PASS |
| V | Simplicity & Local-First Scope | No new dependencies, no new infrastructure, no polling, no view toggle (clarified: grid replaces list). Dead code (`AnalysisCard`) is deleted, not kept "just in case". | PASS |
| VI | Consistency Across Layers | Signal/conviction enums (`bullish/bearish/neutral`, `high/medium/low`) are consumed as-is from the shared API contract; no divergence introduced. | PASS |

**Initial gate**: PASS — no violations, Complexity Tracking left empty.

**Post-design re-check (after Phase 1)**: PASS — design artifacts introduce no new dependencies, endpoints, or infrastructure; all deltas are contained in `frontend/src/` plus spec-tree updates.

## Project Structure

### Documentation (this feature)

```text
specs/019-feed-checkerboard-grid/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── feed-grid-ui.md  # UI contract: tile, preview, grid grouping, a11y
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── pages/
│   │   └── Feed.tsx                          # MODIFIED — renders grouped tile grid instead of card list
│   ├── components/
│   │   ├── feed/
│   │   │   ├── AnalysisCard.tsx              # DELETED — Feed-only, replaced by AnalysisTile
│   │   │   ├── AnalysisTile.tsx              # NEW — compact tile: ticker + signal fill + conviction dots
│   │   │   ├── TilePreview.tsx               # NEW — rich hover/focus preview with watchlist action
│   │   │   ├── SkeletonTile.tsx              # NEW — tile-shaped loading placeholder
│   │   │   ├── FilterBar.tsx                 # UNCHANGED
│   │   │   └── MarketFlowCard.tsx            # UNCHANGED content; may get slimmer spacing only
│   │   ├── shared/
│   │   │   ├── ConvictionMeter.tsx           # UNCHANGED (reused inside preview; tile draws its own dots)
│   │   │   ├── SignalBadge.tsx               # UNCHANGED (reused inside preview)
│   │   │   └── SkeletonCard.tsx              # UNCHANGED (still used by InstitutionalFlow)
│   │   └── ...
│   ├── lib/
│   │   └── groupFeed.ts                      # NEW — pure groupBySignal(items) helper
│   ├── hooks/
│   │   └── useAnalysis.ts                    # MODIFIED — page_size 20 → 60 for grid density
│   └── api/
│       └── types.ts                          # UNCHANGED (Signal, Conviction, AnalysisFeedItem reused)
└── src/components/feed/*.test.tsx, src/lib/groupFeed.test.ts, src/pages/Feed.test.tsx  # NEW tests

specs/component-specs/frontend/
├── pages/Feed.md                             # MODIFIED — grid layout, grouping, preview
└── components/feed/AnalysisTile.md           # NEW — tile + preview component spec
    (AnalysisCard.md updated to note replacement by AnalysisTile in 019)
```

**Structure Decision**: Existing web-application layout; all code changes live under `frontend/src/` (pages, components/feed, lib, hooks), with documentation deltas under `specs/component-specs/frontend/`. `backend/` and `agent-runner/` are untouched.

## Complexity Tracking

*No constitution violations — table intentionally empty.*
