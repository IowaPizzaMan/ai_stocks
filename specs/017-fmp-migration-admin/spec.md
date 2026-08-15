# Feature Specification: FMP Paid-Tier Migration & Admin Data Operations

**Feature Branch**: `017-fmp-migration-admin`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "I upgraded my FMP subscription from the free tier to the paid tier. I want to switch everything from the yahoo ticket to this api. I want also review the FMP api for things I'm not pulling in. I'm not interested in anything crypto. I want to think about how I can visual take in all this infomation as well. I also need an admin section in my front end where I can kick off processes that are not stock specific to collect data like the superinvstory stuff. and maybe it makes sense to pull in things from this page from FMP outside what my agents currenlty do since those are basically needing a ticket and then run."

## Overview

The project's Financial Modeling Prep (FMP) subscription has moved from the free tier (250 calls/day) to a paid tier, removing the budget pressure that originally forced Yahoo Finance to be the primary source for price history, market breadth inputs, and several fundamentals. This feature covers four connected outcomes:

1. **Source migration** — retire Yahoo Finance as a data source and serve everything it currently provides from FMP instead.
2. **Coverage expansion** — a systematic review of what the paid FMP subscription offers that the system does not yet collect (excluding all crypto data), with an explicit adopt/defer/reject decision per dataset.
3. **Visual consumption** — a way for the user to actually take in the newly available market-wide information, not just store it.
4. **Admin operations** — a dedicated admin section in the frontend where the user can manually kick off and monitor data-collection processes that are not tied to a single ticker (fund/ETF-holdings pulls, market breadth refresh, earnings-calendar scans, and the new market-wide FMP collections), which today have no user-facing trigger because the existing agent flow assumes "give me a ticker, then run."

**Entitlement decisions (2026-08-15, user-verified against the live subscription)**: insider trading, senate/house congressional trading, ETF & fund holdings, market news, company info, and the economics route (treasury rates, economic indicators, economic data releases, market risk premium) are entitled and adopted. **13F institutional holdings and earnings-call transcripts are NOT entitled and are out of scope** — the user will pursue those outside FMP later. The FMP ETF & fund holdings dataset **replaces the Dataroma superinvestor scraper**, which is retired.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Yahoo Finance Fully Replaced by FMP (Priority: P1)

As the system's operator, I want every piece of data currently sourced from Yahoo Finance to come from FMP instead, so that the system depends on one paid, supported provider rather than an unofficial free source that fails on some of my tickers and could break without notice.

**Why this priority**: Everything else in this feature builds on FMP being the trusted primary source. Yahoo coverage gaps (tickers returning empty/errored history) are a known existing problem, and the paid FMP tier is already paid for — this is the core value unlock.

**Independent Test**: Can be fully tested by exercising every existing data view and analysis flow (price charts, breadth signals, fundamentals, earnings dates) and confirming the data is present, correct, and no longer fetched from Yahoo Finance.

**Acceptance Scenarios**:

1. **Given** a ticker already tracked in the system, **When** its price history is requested for any existing chart or analysis, **Then** the data is served from FMP (or its cache) and matches the ticker's actual trading history.
2. **Given** a ticker that previously failed on Yahoo Finance, **When** it is analyzed, **Then** price history now loads successfully from FMP.
3. **Given** the daily market-breadth computation over the index universes, **When** it runs, **Then** all constituent closing prices come from FMP and the breadth signals still compute to sane values.
4. **Given** the migration is complete, **When** the codebase and runtime are inspected, **Then** no live code path calls Yahoo Finance, and the data-sources documentation reflects the new ownership map.
5. **Given** a data item Yahoo provided that FMP does not offer on the current plan, **When** the migration is planned, **Then** that item is explicitly listed with a decision (serve from an already-integrated alternate source, or consciously dropped) rather than silently disappearing.

---

### User Story 2 - Admin Section for Market-Wide Data Jobs (Priority: P2)

As the system's operator, I want an admin area in the frontend that lists every market-wide (non-ticker-specific) data-collection process — fund/ETF-holdings pulls, market-breadth refresh, earnings-calendar scans, and the new market-wide FMP collections — and lets me kick each one off on demand and see whether it succeeded, so that I no longer need terminal access or a specific ticker to keep global datasets fresh.

**Why this priority**: The user explicitly needs this today for fund-holdings data (which replaces the superinvestor scraper), and every new market-wide dataset adopted from User Story 3 needs a trigger and visibility to be usable. It is valuable even before any new datasets are added.

