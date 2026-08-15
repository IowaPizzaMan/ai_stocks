# Feature Specification: Stair-Step Stop Loss Position Management

**Feature Branch**: `015-position-management-agent`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Import of the hand-written spec `specs/position_management_agent_spec.md` (the Position Management Agent's daily Stair-Step Stop Loss trailing logic for open swing-trade positions) into spec-kit format."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily Stop Trailing for Active Positions (Priority: P1)

A swing trader with open positions wants their stop loss automatically walked up to just below the prior session's low each trading day, so winning trades can run as far as their daily structure holds, without the trader manually recalculating stops every day.

**Why this priority**: This is the core mechanism of the entire feature — the Stair-Step Stop Loss method — and every other capability (exit detection, market-condition adjustment, alerts) exists to support or report on it.

**Independent Test**: Can be fully tested by feeding a sequence of daily OHLC data for one open position and confirming the stop is raised exactly when the new candidate stop exceeds the current stop, and left unchanged otherwise.

**Acceptance Scenarios**:

1. **Given** an active position's prior session low minus the configured buffer is higher than the current stop, **When** the daily update runs, **Then** the stop is raised to that new level and the action is reported as UPDATE.
2. **Given** the calculated new stop would be lower than or equal to the current stop, **When** the daily update runs, **Then** the existing stop is left unchanged and the action is reported as HOLD.
3. **Given** a position has not yet reached its minimum profit threshold to begin trailing, **When** the daily update runs, **Then** the stop is not moved based on the daily-low rule until that threshold is met.

---

### User Story 2 - Exit Trigger Detection (Priority: P1)

A swing trader wants to be notified the moment price closes — or, per configuration, trades intraday — below their current stop, so they know a position has been stopped out and can close it without delay.

**Why this priority**: Detecting the exit trigger correctly and promptly is as critical as trailing the stop itself — a missed or delayed exit signal defeats the purpose of the trailing-stop method.

**Independent Test**: Can be fully tested by feeding a price sequence that crosses below a known stop level (including a gap-down-at-open case) and confirming the system flags EXIT with the correct reason and P&L.

**Acceptance Scenarios**:

1. **Given** the current price is at or below the current stop, **When** evaluated, **Then** the position is flagged EXIT with a reason referencing the stop being breached, and the report includes unrealized P&L.
2. **Given** a position gaps down at the open below its current stop, **When** evaluated, **Then** the exit is flagged immediately at the open rather than waiting for further intraday movement, and the user is notified without delay.

---

### User Story 3 - Market-Condition-Aware Risk Adjustment (Priority: P2)

A swing trader wants the system to flag their positions for manual review — and optionally recommend tightening stops — when broad market conditions turn unfavorable, without automatically closing positions unless they've explicitly configured it to do so.

**Why this priority**: This adds a risk-management layer on top of the core trailing mechanism (P1); the trailing method still works without it, but this reduces exposure to broad market downturns.

**Independent Test**: Can be fully tested by feeding a set of market-condition signal values (index trend, volatility level, breadth trend, new-highs-vs-lows) and confirming the resulting favorable/unfavorable classification, and confirming affected positions are flagged for review rather than auto-exited.

**Acceptance Scenarios**:

1. **Given** two or more of the tracked market-condition signals are negative, **When** market condition is assessed automatically, **Then** overall market condition is set to unfavorable and trailing is paused or tightened.
2. **Given** market condition is unfavorable, **When** the daily update runs, **Then** affected positions are flagged for manual review rather than auto-exited, unless the user has explicitly configured auto-exit behavior.
3. **Given** market condition later improves, **When** re-assessed, **Then** affected positions return to normal active trailing.

---

### User Story 4 - Alerts for Stop Changes, Exits, and Upcoming Earnings (Priority: P2)

A swing trader wants to be alerted whenever a stop is updated or triggered, when market condition changes, or when a held position has earnings coming up within the next few sessions, so they don't have to check every position manually every day.

**Why this priority**: This is the notification layer that makes the daily results actionable without the trader having to pull the full report every day; it depends on the underlying detection capabilities (P1–P3) already existing.

**Independent Test**: Can be fully tested by triggering each alert-worthy condition (stop update, exit, market-condition change, earnings within 3 days) and confirming a corresponding alert is emitted with the correct content.

**Acceptance Scenarios**:

1. **Given** a stop is updated, **When** the daily run completes, **Then** an alert is emitted stating the new level and how much it moved.
2. **Given** a position has an earnings date within 3 trading days, **When** the daily run completes, **Then** an alert is emitted warning the user ahead of the event.

---

### Edge Cases

- What happens when a position's underlying stock is halted? The position is held as-is and flagged for manual review; no automatic stop recalculation occurs while halted.
- What happens when a stock consolidates flat and the stop hasn't moved in many sessions? The system emits HOLD with a note, and flags the position if there has been no upward movement for a configurable number of days.
- What happens when a position is currently below its entry price (negative unrealized P&L)? It is flagged, and the system reverts to the position's original initial stop whenever that initial stop remains above what the daily trailing calculation would otherwise produce — the trailing rule must never produce a looser stop than the original risk plan intended.
- What happens when an earnings date falls within the alert window while overall market condition is otherwise favorable? The earnings-proximity alert is still emitted independent of overall market condition, and the stop for that specific position may still be tightened or an exit recommended ahead of the event.
- What happens when the minimum-profit-to-trail threshold has not yet been reached and price is falling? The position keeps its original entry stop (not yet trailing) rather than the daily-low rule producing a premature exit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST retrieve, for each active position, the prior trading session's daily low as an input to that day's stop calculation.
- **FR-002**: System MUST compute a candidate new stop as the prior day's low minus a configured buffer (a fixed dollar amount by default, or a percentage of price for higher-priced positions).
- **FR-003**: System MUST only raise a position's stop, never lower it: the stop is updated to the new candidate value only when that value is higher than the current stop; otherwise the current stop is held unchanged.
- **FR-004**: System MUST NOT begin daily-low-based trailing on a position until it has reached a configured minimum unrealized profit percentage.
- **FR-005**: System MUST flag a position EXIT when the current price is at or below the current stop, using either an intraday-break rule or a closing-price-only rule, per configuration.
- **FR-006**: System MUST flag an immediate EXIT at the market open — rather than waiting for further intraday movement — when a position gaps down through its current stop at the open, and MUST notify the user without delay.
- **FR-007**: System MUST assess overall market condition (favorable / neutral / unfavorable) either from an explicit user-provided value or, when configured to assess automatically, from a defined set of signals: the broad market index trend versus its short-term moving average, the volatility-index level, the advance/decline trend, and the count of new highs versus new lows.
- **FR-008**: System MUST classify automatically-assessed market condition as unfavorable when 2 or more of the tracked signals are negative, and MUST pause or tighten trailing stops while in that state.
- **FR-009**: System MUST flag positions for manual review when market condition is unfavorable, and MUST NOT automatically exit those positions unless the user has explicitly configured auto-exit behavior.
- **FR-010**: System MUST return a flagged position to normal active trailing once market condition subsequently improves.
- **FR-011**: System MUST hold (not recalculate) the stop for any position whose underlying stock is currently halted, and MUST flag it for manual review while halted.
- **FR-012**: System MUST flag a position when it has shown no upward stop movement for a configurable number of consecutive sessions (flat consolidation).
- **FR-013**: System MUST flag a position with negative unrealized P&L from entry, and MUST revert to that position's original initial stop rather than a looser trailing-derived stop whenever the initial stop remains above the trailing calculation.
- **FR-014**: System MUST warn the user when a position's next earnings date falls within 3 trading days, and MUST offer the option to tighten the stop or recommend an exit ahead of that event.
- **FR-015**: System MUST emit, on every daily run, a structured per-position report containing at minimum: the action taken (UPDATE / HOLD / EXIT / REVIEW), the new and previous stop levels, the amount the stop moved, entry price, unrealized P&L, and days held.
- **FR-016**: System MUST emit alerts whenever a stop is updated, whenever an exit is triggered, whenever market condition changes state, and whenever an earnings-proximity warning applies.
- **FR-017**: System MUST track each position through a defined lifecycle — Entry → Active (trailing) → Exited — with an optional Review sub-state entered from Active when market condition turns unfavorable, and exited back to Active or forward to Exited.
- **FR-018**: System MUST treat trade entry/selection and position sizing as out of scope for this feature — it only manages stops on positions that already exist.
- **FR-019**: System MUST NOT apply a fixed profit target; upside is left open-ended by design, bounded only by the trailing-stop mechanism.
- **FR-020**: System MUST default to long-only position management; short-position support is out of scope unless explicitly extended.

### Key Entities *(include if feature involves data)*

- **Position**: An active swing trade under management — ticker, entry price/date, current stop, share count, breakout/entry trigger level, and lifecycle state.
- **Daily Stop Calculation**: The per-session computation of prior-day low, buffer, and resulting candidate stop for one position.
- **Market Condition Assessment**: The favorable/neutral/unfavorable determination, either user-supplied or automatically derived from the tracked breadth/trend/volatility signals.
- **Action Report**: The daily structured output per position (action, stop levels, P&L, notes).
- **Alert**: A notification event — stop update, exit trigger, market-condition change, or earnings proximity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of active positions receive an updated action report (UPDATE / HOLD / EXIT / REVIEW) on every scheduled daily run.
- **SC-002**: A position's stop is never recommended lower than its previously recorded stop across the life of the position (zero regressions in validation testing).
- **SC-003**: Users are alerted to an exit-triggering price move no later than the same trading day it occurs, including gap-down-at-open cases.
- **SC-004**: Users receive an earnings-proximity warning at least 3 trading days ahead of a held position's earnings date whenever that date is known in advance.
- **SC-005**: During a validation period covering both favorable and unfavorable market conditions, positions are correctly flagged for review in 100% of sessions where 2 or more tracked market signals are negative.

## Assumptions

- Daily OHLC price data and an earnings-calendar date per ticker are available as inputs to this feature; how they are sourced is outside this spec's scope.
- Default configuration values (a buffer of roughly $0.10–$0.25, or about 0.3% of price for higher-priced stocks; a minimum profit-to-trail of 5%; an earnings warning window of 3 trading days) are carried over from the source methodology as sensible starting defaults, and may be tuned per position or globally without changing the underlying rule structure.
- Automated broker order submission and portfolio-ledger persistence are optional integrations, not required behavior of this feature itself; this spec covers the decision logic (what the stop should be and when to alert), not how orders are placed or where state is stored.
- The automatic market-condition signals (index versus moving average, volatility level, breadth trend, new-highs-versus-lows) are computed elsewhere in this app (e.g., by the market-breadth capability) and consumed here as inputs, rather than being redefined by this feature.
