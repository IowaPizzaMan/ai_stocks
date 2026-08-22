# Feature Specification: Company Profile, Peers & Navigation Tweaks

**Feature Branch**: `029-company-profile-tweaks`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "I have a few tweeks I want to make. 1. In the stocks tab there is a new tab. I want the news tab to actually be on the nav bar, not nested inside the stocks screen. 2. In the stocks page. I actually want to get rid of the potfloio summary section, instead when i hover over a stock, I want to be able to see the AI summary on the hover popup. 3. On the sectors page. I want to make the graph taller so its easier to undertstand what is going on when all the line graphs are displayed. I also want to be able to toggle each graph by clicking the ticker name in the ledgend. 3. I want to add another section to the overview tab for a stock. I want this to show the stocks' peers [FMP stock-peers]. 4. I want to add one more section to the overview tab. I want an employ count graph [FMP historical-employee-count]. 4. One more new section for the overview tab. I want to put this infroatmion in the top most section [FMP profile]. I want the indust to be used on the sector page, its looking for sector but it should use the industry fild for its process. also notice I have an impage link. I want to put that up by the ticker. and I want to put that on the stocks page in the little container for the company. 5. Now that I have the industry, i want to add that as a filter on the stock page."

## Overview

Seven independent tweaks across the Stocks page, the Sectors page, the stock detail page, and the top-level navigation. The connecting thread through most of them is a company profile record the app does not keep today — the authoritative company identity, classification, logo, and headline stats published by the market data provider. Bringing that record in gives the stock detail page a proper identity header, gives every stock hover card a logo, replaces the analysis-derived sector classification the Sectors page groups by today with the provider's own sector value, and unlocks a new industry filter on the Stocks page. Alongside that, market news is promoted from a tab nested inside the Stocks page to its own top-level nav destination, the Portfolio Summary panel is retired in favor of per-stock AI summaries on hover, the Sectors chart gets more vertical room and per-series legend toggling, and the Overview tab gains peers and employee-count sections.

## Clarifications

### Session 2026-08-22

- Q: How far should the removal of the Portfolio Summary section go? → A: Remove the feature entirely — the panel, its background generation job, its endpoints, and its stored records, matching how the Pull Cost section was retired in spec 028.
- Q: The Sectors page should key off the company profile rather than the analysis-derived value — by industry or by sector? → A: Sector. The company profile publishes both; the Sectors page keeps grouping by sector, but sourced from the profile record rather than derived during analysis. Industry is a new, finer-grained attribute used for the Stocks page filter.
- Q: Which sector value should the Stocks page's sector filter match against after this change? → A: The profile's sector becomes the system's only sector. The Sectors page, the Stocks page sector filter, and the per-sector macro read all read it, and the analysis stops writing a sector of its own.
- Q: How do already-analyzed stocks acquire a profile, given sector now comes only from the profile? → A: No backfill job. A ticker gets its profile on its next normal analysis pull; the existing "Run All" control is how the user catches the whole universe up in one action.
- Q: Should the Overview tab's profile section display the profile feed's own price, change, and volume, given the Charts tab shows price data too? → A: No — price, change, and volume come from the app's existing price data so the page never shows two disagreeing prices. The profile supplies only the stats nothing else has: beta, last dividend, average volume, and the 52-week range.
- Q: Should the company logo appear on the compact stock tile itself, or only on its hover card? → A: Both. A small logo sits beside the ticker on each tile, with a neutral chip behind it so it stays legible against the signal-colored fill, and it also appears on the hover card.
- Q: How often should peers and employee-count history be re-fetched? → A: On the analysis pull, but behind a long (~90-day) cache window matching the existing financials cache — a repeat pull inside that window re-fetches only the profile. The profile itself refreshes on every pull.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - News Is a Top-Level Destination (Priority: P1)

Market news is currently reachable only by first landing on the Stocks page and then selecting a tab inside it. A user who wants headlines should be able to go straight there from the main navigation, the same way they reach Macro, Sectors, Earnings, or Congress. After this change the main navigation includes a News destination, and the Stocks page no longer carries a News tab.

