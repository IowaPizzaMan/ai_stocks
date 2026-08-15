# Feature Specification: Feed Checkerboard Grid

**Feature Branch**: `019-feed-checkerboard-grid`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "I want to redesign the Feed page. I want it to look more like a check board. I want each stock's real estate to be small. I just want to see the ticker and then the Bullish/Bearish/Neutral — I want that to be reflected in the inside color of the container. Then for the conviction levels inside the container just put 1, 2, or 3 dots to represent. I want to be able to see a lot of stocks on my screen to leverage the real estate wisely."

## Clarifications

### Session 2026-08-15

- Q: In what order should the stock tiles appear in the grid? → A: Grouped by signal — bullish tiles together, then neutral, then bearish; newest first within each group.
- Q: Should the new grid completely replace the current large-card feed, or should users be able to switch between grid and list views? → A: Replace entirely — the grid is the only Feed layout; full detail lives on the stock detail page.
- Q: What should hovering over a tile show, and where should the "add to watchlist" action live? → A: Rich hover preview — signal label, conviction, recency, summary snippet, and an add-to-watchlist button.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scan many stocks at a glance (Priority: P1)

As a trader opening the Feed page, I see a dense checkerboard-style grid of small tiles — one tile per stock. Each tile shows only the ticker symbol, a fill color that communicates the analysis signal (bullish, bearish, or neutral), and 1–3 dots representing conviction level. I can absorb the state of my whole analyzed universe in a single screen instead of scrolling through a handful of large cards.

**Why this priority**: This is the core of the redesign — maximizing how many stocks are visible at once is the stated goal. Without the compact tile grid, nothing else in this feature matters.

**Independent Test**: Load the Feed page with 30+ analyzed stocks and confirm that a full desktop screen shows dozens of tiles, each displaying exactly a ticker, a signal color, and conviction dots — with no scrolling required to see substantially more stocks than the current card layout shows.

**Acceptance Scenarios**:

1. **Given** 40 stocks have completed analyses, **When** the user opens the Feed page on a typical desktop screen, **Then** at least 30 tiles are visible without scrolling, arranged in a multi-column grid grouped by signal (bullish, then neutral, then bearish; newest first within each group).
2. **Given** a stock's latest analysis is bullish, **When** its tile renders, **Then** the tile's interior fill color is the bullish color (green family); bearish renders in the red family and neutral in a distinct muted/gray tone.
3. **Given** a stock's analysis has conviction level 2, **When** its tile renders, **Then** exactly 2 dots appear inside the tile (1 dot for level 1, 3 dots for level 3).
4. **Given** the grid is displayed, **When** the user views any tile, **Then** the only text on the tile face is the ticker symbol — no summary text, sector labels, or timestamps consume tile space.
5. **Given** the user is on a narrower screen, **When** the Feed loads, **Then** the grid reflows to fewer columns while tiles keep their compact size and remain readable and tappable.

---

### User Story 2 - Drill into a stock from a tile (Priority: P2)

The compact tiles intentionally omit detail, so when something catches my eye (a high-conviction bullish tile, say), I click or tap the tile and land on that stock's detail page where the full analysis lives.

**Why this priority**: The grid trades detail for density; the click-through is what makes that trade safe. It preserves access to everything the old large cards displayed.

**Independent Test**: Click any tile and verify navigation to that stock's detail page.

**Acceptance Scenarios**:

1. **Given** the grid is displayed, **When** the user clicks/taps a tile, **Then** they navigate to that stock's detail page.
2. **Given** a user hovers over a tile (on devices with a pointer), **When** the hover state activates, **Then** a rich preview is revealed without navigating — signal label, conviction, analysis recency, the summary snippet, and an add-to-watchlist button — so the user can triage and act before committing a click.

---

### User Story 3 - Filter the grid (Priority: P3)

I still want to narrow the board using the existing filters (ticker, signal, sector, conviction) — e.g., show me only bearish tiles, or only one sector — and have the grid update to show just the matching tiles.

**Why this priority**: Filtering already exists on the Feed and remains valuable, but the grid is useful without it; this story preserves current behavior in the new layout.

**Independent Test**: Apply each existing filter and confirm the grid shows only matching tiles.

**Acceptance Scenarios**:

1. **Given** the grid shows mixed signals, **When** the user filters by signal "bearish", **Then** only bearish-colored tiles remain.
2. **Given** a filter is active, **When** the user clears it, **Then** the full grid returns.
3. **Given** no filters are active, **When** market-wide flow events exist (which have no ticker), **Then** they remain visible above the grid in a compact form rather than being lost in the redesign.

---

### Edge Cases

