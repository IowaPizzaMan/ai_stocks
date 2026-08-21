# Feature Specification: Earnings Page Readability & Filters

**Feature Branch**: `025-earnings-page-filters`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: "I would like to make the earnings page easier to read. Lets have a filter that shows a date range, i want a slider, have it default to 2 days before current date to 2 days after current date. Then I want a few other filters to help reduce the noise, one for rev and eps #'s, maybe sliders for both. Then I want the tickers to always be ordered by market cap. Can I show any tickers that if they have reported then you show an earnings surprise type data, using the FMP earnings-calendar endpoint (Symbol / Date / Eps Actual / Eps Estimated / Revenue Actual / Revenue Estimated / Last Updated). Then I want the stock ticker to be a link to the stock page."

## Clarifications

### Session 2026-08-17

- Q: The original description ended mid-sentence at "Also since" — what was the rest? → A: "…since I don't need to store anything, I should just get the data from the API." No new persisted storage for this feature: read from the provider and derive everything on the fly.
- Q: Should the existing "Scan Earnings" section stay on the page? → A: No. Remove the Scan Earnings button; the page fetches its data automatically on load with the filters pre-set to their defaults.
- Q: Do the revenue and EPS sliders filter on size or on surprise magnitude? → A: Both. The two sliders are size floors (minimum revenue, minimum EPS magnitude), plus a separate "big movers only" toggle that narrows to companies whose surprise was large.
- Q: Where do the size sliders start, and what counts as a "big mover"? → A: Gentle defaults — revenue ≥ $10M, EPS magnitude ≥ $0.01, big mover = 10% absolute surprise. Enough to drop listings with no published figures, low enough that no covered company is hidden by default.
- Q: On widening the date window, refetch or re-filter data already held? → A: Refetch. The page requests exactly the selected window whenever the date range changes. Size sliders and the big-movers toggle stay purely client-side.
- Q: Given refetch-on-change, is a slider still the right date control? → A: No. Replaced with a row of one-click range presets plus two custom date inputs. A bounded set of preset windows caches cleanly and fires exactly one request per click, where a continuous slider makes every drag position a candidate request.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse a bounded date window around today (Priority: P1)

A user opens the earnings page and immediately sees only the companies reporting in a
tight window around today — two days back through two days forward — instead of a
several-hundred-row forward-only list. A row of one-click presets lets them jump to the
other windows they care about — what reported this past week, what is coming next week —
and two date inputs cover anything the presets miss.

**Why this priority**: The current page only looks forward and always shows the full
screened calendar, which is the single largest source of unreadability. Bounding the
window is the change that delivers a usable page on its own, and it is the prerequisite
for showing already-reported results at all, since those live in the past.

**Independent Test**: Load the page with no other interaction and confirm the visible rows
all fall between today−2 and today+2; click a different preset and confirm the row set
changes to match the new window without a page reload.

**Acceptance Scenarios**:

1. **Given** a first visit to the earnings page, **When** the page finishes loading, **Then** results appear without the user pressing any button, the ±2 days preset is shown as active, the window reads today−2 through today+2, and every visible row's report date falls inside that inclusive window.
2. **Given** the default window, **When** the user clicks the "last 7 days" preset, **Then** the table reloads to that window, the preset is marked active, the custom date inputs update to the resolved dates, and the row count updates accordingly.
3. **Given** any active preset, **When** the user types a custom start date that no preset matches, **Then** the preset highlight clears and the table reloads to the typed window once the date is committed.
4. **Given** a custom window, **When** the user enters an end date earlier than the start date, **Then** the range is rejected, no request is issued, and the previously displayed data remains valid.
5. **Given** a window that contains no qualifying companies, **When** filtering resolves, **Then** an empty-state message explains that no companies report in this window and suggests a wider preset.

---

### User Story 2 - See how already-reported companies actually did (Priority: P1)

For any company in the window whose report date has passed and whose actuals have been
published, the row shows what they printed versus what was expected: actual EPS, actual
revenue, and the surprise for each — signed and visually distinguishable as a beat or a
miss. Companies that have not reported yet continue to show estimates only.

**Why this priority**: This is the reason the window extends backwards. Without it, looking
two days back adds rows carrying no new information. It is independently valuable and can
ship without the noise-reduction sliders.

**Independent Test**: Set the window to a past range containing a known reporter and confirm
its row shows actual EPS and revenue alongside the estimates plus a signed surprise
percentage, while a future-dated row in the same table shows estimates and blank actuals.

**Acceptance Scenarios**:

1. **Given** a company that reported inside the window and has published actuals, **When** its row renders, **Then** it displays actual EPS, actual revenue, and an EPS surprise percentage relative to the estimate, marked as a beat or a miss.
2. **Given** a company that reported and has an actual but no published estimate, **When** its row renders, **Then** the actual is shown and the surprise is shown as unavailable rather than as zero or as a beat.
3. **Given** a company whose report date has not yet arrived, **When** its row renders, **Then** actual and surprise fields are shown as not-yet-reported and the estimates remain visible.
4. **Given** a company whose EPS estimate is zero, **When** the surprise would require dividing by that estimate, **Then** the surprise is shown as unavailable instead of an infinite or misleading value.
5. **Given** a company that reported both revenue actual and revenue estimate, **When** its row renders, **Then** a revenue surprise percentage is shown using the same beat/miss treatment as EPS.

---

### User Story 3 - Cut the noise with size filters and market-cap ordering (Priority: P2)

The user reduces a busy window down to the names that matter: rows are always ordered by
market capitalization, largest first, and two additional range controls let them require a
minimum expected revenue and a minimum expected EPS magnitude, dropping shells, warrants,
and thinly-covered listings that carry no usable numbers. A separate "big movers only"
toggle goes further, narrowing the table to companies whose reported results diverged
sharply from expectations.

**Why this priority**: Ordering and size filters make a heavy earnings week readable, but
the page is already materially better with Stories 1 and 2 alone.

**Independent Test**: Load a window spanning a heavy earnings day and confirm rows descend
by market cap; raise the revenue floor and confirm only companies at or above that expected
revenue remain.

**Acceptance Scenarios**:

1. **Given** any set of visible rows, **When** the table renders, **Then** rows are ordered by market capitalization from largest to smallest, regardless of report date.
2. **Given** two companies reporting on different dates, **When** the larger-cap company reports later, **Then** it still sorts above the smaller-cap company.
3. **Given** the revenue filter raised above its floor, **When** filtering resolves, **Then** every visible row's revenue figure meets or exceeds the threshold and companies with no revenue figure are excluded.
4. **Given** the EPS filter raised above its floor, **When** filtering resolves, **Then** every visible row's EPS figure meets the threshold and companies with no EPS figure are excluded.
5. **Given** all size filters returned to their minimum positions and the toggle off, **When** filtering resolves, **Then** no rows are excluded on size or surprise grounds and only the date window applies.
6. **Given** the "big movers only" toggle turned on, **When** filtering resolves, **Then** only companies with a computable surprise at or above the threshold remain, not-yet-reported companies are gone, and the page states that a results filter is active.

---

### User Story 4 - Jump from a ticker to its stock page (Priority: P2)

Every ticker symbol in the earnings table is a link. Activating it opens that company's
existing stock detail page, so the user can go from "who reports today" to full analysis
without retyping the symbol.

**Why this priority**: A small, self-contained navigation win that removes a manual step,
but it changes nothing about readability on its own.

**Independent Test**: Click any ticker in the table and confirm the application navigates to
that ticker's stock detail page.

**Acceptance Scenarios**:

1. **Given** any row in the earnings table, **When** the user clicks its ticker symbol, **Then** the application navigates to the stock detail page for that ticker.
2. **Given** a ticker link, **When** the user activates it via keyboard, **Then** it behaves as a link: focusable, activatable, and visually distinguishable from plain text.
3. **Given** a row's queue-for-analysis action, **When** the user clicks the ticker link, **Then** the queue action is not triggered, and activating the queue action does not navigate away.

---

### Edge Cases

- **Window with no data**: an empty window (weekend, holiday, or over-tight filters) shows an explicit empty state naming which control to relax, not a blank table.
- **Reported but actuals not yet published**: a company whose date has passed but whose provider record still carries no actuals is shown as awaiting results, not as a miss.
- **Estimate of zero or missing**: surprise is suppressed and labeled unavailable rather than computed.
- **Negative EPS**: a company beating a negative estimate (−0.20 actual against −0.30 estimate) is presented as a beat; sign handling must not invert.
- **Company missing market cap**: a calendar entry carrying no market cap in the reference universe is excluded from the table, consistent with the existing size screen, rather than sorted to an arbitrary position.
- **No report time-of-day**: the before-open / after-close marker is not available from the data source that carries actuals, so it is not shown. Rows sort and filter on report date alone. Recorded as a deliberate loss in `research.md` D4, not an oversight.
- **Duplicate symbols in a window**: a symbol appearing more than once for the same window resolves to a single row using the most recently updated record.
- **Filter interaction**: date, revenue, EPS, and the big-movers toggle combine as AND; changing one never silently resets another.
- **Big movers on a forward-looking window**: turning the toggle on while the window contains only future dates empties the table; the empty state must name the toggle as the cause rather than implying no companies report.
- **Provider unavailable or rate-limited**: the page shows the most recent usable data with a staleness indication, or a clear error state — never an empty table that reads as "nobody reports this week."
- **Rapid preset clicking**: a slow response for an abandoned window must never replace the data for the window the user has since settled on.
- **Partially typed custom date**: an incomplete or unparseable date in a custom input must not trigger a request or clear the current results.
- **Failed refetch**: if the request for a newly selected window fails, the previously displayed window's rows must not be silently presented as if they matched the new range; the mismatch must be surfaced.
- **Filter state on revisit**: returning to the page within the same session restores the last-used window rather than snapping back to the default.