**Independent Test**: Can be fully tested by opening the admin section, triggering one existing global process (e.g., the market-breadth refresh), and observing the run reach a terminal status with a visible outcome — without touching any other part of this feature.

**Acceptance Scenarios**:

1. **Given** the admin section, **When** the user opens it, **Then** they see every available market-wide job with its last run time, last run outcome, and a description of what data it collects.
2. **Given** a listed job, **When** the user triggers it, **Then** the job is queued/started, the UI confirms it was accepted, and its status is visible as it progresses to success or failure.
3. **Given** a job that is already running, **When** the user attempts to trigger it again, **Then** the system prevents or safely ignores the duplicate request and tells the user why.
4. **Given** a job that failed, **When** the user views it, **Then** they can see enough of the failure reason to decide whether to retry.
5. **Given** a completed job, **When** the user navigates to the page that displays that dataset, **Then** the newly collected data is visible.

---

### User Story 3 - FMP Coverage Gap Review & New Market-Wide Datasets (Priority: P3)

As the system's operator, I want a documented review of everything my paid FMP subscription offers that I am not currently collecting — explicitly excluding crypto — and I want the datasets judged worthwhile (particularly market-wide ones like analyst actions, sector performance, market movers, economic/IPO/dividend calendars, senate & house trading, and market-wide insider activity feeds) to actually be collected and stored, so that the subscription is fully exploited rather than used only for per-ticker financials.

**Why this priority**: High leverage but depends on the migration (P1) settling the FMP integration and on the admin section (P2) providing triggers for non-ticker collections. The review itself also feeds the visualization work (P4).

**Independent Test**: Can be tested by reading the produced gap-review document (every relevant FMP dataset family listed with an adopt/defer/reject decision and rationale) and by verifying that each "adopt" dataset has data landing in storage when its collection runs.

**Acceptance Scenarios**:

1. **Given** the paid FMP subscription, **When** the gap review is complete, **Then** a written inventory exists covering the plan's dataset families, each marked adopt / defer / reject with a one-line rationale, and containing zero crypto datasets marked adopt.
2. **Given** a dataset marked adopt, **When** its collection process runs (via the admin section for market-wide ones, or the existing per-ticker flow for ticker-scoped ones), **Then** the data is stored and retrievable.
3. **Given** the existing cache-first and budget-guard rules, **When** new datasets are collected, **Then** they respect the same cache discipline and the provider budget guard reflects the paid tier's actual limits instead of the old 250/day free limit.

---

### User Story 4 - Visual Consumption of Market-Wide Data (Priority: P4)

As the system's operator, I want the newly collected market-wide information presented visually — organized so I can absorb market conditions at a glance rather than reading raw records — so that the expanded data collection actually improves my decision-making.

**Why this priority**: Real value, but it can only be designed once it's known which datasets were adopted (P3) and it builds on data the earlier stories make available. Shipping the earlier stories without this still leaves the data queryable.

**Independent Test**: Can be tested by opening the market-wide views and confirming each adopted dataset from User Story 3 is visible somewhere reasonable, renders with real collected data, and answers "what is the market doing?" without requiring a ticker first.

**Acceptance Scenarios**:

1. **Given** adopted market-wide datasets with collected data, **When** the user opens the market-overview experience, **Then** each dataset is visible in a dedicated visual treatment (not raw tables of records) with an indication of how fresh the data is.
2. **Given** a market-wide visual (e.g., sector performance or market movers), **When** the user spots an interesting ticker, **Then** they can navigate from it to that ticker's existing detail view.
3. **Given** a dataset whose collection has never run, **When** its visual is shown, **Then** the user sees a clear empty state pointing them to the admin section rather than a broken or blank chart.

---

### Edge Cases

- What happens when FMP is down or rate-limits a request mid-migration? The system must degrade the same way it does today: serve stale cache where available, surface a clear "data unavailable" state where not, and never crash an analysis run.
- What happens to tickers that FMP itself does not cover (e.g., some OTC or foreign listings)? They must be flagged as uncovered rather than silently showing empty charts.
- What happens if a market-wide admin job runs long (e.g., a full superinvestor re-scrape)? Status must remain truthful without the frontend needing continuous live updates — the user can leave and come back to see the outcome.
- What happens when two datasets provide overlapping values (a known FMP issue between its ratio and metric families)? One canonical source per metric must be chosen; duplicates are not stored twice.
- What happens to historical data collected under Yahoo Finance? Existing stored history remains valid; the transition must not wipe or fork previously cached data, and any provider-level field differences (e.g., adjusted-close conventions) must be reconciled rather than mixed silently.
- What happens if the paid subscription lapses back to the free tier? The budget guard must be configurable so the system can be dialed back without code changes to survive on 250 calls/day again.

