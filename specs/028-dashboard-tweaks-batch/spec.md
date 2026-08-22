# Feature Specification: Dashboard Tweaks Batch

**Feature Branch**: `028-dashboard-tweaks-batch`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "I have a few tweeks I want to make. 1 to the On the potroloi summary. When When I use the filter on the page I want that to apply to this summary as well. 2, when I click on a ticker in the portfolio summary I want it to take me to the stock page, for some reason not it is trying but the page is balnk. 3, I want to add another category to the filter, its like/dislike. Then I want to be able to go into a stock and hit a thumps up image next to the ticker for a 'like' or a thumbs down button for a dislike. 4. I want to remove the Pull cost section from the stock page. I don't need that and I don't need to store that infomration in the database eiter. 5. for the sectors page. I want to add a line chart that shows these sector tickers ... XLC, XLY, XLP, XLE, XLF, XLI, XLV, XLB, XLRE, XLK, XLU. On the stocks page, below the tickers I want to show the top traded stocks section (FMP most-actives). 6. I want to add a table called Congress. This will be a tab on the nav bar of the page. I want to view recent senate disclosures and recent house disclosures (FMP senate-latest / house-latest). If I can I want to have a summary section where it shows what stocks are being bought more and if there are any recent high dollar trades. I also would like to be able to filter on this page by stock or by person. If I click on a stock ticker I should be able to navigate to the stock page."

## Clarifications

### Session 2026-08-22

- Q: When the feed filter is applied, should the Portfolio Summary's AI-written paragraph be re-written for the filtered set, or should only its ticker highlights narrow? → A: Narrow the highlight list only; the AI paragraph stays unchanged and continues to describe all tracked stocks (no LLM re-run on filter change).
- Q: Should the sector chart plot actual dollar price or percentage change from a common baseline, and should the time window be switchable? → A: Percentage change from the start of the selected window, with a window selector offering 1M / 3M / 6M / 1Y.
- Q: What window and rules define the Congress summary's "most bought" tickers and "high dollar" trades? → A: A rolling 90-day window; "most bought" ranks tickers by the number of buy disclosures; "high dollar" flags any disclosure whose reported amount bracket reaches $100,001 or above.
- Q: Should the thumbs-up/down controls work on any ticker, including untracked ones reached from the Congress or Top Traded lists? → A: No — the controls appear only for stocks the system already tracks; they are hidden for untracked tickers.
- Q: Should existing pull-diagnostics data be dropped outright or left to expire on its own? → A: Dropped outright — stop writing, delete the stored records, and remove the collection and its indexes in the same change.

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

A user applies the feed's filter (e.g., narrows to bearish signals, high conviction, or a specific ticker) to focus on a subset of tracked stocks, and expects the Portfolio Summary panel's ticker highlights to narrow to that same subset rather than continuing to list stocks the filter excluded.

**Why this priority**: Builds directly on the filter bar and summary panel that already exist; without it, the highlights contradict the filtered feed below them, but the summary is still independently useful even before this is fixed.

**Independent Test**: Apply a feed filter (e.g., ticker filter or signal filter) and confirm the Portfolio Summary panel's highlights narrow to only the filtered stocks; clear the filter and confirm all highlights return.

**Acceptance Scenarios**:

1. **Given** no filters are applied, **When** the user views the Portfolio Summary panel, **Then** it shows all of its highlights, as it does today.
2. **Given** the user applies a signal or conviction filter, **When** the Portfolio Summary panel is viewed, **Then** its highlights list shows only stocks matching the active filter.
3. **Given** the user filters to a single ticker, **When** the Portfolio Summary panel is viewed, **Then** its highlights show only that ticker (if that ticker is among the highlights).
4. **Given** any filter is active, **When** the user views the Portfolio Summary panel, **Then** the AI-written overview paragraph is unchanged and is visibly labeled as describing all tracked stocks, so it is not misread as describing the filtered subset.
5. **Given** an active filter matches none of the panel's highlights, **When** the user views the panel, **Then** the highlights area clearly indicates no highlighted stocks match the current filter, rather than showing unrelated highlights.

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
6. **Given** a ticker the system does not track (e.g., opened from the Congress or Top Traded list), **When** the user views its detail page, **Then** no thumbs-up or thumbs-down control is shown.
7. **Given** an untracked ticker the user then pulls for the first time, **When** the analysis completes and the stock becomes tracked, **Then** the thumbs controls appear on its detail page.

