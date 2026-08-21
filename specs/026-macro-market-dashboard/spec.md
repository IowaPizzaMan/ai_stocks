# Feature Specification: Macro Market Dashboard

**Feature Branch**: `026-macro-market-dashboard`

**Created**: 2026-08-21

**Status**: Draft

**Input**: User description: "Lets work on the Macro page. For the market flow I want to add the NAMO as well. Then it looks like that graph is duplicated on this page. Lets just keep the one with the yellow outline. Below that graph there is a technology summary it looks like, not sure why this is specific to technology, I am wanting this page to be a more macro view of things, getting sector specific will be for the sector page at a later time. Look at some of these API routes to get data, think about what a stock trader needs to know to understand what is going on in the market: treasury-rates, economic-indicators, economic-calendar, market-risk-premium. I would love to have a yield curve on there, 10/2 and maybe even 30/10/2 to show the full picture."

## Overview

The Macro page today shows three things: a pinned market-flow card with a breadth chart inside it, a second copy of that same breadth chart directly below it, and a grid of per-sector macro commentary cards (of which only Technology is currently populated). Two of those three are wrong for the page: the chart is duplicated, and sector-level commentary belongs on the Sectors page, not here.

This feature turns the Macro page into a single market-wide dashboard a trader can read in under a minute to answer "what is the market environment right now?" — breadth on both exchanges, the shape and direction of the yield curve, what economic releases are coming and how the last ones landed, and the standing growth/inflation/risk backdrop.

## Clarifications

### Session 2026-08-21

- Q: When there is no recent market-flow event, should the Macro page still show a breadth chart? → A: The breadth panel always renders. An active market-flow event decorates it with the event headline and a divergence-tinted outline; with no active event it renders in a neutral outline showing the chart and the current divergence state.
- Q: How should NYMO and NAMO be laid out inside the breadth panel — two stacked panes, or two lines sharing one oscillator pane? → A: One shared oscillator pane carrying both lines on the same ±60 scale, below a SPY pane. Divergence overlay drawn against the NYMO line only.
- Q: Should the system backfill Treasury rate history on first run, or only accumulate it going forward? → A: One-time paginated backfill of approximately 2 years of daily rates at first run (the provider caps each request at roughly 3 months), then a single incremental call per day thereafter.
- Q: Which source should supply the growth / inflation / employment / policy-rate tiles? → A: The market-data provider's economic-indicators series, as the single source for these tiles. Its shallow per-series history and lagging release dates are accepted, and must be surfaced in the UI rather than hidden (see FR-024a, FR-026a).
- Q: For recent releases, should "beat / miss" mean above-or-below the estimate, or good-or-bad for the market? → A: Mechanical only — actual versus estimate labeled above / below / in line with the surprise magnitude, in neutral coloring. The page asserts no market-direction judgment and maintains no per-event polarity list.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A clean, non-duplicated breadth read across both exchanges (Priority: P1)

As a trader opening the Macro page, I see exactly one market-breadth panel — the highlighted market-flow card — and it shows me the McClellan oscillator for **both** the NYSE (NYMO) and the Nasdaq (NAMO) against SPY, so I can tell whether the two exchanges confirm each other or are pulling apart. Nothing sector-specific appears on the page.

**Why this priority**: This is a direct correction of what is on screen today — a duplicated chart and an out-of-place sector card. It is the smallest change that makes the page correct, and it can ship without any new data source.

**Independent Test**: Load the Macro page with breadth data and a live market-flow event present. Exactly one breadth visualization renders, it is the outlined market-flow card, it plots both NYMO and NAMO, and no sector commentary card appears anywhere on the page.

**Acceptance Scenarios**:

1. **Given** breadth data and an active market-flow event exist, **When** the Macro page loads, **Then** exactly one breadth visualization is rendered and it is the one inside the outlined market-flow card.
2. **Given** the breadth panel is rendered, **When** the user views it, **Then** both the NYSE and the Nasdaq McClellan oscillator series are visible as separately identifiable lines within one oscillator pane, on a shared date axis with SPY above them.
3. **Given** a breadth divergence is currently detected, **When** the card renders, **Then** the divergence is drawn on the series it was measured against and its type and description are stated in words.
4. **Given** per-sector macro reads exist in the system, **When** the Macro page loads, **Then** no sector-specific card or commentary is rendered on the Macro page.
5. **Given** no breadth data has been computed yet, **When** the page loads, **Then** the breadth area shows a plain "not computed yet" state rather than an error or a blank frame.
6. **Given** breadth data exists but no market-flow event is active, **When** the page loads, **Then** the breadth panel still renders — in a neutral outline, without an event headline — showing both oscillators and the current divergence state.

---

### User Story 2 - The yield curve and where rates stand (Priority: P2)

As a trader, I want to see the current Treasury yield curve and how it has moved, including the key spreads (10y–2y, 30y–10y, and 10y–3m), so I can judge recession risk, the direction of policy expectations, and whether long-duration assets are getting cheaper or dearer.

**Why this priority**: The user called this out explicitly ("I would love to have a yield curve on there"). It is the single highest-signal macro visual for an equity trader and is available from one data call.

**Independent Test**: With Treasury rate data available, the page renders a curve across maturities plus the named spreads with their current values and inversion state, verifiable against the raw rates for the same date without any other part of the feature being built.

**Acceptance Scenarios**:

1. **Given** current Treasury rate data, **When** the Macro page loads, **Then** a yield curve is plotted across the full set of maturities (1-month through 30-year) for the most recent session, labeled with that session's date.
2. **Given** the curve is displayed, **When** the user views it, **Then** curves from approximately one month earlier and one year earlier are overlaid for comparison so the shift in the curve is visible, with each line distinguishable.
3. **Given** the curve data, **When** the page renders, **Then** the 10y–2y, 30y–10y and 10y–3m spreads are each shown with their current value in basis points and their change since the prior session.
4. **Given** any tracked spread is negative, **When** it is displayed, **Then** it is visually marked as inverted and labeled as such in text.
5. **Given** historical Treasury data, **When** the user views the spreads, **Then** each spread's recent trend over a rolling window is visible, so a curve that is steepening or flattening can be told apart from one that is merely inverted.
6. **Given** the Treasury data source is unreachable or over budget, **When** the page loads, **Then** the last known curve is shown with a visible "as of" age rather than an error state.

---

### User Story 3 - What is coming and how the last releases landed (Priority: P3)

As a trader planning the week, I want a forward-looking list of the economic releases that actually move US equities, with the consensus estimate and the previous reading, plus the results of recent releases showing where the actual landed against the estimate, so I know which days carry event risk and how recent data has been trending against expectations. I draw my own conclusion about what a given surprise means for the market.

**Why this priority**: Event risk is actionable but secondary to knowing the current environment; the page is still useful without it.

**Independent Test**: Load the page and confirm an upcoming-releases list and a recent-results list render with date, event name, previous, estimate, and (for past events) actual and surprise magnitude — verifiable against the source calendar for the same window.

**Acceptance Scenarios**:

1. **Given** calendar data is available, **When** the page loads, **Then** upcoming US economic releases within the next two weeks are listed in chronological order with date/time, event name, previous value, and consensus estimate.
2. **Given** the calendar contains events of varying market impact, **When** the list renders, **Then** only high- and medium-impact US events are shown, and each row's impact level is visible.
3. **Given** releases that have already reported in the trailing week, **When** the user views the recent-results list, **Then** each shows the actual value alongside the estimate, the size of the surprise, and a neutral above / below / in line label.
3a. **Given** a reported release came in above its estimate, **When** its row renders, **Then** it is labeled as above the estimate without any coloring or wording implying the result is good or bad for the market.
4. **Given** an upcoming event has no consensus estimate published, **When** its row renders, **Then** the estimate field reads as unavailable rather than showing a zero or a blank cell.
5. **Given** no qualifying events fall in the window, **When** the page loads, **Then** the section states that there are no major releases scheduled rather than rendering an empty box.