**Why this priority**: Smallest, most self-contained change in the batch, blocks nothing else, and immediately fixes a discoverability problem the user called out first.

**Independent Test**: Open the app, click News in the main navigation, confirm the market news list renders on its own page with the same content and behavior it had inside the Stocks page. Return to the Stocks page and confirm no News tab is present.

**Acceptance Scenarios**:

1. **Given** any page in the app, **When** the user clicks News in the main navigation, **Then** the market news list renders as its own page.
2. **Given** the News page, **When** it renders, **Then** it shows the same market-wide headlines (most recent articles, newest first, ticker links, external article links, no auto-loading on scroll) that previously appeared in the Stocks page's News tab.
3. **Given** the Stocks page, **When** it renders, **Then** no News tab appears in its tab bar and the stock grid is the page's content.
4. **Given** the user is on the News page, **When** they look at the main navigation, **Then** News is marked as the active destination.
5. **Given** an existing bookmark or link to the old in-page News tab anchor, **When** it is opened, **Then** the user lands on a working page rather than a blank or error view.

---

### User Story 2 - Company Profile Header on the Stock Page (Priority: P1)

A user opening a stock's Overview tab sees, as the very first section, a company identity block: the company's logo, name, exchange, sector, industry, country, website, CEO, employee headcount, IPO date, the company description, and a headline stats row (price, change, market cap, beta, last dividend, 52-week range, volume and average volume) — with price, change and volume read from the app's own price data so they agree with the Charts tab. The company's logo also appears next to the ticker in the stock page header, so the page is identifiable at a glance.

**Why this priority**: This is the data foundation the batch depends on — the Sectors page's sector source, the Stocks page's industry filter, and the logos on the hover cards all read from the same profile record. Delivering it first makes the later stories cheap.

**Independent Test**: Open any tracked stock's detail page, confirm the logo renders next to the ticker in the header, switch to the Overview tab, and confirm a company profile section renders above every other section with the company's identity, classification, and headline stats populated.

**Acceptance Scenarios**:

1. **Given** a stock with an available company profile, **When** the user opens its Overview tab, **Then** a company profile section renders as the topmost section, above the existing Verdict section.
2. **Given** the profile section is rendering, **When** the user reads it, **Then** it shows the company name, logo, exchange, sector, industry, country, CEO, full-time employee count, IPO date, a link to the company website, and the company description.
3. **Given** the profile section is rendering, **When** the user reads it, **Then** it shows the headline market stats — current price, change and change percentage, market cap, beta, last dividend, 52-week range, volume, and average volume — each clearly labeled.
3a. **Given** the profile section and the Charts tab are both showing a price for the same stock, **When** the user compares them, **Then** the two agree, because both read the app's own price data.
4. **Given** a stock's detail page, **When** it renders, **Then** the company logo appears next to the ticker in the page header.
5. **Given** a stock whose profile has no usable logo (missing, or flagged by the provider as a placeholder), **When** the page renders, **Then** a neutral fallback stands in for the logo and no broken image appears.
6. **Given** a ticker with no profile available at all, **When** the user opens its Overview tab, **Then** the rest of the tab renders normally and the profile section shows a clear "profile unavailable" state rather than blocking the page.
7. **Given** a profile retrieved some time ago, **When** the user views the profile section, **Then** the section states when the profile was last refreshed, so its slow-moving stats are not mistaken for live figures.

---

### User Story 3 - Logo and AI Summary on Hover, Portfolio Summary Retired (Priority: P1)

The Stocks page's Portfolio Summary panel is removed outright — panel, background generation, and stored summaries. In its place, the per-stock hover card that already appears when the user points at a stock tile carries that stock's own AI summary in full, alongside its logo and company name, so the user reads the AI's take stock-by-stock rather than as one blended paragraph. Each tile in the grid also carries a small company logo beside its ticker, so the grid is scannable by brand and not just by symbol. With the panel gone, the grid occupies the full width of the page.

