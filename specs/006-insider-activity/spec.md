# Feature Specification: Insider Activity

**Feature Branch**: `006-insider-activity`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "SEC Form 4 filings (insider buys/sells); cluster buying signals (multiple insiders buying near the same time); distinguish open-market purchases vs. option exercises; track insider sentiment over time per ticker." (from StockAI product spec, Core Feature Areas #6)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Insider Buy/Sell Filings for a Stock (Priority: P1)

A user researching a stock wants to see its insiders' (executives', directors') disclosed buy and sell transactions, so they can see whether the people closest to the company are buying or selling.

**Why this priority**: The raw filing feed is the foundational data every other part of this feature (cluster detection, transaction-type distinction, sentiment trend) depends on.

**Independent Test**: Can be fully tested by viewing a stock's insider activity and confirming individual buy/sell transactions are listed with insider name, action, shares, value, and date.

**Acceptance Scenarios**:

1. **Given** a stock with disclosed insider transactions, **When** the user views its insider activity, **Then** the system lists each transaction with the insider's name, action (buy/sell), shares, value, and date.
2. **Given** a stock with no recent insider transactions, **When** the user views its insider activity, **Then** the system clearly indicates there is no recent activity rather than showing a blank view.

---

### User Story 2 - Distinguish Purchase Type and See Cluster Buying (Priority: P2)

A user wants to tell an open-market purchase (an insider using their own money to buy shares — typically a stronger signal) apart from an option exercise (which may just be routine compensation activity), and wants to be alerted when multiple insiders buy around the same time, since clustered buying is a stronger signal than a single insider's trade.

**Why this priority**: This adds crucial interpretive context to the raw feed from User Story 1 — without it, all buys look equally meaningful, which is misleading — but it depends on the base feed already existing.

**Independent Test**: Can be fully tested by viewing a mix of open-market purchases and option exercises and confirming each is labeled correctly, and separately by viewing a stock with multiple insiders buying near the same time and confirming a cluster signal is shown.

**Acceptance Scenarios**:

1. **Given** an insider transaction, **When** the user views it, **Then** the system indicates whether it was an open-market purchase or an option exercise.
2. **Given** multiple insiders buying the same stock within a short window of each other, **When** the user views that stock's insider activity, **Then** the system surfaces this as a cluster buying signal distinct from the individual transactions.

---

### User Story 3 - Track Insider Sentiment Over Time (Priority: P3)

A user wants to see how insider sentiment (the overall tilt toward buying vs. selling) for a stock has trended over time, to judge whether insider conviction is strengthening or weakening.

**Why this priority**: A longer-horizon, trend-level view built on top of the individual transactions and cluster signals already surfaced; valuable for deeper research but not needed to get initial value from the feature.

**Independent Test**: Can be fully tested by viewing a stock's insider sentiment trend and confirming it reflects the balance of buys vs. sells over recent history.

**Acceptance Scenarios**:

1. **Given** a stock with insider transaction history, **When** the user views its insider sentiment trend, **Then** the system shows how the buy/sell balance has changed over recent periods.
2. **Given** an insider sentiment trend, **When** the user views it, **Then** the system indicates the current overall sentiment (e.g., net bullish, net bearish, or neutral) based on that history.

---

### Edge Cases

- What happens when an insider transaction is a type other than a clean open-market buy/sell or option exercise (e.g., a gift, a transfer, or an award)? System should still show the transaction with an accurate type label rather than forcing it into "buy" or "sell."
- How does the system define "near the same time" for cluster buying when insiders buy days apart rather than the same day? The clustering window should be a reasonable, consistent period, not just same-day.
- What happens when a single insider makes both buys and sells in the same window (e.g., a scheduled sell-to-cover alongside an open-market buy)? Both should appear individually, and sentiment aggregation should reflect the net, not just count one.
- What happens when insider data is incomplete for a very recently listed stock? System should show what's available and indicate history is limited rather than implying no insider activity has ever occurred.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display disclosed insider buy and sell transactions for a stock, each showing insider name, action, shares, value, and date.
- **FR-002**: System MUST indicate when a stock has no recent insider transactions rather than presenting an ambiguous empty state.
- **FR-003**: System MUST distinguish, for each insider transaction, whether it was an open-market purchase or an option exercise (or otherwise label transaction types that are neither).
- **FR-004**: System MUST detect when multiple insiders buy the same stock within a defined recent window and surface this as a distinct cluster buying signal.
- **FR-005**: System MUST show, for a cluster buying signal, which individual insiders and transactions contributed to it.
- **FR-006**: System MUST show how a stock's insider sentiment (balance of buying vs. selling) has trended over recent history.
- **FR-007**: System MUST indicate a stock's current overall insider sentiment (e.g., net bullish, net bearish, neutral) derived from recent transaction history.

### Key Entities

- **Insider Transaction**: A disclosed Form 4 filing — has an insider, ticker, action (buy/sell), transaction type (open-market purchase, option exercise, or other), shares, value, and date.
- **Insider**: A company executive or director required to disclose transactions in their company's stock.
- **Cluster Buying Signal**: A derived signal indicating multiple insiders bought the same stock within a recent window; references the contributing transactions.
- **Insider Sentiment Trend**: A derived, time-series view of the net buy/sell balance for a stock's insiders over recent history, plus a current overall sentiment reading.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can see a stock's recent insider transactions, with type and value, without leaving the stock's own page.
- **SC-002**: A user can distinguish an open-market purchase from an option exercise for any listed transaction without additional research.
- **SC-003**: A user can identify when a stock has a cluster buying signal at a glance, distinct from scanning individual transactions themselves.
- **SC-004**: A user can determine a stock's current overall insider sentiment and its recent trend direction without manually tallying individual transactions.

## Assumptions

- The specific cluster-buying time window (what counts as "near the same time") is a tunable analytical parameter rather than a fixed number decided in the source description; this spec requires that clustering exist and be shown, without prescribing the exact window length.
- Insider sentiment aggregation weighs both count and dollar value of transactions at a reasonable default balance; the precise weighting formula is an implementation-level analytical decision, not specified in the source.
- Insider transaction data (Form 4 filings) is scoped to publicly traded companies with SEC reporting obligations, consistent with the feature's SEC Form 4 basis.