---

### User Story 4 - The standing growth, inflation and risk backdrop (Priority: P4)

As a trader, I want the headline macro indicators — GDP, inflation, unemployment, the policy rate — and the current US equity risk premium presented as a compact set of readings with their direction of travel, so I have the slow-moving backdrop in the same place as the fast-moving signals.

**Why this priority**: Useful orientation, but these move quarterly or monthly and are the least time-sensitive part of the page.

**Independent Test**: The indicator tiles render with a current value, the reading's own as-of date, and a direction versus the prior reading, independently of the breadth, curve, and calendar sections.

**Acceptance Scenarios**:

1. **Given** indicator data is available, **When** the page loads, **Then** headline readings for economic growth, inflation, employment and the policy rate are each shown with a value, the date that reading refers to, and — where a prior reading exists — its change versus that prior reading.
1a. **Given** a series returns only a single reading and none was retained earlier, **When** its tile renders, **Then** the value and its date are shown with no direction indicator, rather than a direction of zero or "unchanged".
1b. **Given** an indicator's as-of date is more than 90 days old, **When** its tile renders, **Then** it is visibly marked as lagging alongside its true as-of date.
2. **Given** an indicator is reported quarterly or monthly, **When** it is displayed, **Then** its own as-of date is shown on the tile, so a value several weeks old is never mistaken for today's.
3. **Given** risk-premium data is available, **When** the page loads, **Then** the US equity risk premium is shown as a single reading, labeled as a slow-moving valuation input rather than a live market quote.
4. **Given** one indicator fails to load while others succeed, **When** the page renders, **Then** the successful readings still display and only the failed one shows as unavailable.

---

### Edge Cases

- **Partial data**: Any one of breadth, curve, calendar or indicators being unavailable must not prevent the other sections from rendering. Each section fails independently and visibly.
- **Stale data served on purpose**: When a provider is unreachable or the daily call budget is spent, the page must serve the last known values with a visible age rather than an error — consistent with the project's fail-soft rule.
- **Nothing at all**: With no data in any section, the page shows a single explanatory empty state, not four separate error boxes.
- **Non-trading days**: On weekends and holidays the most recent Treasury session is several days old; the "as of" date must reflect the actual session, and spread "change since prior session" must compare to the prior *trading* session, not the prior calendar day.
- **Missing maturities**: If a maturity is absent from a session's data, the curve must skip that point rather than plotting it as zero.
- **Single-reading indicator**: When a series returns only one reading and nothing has been retained from a prior fetch, the tile shows the value and its date with no direction indicator — never a fabricated "unchanged".
- **Long-lagging indicator print**: A reading months behind the current date must render with its true as-of date and a visible lagging marker, not be suppressed or silently refreshed to today.
- **Divergence measured on one exchange**: When a divergence is detected against NYMO only, the NAMO series must still display without falsely implying the same divergence was measured there.
- **Timezone**: Economic-calendar timestamps must be presented in a consistent, explicitly labeled timezone so a release time is never off by hours.
- **Event-risk window boundary**: An event happening later today must appear in the upcoming list, not be dropped as already past.
- **Reported release with no estimate**: A release that published an actual but never had a consensus estimate must show the actual with the comparison marked unavailable, rather than being labeled in line by default.

## Requirements *(mandatory)*

### Functional Requirements

**Page composition and cleanup**