## Requirements *(mandatory)*

### Functional Requirements

**Page load and controls**

- **FR-000**: The page MUST load its earnings data automatically on arrival, with no manual trigger. There MUST be no scan, search, or refresh button the user has to press to see results.
- **FR-000a**: All filters MUST arrive pre-set to their default positions so the page is useful before the user touches any control. The defaults are: date window today−2 through today+2, minimum revenue $10M, minimum EPS magnitude $0.01, big-movers toggle off.
- **FR-000b**: The manually triggered earnings scan and its separate ranked-candidate table MUST be removed from this page. The filtered calendar becomes the entire page.
- **FR-000c**: While the initial load is in flight, the page MUST show a loading state rather than an empty table.

**Date range filtering**

- **FR-001**: The earnings page MUST provide a set of one-click date range presets that each select a complete window in a single interaction. The set MUST cover, at minimum: today only, ±2 days, the last 7 days, the next 7 days, ±2 weeks, and ±1 month.
- **FR-001a**: The page MUST also provide two custom date inputs — a start and an end — for windows the presets do not cover.
- **FR-001b**: The currently active preset MUST be visually indicated. Entering custom dates that do not match any preset MUST clear that indication rather than leaving a preset falsely highlighted.
- **FR-001c**: Selecting a preset MUST populate the custom date inputs with the dates it resolved to, so the active window is always readable as concrete dates.
- **FR-002**: On first load in a session, the ±2 days preset MUST be active, giving a window of two days before through two days after the current date, inclusive.
- **FR-003**: The custom date inputs MUST accept dates in the past and in the future, spanning at least 30 days back and 30 days forward from today.
- **FR-004**: The control MUST prevent an inverted range where the start falls after the end, and MUST NOT issue a request for an invalid range.
- **FR-005**: The visible table MUST contain only companies whose report date falls inside the selected inclusive window, and MUST update when the window changes without a full page reload.
- **FR-006**: The active window MUST be displayed as human-readable dates alongside the count of companies it contains.

**Reported results and surprise**

- **FR-007**: For each company in the window, the system MUST show estimated EPS and estimated revenue when available.
- **FR-008**: For each company whose actuals have been published, the system MUST additionally show actual EPS and actual revenue.
- **FR-009**: The system MUST compute and display an EPS surprise as the signed percentage difference between actual and estimate, taken relative to the absolute value of the estimate.
- **FR-010**: The system MUST compute and display a revenue surprise using the same signed-percentage definition.
- **FR-011**: Surprise MUST be suppressed and labeled unavailable when the estimate is missing, the estimate is zero, or the actual is missing — it MUST NOT be rendered as zero or as a beat.
- **FR-012**: Beats and misses MUST be visually distinguishable at a glance, not by sign character alone.
- **FR-013**: Each row MUST indicate its reporting state: not yet reported, reported with results, or reported and awaiting results.
- **FR-014**: Missing numeric values MUST render as an explicit placeholder rather than as blank, zero, or a raw null.

**Noise reduction and ordering**

