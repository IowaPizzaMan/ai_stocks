# Feature Specification: Price Tracking

**Feature Branch**: `001-price-tracking`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Real-time and historical price data; customizable watchlists and portfolios; alerts (price targets, % moves, volume spikes)." (from StockAI product spec, Core Feature Areas #1)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Real-Time and Historical Price (Priority: P1)

A user looks up a ticker and sees its current price alongside historical price and volume data, so they can understand where a stock stands and how it got there before doing any deeper research.

**Why this priority**: Price data is the foundation every other feature in the app builds on (technicals, alerts, watchlist context). Without it there is no usable product.

**Independent Test**: Can be fully tested by looking up a ticker and confirming current price and a historical price/volume series are both displayed, independent of any other feature area.

**Acceptance Scenarios**:

1. **Given** a valid, actively-traded ticker, **When** the user looks it up, **Then** the system displays its current (or most recently available) price.
2. **Given** a valid ticker, **When** the user requests historical data, **Then** the system displays historical price and volume over a selectable range of time periods.
3. **Given** a ticker that has stopped trading (delisted), **When** the user looks it up, **Then** the system displays its last known price/history along with a clear indicator that it is no longer active, rather than an error.

---

### User Story 2 - Maintain a Watchlist (Priority: P2)

A user builds a personal list of tickers they care about so they can check on all of them at a glance instead of searching for each one individually.

**Why this priority**: A watchlist is the primary way a returning user re-engages with tracked stocks; it's the second most-used surface after looking up an individual stock.

**Independent Test**: Can be fully tested by adding a ticker to the watchlist, confirming it appears in the watchlist view with current price info, and removing it.

**Acceptance Scenarios**:

1. **Given** a ticker the user is viewing, **When** the user adds it to their watchlist, **Then** it appears in the watchlist view.
2. **Given** a ticker on the watchlist, **When** the user removes it, **Then** it no longer appears in the watchlist view.
3. **Given** one or more tickers on the watchlist, **When** the user opens the watchlist view, **Then** each ticker shows its current price at a glance without the user having to open each one individually.

---

### User Story 3 - Configure Price and Volume Alerts (Priority: P3)

A user sets up an alert on a ticker (a target price, a percentage move, or an unusual volume spike) so they're made aware of a significant move without having to continuously watch the stock themselves.

**Why this priority**: Valuable but depends on price tracking and watchlists already existing to be useful; it's an enhancement to a ticker the user is already following, not a standalone entry point.

**Independent Test**: Can be fully tested by configuring an alert condition on a ticker, causing (or simulating) that condition to be met, and confirming the user is shown the alert.

**Acceptance Scenarios**:

1. **Given** a ticker, **When** the user configures a target-price alert, **Then** the system surfaces the alert once the ticker's price reaches that target.
2. **Given** a ticker, **When** the user configures a percentage-move alert, **Then** the system surfaces the alert once the ticker moves by that percentage within the configured period.
3. **Given** a ticker, **When** the user configures a volume-spike alert, **Then** the system surfaces the alert once trading volume exceeds the ticker's typical volume by the configured margin.
4. **Given** one or more configured alerts, **When** the user views their alerts, **Then** they can see each alert's condition and status, and can edit or delete it.

---

### Edge Cases