**Why this priority**: The user asked for this directly, it removes a whole subsystem (reducing maintenance and generation cost), and it depends on the profile record from User Story 2 for the logo.

**Independent Test**: Open the Stocks page, confirm no Portfolio Summary panel appears and the grid spans the full width; hover a stock tile and confirm its hover card shows the company logo, name, and that stock's AI summary in full.

**Acceptance Scenarios**:

1. **Given** the Stocks page, **When** it renders, **Then** no Portfolio Summary panel appears anywhere on it and the stock grid uses the page's full width.
1a. **Given** the stock grid, **When** it renders, **Then** each tile shows a small company logo beside its ticker, with the ticker and conviction dots still legible at the tile's existing size.
2. **Given** the user points at (or keyboard-focuses) a stock tile, **When** the hover card appears, **Then** it shows that stock's AI summary text in full, not truncated to a few lines.
3. **Given** the hover card is showing, **When** the user reads it, **Then** it also shows the company's logo and name next to the ticker, plus the signal, conviction, and recency information it already showed.
4. **Given** a stock whose AI summary is longer than the hover card's height, **When** the card renders, **Then** the summary remains fully readable within the card (the card scrolls or grows) without pushing content off screen.
5. **Given** a stock with no completed analysis, **When** its hover card appears, **Then** the card states that no summary is available rather than rendering empty.
6. **Given** the app after this change, **When** any page is opened, **Then** no portfolio-summary content, regeneration control, or last-generated timestamp appears anywhere, and no portfolio-summary generation work is queued or run.
7. **Given** previously stored portfolio summaries, **When** this change is deployed, **Then** those stored records are deleted rather than left to linger.

---

### User Story 4 - Sectors Page: Taller Chart with Toggleable Series (Priority: P2)

With all eleven sector series plotted at once, the Sectors momentum chart is too short to read — lines crowd together and the user cannot follow any single sector. The chart gets meaningfully more vertical room, and clicking a ticker in the legend hides or shows that sector's line, so the user can isolate two or three sectors and compare them directly.

**Why this priority**: A focused usability fix to an already-shipped chart; valuable and quick, but nothing else depends on it.

**Independent Test**: Open the Sectors page with data loaded, confirm the chart is visibly taller than before, click a ticker in the legend and confirm that line disappears while the rest remain, then click it again and confirm it returns.

**Acceptance Scenarios**:

1. **Given** the Sectors page with chart data, **When** the chart renders, **Then** it is materially taller than its current height, giving visibly more vertical separation between the plotted lines.
2. **Given** all eleven series are plotted, **When** the user clicks a ticker in the legend, **Then** that ticker's line is hidden from the chart and its legend entry is visibly marked as hidden.
3. **Given** a hidden series, **When** the user clicks its legend entry again, **Then** the line returns to the chart and the legend entry returns to its normal state.
4. **Given** several series are hidden, **When** the chart re-renders, **Then** the vertical axis fits the visible series so the remaining lines use the full plot area.
5. **Given** the user has hidden some series, **When** they change the chart's time window, **Then** their hidden/shown choices are preserved rather than reset.
6. **Given** the user hides every series, **When** the chart renders, **Then** it shows an empty-plot state that makes clear the series are hidden, not missing.
7. **Given** a keyboard user, **When** they move focus to a legend entry and activate it, **Then** the same toggle occurs as with a mouse click.

---

### User Story 5 - Sector Classification and Industry Filter from the Profile (Priority: P2)

The Sectors page groups stocks by a sector value produced during analysis, which is inconsistent between stocks and occasionally missing. The profile's sector replaces it outright and becomes the only sector in the system — the Sectors page, the Stocks page's sector filter, and the per-sector macro read all read the same value, so a sector's rollup and its filtered grid can never disagree. The profile also carries a finer-grained industry, which becomes a new filter on the Stocks page so the user can narrow the grid to, say, Consumer Electronics rather than all of Technology.

**Why this priority**: Fixes a real data-quality problem on an existing page and adds a filter the user asked for, but both depend on the profile record from User Story 2.

