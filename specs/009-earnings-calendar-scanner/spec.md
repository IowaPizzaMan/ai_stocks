# Feature Specification: Earnings Calendar Scanner

**Feature Branch**: `009-earnings-calendar-scanner`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Sweep the upcoming earnings calendar across all publicly traded companies; score each for 'earnings play' potential; surface the most interesting candidates as an interactive ranked list; conversational handoff to full analysis; post-earnings tracking of actual vs. predicted moves." (from StockAI product spec, Core Feature Areas #9, elaborated further in "Earnings Scanner — Workflow Design")

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a Ranked List of Upcoming Earnings Candidates (Priority: P1)

A user wants to find interesting upcoming earnings plays without manually checking every company reporting in the next couple of weeks, so they run a scan and get back a short, ranked list of the most notable candidates with a explanation of why each one stands out.

**Why this priority**: This is the core value proposition of the feature — discovering opportunities the user wouldn't have found by browsing their existing watchlist. Every other part of the feature (conversational handoff, post-earnings tracking) depends on this ranked list existing first.

**Independent Test**: Can be fully tested by running a scan over a defined date window and confirming a ranked list of candidates is returned, each with a score and the reasons contributing to it, independent of any follow-up analysis.

**Acceptance Scenarios**:

1. **Given** a window of upcoming days, **When** the user runs an earnings scan, **Then** the system returns a ranked list of the companies reporting in that window most worth a closer look.
2. **Given** the full set of companies reporting in the window, **When** the scan runs, **Then** the system excludes companies unlikely to be worthwhile candidates (e.g., very small companies, or companies without enough trading/earnings history to score reliably) before ranking.
3. **Given** a ranked candidate, **When** the user views it, **Then** the system shows the reasoning behind its score (e.g., historical earnings move size, analyst estimate trends, recent insider activity, institutional accumulation) not just a single opaque number.
4. **Given** no upcoming earnings in the requested window, **When** the user runs a scan, **Then** the system indicates there are no candidates rather than an empty or broken result.

---

### User Story 2 - Hand Off a Candidate to Full Analysis Conversationally (Priority: P2)

Once the user sees the ranked candidates, they want to say (in their own words) which one(s) they want a deeper look at, and have the system run a full analysis on just those, without having to leave the conversation to manually trigger it elsewhere.

**Why this priority**: This is what makes the scan actionable rather than just informational — it depends on User Story 1's ranked list already existing, and is the natural next step a user takes after seeing interesting candidates.

**Independent Test**: Can be fully tested by presenting a ranked list, selecting one or more candidates by name in conversation, and confirming a full analysis is triggered for exactly those tickers.

**Acceptance Scenarios**:

1. **Given** a ranked list of candidates has been presented, **When** the user selects one or more by name (or a relative reference like "the top 3"), **Then** the system triggers a full analysis for exactly those tickers.
2. **Given** the user's selection is ambiguous or unclear, **When** they respond, **Then** the system asks a clarifying question rather than guessing which tickers were meant.
3. **Given** a full analysis has been triggered from a scan handoff, **When** the user checks back, **Then** they can see the resulting analysis the same way they would for any other analyzed stock.

---

### User Story 3 - Track Post-Earnings Outcomes (Priority: P3)

After a scanned company actually reports earnings, the user wants to know how its price moved and how that compares to what the pre-earnings scan predicted, so they can judge how reliable the scanner's scoring has been over time.

**Why this priority**: A retrospective, trust-building layer on top of the scan/handoff flow; valuable for evaluating the feature's own usefulness over time, but not required for a user to get value from a single scan-and-analyze session.

**Independent Test**: Can be fully tested by scanning and later checking a ticker's post-earnings history to confirm the actual move and the original pre-earnings prediction are both shown together.

**Acceptance Scenarios**:

1. **Given** a company that was previously surfaced by the scanner and has since reported earnings, **When** the user looks up its post-earnings history, **Then** the system shows the actual price move alongside the original pre-earnings score/prediction for comparison.
2. **Given** a company the scanner has tracked across multiple earnings cycles, **When** the user views its history, **Then** the system shows the outcome for each cycle, not just the most recent one.