## Requirements *(mandatory)*

### Functional Requirements

**Migration (User Story 1)**

- **FR-001**: System MUST source all data currently obtained from Yahoo Finance — price history (OHLCV), index-universe closing prices for breadth computation, quote/company metadata, and any fundamentals or earnings fields still served by Yahoo — from FMP instead.
- **FR-002**: System MUST remove Yahoo Finance from all live data paths once migration is complete; no runtime behavior may depend on it.
- **FR-003**: The migration MUST produce an explicit disposition for every Yahoo-provided data item that FMP does not offer on the current plan: either served by an already-integrated alternate source or consciously dropped and documented. No data item may disappear silently.
- **FR-004**: All FMP calls, including newly migrated ones, MUST flow through the existing cache-first data layer and respect existing cache lifetimes.
- **FR-005**: The FMP budget guard MUST be updated to reflect the paid tier's actual limits, remain configurable (so a downgrade back to the free tier is a configuration change), and continue to fail soft — stale cache plus a logged warning, never a hard outage.
- **FR-006**: Previously cached data collected from Yahoo Finance MUST remain usable; the transition MUST NOT delete or corrupt existing stored history, and any systematic value differences between providers MUST be reconciled in one consistent convention.
- **FR-007**: The data-sources documentation (coverage map) MUST be updated to reflect the post-migration ownership of every data need.

**Admin Section (User Story 2)**

- **FR-008**: The frontend MUST provide an admin section listing every market-wide (non-ticker-specific) data-collection job, including at minimum: ETF & fund-holdings collection, market-breadth refresh, earnings-calendar scan, and each market-wide collection adopted under FR-013.
- **FR-009**: The user MUST be able to trigger any listed job on demand from the admin section, and triggering MUST use the same queueing mechanism as all other analysis/collection work.
- **FR-010**: The admin section MUST show, per job: a plain-language description of what it collects, its last run time, its last run outcome, and the current run's status when one is active. Status MUST be available on page load and manual refresh without continuous background polling.
- **FR-011**: The system MUST prevent duplicate concurrent runs of the same job and inform the user when a trigger is rejected for this reason.
- **FR-012**: A failed job run MUST record and surface a human-readable failure reason sufficient to decide between retrying and investigating.

**Coverage Expansion (User Story 3)**

- **FR-013**: A gap-review document MUST be produced enumerating the dataset families available on the paid FMP subscription that the system does not currently collect, each marked adopt / defer / reject with a one-line rationale. Crypto-related datasets MUST all be marked reject.
- **FR-014**: Every dataset marked adopt MUST have a working collection path: market-wide datasets triggerable from the admin section, ticker-scoped datasets integrated into the existing per-ticker flow.
- **FR-015**: Adopted datasets MUST be stored with enough provenance (source, collected-at time) to display data freshness to the user.
- **FR-016**: Where an adopted dataset overlaps a value already collected elsewhere, one canonical source per value MUST be designated; the system MUST NOT store competing duplicates.

**Visualization (User Story 4)**

- **FR-017**: Each adopted market-wide dataset MUST be viewable in the frontend through a visual treatment appropriate to the data (trend, ranking, calendar, flow — not raw record dumps), reachable without first selecting a ticker.
- **FR-018**: Every market-wide visual MUST display the freshness of its underlying data and a clear empty state (pointing to the admin section) when the data has never been collected.
- **FR-019**: Wherever a market-wide visual surfaces an individual ticker, the user MUST be able to navigate to that ticker's existing detail view.

**Adopted Datasets (user decisions, 2026-08-15)**

- **FR-020**: System MUST collect insider-trading data and senate/house congressional-trading data from FMP (both confirmed entitled). 13F institutional holdings and earnings-call transcripts MUST NOT be sourced from FMP (not entitled); sourcing them by other means is a separate future feature.
- **FR-021**: System MUST collect ETF & fund holdings from FMP, and this dataset REPLACES the Dataroma superinvestor scraper — the scraper and its collection process are retired. Existing superinvestor data already stored remains readable.
- **FR-022**: System MUST collect per-ticker stock news whenever a ticker's data is retrieved (the existing per-ticker collection flow), and market-wide news via a market-wide collection job. Market news MUST be shown as a section on the existing feed page; per-ticker news MUST be viewable on that ticker's detail view. A full feed-page redesign is explicitly out of scope (future feature).
- **FR-023**: System MUST collect company information (profile/company-info route) for tracked tickers as part of per-ticker data retrieval.
- **FR-024**: System MUST collect the FMP economics-route data the user selected: treasury rates, economic indicators, economic data releases, and market risk premium — subject to FR-016: where a series duplicates one already served by the existing macro source (FRED), one canonical source per series MUST be designated rather than storing both.

