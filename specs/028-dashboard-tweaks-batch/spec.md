# Feature Specification: Dashboard Tweaks Batch

**Feature Branch**: `028-dashboard-tweaks-batch`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "I have a few tweeks I want to make. 1 to the On the potroloi summary. When When I use the filter on the page I want that to apply to this summary as well. 2, when I click on a ticker in the portfolio summary I want it to take me to the stock page, for some reason not it is trying but the page is balnk. 3, I want to add another category to the filter, its like/dislike. Then I want to be able to go into a stock and hit a thumps up image next to the ticker for a 'like' or a thumbs down button for a dislike. 4. I want to remove the Pull cost section from the stock page. I don't need that and I don't need to store that infomration in the database eiter. 5. for the sectors page. I want to add a line chart that shows these sector tickers ... XLC, XLY, XLP, XLE, XLF, XLI, XLV, XLB, XLRE, XLK, XLU. On the stocks page, below the tickers I want to show the top traded stocks section (FMP most-actives). 6. I want to add a table called Congress. This will be a tab on the nav bar of the page. I want to view recent senate disclosures and recent house disclosures (FMP senate-latest / house-latest). If I can I want to have a summary section where it shows what stocks are being bought more and if there are any recent high dollar trades. I also would like to be able to filter on this page by stock or by person. If I click on a stock ticker I should be able to navigate to the stock page."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Portfolio Summary Ticker Links Work (Priority: P1)

A user reading the Portfolio Summary panel clicks a ticker mentioned in one of its highlights, expecting to land on that stock's detail page. Today the click appears to navigate but lands on a blank page, so the user loses their place and has to navigate manually.

**Why this priority**: This is an outright broken interaction on an already-shipped panel — every click on a highlighted ticker currently fails. It blocks the core "read the summary, drill into a stock" flow the panel exists for, and is the cheapest of all six tweaks to verify.

**Independent Test**: Open the Stocks page, open the Portfolio Summary panel, click any ticker in its highlights list, and confirm the corresponding stock's detail page renders with content (not a blank page).

**Acceptance Scenarios**:

1. **Given** the Portfolio Summary panel is showing a highlight for ticker "AAPL", **When** the user clicks "AAPL", **Then** the user lands on AAPL's stock detail page and sees its content.
2. **Given** the Portfolio Summary panel is showing highlights for several tickers, **When** the user clicks each ticker in turn, **Then** each click navigates to that specific ticker's own detail page.

---

### User Story 2 - Portfolio Summary Respects the Feed Filter (Priority: P2)

A user applies the feed's filter (e.g., narrows to bearish signals, high conviction, or a specific ticker) to focus on a subset of tracked stocks, and expects the Portfolio Summary panel above/alongside the feed to summarize that same subset rather than the full tracked list.

**Why this priority**: Builds directly on the filter bar and summary panel that already exist; without it, the summary is misleading whenever a filter is active, but the summary is still independently useful even before this is fixed.

**Independent Test**: Apply a feed filter (e.g., ticker filter or signal filter) and confirm the Portfolio Summary panel's content changes to reflect only the filtered stocks; clear the filter and confirm it reverts to summarizing all tracked stocks.

**Acceptance Scenarios**:

1. **Given** no filters are applied, **When** the user views the Portfolio Summary panel, **Then** it summarizes all tracked stocks, as it does today.
2. **Given** the user applies a signal or conviction filter, **When** the Portfolio Summary panel is viewed, **Then** its overview and highlights reflect only stocks matching the active filter.
3. **Given** the user filters to a single ticker, **When** the Portfolio Summary panel is viewed, **Then** it summarizes only that ticker.
4. **Given** an active filter matches zero tracked stocks, **When** the user views the Portfolio Summary panel, **Then** it clearly indicates there is nothing to summarize for the current filter, rather than showing stale or unrelated content.

---

### User Story 3 - Like / Dislike a Stock (Priority: P2)

A user forms an opinion about a stock beyond what the AI analysis says — they want to mark it as one they personally like or dislike, then later filter the feed down to just their liked or disliked stocks.

**Why this priority**: A new, self-contained capability (tagging + filtering) that adds real personal-curation value and is independent of the other five tweaks, but is new functionality rather than a fix to something already shipped.

**Independent Test**: Open a stock's detail page, click the thumbs-up control, confirm it shows as liked; go to the feed filter bar, filter by "liked", and confirm the stock appears; repeat for thumbs-down/disliked.

**Acceptance Scenarios**:

1. **Given** a stock detail page, **When** the user clicks the thumbs-up control next to the ticker, **Then** the stock is marked "liked" and the control visibly reflects that state.
2. **Given** a stock detail page, **When** the user clicks the thumbs-down control next to the ticker, **Then** the stock is marked "disliked" and the control visibly reflects that state.
3. **Given** a stock already marked "liked", **When** the user clicks the thumbs-up control again, **Then** the "liked" mark is cleared.
4. **Given** a stock marked "liked", **When** the user clicks the thumbs-down control, **Then** the stock becomes "disliked" and is no longer "liked" (the two are mutually exclusive).
5. **Given** the feed filter bar, **When** the user selects the "liked" filter, **Then** only stocks marked "liked" are shown; selecting "disliked" instead shows only stocks marked "disliked".

---

### User Story 4 - Congress Trading Disclosures Tab (Priority: P3)

A user wants a dedicated place to see what members of Congress have recently disclosed buying or selling, get a quick read on which tickers are seeing the most buying activity and which recent trades were unusually large, and narrow the list down by a specific stock or lawmaker.

**Why this priority**: The single largest net-new surface in this batch (new nav tab, new page, two new external data feeds, a derived summary), but it's additive — nothing else in the batch depends on it, and it delivers value even without the other five tweaks.

**Independent Test**: Open the new "Congress" tab from the nav bar, confirm recent Senate and House disclosures are listed, apply a ticker filter and a person filter independently, and click a ticker in a disclosure row to confirm it navigates to that stock's detail page.

**Acceptance Scenarios**:

1. **Given** the nav bar, **When** the user clicks "Congress", **Then** they land on a page listing recent Senate and House trade disclosures, each showing the disclosing member, ticker, trade action (buy/sell), and date.
2. **Given** the Congress page, **When** the user filters by a specific ticker, **Then** only disclosures for that ticker are shown.
3. **Given** the Congress page, **When** the user filters by a specific member's name, **Then** only that member's disclosures are shown.
4. **Given** the Congress page, **When** the user views the summary section, **Then** it shows which tickers are seeing the most recent buying activity and calls out any recently disclosed high-dollar trades.
5. **Given** a disclosure row with a valid ticker, **When** the user clicks that ticker, **Then** they land on that stock's detail page.
6. **Given** a disclosure with no associated tradable ticker (e.g., a non-equity or unclassified asset), **When** the user views that row, **Then** it is shown without a broken or misleading navigation link.

---

### User Story 5 - Sector Momentum Charts (Priority: P4)

A user watching the Sectors page wants to visually scan the major sector ETFs at once to quickly spot which ones look like they may be topping out or bottoming, instead of checking each one individually.

**Why this priority**: High analytical value but the most open-ended item in the batch (see clarification below); it depends on new external data but not on any other tweak in this batch.

**Independent Test**: Open the Sectors page and confirm a line chart is present showing recent price history for all 11 listed sector ETFs, allowing visual comparison of their trends.

**Acceptance Scenarios**:

1. **Given** the Sectors page, **When** the user views it, **Then** a line chart displays recent price trends for XLC, XLY, XLP, XLE, XLF, XLI, XLV, XLB, XLRE, XLK, and XLU.
2. **Given** the sector chart, **When** the user looks at an individual sector's line, **Then** they can distinguish it from the others (e.g., by color and label) well enough to judge its trend independently.
3. **Given** one of the 11 sector ETFs has no recent data available, **When** the chart renders, **Then** the chart still renders for the remaining sectors and indicates the missing one rather than failing entirely.

---

### User Story 6 - Top Traded Stocks Section (Priority: P4)

A user on the Stocks page wants to see, at a glance, which stocks are seeing the most trading activity across the market today, independent of their own tracked list.

**Why this priority**: A self-contained, additive read-only panel; useful but lower priority than the fixes and the tagging feature.

**Independent Test**: Open the Stocks page, scroll below the ticker feed, and confirm a "Top Traded Stocks" section lists currently most-active stocks.

**Acceptance Scenarios**:

1. **Given** the Stocks page, **When** the user scrolls below the main ticker feed, **Then** a "Top Traded Stocks" section lists the market's currently most actively traded stocks.
2. **Given** the Top Traded Stocks section, **When** the user clicks a listed ticker, **Then** they land on that stock's detail page.
3. **Given** the most-active data is temporarily unavailable, **When** the user views the section, **Then** it shows a clear unavailable state rather than an empty or broken section.

---

### User Story 7 - Remove Pull Diagnostics from the Stock Page (Priority: P5)