---

### User Story 4 - Congress Trading Disclosures Tab (Priority: P3)

A user wants a dedicated place to see what members of Congress have recently disclosed buying or selling, get a quick read on which tickers are seeing the most buying activity and which recent trades were unusually large, and narrow the list down by a specific stock or lawmaker.

**Why this priority**: The single largest net-new surface in this batch (new nav tab, new page, two new external data feeds, a derived summary), but it's additive — nothing else in the batch depends on it, and it delivers value even without the other five tweaks.

**Independent Test**: Open the new "Congress" tab from the nav bar, confirm recent Senate and House disclosures are listed, apply a ticker filter and a person filter independently, and click a ticker in a disclosure row to confirm it navigates to that stock's detail page.

**Acceptance Scenarios**:

1. **Given** the nav bar, **When** the user clicks "Congress", **Then** they land on a page listing recent Senate and House trade disclosures, each showing the disclosing member, ticker, trade action (buy/sell), and date.
2. **Given** the Congress page, **When** the user filters by a specific ticker, **Then** only disclosures for that ticker are shown.
3. **Given** the Congress page, **When** the user filters by a specific member's name, **Then** only that member's disclosures are shown.
4. **Given** the Congress page, **When** the user views the summary section, **Then** it ranks tickers by number of buy disclosures over the last 90 days and calls out any disclosure in that window whose amount bracket reaches $100,001 or above.
5. **Given** no disclosure in the last 90 days reaches the $100,001 bracket, **When** the user views the summary section, **Then** it states that plainly rather than showing lower-value trades in the high-dollar slot.
6. **Given** a disclosure row with a valid ticker, **When** the user clicks that ticker, **Then** they land on that stock's detail page.
7. **Given** a disclosure with no associated tradable ticker (e.g., a non-equity or unclassified asset), **When** the user views that row, **Then** it is shown without a broken or misleading navigation link.

---

### User Story 5 - Sector Momentum Charts (Priority: P4)

A user watching the Sectors page wants to visually scan the major sector ETFs at once to quickly spot which ones look like they may be topping out or bottoming, instead of checking each one individually.

**Why this priority**: High analytical value but the most open-ended item in the batch (see clarification below); it depends on new external data but not on any other tweak in this batch.

**Independent Test**: Open the Sectors page and confirm a line chart is present comparing all 11 listed sector ETFs on a common percentage-change scale, and that changing the time window redraws the chart over that period.

**Acceptance Scenarios**:

1. **Given** the Sectors page, **When** the user views it, **Then** a line chart displays XLC, XLY, XLP, XLE, XLF, XLI, XLV, XLB, XLRE, XLK, and XLU, each plotted as percentage change from the start of the selected window so all 11 share a common baseline.
2. **Given** the sector chart, **When** the user looks at an individual sector's line, **Then** they can distinguish it from the others (e.g., by color and label) well enough to judge its trend independently.
3. **Given** the sector chart, **When** the user switches the time window between 1 month, 3 months, 6 months, and 1 year, **Then** the chart redraws over that period with every line rebased to that window's starting point.
4. **Given** one of the 11 sector ETFs has no data available for the selected window, **When** the chart renders, **Then** the chart still renders for the remaining sectors and indicates the missing one rather than failing entirely.

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
3. **Given** the change has been applied, **When** the database is inspected, **Then** the pull-diagnostics collection and its indexes no longer exist.
4. **Given** the change has been applied, **When** a ticker is pulled, **Then** the pull completes and produces the same analysis it would have before, unaffected by the removal.