- **FR-001**: The Macro page MUST render exactly one market-breadth visualization; the duplicate standalone breadth chart currently rendered below the market-flow card MUST be removed.
- **FR-002**: The retained breadth visualization MUST be the one inside the outlined market-flow card.
- **FR-002a**: The breadth panel MUST render whenever breadth data exists, independently of whether a market-flow event is active. An active market-flow event decorates the panel with its headline and a divergence-tinted outline; with no active event the panel renders in a neutral outline and still shows the chart and the current divergence state.
- **FR-003**: The Macro page MUST NOT render per-sector macro commentary. Sector-level content is out of scope for this page and is deferred to the Sectors page.
- **FR-004**: Removing sector commentary from the page MUST NOT stop the system from producing or storing sector macro reads, so a future Sectors-page feature can surface them without re-deriving the data.
- **FR-005**: The page MUST present its sections in a fixed order reflecting decreasing time-sensitivity: market flow and breadth, then rates and the yield curve, then the economic calendar, then the standing indicator backdrop.
- **FR-006**: Every section MUST display an "as of" indicator for the data it shows.

**Breadth**

- **FR-007**: The breadth panel MUST display both the NYSE McClellan oscillator (NYMO) and the Nasdaq McClellan oscillator (NAMO) as two visually distinguishable lines within a **single** oscillator pane on one shared value scale, positioned below a SPY price pane on the same date axis. Both series MUST be labeled such that either line can be identified without interaction.
- **FR-008**: A detected breadth divergence MUST be drawn on the oscillator series it was measured against, and MUST NOT be drawn on the other series.
- **FR-009**: The card MUST state the current divergence type and its plain-language description when one is present.
- **FR-010**: Oscillator overbought/oversold reference levels MUST remain visible on the oscillator panes.

**Yield curve and rates**

- **FR-011**: The page MUST plot the Treasury yield curve across all reported maturities from 1 month to 30 years for the most recent available session.
- **FR-012**: The curve display MUST overlay prior-period curves for approximately one month prior and one year prior, so the shift in the curve is directly visible. Both overlays are expected to be available from first run, since history is backfilled (FR-017a).
- **FR-013**: The page MUST display the 10y–2y, 30y–10y, and 10y–3m spreads with current values expressed in basis points.
- **FR-014**: Each displayed spread MUST show its change versus the prior trading session.
- **FR-015**: A negative spread MUST be marked as inverted both visually and in text.
- **FR-016**: Each spread MUST show its recent trend across a rolling historical window, so steepening and flattening are distinguishable from the level alone.
- **FR-017**: The system MUST retain Treasury rate history locally, covering at least the trailing 2 years, so FR-012 and FR-016 are satisfied without re-fetching history on every page load.
- **FR-017a**: On first run the system MUST backfill approximately 2 years of daily Treasury rates, requesting them in windows small enough to stay under the provider's per-request row cap, and MUST NOT repeat the backfill on subsequent runs.
- **FR-017b**: After backfill, the system MUST extend its rate history with at most one provider call per day, and MUST tolerate gaps (weekends, holidays, a missed day) by fetching from the last stored session forward rather than assuming yesterday.

**Economic calendar**

- **FR-018**: The page MUST list upcoming US economic releases occurring within the next 14 days, in chronological order.
- **FR-019**: The list MUST be filtered to US events of high or medium market impact, and MUST show each row's impact level.
- **FR-020**: Each upcoming row MUST show the scheduled date and time, event name, previous reading, and consensus estimate; a missing estimate MUST render as explicitly unavailable.
- **FR-021**: The page MUST list US releases from the trailing 7 days that have reported, showing the actual value against the estimate and labeling each as above, below, or in line with the estimate.
- **FR-021a**: Each reported release MUST show the magnitude of the surprise (the difference between actual and estimate) alongside the label.
- **FR-021b**: The above/below/in-line label MUST be presented neutrally and MUST NOT assert whether the result is good or bad for the market. The system MUST NOT maintain a per-event polarity mapping, and MUST NOT color releases by implied market direction.
- **FR-021c**: A release with no published estimate MUST show its actual value with the comparison explicitly unavailable, rather than being labeled above, below, or in line.
- **FR-022**: Release times MUST be rendered in a single, explicitly labeled timezone.
- **FR-023**: An event scheduled later on the current day MUST appear in the upcoming list.

**Indicator backdrop**