- **FR-015**: The page MUST provide a minimum-revenue range control that excludes companies whose revenue figure — actual when reported, otherwise estimate — falls below the selected threshold. It MUST default to $10M and be adjustable down to zero (no revenue filtering).
- **FR-016**: The page MUST provide a minimum-EPS-magnitude range control that excludes companies whose EPS figure falls below the selected threshold in absolute terms, so that large losses are treated as significant rather than filtered out. It MUST default to $0.01 and be adjustable down to zero.
- **FR-016a**: The page MUST provide a "big movers only" toggle, separate from the two size sliders, that narrows the table to companies whose absolute EPS surprise or absolute revenue surprise meets or exceeds 10%.
- **FR-016b**: While the "big movers only" toggle is on, companies that have not yet reported, and companies that reported without a computable surprise, MUST be excluded — the toggle is a results filter and has nothing to measure for them.
- **FR-016c**: The toggle MUST be off by default, and turning it off MUST restore every row the other filters allow.
- **FR-016d**: The toggle's effect MUST be self-evident: when it is on and rows are hidden as a result, the page MUST say so, so the user never mistakes a filtered view for a quiet earnings day.
- **FR-017**: Companies with no value for an active size filter MUST be excluded while that filter sits above its minimum, and MUST be included when it sits at its minimum.
- **FR-018**: All active filters MUST combine as a logical AND, and changing one MUST NOT reset another.
- **FR-019**: The table MUST always be ordered by market capitalization, largest first, independent of report date and of which filters are active. This ordering is fixed and not user-overridable.
- **FR-020**: The existing minimum market-capitalization screen MUST continue to apply, so sub-threshold listings such as shells, warrants, and thin foreign listings never enter the table.
- **FR-021**: The page MUST display the count of companies currently visible and, when filters exclude rows, the count before filtering.

**Navigation**

- **FR-022**: Each ticker symbol in the earnings table MUST be a link to that ticker's existing stock detail page.
- **FR-023**: Ticker links MUST be keyboard-accessible and visually identifiable as links.
- **FR-024**: Activating a ticker link MUST NOT trigger the row's queue-for-analysis action.

**Data and resilience**

- **FR-025**: Reported actuals and estimates MUST be sourced from an earnings calendar covering both past and future dates, so that a backward-looking window returns results rather than an empty table.
- **FR-026**: This feature MUST NOT introduce any new persisted storage. No new stored collection, table, or precomputed record is created for calendar entries, actuals, or surprise values — the page reads from the provider feed and derives what it displays at request time.
- **FR-026a**: Surprise values, beat/miss classification, and reporting state MUST be derived on read from the fetched estimate and actual figures. They MUST NOT be stored, precomputed, or backfilled.
- **FR-026b**: Provider responses MUST still pass through the project's existing short-lived response cache so that the provider's daily request budget is protected. This cache is a rate-limit guard holding raw responses for a bounded interval, not a persisted data model, and it MUST NOT be treated as a source of record.
- **FR-026c**: The page MUST NOT issue a provider request for every filter adjustment: only date window changes reach the provider, one per preset click or committed custom date, and cache-checked first (see FR-027a, FR-027d).
- **FR-027**: The page MUST request exactly the currently selected date window. Changing the date range MUST trigger a new request for the new window rather than reusing a wider preloaded set.
- **FR-027a**: Selecting a preset MUST result in exactly one provider request. Custom date entry MUST request only once the date is committed, not on each keystroke or partial date.
- **FR-027b**: The revenue slider, EPS slider, and big-movers toggle MUST filter rows already held by the client and MUST NOT trigger any provider request.
- **FR-027c**: While a new window is being fetched, the page MUST keep the previous rows visible with a loading indication rather than blanking the table, so adjusting the range never flashes an empty or misleading view.
- **FR-027d**: Re-selecting a window that was already requested within the cache interval MUST be served from the existing response cache without a new provider call.
- **FR-027e**: Out-of-order responses MUST NOT overwrite newer results — if a slow response for an earlier window arrives after a newer one, the newer window's data stays displayed.
- **FR-028**: When the provider is unavailable or rate-limited, the page MUST serve the most recent cached data with a visible staleness indication, or show an explicit error state — never a silently empty table.
- **FR-029**: The last-published-update timestamp for a company's figures MUST be available to the user, at minimum on the row's detail or hover, so a stale actual can be distinguished from a fresh one.

### Key Entities

None of the entities below are persisted by this feature — they describe the shape of data
read from the provider and held in memory for the current view (see FR-026).