---

### Edge Cases

- What happens when the Portfolio Summary panel has no tracked stocks at all (not just filtered to zero, but genuinely empty)? It should show its existing "no summary yet" state, unaffected by filter state.
- What happens if the active filter references a stock that is tracked but was not among the AI's chosen highlights? The highlights area simply shows no match for that filter; the panel does not fabricate a highlight for it.
- What happens when a user rapidly toggles like/dislike on the same stock? The final state should reflect the last click, with no lingering inconsistent state between the stock page and the filter.
- What happens to a stock's like/dislike tag if that stock later stops being tracked? The tag is retained but neither shown nor applied to filters while the stock is untracked, and is restored if the stock is tracked again — so removing and re-adding a stock does not silently discard the user's opinion.
- What happens when a disclosed congressional trade's dollar amount is reported as a bracket rather than an exact figure (typical for these disclosures)? The high-dollar test compares the bracket directly against the $100,001 boundary — no midpoint or estimated figure is ever derived or displayed.
- What happens when a disclosure's amount bracket straddles the $100,001 boundary or is missing entirely? A bracket that reaches $100,001 at its upper end qualifies; a disclosure with no reported amount is listed in the main table but never flagged as high-dollar.
- What happens when the same person appears in disclosures under slightly different name formats? Out of scope for this batch to reconcile identities beyond exact/near-exact name matching; treated as a known limitation.
- What happens when a sector ETF or the most-actives/Congress feeds are rate-limited or temporarily unavailable from the external data source? The affected section should show a clear unavailable/stale state and the rest of the page should keep working.

## Requirements *(mandatory)*

### Functional Requirements

**Portfolio Summary fixes**

- **FR-001**: Clicking a ticker within the Portfolio Summary panel MUST navigate the user to that ticker's stock detail page, and that page MUST render with content.
- **FR-002**: The Portfolio Summary panel MUST narrow its ticker highlights to only those stocks matching the feed's active filter(s), updating as the filter changes.
- **FR-003**: When no feed filter is active, the Portfolio Summary panel MUST show all of its highlights, matching its current behavior.
- **FR-004**: When the active filter matches none of the panel's highlights, the highlights area MUST clearly indicate that no highlighted stocks match the current filter.
- **FR-004a**: The Portfolio Summary panel's AI-written overview paragraph MUST NOT be regenerated or re-scoped in response to filter changes; it always reflects the full tracked set.
- **FR-004b**: Whenever a filter is active, the panel MUST visibly indicate that the overview paragraph describes all tracked stocks rather than the filtered subset.

**Like / Dislike**

- **FR-005**: Users MUST be able to mark a stock the system already tracks as "liked" from its stock detail page, via a thumbs-up control positioned next to the ticker.
- **FR-006**: Users MUST be able to mark a stock the system already tracks as "disliked" from its stock detail page, via a thumbs-down control positioned next to the ticker.
- **FR-006a**: The thumbs-up and thumbs-down controls MUST be hidden on the detail page of a ticker the system does not track, so that like/dislike state can only ever exist for stocks the feed filter can actually surface.
- **FR-007**: A stock's like/dislike state MUST be mutually exclusive (liked, disliked, or neither — never both at once).
- **FR-008**: Clicking the active like or dislike control again MUST clear that state back to neither.
- **FR-009**: The feed filter bar MUST offer a "liked" and a "disliked" filter option, each narrowing the feed to stocks currently in that state.
- **FR-010**: A stock's like/dislike state MUST persist across sessions.

**Congress disclosures**