### Key Entities

- **Data Source Assignment**: The mapping of each data need (price history, breadth inputs, fundamentals, etc.) to its owning provider and backup; this feature rewrites the assignments that currently name Yahoo Finance.
- **Admin Job**: A named, non-ticker-specific data-collection process — description, what dataset it feeds, trigger availability, and its run history.
- **Job Run**: A single execution of an admin job — start time, end time, terminal status (success/failure), and failure reason when applicable.
- **Market-Wide Dataset**: A collected body of data not scoped to a single ticker (e.g., superinvestor portfolios, sector performance, market movers, economic calendar, congressional trading feed), with source and freshness metadata.
- **Gap-Review Decision**: One dataset family from the paid FMP plan with its adopt/defer/reject status and rationale; the collection of these forms the review deliverable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tracked tickers return usable price history after migration — including every ticker known to fail under Yahoo Finance today (or are explicitly flagged as uncovered by the new provider, with zero silent empty charts).
- **SC-002**: Zero live references to Yahoo Finance remain in the running system after migration, verified by inspection and by all existing data views functioning normally.
- **SC-003**: Existing analyses, charts, breadth signals, and tests produce equivalent (or corrected) results after migration — no regression in any currently working view.
- **SC-004**: The user can trigger any market-wide data-collection job from the admin section in 3 clicks or fewer from app load, and can determine its outcome from the same section without using a terminal.
- **SC-005**: The gap review covers 100% of the paid plan's non-crypto dataset families, and every family has a recorded decision with rationale.
- **SC-006**: Every adopted dataset has data visible in the frontend with a freshness indicator within one collection run of being adopted.
- **SC-007**: A simulated provider outage or budget exhaustion degrades to stale-cache/clear-empty-state behavior with zero crashed analysis runs.

## Assumptions

- "Yahoo ticket" in the feature description is read as the Yahoo Finance integration (the yfinance-backed data paths); "superinvstory stuff" is read as the superinvestor (Dataroma) portfolio collection; "this page from FMP" is read as the FMP API's catalog of market-wide endpoints (movers, calendars, sector performance, congressional trading, etc.) that don't fit the current ticker-first agent flow.
- The migration is a full replacement of Yahoo Finance, not a fallback arrangement — the user said "switch everything." Data items with no FMP equivalent on the current plan follow FR-003 (alternate already-integrated source or documented drop) rather than keeping Yahoo alive for them.
- The exact paid FMP plan level (and therefore its precise endpoint list and rate limits) will be confirmed against the user's account during planning; the spec intentionally says "the paid subscription's actual limits/datasets" rather than assuming a specific plan's numbers.
- The admin section needs no authentication or role model: the app is single-user, self-hosted, and has no auth by design. "Admin" is a navigation area, not a permission boundary.
- Real-time/streaming quotes are out of scope; the system remains fetch-on-navigation and manual-trigger only, consistent with the project's no-polling rule. Options-chain data (available from Yahoo, not core to any current view) is expected to be a documented drop under FR-003 unless the gap review finds an FMP equivalent worth adopting.
- Visualization scope is bounded to presenting the adopted datasets well within the existing app (extending existing pages and/or adding a market-overview area); a from-scratch redesign of the app's information architecture is out of scope.
- Scheduled/automated recurring collection remains out of scope: jobs run when manually triggered from the admin section (or by existing agent flows), preserving the project's manual-trigger design. Making any job recurring would be a future, deliberate scope expansion.
- Existing per-ticker agent flows keep working unchanged throughout; this feature adds market-wide collection alongside them rather than restructuring them.
- The FMP entitlement question is settled by the user's own verification (2026-08-15): insider, senate/house, ETF/fund holdings, market news, company info, and economics are in; 13F and transcripts are out. The automated entitlement probe remains as a verification/regression tool for ambiguous families (batch quotes, intraday resolutions, analyst grades).
- Retiring the Dataroma scraper means true superinvestor (13F-portfolio) tracking pauses until the user sources 13F data outside FMP — accepted consciously; ETF & fund holdings is the replacement signal in the meantime.
