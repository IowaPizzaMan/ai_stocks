# Feature Specification: Stocks Page News Tab and Cross-Stock AI Summary

**Feature Branch**: `027-stocks-news-tab-ai-summary`

**Created**: 2026-08-21

**Status**: Draft

**Input**: User description: "I want to move the news section in the stocks page to its own tab called News. I don't want the infinate scroll, just make it so there is an overflow and the main page has no scroll. I want to add a AI summary to the Stocks page, I want to be able to click a button to rerun the AI analysis, but basically I want the AI to summarize all the AI summary sections for the stocks I have and provide me some guidance on what to look at."

## Overview

The Stocks page today has three things stacked on one continuously growing view: a filter bar, a grid of stock analysis tiles that fetches more tiles automatically as the user scrolls the browser window, and a market-wide news list pinned below the grid (added in [spec 022](../022-market-news-feed/spec.md), already capped at 20 articles with no infinite scroll of its own). This feature reorganizes that page into a tabbed layout — the grid stays on the default view and the news list moves to its own "News" tab — replaces the grid's auto-fetch-on-scroll behavior with a bounded, internally scrollable panel so the page itself never grows past the viewport, and adds a new cross-stock AI summary panel that synthesizes every tracked stock's existing AI analysis into a single overview with guidance on what deserves attention, refreshable on demand.

## Clarifications

### Session 2026-08-21

