# Feature Specification: Economic Data

**Feature Branch**: `002-economic-data`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Macro indicators: CPI, PCE, interest rates, unemployment, GDP; Fed decisions and commentary; yield curve tracking; sector rotation signals tied to macro regime." (from StockAI product spec, Core Feature Areas #2)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Current Macro Indicators (Priority: P1)

A user wants to understand the current macroeconomic backdrop (inflation, rates, employment, growth) before interpreting any individual stock's signals, so they check a macro data view showing the latest values for key indicators.

**Why this priority**: Macro context is the baseline every other macro-dependent feature (sector rotation, Fed commentary, yield curve) is read against; without it those features have nothing to anchor to.

**Independent Test**: Can be fully tested by opening the macro data view and confirming current values are shown for CPI, PCE, interest rates, unemployment, and GDP, independent of any stock-specific feature.

**Acceptance Scenarios**:

1. **Given** the user opens the macro data view, **When** the data has been fetched at least once, **Then** the system displays the latest available value for CPI, PCE, interest rates, unemployment, and GDP.
2. **Given** a macro indicator's latest value, **When** the user views it, **Then** the system also shows how it has trended over recent history (not just the single latest reading).
3. **Given** macro data that hasn't been refreshed recently, **When** the user views it, **Then** the system indicates how current the data is (e.g., as-of date) rather than presenting it as live.

---

### User Story 2 - Track Fed Decisions and Commentary (Priority: P2)

A user wants to know what the Federal Reserve has recently decided or said, since Fed policy materially affects market conditions.

**Why this priority**: High-value context but narrower than the broad indicator dashboard in User Story 1 — it's one specific input a user checks periodically rather than the primary landing view.

**Independent Test**: Can be fully tested by opening the Fed section and confirming recent decisions/commentary are listed with dates, independent of other macro indicators.

**Acceptance Scenarios**:

1. **Given** the Fed has made a recent rate decision, **When** the user views the Fed section, **Then** the system shows that decision and its date.
2. **Given** recent Fed commentary is available, **When** the user views the Fed section, **Then** the system shows it alongside the decision history so the user can read policy intent, not just the numeric outcome.

---

### User Story 3 - Track Yield Curve and Sector Rotation Signals (Priority: P3)

A user wants to see the current shape of the yield curve and understand which sectors tend to benefit or suffer under the current macro regime, to inform where they look for opportunities.

**Why this priority**: A more advanced, derived view built on top of the raw indicators in User Story 1; valuable but narrower audience than the base macro dashboard.

**Independent Test**: Can be fully tested by viewing the yield curve display and the sector rotation signal independently of the raw indicator dashboard.

**Acceptance Scenarios**:

1. **Given** current yield data across maturities, **When** the user views the yield curve, **Then** the system displays the curve's current shape and how it has changed over recent history (e.g., steepening, flattening, inverted).
2. **Given** the current macro regime (as derived from the tracked indicators), **When** the user views sector rotation signals, **Then** the system indicates which sectors are favored or disfavored under that regime.

---

### Edge Cases

- What happens when a macro data source has no update yet for the most recent reporting period (e.g., this month's CPI hasn't been released)? System should show the most recent available reading with its as-of date rather than a gap or error.
- What happens when the yield curve is inverted? System should represent this clearly rather than only showing a chart that requires the user to infer inversion themselves.
- How does the system handle a user viewing sector rotation signals when there isn't yet enough macro history to characterize a "regime"? System should indicate the signal has low confidence or is unavailable rather than guessing silently.
- What happens when Fed commentary text is long or highly technical? System should present it in a way the user can scan (e.g., summarized or excerpted) rather than requiring them to read a full transcript to find the key takeaway.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display the latest available value for each tracked macro indicator: CPI, PCE, interest rates, unemployment, and GDP.
- **FR-002**: System MUST display recent historical trend, not just the latest single reading, for each tracked macro indicator.
- **FR-003**: System MUST show the as-of date/period for each macro indicator value displayed.
- **FR-004**: System MUST display recent Federal Reserve rate decisions with their dates.
- **FR-005**: System MUST display Federal Reserve commentary associated with those decisions in a form the user can scan for key takeaways.
- **FR-006**: System MUST display the current yield curve shape across tracked maturities.
- **FR-007**: System MUST show how the yield curve has changed over recent history (e.g., steepening, flattening, inversion).
- **FR-008**: System MUST derive and display a sector rotation signal that indicates which sectors are favored or disfavored under the current macro regime.
- **FR-009**: System MUST indicate when a displayed sector rotation signal has low confidence (e.g., insufficient history to characterize the regime) rather than presenting it with the same confidence as a well-supported signal.

### Key Entities

- **Macro Indicator**: A tracked economic data series (CPI, PCE, interest rate, unemployment, GDP) with a current value, an as-of date/period, and historical values over time.
- **Fed Decision/Commentary**: A dated record of a Federal Reserve policy decision (e.g., a rate change) and any associated commentary text.
- **Yield Curve Snapshot**: The set of yield values across tracked maturities as of a point in time, used to derive curve shape and its change over time.
- **Macro Regime / Sector Rotation Signal**: A derived characterization of current macro conditions (e.g., based on the tracked indicators) mapped to a set of favored/disfavored sectors.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can see the current value of every tracked macro indicator within a few seconds of opening the macro data view.
- **SC-002**: A user can identify the most recent Fed decision and its date without leaving the Fed section.
- **SC-003**: A user can determine the current yield curve shape (e.g., normal, flat, inverted) at a glance without manually comparing individual maturity values.
- **SC-004**: A user can identify which sectors are currently favored under the prevailing macro regime without cross-referencing indicators themselves.
- **SC-005**: Macro data displayed is never presented without an as-of date, so a user is never misled into treating stale data as current.

## Assumptions

- Macro data update frequency follows each underlying indicator's natural real-world release cadence (e.g., CPI monthly, GDP quarterly); the system is not expected to produce intra-period estimates.
- "Sector rotation signals tied to macro regime" is a derived, best-effort signal based on the tracked indicators and yield curve — the source spec does not define the exact regime classification model, so this spec describes the user-facing behavior (a regime-to-sector mapping is shown) without prescribing the specific classification logic, which is an implementation-level decision.
- This feature is read-only/informational for the user (no user-configurable macro alerts) since the source description does not mention macro-specific alerting the way Price Tracking does for price/volume.