- **Long tickers** (e.g., 5-character symbols like GOOGL, or symbols with dots like BRK.B): the ticker must fit the tile without truncation that makes it ambiguous.
- **Missing or unrecognized signal value**: the tile renders in a clearly distinct fallback style (not silently shown as neutral) so bad data is visible.
- **Missing conviction**: the tile renders with no dots rather than a misleading count.
- **Color alone must not carry the signal**: color-blind users must still be able to distinguish bullish/bearish/neutral (e.g., via accessible names, hover preview, or a secondary visual cue).
- **Empty feed**: the existing "No analyses yet" guidance still appears when there are no analyses.
- **Large universes**: when more stocks exist than fit on one screen, additional tiles load as the user scrolls (current infinite-scroll behavior carries over to the grid).
- **Duplicate analyses for one stock**: exactly one tile per stock appears, reflecting its most recent analysis (existing feed dedupe behavior is preserved).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Feed page MUST display analyses as a multi-column grid of compact, uniformly sized tiles ("checkerboard" layout), replacing the current single-column large-card list.
- **FR-002**: Each tile MUST display the stock's ticker symbol as its primary (and only) text on the tile face.
- **FR-003**: Each tile's interior fill color MUST encode the analysis signal, with three visually distinct colors for bullish (green family), bearish (red family), and neutral (muted/gray), consistent with the signal colors used elsewhere in the app.
- **FR-004**: Each tile MUST display the conviction level as 1, 2, or 3 dots inside the tile; an analysis with no conviction value shows no dots.
- **FR-005**: Signal and conviction MUST be perceivable without relying on color alone (e.g., accessible labels announced to assistive technology and/or a hover preview stating "Bullish · conviction 2/3").
- **FR-006**: Clicking or tapping a tile MUST navigate to that stock's detail page, preserving the current card click-through behavior.
- **FR-007**: The existing feed filters (ticker, signal, sector, conviction) MUST continue to work, filtering which tiles appear in the grid.
- **FR-008**: The grid MUST be responsive: more columns on wide screens, fewer on narrow screens, with tiles remaining legible and comfortably tappable on touch devices.
- **FR-009**: The feed MUST continue to show exactly one entry (tile) per stock, reflecting its latest analysis.
- **FR-010**: Market-wide flow event cards (which have no ticker) MUST remain visible above the grid when no filters are active, in a form that does not undermine the density goal.
- **FR-011**: Loading, error, and empty states MUST be preserved, with the loading state visually matching the new grid (e.g., placeholder tiles rather than large placeholder cards).
- **FR-012**: Each tile MUST offer a rich hover preview (on pointer devices) showing the signal label, conviction, analysis recency, the summary snippet, and an add-to-watchlist action — none of which occupy space on the tile face. Remaining card detail (flags, institutional/insider activity) stays available on the stock detail page.
- **FR-013**: Additional tiles MUST load automatically as the user scrolls past the currently loaded set (infinite scroll parity with the current feed).
- **FR-014**: Tiles MUST be grouped by signal — bullish first, then neutral, then bearish — with the most recently analyzed stocks first within each group. Tiles loaded by scrolling merge into their signal group rather than appending to the bottom of the board.

### Key Entities

- **Analysis Tile**: The compact visual unit of the grid. Derived from a stock's latest analysis: ticker symbol, signal (bullish / bearish / neutral), conviction level (1–3, optional), and analysis timestamp (used for the hover preview, not the tile face).
- **Market Flow Event**: A market-wide (ticker-less) event pinned above the grid; unchanged in meaning, compacted in presentation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A typical desktop screen displays at least 30 stock tiles without scrolling — roughly a 10× improvement over the current layout (~3 cards per screen).
- **SC-002**: A user can state the signal (bullish/bearish/neutral) of any visible stock within 2 seconds of looking at its tile, without reading any text other than the ticker.
- **SC-003**: A user can state the conviction level of any visible stock without clicking, hovering, or navigating.
- **SC-004**: Reaching a stock's full analysis takes exactly one click/tap from the grid.
- **SC-005**: All information previously available on the feed (summaries, flags, activity notes, watchlist add) remains reachable within one interaction (hover or click) — nothing is lost, only relocated.
- **SC-006**: Signal states are distinguishable by users with common color-vision deficiencies (verified via accessible names or a non-color cue).

## Assumptions

- "Check board" is interpreted as a **checkerboard/dashboard-style dense grid** of uniform tiles, in the spirit of a market heatmap — not an actual alternating two-color checkerboard pattern.
- The grid **replaces** the current large-card feed layout entirely (confirmed in clarification — no list/grid toggle); full analysis detail lives on the stock detail page.
- "Conviction levels" map to the existing 1–3 conviction scale already produced by analyses and shown today by the conviction meter; no new scale is introduced.
- Signal colors follow the app's existing convention (green = bullish, red = bearish, gray/muted = neutral) rather than introducing a new palette.
- The add-to-watchlist action, currently a button on each card, moves off the tile face into the hover preview (confirmed in clarification); on touch devices without hover, it remains available via the stock detail page.
- Market flow events stay pinned above the grid (their current placement) since they are ticker-less and cannot be tiles; they may be visually slimmed but their content is unchanged.
- Existing feed behaviors not visible in the layout — one-entry-per-stock dedupe, filter state in the URL, fetch-on-navigation (no polling), infinite scroll — carry over unchanged.
- Mobile/touch support means the grid reflows to fewer columns and tiles stay tappable; a dedicated mobile design is out of scope.
