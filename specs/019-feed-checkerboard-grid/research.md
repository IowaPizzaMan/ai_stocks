# Research: Feed Checkerboard Grid

**Feature**: 019-feed-checkerboard-grid | **Date**: 2026-08-15

No `NEEDS CLARIFICATION` markers remained after `/speckit-clarify`; this document records the technical decisions that resolve the plan's open implementation choices, grounded in the existing codebase.

## R1. Where grouping happens: client-side over loaded pages

- **Decision**: Group tiles by signal (bullish → neutral → bearish, newest-first within groups) in the frontend with a pure helper `groupBySignal(items: AnalysisFeedItem[])`, applied to the flattened `useInfiniteQuery` pages. The backend feed endpoint keeps its newest-first order.
- **Rationale**: The backend already returns deduped, newest-first, filterable pages (`/analysis/feed`); adding a server-side sort/group param would change a shared contract for a purely presentational need (violates simplicity, Principle V) and complicate pagination (grouped server order breaks "page N of newest-first" semantics). Client-side grouping over the loaded set is O(n) on at most a few hundred items, trivially testable as a pure function (Principle I), and satisfies FR-014's "later pages merge into their group" requirement naturally — regrouping runs on every page merge.
- **Alternatives considered**: (a) Backend `sort=signal` query param — rejected: contract churn, pagination ambiguity, two services to keep consistent. (b) Three parallel filtered queries (one per signal) — rejected: triples request volume and breaks the single `total`/infinite-scroll model.

## R2. Page size: 20 → 60 for the grid

- **Decision**: Raise the feed request `page_size` from 20 to 60 in `useFeed`.
- **Rationale**: SC-001 requires ≥30 visible tiles without scrolling; a 20-item first page would under-fill a 1920×1080 board and force an immediate second fetch. 60 fills the viewport with headroom in one request against our own API (no third-party budget involved, Principle IV untouched). The backend endpoint already accepts `page_size` as a parameter.
- **Alternatives considered**: Keep 20 (rejected: immediate double-fetch on load); fetch-all (rejected: unbounded response as the universe grows; infinite scroll already handles the tail).

## R3. Hover/focus preview: lightweight local popover, no new dependency

