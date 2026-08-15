# Feature Specification: Trend Recognition

**Feature Branch**: `004-trend-recognition`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Pattern detection across price, volume, financials, and macro data; momentum, mean-reversion, and breakout signals; alerts when multiple signals align." (from StockAI product spec, Core Feature Areas #4)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See Detected Signals for a Stock (Priority: P1)

A user viewing a stock wants to see what patterns and signals the system has detected in its price, volume, financial, and macro data, so they can quickly understand what's notable about it without manually analyzing charts and statements themselves.

**Why this priority**: Surfacing detected signals is the core value of trend recognition; every other part of this feature (categorizing signal type, alerting on alignment) depends on signals being detected and shown first.

**Independent Test**: Can be fully tested by viewing a stock with known notable activity and confirming at least one detected signal is displayed with a description of what was detected.

**Acceptance Scenarios**:

1. **Given** a stock with a detected momentum, mean-reversion, or breakout pattern, **When** the user views the stock, **Then** the system displays the detected signal(s) with an indication of what type each is.
2. **Given** a stock with no currently detected signals, **When** the user views the stock, **Then** the system clearly indicates no signals are currently active rather than showing a blank or ambiguous state.
3. **Given** a detected signal, **When** the user views its details, **Then** the system indicates which underlying data it was derived from (e.g., price/volume, financials, or macro data) so the user understands its basis.

---

### User Story 2 - Get Alerted When Multiple Signals Align (Priority: P2)

A user wants to be alerted specifically when multiple independent signals point the same direction on a stock at once, since convergence across signal types is a stronger indicator than any single signal alone.

**Why this priority**: This is a valuable escalation on top of User Story 1's per-signal display, but it depends on individual signal detection already existing and is a narrower, higher-conviction subset of that broader capability.

**Independent Test**: Can be fully tested by causing (or simulating) multiple aligned signals on a stock and confirming the user is alerted, separately from simply viewing the individual signals.

**Acceptance Scenarios**:

1. **Given** a stock where two or more independent signals currently align in the same direction, **When** the condition is met, **Then** the system surfaces this as a distinct, higher-priority alert rather than treating it the same as a single isolated signal.
2. **Given** an alignment alert, **When** the user views it, **Then** the system shows which individual signals contributed to the alignment.

---

### Edge Cases

- What happens when signals conflict (e.g., a momentum signal is bullish while a mean-reversion signal is bearish) on the same stock? System should show both rather than suppressing one or forcing a single verdict.
- What happens when there isn't enough historical data for a stock to reliably detect a pattern (e.g., a recent IPO)? System should indicate insufficient data rather than presenting a low-confidence signal as equally reliable.
- How does the system handle a signal that was active but is no longer valid by the time the user views it (e.g., the pattern that triggered it has since resolved)? The signal should be shown as no longer active, not left displayed as current.
- What happens when macro data used as an input to a signal is stale or unavailable? Any signal depending on it should indicate that dependency was degraded rather than silently using outdated data as if current.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect and display momentum signals for a stock based on its price and volume data.
- **FR-002**: System MUST detect and display mean-reversion signals for a stock based on its price and volume data.
- **FR-003**: System MUST detect and display breakout signals for a stock based on its price and volume data.
- **FR-004**: System MUST be able to incorporate financial data (not just price/volume) as an input to pattern/signal detection.
- **FR-005**: System MUST be able to incorporate macro data as an input to pattern/signal detection.
- **FR-006**: System MUST indicate, for each detected signal, which category of underlying data (price/volume, financial, or macro) it is derived from.
- **FR-007**: System MUST clearly indicate when a stock currently has no active detected signals.
- **FR-008**: System MUST detect when multiple independent signals align in the same direction for a stock.
- **FR-009**: System MUST surface signal alignment as a distinct, higher-priority alert, showing which individual signals contributed.
- **FR-010**: System MUST stop displaying a signal as active once the condition that triggered it is no longer true.

### Key Entities

- **Signal**: A detected pattern instance for a stock — has a type (momentum, mean-reversion, or breakout), a source data category (price/volume, financial, or macro), a direction (e.g., bullish/bearish), and an active/expired status.
- **Signal Alignment Alert**: A derived, higher-priority alert raised when two or more signals for the same stock currently align in direction; references the contributing signals.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can see all currently active signals for a stock in a single view, without having to inspect raw price, volume, financial, or macro data themselves.
- **SC-002**: A user can distinguish a single-signal situation from a multi-signal-alignment situation at a glance, without comparing signals manually.
- **SC-003**: A user is never shown a signal as active after the condition that produced it has resolved.
- **SC-004**: A user can identify what underlying data category (price/volume, financial, macro) any given signal is based on without additional lookup.

## Assumptions

- The source description names momentum, mean-reversion, and breakout as the supported signal categories; this spec treats that as the decided, closed set of categories rather than expanding it, since no other categories are mentioned anywhere in the source.
- The precise detection logic/thresholds for each signal type (e.g., what specifically counts as a "breakout") are implementation-level analytical decisions, not user-facing product requirements, and are intentionally left unspecified here — this spec defines what the user sees and when, not how the underlying pattern math works.
- "Alerts when multiple signals align" is treated as an in-app alert consistent with how alerts are handled elsewhere in the product (surfaced to the user on next view, not a push/SMS/email notification), matching the assumption made in the Price Tracking feature spec for the same reason: the product's overall model is manual-refresh, not continuously polling in the background.