- **Earnings Calendar Entry**: One company's scheduled or completed report for a specific date. Attributes: ticker symbol, company name, report date, estimated EPS, actual EPS, estimated revenue, actual revenue, last-updated timestamp, market capitalization, sector, reporting state.
- **Surprise Result**: The derived comparison for a reported entry, computed on read and never stored. Attributes: EPS surprise percentage, revenue surprise percentage, beat/miss classification, and an availability flag for when the comparison cannot be computed.
- **Filter State**: The user's current view configuration. Attributes: window start date, window end date, minimum revenue threshold, minimum EPS magnitude threshold, big-movers-only flag. Persists for the duration of the session.
- **Reference Universe**: The market-cap, company-name, and sector source used to screen and order the calendar. Already exists in the system.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On first load with no user interaction — no button pressed — the earnings table shows only companies reporting within today−2 through today+2.
- **SC-001a**: The page presents zero manual trigger controls; a user who never clicks anything still sees a fully filtered, ordered table.
- **SC-001b**: With default filters applied, every listing whose revenue and EPS figures are entirely unpublished is absent from the table, and every company with published figures above the defaults is present — the defaults remove noise without hiding covered companies.
- **SC-002**: The default view renders at least 90% fewer rows than the current forward-looking default view during a typical earnings week.
- **SC-003**: A user can identify the largest company reporting today and whether it beat or missed within 10 seconds of the page loading, without scrolling past the first screen.
- **SC-004**: Adjusting the size sliders or the big-movers toggle updates the visible table in under 200ms, with no network round trip and no visible full-page reload.
- **SC-004a**: Changing the date range shows the updated window in under 2 seconds in 95% of interactions, keeping the prior rows visible under a loading indication until the new ones arrive.
- **SC-005**: For companies that reported inside the selected window, at least 95% of those with published actuals display both an actual and a surprise value; the remainder legitimately lack an estimate.
- **SC-006**: Zero rows display a computed surprise where the underlying estimate is missing or zero.
- **SC-007**: 100% of visible rows appear in descending market-cap order, verified across at least three different filter combinations.
- **SC-008**: Every ticker in the table navigates to the correct stock detail page when activated, verified across the full visible set.
- **SC-009**: Adjusting the revenue slider, the EPS slider, or the big-movers toggle triggers zero provider requests, no matter how many times they are moved.
- **SC-009a**: Each date preset click results in exactly one provider request; clicking through every preset in the set issues no more requests than there are presets.
- **SC-010**: With the provider forced to fail, the page still renders either cached rows marked stale or an explicit error message — never an empty table without explanation.

## Assumptions

- The earnings calendar provider offers a single feed covering both past-dated entries (with actuals) and future-dated entries (estimates only), keyed by symbol and date, matching the sample the user supplied. Dash values in that sample represent genuinely unavailable figures, not zeroes.
- Market capitalization, company name, and sector continue to come from the existing reference universe, which already enforces the minimum-cap screen; symbols absent from that universe do not appear on the page.
- "Ordered by market cap" means descending, largest first, which is why report date is no longer the primary sort. Report date remains visible on every row so the user can still see when each company reports.
- The revenue and EPS sliders are size floors that remove small and thinly-covered names. Surprise magnitude is filtered separately, by the "big movers only" toggle, so the two concerns stay independent: the sliders control which companies are worth listing, the toggle controls whether to show only those whose results were dramatic.
- The date presets and custom inputs operate on calendar days using the same timezone convention the existing calendar already uses. Weekends and holidays are selectable but simply contain no reporters, which is why the preset set is built from ±N-day spans rather than trading days.
- Presets resolve relative to the current date each time they are clicked, so a preset selected before midnight and re-clicked after it yields a different window. The active window is always shown as concrete dates (FR-001c) so this is never hidden from the user.
- Filter state persists for the browser session only; it is not stored server-side or across sessions.
- "No storage" means no new persisted domain data: no earnings collection, no saved surprise records, no backfill job. The existing short-lived response cache is retained because the provider's daily request budget is a hard project constraint and an uncached page would spend it on page refreshes alone; it holds raw responses briefly and is discarded, not queried as a source of record.
- The earnings page becomes a single auto-loading filtered table. The manually triggered scan, its controls, and its ranked-candidate table are removed from this page. The scan's backend job and worker are not deleted by this feature, but they are no longer reachable from the earnings page — if that capability is wanted later it needs its own entry point.
- The per-row queue-for-analysis action and the read-only nature of the calendar endpoint are preserved.
- Desktop browser is the primary target; filter controls should remain usable at narrower widths, but a dedicated mobile layout is out of scope.
- Provider credentials are already configured in the project's settings; no new credential handling is introduced.

## Out of Scope

- Filtering or sorting by sector.
- Restoring the before-open / after-close marker, which this feature drops (see Edge Cases).
- Sorting by surprise magnitude, or any user-selectable sort order (market cap ordering is fixed).
- Historical surprise trends beyond the selected window; the existing per-ticker earnings history view already covers this.
- Alerts, notifications, or watchlist integration driven by surprise results.
- Changes to the earnings scoring scan's algorithm or its candidate ranking.
- Any new persisted store, historical archive, or backfill of earnings actuals and surprises.
- Intraday or real-time push updates as results are published.
- Persisting filter preferences across sessions or devices.

## Dependencies

- An earnings calendar data source covering past and future dates, including actual and estimated EPS and revenue plus a last-updated timestamp.
- The existing reference universe for market capitalization, company name, and sector.
- The existing cache-first data layer and its rate-limit budget guard.
- The existing stock detail page route, which ticker links target.
