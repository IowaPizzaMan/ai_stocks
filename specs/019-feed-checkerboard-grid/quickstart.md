# Quickstart: Validating the Feed Checkerboard Grid

**Feature**: 019-feed-checkerboard-grid

## Prerequisites

- Docker Compose stack running (`docker compose up -d mongodb backend`), or backend reachable at the URL in `frontend/.env`
- Node deps installed: `cd frontend && npm install`
- Enough analyses to exercise grouping: at least a handful of tickers spanning bullish/bearish/neutral signals and different conviction levels (run analyses via the Feed's Pull / Run All controls if the DB is sparse)

## Automated validation

```powershell
cd frontend
npx vitest run src/lib/groupFeed.test.ts          # grouping rules (order, newest-first, unknown bucket)
npx vitest run src/components/feed               # AnalysisTile, TilePreview, SkeletonTile
npx vitest run src/pages/Feed.test.tsx           # page composition, states, filters
npx vitest run                                   # full frontend suite — must stay green
```

Expected: all suites pass; no test references `AnalysisCard` anymore (component deleted).

## Manual validation (maps to spec success criteria)

Start the frontend: `cd frontend && npm run dev`, open the Feed (default route).

1. **Density (SC-001)**: On a maximized 1080p+ window, count visible tiles — must be ≥30 without scrolling, arranged bullish → neutral → bearish with labeled dividers.
2. **Signal at a glance (SC-002 / FR-003)**: Tiles are visibly green/red/gray; only text on a tile face is the ticker (FR-002). Long tickers (GOOGL, BRK.B) fit untruncated.
3. **Conviction dots (SC-003 / FR-004)**: Spot-check tiles against known analyses — high = 3 dots, medium = 2, low = 1.
4. **Click-through (SC-004 / FR-006)**: Click a tile → lands on that stock's detail page in one click.
5. **Hover preview (SC-005 / FR-012)**: Hover a tile → preview shows signal label, conviction with label, recency, summary snippet, and a working "+ Watchlist" button (adds without navigating). Tab to a tile → preview appears on focus; the watchlist button is keyboard-reachable.
6. **Grouped infinite scroll (FR-013/FR-014)**: With >60 analyses, scroll to the bottom sentinel — new tiles merge into their signal groups (watch a bullish tile appear mid-board, not appended at the end).
7. **Filters (FR-007)**: Apply signal/sector/conviction filters and the ticker search — the board narrows; the URL carries the filter params; clearing restores the full board. Market-flow cards hide while filtered, reappear when cleared (FR-010).
8. **States (FR-011)**: Hard-refresh → tile-shaped skeletons; stop the backend → existing error message; empty DB (or absurd filter) → "No analyses yet" / empty result handling.
9. **Responsive (FR-008)**: Narrow the window to phone width — column count drops, tiles stay legible/tappable, no horizontal page scroll.
10. **Accessibility (SC-006 / FR-005)**: Inspect a tile — `aria-label` announces ticker, signal, conviction, recency. Verify tiles are reachable and activatable by keyboard alone.

## References

- Spec: [spec.md](./spec.md) — FR/SC numbering used above
- UI contract: [contracts/feed-grid-ui.md](./contracts/feed-grid-ui.md)
- Grouping rules: [data-model.md](./data-model.md)