- **FR-024**: The page MUST display headline readings for economic growth, inflation, employment, and the policy rate, sourced from the market-data provider's economic-indicators series, each with a value, the date that reading refers to, and its direction versus the prior reading.
- **FR-024a**: Direction versus the prior reading MUST be derived from a second reading of the same series where one is available — from the source's own response, or failing that from a previously retained reading. When no prior reading exists for a series, the tile MUST omit the direction indicator rather than displaying it as flat, zero, or unchanged.
- **FR-024b**: The system MUST retain each indicator reading it fetches, so that series returning only a single reading per request accumulate a prior value over time and satisfy FR-024a on later loads.
- **FR-024c**: Where a provider series offers materially deeper history than its headline equivalent, the deeper series SHOULD be preferred for that tile, so direction and trend are available immediately.
- **FR-025**: The page MUST display the current US equity risk premium, labeled as a slow-moving valuation input.
- **FR-026**: Each indicator MUST show its own as-of date independently of the page-level freshness line.
- **FR-026a**: An indicator reading whose as-of date is more than 90 days old MUST be visibly marked as lagging, so a stale print is never read as a current one. This is expected to be the normal case for several series from this source, not an error condition.

**Resilience and cost**

- **FR-027**: Each section MUST render independently; a failure in one section MUST NOT prevent any other section from rendering.
- **FR-028**: When a data provider is unreachable, errors, or the daily call budget is exhausted, the affected section MUST serve the last known values marked with their age, rather than surfacing an error state.
- **FR-029**: External macro data MUST be served cache-first, with refresh frequency matched to how often each series actually changes: Treasury rates and the calendar at most daily, indicators and the risk premium less often.
- **FR-030**: Repeated page loads within a cache window MUST NOT trigger additional external provider calls.
- **FR-031**: When every section is empty, the page MUST render a single explanatory empty state and MUST NOT render an error.

### Key Entities

- **Treasury Curve Snapshot**: One trading session's yields across every reported maturity (1m, 2m, 3m, 6m, 1y, 2y, 3y, 5y, 7y, 10y, 20y, 30y), keyed by session date. At least 2 years of snapshots are retained — seeded by a one-time backfill, then extended daily — so prior-period curves and spread trends are derived from local history rather than refetched.
- **Yield Spread**: A named difference between two maturities (10y–2y, 30y–10y, 10y–3m) with a current value, a change versus the prior session, an inverted flag, and a recent series for its trend.
- **Economic Event**: A scheduled release with date/time, country, event name, impact level, previous value, consensus estimate, actual value (once reported), unit, and — once reported and where an estimate exists — a neutral above/below/in-line comparison plus the surprise magnitude. Carries no good/bad polarity.
- **Economic Indicator Reading**: A named macro series (growth, inflation, employment, policy rate) with a value, the period the value refers to, and an optional prior reading used for direction. Readings are retained as they are fetched, so series that expose only one reading per request accumulate a prior value over time; direction is absent until one exists.
- **Equity Risk Premium**: The current US total equity risk premium and country risk premium, with the date it was last revised.
- **Market Breadth Series** *(existing)*: SPY closes plus the NYSE and Nasdaq McClellan oscillator series over a lookback window, with the current divergence state and its resolved history.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The Macro page renders exactly one breadth visualization — down from two today — and zero sector-specific cards.
- **SC-002**: A trader can determine, without leaving the page or clicking anything, whether NYSE and Nasdaq breadth agree, whether the yield curve is inverted, and what the next major economic release is.
- **SC-003**: The current value and inversion status of all three tracked spreads (10y–2y, 30y–10y, 10y–3m) are visible in a single glance without interaction.
- **SC-004**: Every displayed number on the page carries a visible as-of date or age, so no reading can be mistaken for being more current than it is.
- **SC-004a**: No release outcome on the page is colored or worded as good or bad for the market; every outcome is stated as a neutral comparison against its estimate.
- **SC-005**: With any single data source unavailable, the page still renders every other section successfully, and the unavailable section shows either aged data or a plain unavailable message — never an error page.
- **SC-006**: Repeated loads of the Macro page within the same cache window consume zero additional external provider calls.
- **SC-007**: The page renders its first meaningful content within 2 seconds on a warm cache.
- **SC-008**: The page is readable and fully usable at a 1280px-wide viewport without horizontal scrolling.

