# Feature Specification: Congressional Trading

**Feature Branch**: `005-congressional-trading`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Track trades disclosed by members of Congress; filter by party, committee membership, sector, ticker; flag unusual timing relative to legislation or hearings." (from StockAI product spec, Core Feature Areas #5)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Disclosed Congressional Trades (Priority: P1)

A user wants to see trades that members of Congress have publicly disclosed, so they can see what lawmakers are buying and selling.

**Why this priority**: This is the foundational data the rest of the feature (filtering, timing flags) is built on; without visible trade data there is nothing to filter or flag.

**Independent Test**: Can be fully tested by opening the congressional trading view and confirming disclosed trades are listed with the trading member, ticker, action, and date.

**Acceptance Scenarios**:

1. **Given** disclosed congressional trades exist in the system, **When** the user opens the congressional trading view, **Then** the system displays them with the member's name, ticker, trade action (buy/sell), and date.
2. **Given** a specific ticker, **When** the user views that ticker's page, **Then** the system shows any congressional trades disclosed for that ticker.

---

### User Story 2 - Filter Congressional Trades (Priority: P2)

A user wants to narrow the list of disclosed trades by party, committee membership, sector, or ticker, so they can focus on the subset relevant to their research (e.g., "what are Financial Services Committee members trading in the financial sector?").

**Why this priority**: Filtering is a natural refinement of the base trade feed from User Story 1 and depends on it, but is not itself required to get initial value from the feature.

**Independent Test**: Can be fully tested by applying each filter type (party, committee, sector, ticker) independently to the trade list and confirming results narrow correctly.

**Acceptance Scenarios**:

1. **Given** a list of disclosed trades, **When** the user filters by party, **Then** only trades by members of the selected party are shown.
2. **Given** a list of disclosed trades, **When** the user filters by committee membership, **Then** only trades by members of the selected committee are shown.
3. **Given** a list of disclosed trades, **When** the user filters by sector, **Then** only trades in tickers belonging to the selected sector are shown.
4. **Given** a list of disclosed trades, **When** the user filters by ticker, **Then** only trades in that ticker are shown.
5. **Given** multiple filters applied at once, **When** the user views results, **Then** only trades matching all applied filters are shown.

---

### User Story 3 - See Flagged Unusual-Timing Trades (Priority: P3)

A user wants trades that look unusually timed relative to related legislative activity (e.g., a hearing or vote touching the traded company's industry) called out, so they can spot potential conflicts of interest without manually cross-referencing legislative calendars themselves.

**Why this priority**: A higher-value analytical layer on top of the base trade feed, but narrower in applicability (only a subset of trades will ever qualify) and depends on the base feed and committee/sector context already existing.

**Independent Test**: Can be fully tested by viewing a trade known to coincide closely with related legislative activity and confirming it is visibly flagged, separately from the general trade list.

**Acceptance Scenarios**:

1. **Given** a disclosed trade made close in time to legislative activity (e.g., a hearing or vote) relevant to the trader's committee and the traded company's sector, **When** the user views that trade, **Then** the system visibly flags it as having unusual timing.
2. **Given** a flagged trade, **When** the user views the flag, **Then** the system shows the specific legislative activity that made the timing notable.

---

### Edge Cases

- What happens when a disclosure is filed late (a known, common occurrence for congressional trade disclosures)? The system should show the actual trade date and the disclosure/filing date separately rather than conflating them, since "unusual timing" should be judged against the trade date.
- What happens when a member of Congress isn't on any tracked committee at the time of a trade? The trade should still appear in the base feed and be filterable by party/sector/ticker; it simply won't be eligible for a committee-based unusual-timing flag.
- How does the system handle a trade in a company that spans multiple sectors or isn't cleanly classified? It should still appear under a best-effort sector classification rather than being dropped from sector filtering entirely.
- What happens when no trades match the combination of filters applied? System should indicate no results found rather than an empty, ambiguous list.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display disclosed congressional trades, each showing the trading member, ticker, trade action, and trade date.
- **FR-002**: System MUST display any disclosed congressional trades associated with a given ticker on that ticker's own page.
- **FR-003**: Users MUST be able to filter the congressional trade list by political party.
- **FR-004**: Users MUST be able to filter the congressional trade list by committee membership.
- **FR-005**: Users MUST be able to filter the congressional trade list by sector.
- **FR-006**: Users MUST be able to filter the congressional trade list by ticker.
- **FR-007**: Users MUST be able to combine multiple filters at once, with results matching all applied filters.
- **FR-008**: System MUST flag trades whose timing is unusually close to legislative activity (e.g., a hearing or vote) relevant to the trading member's committee and the traded company's sector.
- **FR-009**: System MUST show, for each flagged trade, the specific legislative activity that made its timing notable.
- **FR-010**: System MUST distinguish and display both the actual trade date and the disclosure filing date for each trade, given that disclosures are commonly filed after the trade itself.

### Key Entities

- **Congressional Trade**: A disclosed transaction by a member of Congress — has a trading member, ticker, action (buy/sell), trade date, and disclosure/filing date.
- **Member of Congress**: The disclosing lawmaker — has a party affiliation and one or more committee memberships (which may change over time).
- **Legislative Activity**: A dated event (e.g., hearing or vote) associated with a committee and/or sector/industry, used as the reference point for unusual-timing flags.
- **Unusual-Timing Flag**: A derived annotation on a trade indicating it occurred close in time to relevant legislative activity, referencing that activity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view a ticker's page and immediately see any disclosed congressional trades in it, without navigating to a separate feature.
- **SC-002**: A user can narrow the full trade list down to a specific party, committee, sector, or ticker (or any combination) in a few actions.
- **SC-003**: A user can identify unusually-timed trades without manually cross-referencing a legislative calendar themselves.
- **SC-004**: For any flagged trade, a user can see exactly which legislative activity triggered the flag, not just that it was flagged.

## Assumptions

- "Unusual timing" has no precisely defined threshold in the source description; this spec treats it as a configurable proximity between a trade's date and related legislative activity (e.g., within some number of days) rather than inventing a specific fixed threshold, since the exact number is a tunable analytical parameter, not a decided product requirement.
- Legislative activity data (hearing/vote schedules and committee associations) is treated as an available reference dataset the feature consumes; how that data is sourced is an implementation detail out of scope for this spec.
- Sector classification for a traded company reuses the same sector taxonomy used elsewhere in the product (e.g., for Company Financials and Economic Data features) rather than defining a separate one here.