**Independent Test**: Open the Sectors page and confirm stocks are grouped under the sector names their company profiles carry; open the Stocks page, apply the new industry filter, and confirm the grid narrows to only stocks in that industry.

**Acceptance Scenarios**:

1. **Given** tracked stocks with company profiles, **When** the user opens the Sectors page, **Then** each stock is grouped under the sector value from its company profile.
2. **Given** a stock whose profile sector differs from the sector previously stored on its analysis, **When** the Sectors page renders, **Then** the profile's sector is the one used.
2a. **Given** a sector on the Sectors page showing a rollup of N stocks, **When** the user follows its link to the filtered Stocks grid, **Then** the grid shows exactly those N stocks.
3. **Given** a stock with no available profile sector, **When** the Sectors page renders, **Then** that stock is grouped into a clearly labeled unclassified bucket rather than silently dropped.
4. **Given** the Stocks page filter bar, **When** the user selects an industry, **Then** the grid shows only stocks whose profile industry matches, and the selection is reflected in the page's shareable URL.
5. **Given** an active industry filter, **When** the user clears it, **Then** the full grid returns.
6. **Given** the industry filter control, **When** the user opens it, **Then** the industries offered are those actually present among tracked stocks, so no available choice yields an empty grid.
7. **Given** an industry filter combined with an existing filter (ticker, signal, conviction, sentiment, or sector), **When** both are active, **Then** the grid shows only stocks matching all active filters.

---

### User Story 6 - Peers Section on the Overview Tab (Priority: P2)

A user assessing a stock wants to see who it trades against. The Overview tab gains a Peers section listing the provider's peer companies for that stock — each with its symbol, company name, current price, and market cap — and clicking a peer navigates to that peer's own stock page.

**Why this priority**: Net-new, self-contained comparison value; independent of every other story except that it lives on the same tab.

**Independent Test**: Open a stock's Overview tab, confirm a Peers section lists peer companies with symbol, name, price, and market cap, and confirm clicking a peer opens that peer's stock page.

**Acceptance Scenarios**:

1. **Given** a stock with available peers, **When** the user opens its Overview tab, **Then** a Peers section lists each peer's symbol, company name, current price, and market cap.
2. **Given** the peers list, **When** the user clicks a peer's symbol, **Then** they navigate to that peer's stock detail page.
3. **Given** a peer the app does not currently track, **When** the user opens its page from the peers list, **Then** the page renders in its normal untracked state rather than blank or erroring.
4. **Given** a stock with no peers published, **When** the user opens its Overview tab, **Then** the Peers section shows a clear empty state.
5. **Given** market caps spanning several orders of magnitude, **When** the peers list renders, **Then** each market cap is formatted for readability (abbreviated, not a raw digit string).
6. **Given** the peers list, **When** it renders, **Then** it is ordered predictably (largest market cap first) rather than arbitrarily.

---

### User Story 7 - Employee Count Graph on the Overview Tab (Priority: P3)

The Overview tab gains a graph of the company's reported employee headcount over time, drawn from its regulatory filings, so the user can see whether the company is growing or shrinking its workforce.

**Why this priority**: The most additive and least urgent item in the batch — genuinely interesting context, but nothing depends on it and its absence blocks nothing.

**Independent Test**: Open a stock's Overview tab and confirm an employee-count chart renders with one point per reported filing period, in chronological order, with readable headcount values.

**Acceptance Scenarios**:

1. **Given** a stock with reported employee-count history, **When** the user opens its Overview tab, **Then** a chart plots employee count over time, oldest to newest.
2. **Given** the chart, **When** the user points at a data point, **Then** they see the period the figure covers, the headcount, and the filing type it came from.
3. **Given** a stock with only one reported period, **When** the chart renders, **Then** it renders that single figure legibly rather than as an empty or broken plot.
4. **Given** a stock with no reported employee history, **When** the user opens its Overview tab, **Then** the section shows a clear empty state.
5. **Given** the chart, **When** it renders, **Then** headcount values are formatted for readability (e.g., abbreviated thousands) rather than as raw digit strings.