- Q: Should the cross-stock AI summary reflect every tracked stock regardless of the grid's active filter, or only the stocks currently matching that filter? → A: Always all tracked stocks with a completed analysis, independent of the grid's filter bar (matches the market news section's existing filter-independence, spec 022 FR-001b).
- Q: When there are too many stocks with completed analyses to fit into one synthesis pass, which stocks should the system prioritize including? → A: Highest conviction / strongest signal stocks first.
- Q: On the default Stocks-page tab, where should the AI summary panel sit relative to the stock grid (the tickers)? → A: Side-by-side — the stock grid and the AI summary panel render as two columns rather than stacked, with the grid in the primary/left position.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dedicated News Tab (Priority: P1)

A user on the Stocks page no longer sees the market-wide news list mixed in below the stock grid. Instead, the page has a News tab; selecting it shows the same market-wide headlines (most recent 20, newest first, ticker-linked, no auto-loading) that used to sit at the bottom of the page. The default tab shows only the filter bar and the stock grid.

**Why this priority**: This is the explicit, primary reorganization the user asked for and is a prerequisite for the "main page has no scroll" story below (removing news from the default view is what makes a bounded layout feasible).

**Independent Test**: Open the Stocks page. Confirm the default view shows the filter bar and grid with no news list present. Select the News tab and confirm the same market news content (headlines, sources, timestamps, ticker links, article links, capped at 20, no further loading on scroll) appears there.

**Acceptance Scenarios**:

1. **Given** the Stocks page, **When** it loads with no tab specified, **Then** the default tab shows the filter bar and stock grid, and no market news list appears on that view.
2. **Given** the Stocks page, **When** the user selects the News tab, **Then** the market-wide news list appears with the same content and behavior it had before the move (up to 20 most recent articles, ticker links, external article links, no infinite scroll).
3. **Given** a shareable link to the News tab, **When** the page is opened from that link, **Then** the News tab is the one shown active.

---

### User Story 2 - Bounded Grid, No Auto-Scroll Fetching (Priority: P1)

The stock grid stops loading more tiles automatically as the user scrolls the browser window. Instead, the page shell (filter bar, tab bar) stays fixed on screen, the grid renders inside its own bounded area, and that area scrolls independently (a normal overflow/scrollbar) when it has more tiles than fit. Loading additional analyses beyond what's already shown requires an explicit action from the user rather than happening automatically as they scroll.

**Why this priority**: Directly requested ("I don't want the infinite scroll... the main page has no scroll") and is a foundational layout change alongside User Story 1.

**Independent Test**: Open the Stocks page with enough analyses to overflow one screen. Confirm the browser window itself does not grow or need scrolling to reveal the filter bar and tab bar. Confirm scrolling inside the grid area only moves the grid's own content, and that no new analyses are fetched until the user takes an explicit action to load more.

**Acceptance Scenarios**:

1. **Given** more tracked stocks than fit on one screen, **When** the Stocks page renders, **Then** the browser window/page itself does not need to scroll — the filter bar and tab bar remain visible without scrolling the page.
2. **Given** the grid area has more tiles than fit in its bounded space, **When** the user scrolls within that area, **Then** only the grid's own content scrolls (a contained overflow/scrollbar), leaving the rest of the page fixed.
3. **Given** the initial set of analysis tiles is showing, **When** the user scrolls within the grid area, **Then** no additional tiles load automatically.
4. **Given** more tiles exist beyond what's shown, **When** the user takes an explicit action to load more (e.g., a "Load more" control), **Then** the additional tiles append within the same bounded, scrollable grid area.

---

### User Story 3 - Cross-Stock AI Summary with Manual Regeneration (Priority: P2)

The default Stocks page view includes a summary panel that reads across every tracked stock's already-generated AI analysis and produces one synthesized overview: what stands out, and what the user should look at next. The panel renders alongside the stock grid as a second column (not stacked above or below it), with the grid in the primary/left position. A button lets the user regenerate this synthesis on demand; the most recently generated summary persists on the page (with a last-generated timestamp) until the user regenerates it again.

**Why this priority**: A new capability, valuable but independent of the tab/layout reorganization in User Stories 1–2.

**Independent Test**: Open the Stocks page with at least one analyzed stock. Confirm a summary panel shows synthesized, stock-specific guidance and a last-generated timestamp. Click the regenerate control and confirm the panel shows an in-progress state, then updates with a fresh summary and timestamp.

**Acceptance Scenarios**:

1. **Given** one or more tracked stocks have a completed AI analysis, **When** the user opens the Stocks page, **Then** the summary panel shows synthesized guidance drawn from those stocks' AI summaries, plus when it was last generated.
2. **Given** no tracked stock has a completed AI analysis yet, **When** the user opens the Stocks page, **Then** the summary panel shows a clear empty/prompt state instead of an error or blank space.
3. **Given** a summary was previously generated, **When** the user clicks the regenerate control, **Then** the panel shows a busy/in-progress state, then replaces its content with a fresh synthesis of the currently stored per-stock AI summaries and an updated timestamp.
4. **Given** a regeneration is triggered, **When** it fails (provider error, budget exhausted, etc.), **Then** the previously generated summary remains visible, marked as stale, rather than the panel going blank or showing a hard error.
5. **Given** some tracked stocks have no AI summary yet, **When** the cross-stock summary is generated, **Then** those stocks are excluded from the synthesis without causing the generation to fail.
6. **Given** the grid's filter bar is set to narrow the visible tiles (e.g., a single sector or signal), **When** the user views the summary panel, **Then** it still reflects all tracked stocks with a completed analysis, not just the filtered subset, and does not change or recompute when the filter changes.

---

### Edge Cases

- Very large number of tracked stocks: the system caps how many stocks' AI summaries feed a single synthesis pass (to keep cost and latency reasonable), prioritizing the highest-conviction / strongest-signal stocks, and indicates that not all tracked stocks were included, rather than failing or taking an unbounded amount of time.
- User clicks regenerate while a previous regeneration is still running: the control shows an in-progress state and does not queue a second, overlapping regeneration.
- A tracked stock's own AI summary is old (that stock hasn't been re-pulled recently): it is still included in the synthesis using its most recently stored content; the cross-stock summary does not silently drop stale-but-present data.
- Stocks page opened via a deep link to an unrecognized tab: falls back to the default (grid) tab, consistent with how the per-ticker detail page handles unknown tab anchors.
- Zero tracked stocks at all (brand-new install): both the grid's empty state and the summary panel's empty state render without errors.

## Requirements *(mandatory)*

### Functional Requirements

**News relocation (US1)**

