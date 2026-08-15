# Feature Specification: Company Financials

**Feature Branch**: `003-company-financials`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Income statement, balance sheet, cash flow (annual + quarterly); key ratios: P/E, EV/EBITDA, gross margin, FCF yield, debt/equity, etc.; YoY and QoQ trend analysis; earnings estimates vs. actuals." (from StockAI product spec, Core Feature Areas #3)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review Core Financial Statements (Priority: P1)

A user researching a company wants to see its income statement, balance sheet, and cash flow statement, for both annual and quarterly periods, to understand its financial health directly from the primary statements.

**Why this priority**: The financial statements are the foundational data every other part of this feature (ratios, trends, estimates) is derived from or displayed alongside; without them the feature has no basis.

**Independent Test**: Can be fully tested by opening a company's financials view and confirming income statement, balance sheet, and cash flow are each viewable for both annual and quarterly periods.

**Acceptance Scenarios**:

1. **Given** a company with available financial data, **When** the user opens its financials view, **Then** the system displays its income statement, balance sheet, and cash flow statement.
2. **Given** a company's financials view, **When** the user switches between annual and quarterly periods, **Then** the system displays the statements for the selected period type.
3. **Given** a company with limited financial history (e.g., a recent IPO), **When** the user views its financials, **Then** the system shows whatever periods are available and indicates the history is limited rather than showing blank periods as if data were missing due to an error.

---

### User Story 2 - Review Key Financial Ratios (Priority: P2)

A user wants a quick read on valuation and financial quality via standard ratios (P/E, EV/EBITDA, gross margin, FCF yield, debt/equity, and similar), without manually calculating them from the raw statements.

**Why this priority**: Ratios are the most commonly scanned financial output for a quick health/valuation check, but they are derived from and depend on the statements in User Story 1 being available first.

**Independent Test**: Can be fully tested by viewing a company's ratio summary and confirming each named ratio is present with a current value.

**Acceptance Scenarios**:

1. **Given** a company with available financial data, **When** the user views its ratio summary, **Then** the system displays P/E, EV/EBITDA, gross margin, FCF yield, debt/equity, and other standard ratios.
2. **Given** a ratio that is not meaningful for a given period (e.g., negative earnings making P/E undefined), **When** the user views it, **Then** the system indicates it is not meaningful rather than displaying a misleading raw number.

---

### User Story 3 - Analyze YoY / QoQ Trends and Earnings Estimates vs. Actuals (Priority: P3)

A user wants to see how a company's financials and earnings performance are trending over time — year-over-year and quarter-over-quarter — and how actual earnings have compared to analyst estimates, to judge momentum and management credibility.

**Why this priority**: A deeper analytical layer built on top of the statements and ratios; high value for active research but a narrower, later step in a user's research flow than simply viewing current figures.

**Independent Test**: Can be fully tested by viewing a company's trend view and confirming YoY/QoQ comparisons are shown, and separately confirming an earnings estimate-vs-actual comparison is shown, independent of the raw statement views.

**Acceptance Scenarios**:

1. **Given** a company with multiple periods of financial history, **When** the user views its trend analysis, **Then** the system shows year-over-year and quarter-over-quarter changes for key line items and ratios.
2. **Given** a company that has reported earnings, **When** the user views its earnings history, **Then** the system shows each period's estimated vs. actual results (e.g., EPS, revenue) and whether it beat, met, or missed.

---

### Edge Cases

- What happens when a company has never reported quarterly data separately from annual (e.g., certain foreign filers)? System should show what's available and indicate the gap rather than presenting an empty quarterly view as an error.
- What happens when a ratio's inputs are missing or zero (e.g., no debt, making debt/equity trivially zero, or negative equity making the ratio not meaningful)? System should distinguish "zero" from "not meaningful/undefined."
- How does the system handle known filing-categorization inconsistencies where a line item is reported as zero in some periods and populated in others for the same company (a data-source quirk, not a real business change)? Trend displays should avoid presenting these as if they were real swings.
- What happens when analyst estimates aren't available for a period (e.g., a company with thin analyst coverage)? System should show actuals alone and indicate no estimate was available, rather than a blank or misleading comparison.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a company's income statement for both annual and quarterly periods.
- **FR-002**: System MUST display a company's balance sheet for both annual and quarterly periods.
- **FR-003**: System MUST display a company's cash flow statement for both annual and quarterly periods.
- **FR-004**: System MUST display key valuation and financial-quality ratios for a company, including at minimum P/E, EV/EBITDA, gross margin, FCF yield, and debt/equity.
- **FR-005**: System MUST indicate when a ratio is not meaningful for a given period (e.g., due to negative or near-zero inputs) rather than displaying a raw but misleading value.
- **FR-006**: System MUST show year-over-year trend comparisons for key financial line items and ratios.
- **FR-007**: System MUST show quarter-over-quarter trend comparisons for key financial line items and ratios.
- **FR-008**: System MUST display, for each reported earnings period, the actual results alongside the analyst-estimated results for comparable metrics (e.g., EPS, revenue).
- **FR-009**: System MUST indicate whether each reported earnings period beat, met, or missed estimates.
- **FR-010**: System MUST indicate when a company has limited or unavailable financial history for a requested period rather than presenting an empty view indistinguishable from an error.

### Key Entities

- **Financial Statement**: A company's income statement, balance sheet, or cash flow statement for a specific period (annual or quarterly), composed of line items.
- **Financial Ratio**: A derived metric (e.g., P/E, EV/EBITDA, gross margin, FCF yield, debt/equity) computed from statement line items and/or market data for a company and period.
- **Earnings Period Result**: A company's actual reported results (e.g., EPS, revenue) for a period, together with the analyst consensus estimate for that period and the beat/meet/miss outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view all three core financial statements (income, balance sheet, cash flow) for a company in a single visit to its financials view.
- **SC-002**: A user can find a company's key ratios (P/E, EV/EBITDA, gross margin, FCF yield, debt/equity) without performing any manual calculation.
- **SC-003**: A user can identify whether a company's key metrics improved or worsened year-over-year and quarter-over-quarter without cross-referencing separate periods manually.
- **SC-004**: A user can determine, for any reported quarter, whether the company beat, met, or missed earnings estimates without consulting an outside source.
- **SC-005**: Ratios that are not meaningful for a given period are never presented as if they were valid comparable numbers.

## Assumptions

- Financial statement and ratio data covers publicly traded companies with standard SEC-equivalent filings; non-standard filers (e.g., certain foreign issuers) may have gaps, which the system surfaces rather than fills in.
- "Key ratios... etc." in the source description is treated as a representative, non-exhaustive set (P/E, EV/EBITDA, gross margin, FCF yield, debt/equity); additional standard ratios may be added without being considered new scope, since the source explicitly signals the list is illustrative.
- Known data-quality quirks in the underlying source data (e.g., a line item flipping between zero and a populated value across periods due to filing-categorization changes rather than a real business shift) are treated as a data-handling concern for the underlying data source, not a new user-facing requirement in this spec, beyond the edge case noting trend displays should not misrepresent them as real swings.