- **Decision**: `TilePreview` renders as an absolutely positioned panel anchored to the tile, shown on `mouseenter`/`focus-within` and hidden on `mouseleave`/`blur`, managed by local component state. The tile itself is a focusable, clickable element; the preview is also reachable by keyboard focus so its watchlist button is operable without a mouse. On touch devices (no hover), tap navigates directly to the detail page; watchlist-add remains available there (per spec assumption).
- **Rationale**: A dependency like floating-ui is unwarranted for a fixed-size preview on a uniform grid (Principle V). CSS-only `group-hover` can't hold interactive content open reliably for keyboard users; a small state-driven popover covers pointer + keyboard with ~no complexity. Edge-of-viewport flipping is handled with a simple "flip to left/above when tile is in the last column/row region" heuristic rather than measurement libraries.
- **Alternatives considered**: floating-ui/popper (rejected: new dependency for one popover); native `title` tooltip (rejected: can't hold a button, not styleable, poor a11y); modal on click (rejected: click is reserved for navigation, FR-006).

## R4. Tile visual encoding: reuse the app's signal palette, translucent fills

- **Decision**: Tile interior fills follow the existing `SignalBadge` convention — `bg-emerald-500/15 border-emerald-500/30` (bullish), `bg-red-500/15 border-red-500/30` (bearish), `bg-zinc-500/15 border-zinc-500/30` (neutral) — with slightly stronger fill on hover. Ticker text uses the matching signal text color (`text-emerald-400`, etc.) for reinforcement. An unrecognized/missing signal renders a distinct fallback: dashed `border-zinc-700`, no fill, `text-zinc-500` ticker (visibly "wrong", not silently neutral — spec edge case).
- **Rationale**: FR-003 requires consistency with the app's existing signal colors; translucent fills keep white/colored ticker text legible on the dark zinc theme; dashed-border fallback makes bad data conspicuous per the spec's edge-case requirement.
- **Alternatives considered**: Solid saturated fills (rejected: harsh on the dark theme, hurts text contrast); conviction-scaled fill intensity heatmap-style (rejected: spec explicitly encodes conviction as dots, and dual-encoding would confuse the two axes).

## R5. Conviction dots: reuse the existing high/medium/low → 3/2/1 mapping

- **Decision**: The tile renders its own compact dot row (3 slots; filled = level) using the same mapping `ConvictionMeter` uses (`high: 3, medium: 2, low: 1`). Filled dots are neutral (`bg-zinc-200`-ish) rather than sky-blue so they read on top of all three fill colors; unfilled slots are omitted or near-invisible. A missing/unknown conviction renders zero filled dots (spec edge case). The full `ConvictionMeter` (with label) is reused inside the preview, not on the tile face.
- **Rationale**: FR-004 wants 1–3 dots on a tiny tile; `ConvictionMeter`'s fixed sky-400 dots and gap sizing are tuned for cards and clash with colored fills. Duplicating a 3-line mapping is cheaper than parameterizing a shared component used elsewhere (and the mapping constant can be imported/shared via `lib/groupFeed.ts` or types).
- **Alternatives considered**: Extend `ConvictionMeter` with size/color props (rejected: touches a shared component used on other pages for a purely local styling need).

## R6. `AnalysisCard` is deleted; `SkeletonCard` stays

- **Decision**: Delete `frontend/src/components/feed/AnalysisCard.tsx` (grep confirms Feed is its only consumer) and mark its component spec as replaced by `AnalysisTile` (019). Keep `frontend/src/components/shared/SkeletonCard.tsx` untouched — InstitutionalFlow uses it — and add a separate `SkeletonTile` for the grid's loading state (FR-011).
- **Rationale**: Clarification confirmed the grid replaces the card list entirely (no toggle); keeping dead code contradicts Principle V. The card's face content relocates to `TilePreview` (summary snippet, watchlist) and the detail page (flags, institutional/insider chips) per FR-012.
- **Alternatives considered**: Keep AnalysisCard for a future toggle (rejected by clarification).

## R7. Grid layout: CSS Grid `auto-fill` with a fixed minimum tile width

- **Decision**: Tailwind CSS Grid — `grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-2` (exact min width tuned during implementation) on a container widened from the current `max-w-3xl` to `max-w-7xl`. Tiles are near-square via a fixed height (~3.5rem) rather than `aspect-square`, keeping rows tight. Signal groups render as one continuous board with subtle group boundaries (a thin labeled divider row per group), not three separate page sections.
- **Rationale**: `auto-fill/minmax` gives responsive column count for free (FR-008) with zero JS; ~88px min width fits 5–6-character tickers (GOOGL, BRK.B) without truncation (spec edge case: longer tickers step down one font size rather than ellipsize). At 1920px usable width this yields ~14+ columns × 4+ visible rows ≫ 30 tiles (SC-001). Group divider rows keep the "one dense board" feel while making FR-014's grouping legible.
- **Alternatives considered**: Fixed breakpoint column counts (`grid-cols-6 lg:grid-cols-10`…) — rejected: more classes, worse intermediate widths. Masonry/virtualized grid — rejected: uniform small tiles don't need it at this scale (Principle V).

## R8. Accessibility: full state in the accessible name

- **Decision**: Each tile is rendered as a link/button with `aria-label` of the form `"NVDA — bullish, high conviction (3 of 3), analyzed 2 hours ago"`. The preview repeats signal as text (`SignalBadge`) and conviction with label (`ConvictionMeter label`). Dots are `aria-hidden` (decorative; the label carries the value). This satisfies FR-005/SC-006: signal is available as text to screen readers, and for color-blind sighted users the hover preview + distinct fill lightness levels provide non-hue cues.
- **Rationale**: Color-only encoding is explicitly prohibited by the spec; the accessible name plus on-demand text preview is the lowest-complexity conforming design.
- **Alternatives considered**: Per-signal icons/shapes on the tile face (deferred: consumes tile space against the density goal; can be revisited if real-world use shows the preview is insufficient).

## R9. Market flow events: keep `MarketFlowCard`, allow full-width row above the grid

- **Decision**: Pinned market-flow events keep their existing component and content, rendered above the grid spanning the board width; only spacing/margins may be slimmed. The 14-day age-out and hide-when-filtered logic in `Feed.tsx` carries over unchanged.
- **Rationale**: FR-010 requires they remain visible without undermining density; they are ticker-less so they cannot be tiles. Content changes are out of scope.
- **Alternatives considered**: Collapsing them to a one-line banner (deferred: content redesign is a separate concern; spacing tweaks suffice for density).

## R10. Testing approach

- **Decision**: (a) `groupFeed.test.ts` — exhaustive pure-function tests: ordering of groups, newest-first within groups, unknown-signal bucket placement, empty input, page-merge regrouping. (b) `AnalysisTile.test.tsx` — fill class per signal, dot count per conviction (3/2/1), zero dots on missing conviction, fallback style on unknown signal, aria-label content, navigation on click. (c) `TilePreview.test.tsx` — content (signal label, conviction, recency, summary), watchlist mutation fired on button click, shown on focus. (d) `Feed.test.tsx` — grid renders grouped sections, skeleton tiles on load, empty/error states preserved, filters still narrow the board.
- **Rationale**: Principle I requires user-facing frontend logic to ship with Vitest + RTL coverage; the pure grouping helper is the deterministic core of this feature and gets the exhaustive suite.