---

### Edge Cases

- The day this ships, no tracked stock has a profile yet: the Sectors page shows every stock in the unclassified bucket, the industry filter offers no choices, and tiles, hover cards and headers all use the logo fallback — all correct, all self-explaining, and all resolved as the user pulls (or runs) the universe. No surface may treat this initial state as an error.
- A ticker that is an ETF or fund rather than an operating company: the profile section renders what is available and omits company-only fields (CEO, employees, industry) rather than showing blanks or zeroes; the employee-count and peers sections show their empty states.
- The provider's rate limit or configured soft cap is hit while a profile, peers list, or employee history is requested: the app serves the last cached copy with its "as of" timestamp, and shows an unavailable state only when nothing has ever been cached — it degrades rather than failing the pull.
- A "Run All" across the whole tracked universe: the first run adds three provider calls per ticker, every subsequent run within the cache window adds one, and the existing throttle governs the pace — no surface issues per-ticker calls outside the pull path.
- A profile's logo reference is reachable but the image fails to load in the browser: the fallback stands in, with no layout shift or broken-image icon.
- A stock's profile sector changes between refreshes (reclassification): the Sectors page reflects the new grouping on the next render, and the industry filter's available choices update accordingly.
- The industry filter is active and the last stock in that industry is removed: the grid shows its normal empty state and the now-empty industry is no longer offered as a choice.
- A user's existing bookmark carries the old Stocks-page News anchor or a Portfolio Summary deep link: it resolves to a working page.
- A stock's AI summary is unusually long: the hover card stays within the viewport and remains fully readable.
- Two peers have identical market caps, or one has none: ordering stays stable and a missing value renders as an explicit dash rather than as zero.

## Requirements *(mandatory)*

### Functional Requirements

**Navigation**

- **FR-001**: The main navigation MUST include a News destination alongside the existing destinations, and it MUST be marked active while the user is on it.
- **FR-002**: The News page MUST present the same market-wide news content and behavior that the Stocks page's News tab presented (most recent articles newest first, ticker links, external article links, capped list, no auto-loading on scroll).
- **FR-003**: The Stocks page MUST NOT present a News tab, and MUST render the stock grid as its content without requiring tab selection.
- **FR-004**: Links and bookmarks to the retired in-page News tab anchor MUST resolve to a working page rather than a blank or error view.

**Company profile**

- **FR-005**: The system MUST retrieve and store a company profile record per ticker containing at minimum: company name, logo image reference, exchange, sector, industry, country, website, CEO, full-time employee count, IPO date, description, currency, current price, change, change percentage, market cap, beta, last dividend, 52-week range, volume, and average volume.
- **FR-006**: Profile, peers, and employee-count retrieval MUST go through the app's existing cache-first, budget-guarded data access path — respecting the provider's daily call limits and serving cached data rather than exhausting the day's quota.
- **FR-007**: A profile record MUST carry the timestamp at which it was retrieved, and the profile section MUST show that timestamp so its slow-moving stats are not mistaken for live figures.
- **FR-008**: A ticker's profile MUST be refreshed as part of the ticker's existing analysis pull, so a stock the user pulls has a current profile without a separate manual action.
- **FR-008a**: Peers and employee-count history MUST be refreshed on the same analysis pull but behind a long cache window matching the existing financials cache (~90 days), so a repeat pull within that window costs one provider call per ticker (the profile) rather than three.
- **FR-008b**: A full refresh of a ticker MUST bypass the FR-008a cache window and re-fetch peers and employee-count history, giving the user an explicit way to force fresh data without waiting out the window.
- **FR-009**: When no profile is available for a ticker, every surface that consumes profile data MUST degrade to a clearly labeled unavailable/fallback state without blocking the rest of that surface.

**Stock detail page**

