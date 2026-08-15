# Feature Specification: Institution Tracking

**Feature Branch**: `008-institution-tracking`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Superinvestor/Institution Tracking — scrape and parse Dataroma for superinvestor portfolio activity; track 13F filings for major funds; identify stocks being accumulated or exited by multiple top investors; overlap analysis across top portfolios; plus a standalone, market-wide Institutional Flow feed of the same underlying moves, independent of the per-stock view." (from StockAI product spec, Core Feature Areas #8, elaborated further in "Institutional Flow — Feature Design")

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See Institutional Activity for a Stock (Priority: P1)

A user researching a specific stock wants to know what major funds and well-known "superinvestors" are doing with it — building a position, trimming, or exiting — so they can weigh smart-money conviction alongside their own research.

**Why this priority**: This is the primary, most direct way a user encounters institutional data — while looking at a stock they already care about — and it's the foundation the market-wide feed in User Story 2 reshapes into a different view of the same underlying data.

**Independent Test**: Can be fully tested by viewing a stock's institutional activity and confirming both 13F fund holdings/changes and superinvestor portfolio activity are shown for that ticker, independent of any market-wide feed.

**Acceptance Scenarios**:

1. **Given** a stock with tracked 13F filings, **When** the user views its institutional activity, **Then** the system shows which major funds hold it and how their positions have changed across recent filing periods.
2. **Given** a stock held by one or more tracked superinvestors, **When** the user views its institutional activity, **Then** the system shows which superinvestors hold or have recently traded it and the nature of that activity (e.g., new position, add, trim, exit).
3. **Given** a stock held by multiple tracked superinvestors, **When** the user views it, **Then** the system indicates how many top investors currently hold it (overlap), so the user can judge broad vs. narrow conviction.
4. **Given** a stock with no tracked institutional activity, **When** the user views it, **Then** the system clearly indicates there is none rather than showing a blank or ambiguous view.

---

### User Story 2 - Browse a Market-Wide Institutional Flow Feed (Priority: P2)

A user wants to see new institutional and superinvestor moves across the entire tracked universe as they happen — not just for one stock they already have open — so they can discover notable activity in stocks they aren't currently watching.

**Why this priority**: This is the standalone, market-wide sibling of User Story 1 — same underlying data, reshaped as a discoverability feed. It's valuable but secondary to the per-stock view: a user typically researches a specific stock first (P1) and browses the broader feed as a separate, exploratory habit (P2).

**Independent Test**: Can be fully tested by opening the institutional flow feed independent of any specific stock and confirming a chronological stream of institutional/superinvestor moves across multiple tickers is shown, each with enough detail to act on.

**Acceptance Scenarios**:

1. **Given** institutional/superinvestor activity has been detected across the tracked universe, **When** the user opens the flow feed, **Then** the system displays a chronological stream of individual moves (newest first), each showing the fund, ticker, action type, and size/magnitude of the move.
2. **Given** the flow feed, **When** the user filters by action type, fund, ticker, or a minimum notability level, **Then** only matching moves are shown.
3. **Given** a move in the flow feed, **When** the user wants more context, **Then** they can navigate from that move directly to the full stock detail view for the underlying ticker.
4. **Given** the user is viewing a specific stock's institutional activity (User Story 1), **When** they want to see the broader flow context for that ticker, **Then** they can navigate from the stock's institutional view into the ticker's flow history.
5. **Given** the user wants the most current activity rather than waiting for the next scheduled update, **When** they request a fresh scan, **Then** the system runs one on demand and the feed reflects any newly found moves.

---

### Edge Cases

