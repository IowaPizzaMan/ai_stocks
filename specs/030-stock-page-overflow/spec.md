# Feature Specification: Remove Stock Page Horizontal Overflow

**Feature Branch**: `030-stock-page-overflow`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "remove the overflow from the stock page."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No page-wide horizontal scroll on narrow screens (Priority: P1)

As a user viewing a stock's detail page on a phone or narrow browser window, I don't want the whole page to scroll sideways, so I can read the ticker header, tabs, and analysis content without side-scrolling to see content that should just be on screen.

**Why this priority**: This is the core complaint — the page currently forces horizontal scrolling at common phone widths, which makes the page feel broken and hides content off-screen. Fixing it is the entire point of the feature.

**Independent Test**: Load `/stock/:ticker` at a 390px-wide viewport (a common phone width) and confirm there is no horizontal scrollbar and no content is clipped or pushed off the right edge of the screen.

**Acceptance Scenarios**:

1. **Given** a phone-width viewport (390px), **When** a user opens a stock's detail page, **Then** the page has no horizontal scrollbar and every header control (back link, ticker, action buttons) is reachable without scrolling sideways.
2. **Given** a phone-width viewport, **When** a user switches between tabs (Charts, Overview, Technicals, etc.), **Then** the tab bar wraps to additional lines instead of forcing the page wider than the viewport.
3. **Given** a stock with a long company name, **When** its detail page renders at a narrow viewport, **Then** the name wraps or truncates instead of pushing the header wider than the screen.

---

### User Story 2 - Layout reflows smoothly across window sizes (Priority: P2)

As a user resizing their browser window (e.g., from a wide desktop window down to a tablet or split-screen width), I want the stock page's layout to reflow — wrapping or stacking elements — rather than staying a fixed width and forcing the page to scroll horizontally.

**Why this priority**: Users don't only hit narrow widths on phones; resizing a desktop window or using split-screen/tiled windows should behave the same way. This confirms the fix is a genuine responsive layout fix rather than a single hardcoded breakpoint.

**Independent Test**: Load the stock detail page at a wide desktop width, then progressively shrink the browser window down to 320px, confirming no horizontal scrollbar appears at any point.

**Acceptance Scenarios**:

1. **Given** the stock detail page is open at a desktop width, **When** the browser window is narrowed continuously down to 320px, **Then** no horizontal page scrollbar ever appears.
2. **Given** the page is at a narrow width, **When** the window is widened back to desktop size, **Then** the layout returns to its normal desktop appearance with no leftover overflow or clipping.

---

### Edge Cases

- What happens with an unusually long ticker or company name? It must wrap or truncate rather than widening the page.
- What happens with panels that legitimately contain wide content (e.g., data tables in the Institutional or Technicals tabs)? They must remain usable via their own internal horizontal scroll, without causing the outer page to scroll.
- What happens at the smallest common phone width (320px)? No horizontal page scroll should appear there either.
- What happens when the Watchlist sidebar has many entries? That should only ever produce vertical scrolling within the sidebar, never horizontal page overflow.
- What happens at very wide desktop viewports? The existing centered, max-width content layout must be unaffected (no regression).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The stock detail page MUST NOT produce page-level horizontal scrolling at any viewport width from 320px up through common desktop widths.
- **FR-002**: Layout elements on the stock detail page (header controls, ticker/company name, tab bar) MUST wrap or stack at narrow widths instead of forcing the page wider than the viewport.
- **FR-003**: The shared page shell (top navigation, watchlist sidebar, and main content area) that the stock detail page renders inside MUST allow the main content area to shrink to fit the viewport, rather than being forced wide by fixed-width neighboring elements.
- **FR-004**: Content that legitimately requires horizontal scrolling (e.g., wide data tables) MUST continue to scroll only within its own bounded container, never causing the whole page to scroll.
- **FR-005**: Long text values (company names, tickers, labels) on the stock detail page MUST wrap or truncate rather than forcing their containers to overflow.
- **FR-006**: The fix MUST be verified on the stock detail page and MUST NOT introduce horizontal overflow regressions on other pages that share the same page shell.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At a 390px-wide viewport (a common phone width), the stock detail page shows zero horizontal scrollbar and 100% of header controls remain reachable without side-scrolling.
- **SC-002**: At a 320px-wide viewport (smallest common phone width), the stock detail page shows zero horizontal scrollbar.
- **SC-003**: Continuously resizing the browser window between 320px and 1920px while on the stock detail page produces no horizontal page scroll at any intermediate width.
- **SC-004**: Existing intentionally-scrollable elements (wide data tables in other tabs) retain their own scroll behavior after the fix, with no loss of functionality.
- **SC-005**: No other page that shares the same page shell (e.g., the main feed page) regresses to having new horizontal overflow as a result of this fix.

## Assumptions

- This matches the previously logged issue that the shared page shell forces horizontal scrolling at phone widths because the fixed-width watchlist sidebar never shrinks and the main content area isn't allowed to shrink below its content's natural width. Since that shell is shared by every page, the underlying fix happens at the shell level, while this feature's acceptance is scored specifically against the stock detail page.
- Supported minimum viewport width is 320px, consistent with standard responsive web practice.
- The watchlist sidebar remains part of the layout; how exactly it adapts at narrow widths (shrinking, stacking above content, or hiding below a breakpoint) is left as an implementation decision, as long as it doesn't reintroduce page-level horizontal overflow.
- No new navigation pattern (e.g., a hamburger/drawer menu) is required unless it turns out to be necessary to eliminate the overflow.
- Tables and panels that already scroll horizontally within their own container on purpose are working as intended and are not part of this fix — only page-level (outer) horizontal scrolling is in scope.