A user viewing a stock's detail page no longer wants to see the "Pull cost" diagnostics panel (per-stage timing/byte breakdown of the last data pull) and doesn't want that diagnostic data collected at all going forward.

**Why this priority**: Pure removal with no new behavior to build — lowest risk and lowest priority, but included because leaving stale diagnostics visible/stored after the other changes ship would be inconsistent with the user's stated intent.

**Independent Test**: Open any stock's detail page and confirm no "Pull cost" section is present anywhere on the page.

**Acceptance Scenarios**:

1. **Given** a stock detail page, **When** the user views it, **Then** no "Pull cost" section is displayed.
2. **Given** a new data pull completes for any ticker after this change ships, **When** the pull's diagnostic detail (per-stage timing/byte breakdown) is considered, **Then** the system does not persist it.

---

### Edge Cases

- What happens when the Portfolio Summary panel has no tracked stocks at all (not just filtered to zero, but genuinely empty)? It should show its existing "no summary yet" state, unaffected by filter state.
- What happens if a user's active filter combination on the feed has no exact equivalent for summarization (e.g., a filter type the summary can't be scoped by)? The summary should degrade to the closest sensible scoping rather than silently ignoring the filter.
- What happens when a user rapidly toggles like/dislike on the same stock? The final state should reflect the last click, with no lingering inconsistent state between the stock page and the filter.
- What happens when a disclosed congressional trade's dollar amount is reported as a range rather than an exact figure (typical for these disclosures)? The system should still be able to identify and surface it as "high dollar" using the disclosed range, rather than requiring an exact amount.
- What happens when the same person appears in disclosures under slightly different name formats? Out of scope for this batch to reconcile identities beyond exact/near-exact name matching; treated as a known limitation.
- What happens when a sector ETF or the most-actives/Congress feeds are rate-limited or temporarily unavailable from the external data source? The affected section should show a clear unavailable/stale state and the rest of the page should keep working.

## Requirements *(mandatory)*

### Functional Requirements

**Portfolio Summary fixes**

- **FR-001**: Clicking a ticker within the Portfolio Summary panel MUST navigate the user to that ticker's stock detail page, and that page MUST render with content.
- **FR-002**: The Portfolio Summary panel MUST scope its overview and highlights to only the stocks currently matching the feed's active filter(s).
- **FR-003**: When no feed filter is active, the Portfolio Summary panel MUST continue to summarize all tracked stocks, matching its current behavior.
- **FR-004**: When the active filter matches zero tracked stocks, the Portfolio Summary panel MUST clearly communicate that there is nothing to summarize for the current filter.

**Like / Dislike**

- **FR-005**: Users MUST be able to mark a stock as "liked" from its stock detail page via a thumbs-up control positioned next to the ticker.
- **FR-006**: Users MUST be able to mark a stock as "disliked" from its stock detail page via a thumbs-down control positioned next to the ticker.
- **FR-007**: A stock's like/dislike state MUST be mutually exclusive (liked, disliked, or neither — never both at once).
- **FR-008**: Clicking the active like or dislike control again MUST clear that state back to neither.
- **FR-009**: The feed filter bar MUST offer a "liked" and a "disliked" filter option, each narrowing the feed to stocks currently in that state.
- **FR-010**: A stock's like/dislike state MUST persist across sessions.

**Congress disclosures**

- **FR-011**: The application's navigation bar MUST include a "Congress" entry linking to a dedicated Congress trading disclosures page.
- **FR-012**: The Congress page MUST display recent Senate trade disclosures and recent House trade disclosures, each showing the disclosing member, ticker, trade action, and date.
- **FR-013**: Users MUST be able to filter the Congress page's disclosures by ticker.
- **FR-014**: Users MUST be able to filter the Congress page's disclosures by disclosing member name.
- **FR-015**: The Congress page MUST include a summary section identifying which tickers currently show the most buying activity among recent disclosures.
- **FR-016**: The Congress page's summary section MUST call out recently disclosed trades of unusually high dollar value.
- **FR-017**: Clicking a ticker within a Congress disclosure row MUST navigate the user to that ticker's stock detail page.
- **FR-018**: A disclosure with no tradable ticker MUST be displayed without offering a broken navigation link.

**Sector momentum**

- **FR-019**: The Sectors page MUST display a line chart showing recent price history for the sector ETFs XLC, XLY, XLP, XLE, XLF, XLI, XLV, XLB, XLRE, XLK, and XLU.
- **FR-020**: Each sector ETF's line on the chart MUST be individually distinguishable (e.g., via color and a legend/label).
- **FR-021**: If one sector ETF's data is unavailable, the chart MUST still render the remaining sectors and indicate the gap rather than failing to render entirely.