- What happens when the superinvestor portfolio data source is temporarily unreachable during a scan? The system should retain the last successfully scanned data and indicate it may not reflect the latest activity, rather than showing stale data as current or clearing existing data.
- What happens when the same underlying move is detected by both the 13F pipeline and the superinvestor pipeline (e.g., a fund that is both a tracked 13F filer and a tracked superinvestor)? It should be presented once as a coherent event, not duplicated in the feed.
- How does the system distinguish a genuinely notable move (e.g., a concentrated, high-conviction fund building a large new position) from routine, low-signal activity (e.g., a passive index fund's mechanical rebalancing)? The feed's notability scoring should downweight passive/index-style activity relative to concentrated, active manager moves, and the user should be able to filter by that notability level.
- What happens when a stock has 13F fund activity but is not held by any tracked superinvestor, or vice versa? Both views (per-stock and feed) should show whichever type of activity exists rather than requiring both to be present.
- What happens when a scan (scheduled or on-demand) is already running and the user requests another? The system should avoid starting a duplicate concurrent scan and should communicate that a scan is already in progress.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST track 13F filing data for major institutional funds and display, per stock, which tracked funds hold it and how their positions have changed across recent filing periods.
- **FR-002**: System MUST track superinvestor portfolio activity (from a curated source of well-known investors) and display, per stock, which tracked superinvestors hold or have recently traded it.
- **FR-003**: System MUST categorize each superinvestor move by action type (e.g., new position, add, trim, exit).
- **FR-004**: System MUST show, per stock, how many currently tracked superinvestors hold it (overlap count), so a user can judge breadth of conviction.
- **FR-005**: System MUST indicate when a stock has no tracked institutional or superinvestor activity, rather than an ambiguous empty state.
- **FR-006**: System MUST provide a market-wide feed of institutional/superinvestor moves across the entire tracked universe, independent of any single ticker, showing each move's fund, ticker, action type, and size/magnitude, ordered newest first.
- **FR-007**: System MUST let users filter the market-wide flow feed by action type, fund, ticker, and a minimum notability level.
- **FR-008**: System MUST assign each flow feed move a notability score that reflects conviction (e.g., weighting concentrated/active managers' moves more heavily than passive/index-style activity).
- **FR-009**: Users MUST be able to navigate from a flow feed move directly to the full stock detail view for the underlying ticker.
- **FR-010**: Users MUST be able to navigate from a stock's own institutional activity view into that ticker's flow history within the market-wide feed.
- **FR-011**: System MUST refresh institutional/superinvestor data on a recurring schedule without requiring the user to take any action.
- **FR-012**: Users MUST be able to manually trigger a fresh scan for new institutional/superinvestor activity on demand, consistent with the rest of the app's manual-refresh model.
- **FR-013**: System MUST avoid presenting the same underlying move as a duplicate entry when it is detected through more than one tracked data source.
- **FR-014**: System MUST prevent a manually triggered scan from running concurrently with an already-in-progress scan, and MUST communicate to the user when a scan is already underway.

### Key Entities

- **13F Holding**: A major fund's disclosed position in a stock as of a filing period, including position size and how it changed from the prior period.
- **Superinvestor**: A curated, well-known investor/fund tracked by the system for portfolio activity (distinct from the broader set of all 13F filers).
- **Superinvestor Move**: A discrete, dated action by a tracked superinvestor on a stock — action type (new position/add/trim/exit), size, and value.
- **Institutional Flow Event**: A unified, feed-ready record of an institutional or superinvestor move (drawn from 13F or superinvestor data) — fund, ticker, action, size, a notability score, and a timestamp.
- **Overlap Count**: A derived, per-stock count of how many currently tracked superinvestors hold that stock.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can determine, for any stock they view, whether major funds and tracked superinvestors are currently building, holding, trimming, or exiting a position, without consulting outside sources.
- **SC-002**: A user can discover a notable institutional move in a stock they are not currently watching by browsing the market-wide flow feed, without having to already know to check that ticker.
- **SC-003**: A user can narrow the flow feed to only high-conviction moves (filtering out routine/passive activity) in a few actions.
- **SC-004**: A user can move from a flow feed entry to full context on the underlying stock, and from a stock's institutional view to its broader flow history, without a separate manual search in either direction.
- **SC-005**: A user can request and see the results of a fresh institutional scan without waiting for the next scheduled update.

## Assumptions

- "Institutional Flow" is scoped as the market-wide, discoverability-oriented sibling of the per-ticker institutional view described in the source ("independent of the per-stock Institutional tab... same underlying data... reshaped as a stream of discrete events"), sharing the same underlying 13F and superinvestor data rather than introducing a new data source.
- The recurring scan cadence defaults to a daily schedule, per the source's description of the flow scan running "once daily (configurable)"; the exact configurable interval is an implementation detail.
- Notability scoring is required to exist and to meaningfully separate high-conviction concentrated funds from passive/index noise, per the source; the precise scoring formula/weights are an implementation-level analytical decision not specified in the source.
- This spec treats the per-stock institutional view (P1) and the market-wide flow feed (P2) as two user stories within one feature area, per the source's explicit framing of the flow feed as this feature's "standalone... independent" sibling rather than a separate feature.