## Assumptions

- **Both oscillators shown at once, not toggled**: "Add the NAMO as well" is read as wanting NYMO and NAMO visible together, since the point of having both is comparing them. The existing toggle on the removed duplicate chart is not carried over; both series are shown simultaneously on one shared scale (see Clarifications).
- **"The one with the yellow outline" is the market-flow card**: The outlined/tinted card is the market-flow event card, whose border color reflects the divergence type. That card and its embedded chart are what the page keeps.
- **Sector reads are removed from the page, not deleted from the system**: The system keeps producing and serving them; only the Macro page stops rendering them. Relocating them to the Sectors page is a separate, later feature.
- **"US only" for the calendar**: The source calendar covers every country. Only US events are shown, since the audience trades US equities. Major foreign central-bank decisions are out of scope for this iteration.
- **Impact filtering**: The raw calendar is dominated by low-impact rows (bill auctions, rig counts). Filtering to high- and medium-impact US events is what makes the section readable.
- **The calendar reports, it does not interpret**: Release outcomes are stated mechanically against the estimate. A hot inflation print and a strong payrolls print are both simply "above estimate"; the trader supplies the market read. This deliberately avoids a per-event polarity list that would rot and eventually mislabel the one release that mattered.
- **The risk premium is a slow-moving reference, not a signal**: The source revises it infrequently and it is a valuation input rather than a market reading; it is presented as a single labeled tile, not charted.
- **Indicator history depth is shallow by design of the source**: The economic-indicators source returns only one to three readings per series and does not honor date-range requests, so "direction versus prior reading" comes from whatever the source returns plus readings retained from earlier fetches. Some tiles will therefore show no direction on first run and gain one later (FR-024a, FR-024b).
- **Indicator prints lag substantially**: Readings from this source have been observed running several months behind the current date. This is accepted as a property of the source rather than treated as a fault; FR-026a requires it be shown rather than hidden. The tiles are positioned last on the page precisely because they are the slowest-moving content.
- **Comparison curves come from backfilled history**: Both the one-month and one-year prior curves are available from first run via the initial backfill (FR-017a). If a requested comparison session is genuinely missing from history, that overlay is omitted rather than approximated from a nearby-but-wrong date.
- **The indicator tiles use one source, not two**: The market-data provider's economic-indicators series is the single source for the growth/inflation/employment/policy-rate tiles on this page. Macro series retained elsewhere in the system for other consumers are left untouched and are not blended into these tiles, so a tile's number always traces to one origin.
- **No new page or route**: This is a rebuild of the existing `/macro` page. Navigation and routing are unchanged.
- **Read-only page**: No user-configurable filters, watchlists, or saved preferences on this page in this iteration.

## Out of Scope

- Sector-level macro commentary and its relocation to the Sectors page.
- Alerting or notifications on economic releases or curve inversions.
- Non-US economic events and foreign central-bank calendars.
- Historical backtesting of macro signals against market returns.
- User-configurable indicator selection or dashboard layout.

## Dependencies

- Existing market-breadth computation (NYMO/NAMO, SPY, divergence detection) continues to run and populate its cache.
- Treasury rates, economic indicators, economic calendar, and market risk premium are all available from the existing paid market-data provider, accessed through the project's budget-guarded, cache-first data layer.
- The economic-indicators series from that provider are accepted with known limitations — one to three readings per request, no working date-range filter, and release dates that can lag the present by months. FR-024a/FR-024b/FR-026a exist to make those limitations visible and non-breaking.
- Sufficient locally retained history to support prior-period curve overlays and spread trends.