**Top traded stocks**

- **FR-022**: The Stocks page MUST display a "Top Traded Stocks" section, positioned below the main ticker feed, listing the market's currently most actively traded stocks.
- **FR-023**: Clicking a ticker within the Top Traded Stocks section MUST navigate the user to that ticker's stock detail page.
- **FR-024**: When most-actives data is unavailable, the section MUST show a clear unavailable state rather than appearing empty or broken.

**Pull diagnostics removal**

- **FR-025**: The stock detail page MUST NOT display a "Pull cost" / pull-diagnostics section.
- **FR-026**: The system MUST NOT persist per-stage pull diagnostic detail (timing/byte breakdown) for new data pulls going forward.

### Key Entities

- **Like/Dislike Tag**: A per-stock, per-user-facing preference state attached to a ticker — one of "liked", "disliked", or unset; drives both the stock-page thumbs controls and the feed filter.
- **Congressional Trade Disclosure**: A disclosed transaction by a member of Congress (Senate or House) — has a disclosing member name, chamber, ticker, trade action (buy/sell), trade/disclosure date, and a disclosed value (typically a range rather than an exact figure).
- **Sector ETF Price Series**: Recent price history for one of the 11 tracked sector ETFs, used to render the sector momentum chart.
- **Top Traded Stock**: A ticker identified by the external data source as among the market's most actively traded for the current period, with enough identifying info (ticker, at minimum) to link to its stock detail page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of ticker clicks within the Portfolio Summary panel land on a populated stock detail page (zero blank-page outcomes).
- **SC-002**: After applying a feed filter, the Portfolio Summary panel's content updates to match the filtered set without requiring a page reload.
- **SC-003**: A user can mark a stock as liked or disliked in a single click from its detail page, and see it reflected in the feed filter results immediately afterward.
- **SC-004**: A user can find recent Senate and House trade disclosures for a specific stock or lawmaker in a few actions, without leaving the Congress page.
- **SC-005**: A user can identify, within seconds of opening the Sectors page, which sector ETFs appear to be trending toward a momentum extreme, by visual inspection of the chart alone.
- **SC-006**: A user can see the market's most actively traded stocks directly on the Stocks page without navigating elsewhere.
- **SC-007**: The stock detail page shows zero references to pull-cost diagnostics, and no new diagnostic records are created after this change ships.

## Assumptions

- "Portfolio summary" refers to the existing cross-stock AI summary panel on the Stocks page (currently labeled "Portfolio Summary"); "the filter on the page" refers to the existing feed filter bar (ticker, signal, conviction).
- The blank-page bug in User Story 1 is a navigation-path mismatch between where the Portfolio Summary panel's ticker links point and where the stock detail route actually lives; the fix is to make them consistent, without changing the stock detail route itself.
- Like/dislike is a single, user-facing preference per ticker (not per-user-account, since this is a single-user local-first product per the project's constitution) and is independent of the AI-generated signal/conviction.
- Congressional trade dollar amounts are disclosed as ranges (a well-known characteristic of these public disclosures), not exact figures; "high dollar trades" in the summary section is judged using the disclosed range.
- This batch's Congress tab is scoped to what was requested here (recent disclosures, a buying/high-dollar summary, ticker/person filters, ticker navigation). It does not include the committee-membership or unusual-legislative-timing analysis described in the pre-existing `specs/005-congressional-trading` spec; that remains a separate, not-yet-implemented feature this batch does not build.
- All new external data pulled for this batch (sector ETF prices, most-actives, Senate/House disclosures) goes through the project's existing cache-first, budget-guarded data access layer rather than being fetched ad hoc, consistent with the project's data-access constraints.
- Removing the Pull cost section stops new diagnostic writes going forward; cleaning up already-stored historical diagnostic records is an implementation-time decision, not a user-facing requirement.
- "Top Traded Stocks" and the Congress disclosures may reference tickers the system isn't already tracking/analyzing; clicking through to such a ticker's stock detail page is still expected to work (consistent with how ticker navigation already behaves elsewhere in the product), even if no AI analysis exists for it yet.

- **Sector chart scope (resolved)**: v1 ships a plain price line chart for the 11 sector ETFs only — no additional indicators (signal overlays, moving averages, RSI, etc.) in this batch. Spotting "bottoming or topping" beyond what's visible from price trend alone is deferred to a later, separate spec once the base chart is in use.