- **FR-001**: The Stocks page MUST present the market-wide news content in a dedicated "News" tab, not on the default view.
- **FR-002**: The relocated market news content and behavior (most recent 20 articles newest-first, ticker links, external article links, no automatic loading of further articles, independence from the grid's filters) MUST remain unchanged by the move.
- **FR-003**: The Stocks page MUST default to the tab containing the filter bar and stock grid when no tab is specified.

**Bounded layout, no auto-scroll fetching (US2)**

- **FR-004**: The Stocks page's page-level shell (filter bar, tab bar) MUST remain visible without the user having to scroll the browser window/page itself, regardless of how many stock tiles or news articles are loaded.
- **FR-005**: The stock grid MUST render within a bounded area that scrolls independently (its own overflow) when its content exceeds the available space.
- **FR-006**: The stock grid MUST NOT fetch additional analyses automatically in response to the user scrolling; fetching further results MUST require an explicit user action.

**Cross-stock AI summary (US3)**

- **FR-007**: The Stocks page's default tab MUST include a summary panel that synthesizes the existing AI summary content of every tracked stock with a completed analysis into one overview with specific guidance on what to look at.
- **FR-007a**: The synthesis input MUST always be every tracked stock with a completed analysis, independent of the grid's active filter (ticker/signal/sector/conviction) — changing the filter MUST NOT change which stocks feed the summary or trigger a recomputation.
- **FR-007b**: On the default tab, the summary panel MUST render alongside the stock grid as a second column (side-by-side layout), not stacked above or below it, with the stock grid in the primary/left position.
- **FR-008**: The summary panel MUST include a control that lets the user manually regenerate the synthesis on demand.
- **FR-009**: Regenerating the synthesis MUST use each tracked stock's most recently stored AI summary content and MUST NOT trigger new per-stock analysis pulls.
- **FR-010**: The system MUST persist the most recently generated cross-stock summary and its generation timestamp so it remains visible across page visits until the user regenerates it again.
- **FR-011**: When no tracked stock has a completed AI analysis, the summary panel MUST show a clear empty state rather than an error.
- **FR-012**: When a regeneration fails, the summary panel MUST continue showing the last successfully generated summary, marked as stale, rather than hiding it behind an error state.
- **FR-013**: Tracked stocks without a completed AI analysis MUST be excluded from the synthesis input without causing regeneration to fail.
- **FR-014**: If the number of stocks with a completed AI analysis exceeds a practical limit for one synthesis pass, the system MUST cap the input set by prioritizing the highest-conviction / strongest-signal stocks first, and MUST indicate that not all tracked stocks were included.
- **FR-015**: Regenerating the summary MUST run as a background operation consistent with the app's existing analysis-queue pattern — the user sees a busy/in-progress indicator while it runs and can continue using the rest of the page.

### Key Entities

- **Cross-Stock AI Summary**: A synthesized narrative and guidance derived from multiple tracked stocks' individually generated AI summaries — includes a generated-at timestamp, the set/count of stocks it covers, and a status (fresh, stale, in-progress, or error).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can locate and view the market-wide news list via the News tab, and it no longer appears on the default Stocks view.
- **SC-002**: On a Stocks page populated with enough tracked stocks to overflow one screen, the browser window's own scroll height never grows with the number of results — verifiable by checking the page shell stays fixed while only the grid area scrolls.
- **SC-003**: Scrolling within the grid area never by itself triggers a new network fetch; loading more results always follows an explicit user action, verifiable across repeated scroll attempts.
- **SC-004**: A user with at least one analyzed stock can read a cross-stock summary containing guidance that references specific tracked stocks (not generic boilerplate) without taking any action beyond opening the page.
- **SC-005**: Clicking regenerate produces a visibly updated summary (new timestamp, refreshed content) without the user navigating away from or reloading the page.
- **SC-006**: If a regeneration attempt fails, the previously shown summary content remains visible 100% of the time — never a blank or broken panel.

## Assumptions

- **"The stocks I have" means every ticker with a stored analysis** — the same set that populates the Stocks-page grid today. The app's separate Watchlist feature is currently an unimplemented placeholder page, so it is not what this phrase refers to.
- **The synthesis reuses already-stored per-ticker AI Summary content** (the News Stance / Technical / Fundamental / Market Timing narratives from [spec 021](../021-stock-page-redesign/spec.md)) rather than re-running any stock's own analysis; "rerun the AI analysis" refers to rerunning the cross-stock synthesis step only.
- **Regeneration follows the app's existing async job pattern** (comparable to Pull / Full Refresh elsewhere in the app): the user triggers it, a busy state shows while it processes, and the result appears once ready, using the same queue/status mechanism already in place rather than introducing new page-level polling.
- **A cap protects the synthesis from unbounded scale**: if feeding every tracked stock's AI summary into one synthesis pass isn't practical, the system falls back to a capped subset prioritizing the highest-conviction / strongest-signal stocks (clarified 2026-08-21), mirroring existing cost-conscious caps elsewhere in the app (e.g., the 15-article summarization cap in spec 021, the 20-article cap in spec 022) rather than failing outright. The exact numeric cap is a planning-phase decision, not fixed by this spec.
- **The Stocks page gains its own lightweight tab set** (default grid view / News), independent of and not to be confused with the per-ticker stock detail page's own tab set, which already includes its own News tab scoped to a single ticker.
- **Grid pagination, once decoupled from scroll-triggered auto-fetch, uses an explicit "load more" control** within the bounded/scrollable grid area — mirroring the pattern already used by the per-ticker detail page's News tab ("Show N more" button), rather than requiring all analyses to load in a single request.
- **Market news content itself is unchanged** (20-article cap, ~60-minute refresh reuse, no permanent history — spec 022); only its page location moves.