---

### Edge Cases

- What happens when a company reporting in the scan window has too little history to score reliably (e.g., a recent IPO with fewer than a handful of prior earnings events)? It should be excluded from the pre-screened candidate list rather than scored on insufficient data.
- What happens when a company has no options market (making volatility expectations hard to gauge)? It should be excluded from the pre-screened candidate list, consistent with the pre-screening criteria.
- What happens when the user asks to analyze a ticker that wasn't actually in the presented candidate list? The system should clarify rather than silently substituting or guessing.
- What happens when a company that was scanned and scored ends up not reporting on the expected date (a delay)? Post-earnings tracking should wait for the actual report rather than logging a move against the wrong date.
- What happens when a user runs the same scan window twice in a short period? The system should return current results rather than requiring the user to know whether a fresher scan is needed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let users run a scan over a configurable window of upcoming days (e.g., the next 1–14 days) covering companies scheduled to report earnings.
- **FR-002**: System MUST exclude companies unlikely to be worthwhile candidates before scoring — at minimum, companies below a configurable market-cap floor, companies without an options market, and companies with too little prior earnings history to score reliably.
- **FR-003**: System MUST score each remaining candidate for "earnings play" potential, incorporating at least: historical size of post-earnings price moves, consistency of the move's direction relative to beat/miss outcomes, spread among analyst estimates, trend in analyst estimate revisions, recent insider buying activity, and institutional accumulation trend.
- **FR-004**: System MUST present scan results as a ranked list of the top candidates, each showing its score and the specific factors contributing to it.
- **FR-005**: System MUST let the user select one or more ranked candidates, by name or by relative reference (e.g., "the top 3"), to hand off for a full analysis.
- **FR-006**: System MUST ask a clarifying question when the user's candidate selection is ambiguous, rather than guessing.
- **FR-007**: System MUST make results of a handed-off full analysis available to the user through the same means as any other analyzed stock.
- **FR-008**: System MUST, after a previously scanned company reports earnings, capture its actual price move and store it alongside the original pre-earnings score/prediction.
- **FR-009**: System MUST let users view a company's post-earnings tracking history across multiple earnings cycles, not only the most recent one.
- **FR-010**: System MUST indicate when a scan window has no qualifying candidates rather than returning an ambiguous empty result.

### Key Entities

- **Earnings Scan**: A run of the scanner over a given upcoming-days window; produces a ranked list of candidates.
- **Earnings Candidate**: A company scored for earnings-play potential — has a score, the contributing factor breakdown, and its scheduled report date.
- **Post-Earnings Outcome**: A record, created after a previously scanned company reports, of its actual price move compared against its original pre-earnings score/prediction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from "what's worth watching this week" to a ranked, reasoned candidate list in a single scan request, without manually checking each reporting company.
- **SC-002**: A user can select candidates for deeper analysis using natural language, without needing to know a specific ticker-entry mechanism elsewhere in the app.
- **SC-003**: A user can determine, for any previously scanned company that has since reported, how its actual move compared to the original prediction, without cross-referencing separate views themselves.
- **SC-004**: Companies unlikely to be useful candidates (too small, no options market, too little history) never appear in the ranked list a user reviews.

## Assumptions

- The default scan window is 1–14 days ahead, per the source description; users can configure it within that range rather than the system supporting arbitrary unbounded windows.
- The relative weighting of scoring factors (e.g., "High," "Medium," "Low" importance per factor in the source) is preserved as a product decision — some factors matter more than others — without prescribing an exact numeric formula, since the source itself only specifies qualitative weights, not a formula.
- Options-based volatility expectation (implied volatility vs. historical) is explicitly noted in the source as a deferred/future scoring input ("Low (deferred) | Future phase") — this spec excludes it from the required scoring factors in FR-003, consistent with the source's own decision to defer it, rather than requiring it now.
- The conversational handoff assumes the user interacts via natural-language responses (as shown in the source's example dialogue) rather than a traditional multi-step form; this spec describes the resulting behavior (selection by name/reference, clarification on ambiguity) without prescribing the underlying conversational mechanism.