- **FR-011**: The application's navigation bar MUST include a "Congress" entry linking to a dedicated Congress trading disclosures page.
- **FR-012**: The Congress page MUST display recent Senate trade disclosures and recent House trade disclosures, each showing the disclosing member, ticker, trade action, and date.
- **FR-013**: Users MUST be able to filter the Congress page's disclosures by ticker.
- **FR-014**: Users MUST be able to filter the Congress page's disclosures by disclosing member name.
- **FR-015**: The Congress page MUST include a summary section ranking tickers by the number of buy disclosures filed within the last 90 days, most-bought first.
- **FR-016**: The Congress page's summary section MUST call out disclosures from the last 90 days whose reported amount bracket reaches $100,001 or above.
- **FR-016a**: The summary section MUST NOT infer or display an exact dollar figure for a disclosure whose amount is reported only as a bracket; brackets are compared and displayed as brackets.
- **FR-016b**: When no disclosure in the last 90 days meets the high-dollar threshold, the summary section MUST say so plainly rather than lowering the bar to fill the section.
- **FR-017**: Clicking a ticker within a Congress disclosure row MUST navigate the user to that ticker's stock detail page.
- **FR-018**: A disclosure with no tradable ticker MUST be displayed without offering a broken navigation link.

**Sector momentum**

- **FR-019**: The Sectors page MUST display a line chart covering the sector ETFs XLC, XLY, XLP, XLE, XLF, XLI, XLV, XLB, XLRE, XLK, and XLU.
- **FR-020**: Each sector ETF's line MUST be plotted as percentage change from the first data point in the selected time window, so all 11 series share a common baseline and are directly comparable.
- **FR-020a**: Each sector ETF's line on the chart MUST be individually distinguishable (e.g., via color and a legend/label).
- **FR-020b**: Users MUST be able to switch the chart's time window between 1 month, 3 months, 6 months, and 1 year, with all lines rebased to the newly selected window's starting point.
- **FR-021**: If one sector ETF's data is unavailable for the selected window, the chart MUST still render the remaining sectors and indicate the gap rather than failing to render entirely.

**Top traded stocks**

- **FR-022**: The Stocks page MUST display a "Top Traded Stocks" section, positioned below the main ticker feed, listing the market's currently most actively traded stocks.
- **FR-023**: Clicking a ticker within the Top Traded Stocks section MUST navigate the user to that ticker's stock detail page.
- **FR-024**: When most-actives data is unavailable, the section MUST show a clear unavailable state rather than appearing empty or broken.

**Pull diagnostics removal**

- **FR-025**: The stock detail page MUST NOT display a "Pull cost" / pull-diagnostics section.
- **FR-026**: The system MUST NOT persist per-stage pull diagnostic detail (timing/byte breakdown) for new data pulls going forward.
- **FR-026a**: Previously stored pull-diagnostics records, along with their collection and indexes, MUST be removed as part of this change, leaving no retired storage behind.
- **FR-026b**: Removing pull diagnostics MUST NOT alter how data pulls themselves behave — no analysis, price baseline, or delta-pull decision depends on this diagnostic data.

### Key Entities

- **Like/Dislike Tag**: A user-facing preference state attached to a tracked ticker — one of "liked", "disliked", or unset; drives both the stock-page thumbs controls and the feed filter. Exists only for tickers the system tracks.
- **Congressional Trade Disclosure**: A disclosed transaction by a member of Congress (Senate or House) — has a disclosing member name, chamber, ticker, trade action (buy/sell), trade date, disclosure date, and a reported amount expressed as a bracket (e.g. "$50,001 – $100,000") rather than an exact figure. The bracket is stored and compared as a bracket; no exact value is ever inferred from it.
- **Sector ETF Price Series**: Daily price history for one of the 11 tracked sector ETFs, covering at least the longest selectable window (1 year), used to render the sector momentum chart. Percentage-change rebasing is a presentation concern derived from this series, not a stored form of it.
- **Top Traded Stock**: A ticker identified by the external data source as among the market's most actively traded for the current period, with enough identifying info (ticker, at minimum) to link to its stock detail page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of ticker clicks within the Portfolio Summary panel land on a populated stock detail page (zero blank-page outcomes).
- **SC-002**: After applying a feed filter, the Portfolio Summary panel's highlights update to match the filtered set instantly — without a page reload and without waiting on any AI regeneration.
- **SC-003**: A user can mark a stock as liked or disliked in a single click from its detail page, and see it reflected in the feed filter results immediately afterward.
- **SC-004**: A user can find recent Senate and House trade disclosures for a specific stock or lawmaker in a few actions, without leaving the Congress page, and can see the most-bought tickers of the last 90 days without applying any filter.
- **SC-005**: A user can identify, within seconds of opening the Sectors page, which sector ETFs are leading and which are lagging over the selected window, by visual inspection of the chart alone, and can re-test that read across a different window without leaving the page.
- **SC-006**: A user can see the market's most actively traded stocks directly on the Stocks page without navigating elsewhere.
- **SC-007**: The stock detail page shows zero references to pull-cost diagnostics, this diagnostic data is no longer retained anywhere after the change ships, and data pulls still complete normally.