- What happens when a user looks up a ticker that doesn't exist or is mistyped? System should indicate no match was found rather than showing a blank or broken view.
- What happens when historical data is requested for a time range in which the ticker didn't yet exist (e.g., recent IPO)? System should show the data that does exist and indicate the range is shorter than requested.
- What happens when a user tries to add the same ticker to their watchlist twice? System should treat it as already present rather than creating a duplicate entry.
- What happens when a ticker on the watchlist becomes delisted? It should remain visible on the watchlist with a clear "no longer active" indicator rather than silently disappearing or erroring.
- What happens when an alert condition is met while a ticker is delisted or has no fresh data? The alert should not fire on stale or missing data.
- How does the system handle a user configuring a nonsensical alert (e.g., a target price that has already been passed)? The system should still accept it (it may fire immediately) rather than reject it, since "already true" is a valid, if unusual, condition.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a ticker's current (or most recently available) price on request.
- **FR-002**: System MUST display a ticker's historical price data over a selectable range of time periods (e.g., day, week, month, several months, year).
- **FR-003**: System MUST display historical trading volume alongside historical price data.
- **FR-004**: Users MUST be able to add a ticker to a personal watchlist.
- **FR-005**: Users MUST be able to remove a ticker from their watchlist.
- **FR-006**: System MUST display all watchlist tickers together with each one's current price so the user can scan them at a glance.
- **FR-007**: Users MUST be able to add a ticker to the watchlist from wherever that ticker is shown in the app (e.g., search results, a stock's own page), not only from a dedicated add-ticker form.
- **FR-008**: Users MUST be able to configure a price-target alert on a ticker (fires when price reaches a specified level).
- **FR-009**: Users MUST be able to configure a percentage-move alert on a ticker (fires when price moves by a specified percentage within a period).
- **FR-010**: Users MUST be able to configure a volume-spike alert on a ticker (fires when trading volume exceeds the ticker's typical volume by a specified margin).
- **FR-011**: System MUST surface triggered alerts to the user in a way they will see without needing to already know to look for them.
- **FR-012**: Users MUST be able to view, edit, and delete their configured alerts.
- **FR-013**: System MUST indicate when a ticker being viewed (in price data, watchlist, or an alert) is no longer actively trading, rather than presenting it as if it were current.

### Key Entities

- **Ticker / Stock**: A publicly traded company or security, identified by its symbol; has a current price, historical price/volume series, and an active/delisted status.
- **Watchlist Entry**: A user's association with a ticker they want to track at a glance; belongs to one user, references one ticker.
- **Price Alert**: A user-configured condition on a ticker (price target, percentage move, or volume spike) plus its current status (armed/triggered) and the parameters needed to evaluate it (e.g., target value, percentage threshold, evaluation period).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can find a ticker's current price and view its historical chart within a few seconds of searching for it.
- **SC-002**: A user can add a ticker to their watchlist in one action from any screen where that ticker appears.
- **SC-003**: A user can see the current price of every watchlist ticker without opening any of them individually.
- **SC-004**: A user can configure a new alert (of any of the three supported types) in under a minute.
- **SC-005**: When an alert condition is met, the user can discover that it fired the next time they open the app, without needing to recheck the underlying ticker manually.
- **SC-006**: Delisted tickers remain visible with historical context rather than disappearing or producing errors, for 100% of tickers that were previously tracked.

## Assumptions

- The app is single-user (personal use), consistent with the rest of the product's current scope, so "the user's watchlist/alerts" means the one user's data, not multi-tenant data isolation.
- The product's overall UI refresh model is manual (the user triggers data pulls / refreshes the page rather than the app polling continuously in the background). Alerts are therefore evaluated against the most recently pulled data and surfaced the next time the user views the app, rather than delivered as an instant push/SMS/email notification the moment a condition is met in the market. Real-time push notification delivery is out of scope for this pass.
- "Historical" price ranges default to common investor-facing windows (e.g., 1 day / 1 week / 1 month / 3 months / 1 year); exact preset ranges are a presentation detail, not a product decision, and may be adjusted during implementation.
- Volume-spike and percentage-move alert thresholds are user-configurable values with reasonable defaults, not fixed system constants.
- Portfolios (holdings with cost basis, quantity, and P&L, as distinct from a simple watchlist) were named alongside watchlists in the source description but not elaborated anywhere else in the product spec; this pass treats "watchlist" as the concrete, decided feature and leaves true portfolio/holdings tracking (cost basis, position size, realized/unrealized P&L) as a future enhancement rather than inventing its requirements here.