- **FR-010**: The Overview tab MUST render a company profile section as its topmost section, above all existing sections.
- **FR-011**: The profile section MUST display the company identity fields (name, logo, exchange, sector, industry, country, CEO, employees, IPO date, website link, description) and the headline market stats (price, change, change percentage, market cap, beta, last dividend, 52-week range, volume, average volume), each clearly labeled.
- **FR-011a**: Price, change, change percentage, and volume shown in the profile section MUST come from the app's existing price data, not from the profile record, so they never contradict the price shown on the Charts tab. Beta, last dividend, average volume, 52-week range, and market cap come from the profile record.
- **FR-011b**: The profile record's own price, change, and volume values MUST NOT be displayed anywhere as the stock's current price.
- **FR-012**: The stock detail page header MUST display the company logo next to the ticker.
- **FR-013**: Where a logo is missing or the provider flags it as a placeholder, the system MUST render a neutral fallback in its place, and MUST NOT render a broken image.
- **FR-014**: The Overview tab MUST render a Peers section listing each peer's symbol, company name, current price, and market cap, ordered by market cap descending, with each peer navigating to that peer's stock detail page when clicked.
- **FR-015**: The Overview tab MUST render an employee-count chart plotting reported headcount over time in chronological order, with each point identifying its reporting period and filing type on inspection.
- **FR-016**: The Peers and employee-count sections MUST each show a clear empty state when the underlying data is unavailable for that ticker.
- **FR-017**: Market cap and employee-count values MUST be displayed in an abbreviated, human-readable form rather than as raw digit strings.

**Stocks page**

- **FR-018**: The Portfolio Summary panel MUST be removed from the Stocks page, and the stock grid MUST occupy the full page width in its place.
- **FR-019**: The portfolio-summary generation job, its endpoints, and its stored records MUST all be removed — the system MUST stop generating summaries, MUST delete the stored records, and MUST NOT retain the collection or its indexes.
- **FR-020**: The per-stock hover card on the Stocks page MUST display that stock's full AI summary text, not a truncated excerpt, while retaining the signal, conviction, and recency information it shows today.
- **FR-021**: The hover card MUST display the company's logo and name next to the ticker, with the same fallback behavior as FR-013.
- **FR-021a**: Each compact stock tile MUST display a small company logo beside its ticker, rendered so that the logo, the ticker text, and the tile's signal fill all remain legible; the ticker and its conviction indicator MUST remain readable at the tile's existing size, and the FR-013 fallback applies.
- **FR-022**: The hover card MUST keep a long summary fully readable within the viewport (by scrolling within the card or sizing to fit) rather than overflowing off screen.
- **FR-023**: The hover card MUST state that no summary is available when the stock has no completed analysis.
- **FR-024**: The Stocks page filter bar MUST offer an industry filter whose choices are the industries actually present among tracked stocks.
- **FR-025**: Selecting an industry MUST narrow the grid to stocks with that profile industry, MUST be reflected in the page's shareable URL, MUST be clearable, and MUST combine with every other active filter as an AND.

**Sectors page**

- **FR-026**: The company profile's sector MUST be the system's single sector value. The Sectors page grouping and rollup, the Stocks page sector filter, and the per-sector macro read MUST all read it, and the analysis MUST stop producing a sector of its own.
- **FR-026a**: Navigating from a sector on the Sectors page to the filtered Stocks grid MUST land on a grid containing exactly the stocks that sector's rollup counted.
- **FR-027**: Stocks with no profile sector MUST be grouped into a clearly labeled unclassified bucket rather than dropped from the page. The bucket MUST make clear that these stocks are awaiting their next analysis pull, so an unclassified stock reads as "not pulled yet" rather than as a defect.
- **FR-027a**: No backfill of existing stocks is required. A ticker acquires its profile on its next analysis pull (FR-008), and the existing "Run All" control MUST be sufficient to bring the whole tracked universe up to date in one action.
- **FR-028**: The sector momentum chart MUST render materially taller than its current height to separate the eleven plotted series.
- **FR-029**: Clicking (or keyboard-activating) a ticker in the chart legend MUST toggle that series' visibility, and the legend entry MUST visibly reflect the hidden/shown state.
- **FR-030**: The chart's vertical axis MUST fit the currently visible series so hiding series expands the remaining lines to use the plot area.
- **FR-031**: Series visibility choices MUST persist across a change of the chart's time window within the same visit.
- **FR-032**: With every series hidden, the chart MUST show an empty-plot state that reads as "hidden", distinct from "no data".