## Assumptions

- "Portfolio summary" refers to the existing cross-stock AI summary panel on the Stocks page (currently labeled "Portfolio Summary"); "the filter on the page" refers to the existing feed filter bar (ticker, signal, conviction).
- The blank-page bug in User Story 1 is a navigation-path mismatch between where the Portfolio Summary panel's ticker links point and where the stock detail route actually lives; the fix is to make them consistent, without changing the stock detail route itself.
- Like/dislike is a single, user-facing preference per ticker (not per-user-account, since this is a single-user local-first product per the project's constitution) and is independent of the AI-generated signal/conviction.
- Congressional trade dollar amounts are disclosed as brackets (a well-known characteristic of these public disclosures), not exact figures. Both summary measures are deliberately designed around that imprecision: most-bought ranks by disclosure *count*, and high-dollar tests the bracket against a boundary that already exists in the disclosure format ($100,001), so neither measure requires inventing a dollar figure.
- This batch's Congress tab is scoped to what was requested here (recent disclosures, a buying/high-dollar summary, ticker/person filters, ticker navigation). It does not include the committee-membership or unusual-legislative-timing analysis described in the pre-existing `specs/005-congressional-trading` spec; that remains a separate, not-yet-implemented feature this batch does not build.
- All new external data pulled for this batch (sector ETF prices, most-actives, Senate/House disclosures) goes through the project's existing cache-first, budget-guarded data access layer rather than being fetched ad hoc, consistent with the project's data-access constraints.
- The pull-diagnostics data is purely diagnostic: it is written only when a pull finishes and read only by the panel being removed. Nothing in the analysis pipeline, price baseline, or delta-pull logic consults it, so deleting it carries no analytical risk. (It also already self-expired after 30 days, so this change makes the removal immediate and explicit rather than gradual.)
- "Top Traded Stocks" and the Congress disclosures may reference tickers the system isn't already tracking/analyzing. Clicking through to such a ticker's stock detail page works today — the page header and its "Pull" action render whether or not an analysis exists — so those links need no special handling beyond hiding the thumbs controls (FR-006a).
- Where the thumbs controls are hidden for an untracked ticker, they are hidden outright rather than shown disabled: that page already surfaces "Pull" as its obvious next action, and a dead control alongside it would add noise without adding information.

- **Sector chart scope**: v1 ships a percentage-change comparison chart for the 11 sector ETFs only — no additional indicators (signal overlays, moving averages, RSI, etc.) in this batch. Spotting "bottoming or topping" beyond what's visible from relative trend across the selectable windows is deferred to a later, separate spec once the base chart is in use.
- The data pipeline for this batch's new external data follows the project's already-established admin-job pattern rather than introducing a new one: `specs/017-fmp-migration-admin/contracts/admin-jobs-api.md` already registers `congress_trades_pull` ("Pull latest senate & house trading disclosures") and `market_movers_pull` ("Pull today's biggest gainers, losers, and most-active stocks") as work_queue admin jobs feeding the `congress_trades` and `market_movers` datasets — both registered but not yet implemented. This batch implements them; the Congress and Top Traded Stocks pages read from those cached datasets rather than calling the provider directly.