### Key Entities

- **Company Profile**: The provider's authoritative record for one ticker — identity (name, logo, description, website, CEO, headquarters, IPO date), classification (exchange, sector, industry, country, currency, and the ETF/fund/ADR/actively-trading flags), and market stats (market cap, beta, last dividend, 52-week range, average volume — plus price, change and volume, which are stored but never displayed as the app's price of record, per FR-011b). Carries a retrieved-at timestamp. One per ticker, refreshed with the ticker's analysis pull. Supplies the sector used by the Sectors page and the industry used by the Stocks page filter.
- **Peer**: One comparable company for a given ticker — symbol, company name, price, market cap. Zero or more per ticker; each symbol may itself be a tracked or untracked ticker.
- **Employee Count Record**: One reported headcount for a ticker from one regulatory filing — reporting period, filing type, filing date, headcount, and the filing's source reference. Zero or more per ticker, forming a time series.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can reach market news from any page in one click, without first visiting the Stocks page.
- **SC-002**: Opening a stock's Overview tab shows its company identity, classification, and headline stats without any further navigation or clicks.
- **SC-003**: A user can identify a stock's company by logo on the Stocks page grid tiles, on its hover card, and in the stock detail page header for at least 95% of tracked stocks with a profile, with a clean fallback for the rest.
- **SC-004**: A user can read any single stock's complete AI summary from the Stocks page without leaving the page or clicking through to the detail page.
- **SC-005**: With all eleven sector series plotted, a user can reduce the chart to any chosen pair of sectors and compare them without leaving the page, using only legend clicks.
- **SC-006**: Every tracked stock appears in exactly one bucket on the Sectors page, with no stock silently missing from the rollup.
- **SC-007**: A user can narrow the Stocks grid to a single industry in one interaction and share that view by copying the page URL.
- **SC-008**: A user can move from a stock to one of its peers' pages in one click.
- **SC-009**: No portfolio-summary content, control, stored record, or background job remains anywhere in the system after this change.
- **SC-010**: All new profile, peers, and employee-count data is served from cache on repeat views — viewing a stock page never issues a provider call — and a repeat "Run All" within the cache window adds no more than one provider call per ticker.

## Assumptions

- The market data provider endpoints named by the user (company profile, stock peers, historical employee count) are entitled on the current plan and reachable through the app's existing budget-guarded data access layer; no new provider or plan tier is needed.
- All three datasets are fetched only on the analysis pull path, never on page view. The profile record's price fields are retained as fetched but are not the app's price of record (FR-011a/FR-011b); they may be useful later for diagnostics.
- The provider account is on a paid tier whose limit is per-minute rather than a hard daily quota, with the daily soft cap currently disabled; the existing throttle and fail-soft-to-cache guard are sufficient for this feature's added calls, and no new budget mechanism is needed.
- The tile logo is a small mark beside the ticker (not a background watermark), on a neutral chip so it reads cleanly against the tile's signal-colored fill.
- No migration or backfill of profile data is in scope; the tracked universe catches up through normal pulls, and the user is expected to run one "Run All" after this ships if they want it caught up immediately.
- Industry is a new filter dimension on the Stocks page and does not replace the sector filter; the two coexist and combine.
- The per-sector macro read continues to key off sector (not industry); it is unaffected beyond now reading the profile's sector, which gives it more consistent and fewer distinct buckets to analyze.
- Sector-series visibility toggles are within-visit UI state; they are not persisted across sessions or encoded in the shareable URL.
- The employee-count chart plots every reported period the provider returns, with no time-window selector, since filings are annual and the full history is small.
- Peers are displayed as the provider supplies them; the app does not compute or curate its own peer set.
- Removing the portfolio summary is a one-way deletion — the stored summaries are dropped and would have to be regenerated from scratch if the feature were ever revived.
