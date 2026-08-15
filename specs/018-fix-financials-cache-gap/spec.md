# Feature Specification: Fix Stale Empty Financials Cache

**Feature Branch**: `018-fix-financials-cache-gap`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "When I pull the most recent data for BSX and look at the financial information, I don't see anything, but when I check FMP directly for this ticker I do see results (income statement data for BSX confirmed available via the provider)."

## Clarifications

### Session 2026-08-15

- Q: How should the system decide when to retry a ticker whose last fetch hit a temporary condition (provider-restricted or budget-exceeded)? → A: Retry on every subsequent analysis run for that ticker, no additional cooldown — rely solely on the existing per-minute/daily budget guard.

Confirmed against the running system while clarifying: the BSX case is the provider-restricted path, not budget. `agent-runner/tools/financials.py` logged `FMP 402 for BSX/income_annual — not covered on this plan, skipping` (and the same for the other six statement types) on 2026-08-09, and that all-empty result has been served from cache since. The daily budget guard (`fmp_daily_soft_cap`) is disabled by default (`0`) in this deployment, so the budget-exceeded path is a designed-for scenario, not the one that actually occurred here. Provider coverage evidently changed within about six days (FMP now returns data for BSX), which is why a long retry cooldown was rejected in favor of retrying on every run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Financial statements appear when the provider has data (Priority: P1)

A user views a stock's financial statements (income, balance sheet, cash flow, ratios) on the stock detail page. The data provider currently has this data available for the ticker. The user expects to see it, not a blank/missing section.

**Why this priority**: This is the reported bug. A ticker with confirmed provider data (BSX) shows nothing in the app, which makes the financials feature look broken and undermines trust in the whole analysis output.

**Independent Test**: Pick a ticker whose most recent cached financials fetch came back empty due to a transient condition (e.g., the provider temporarily didn't cover the symbol, or the daily call budget was exceeded mid-fetch). Trigger a fresh analysis for that ticker. Confirm the financial statements now populate, since the provider currently has the data.

**Acceptance Scenarios**:

1. **Given** a ticker's cached financial data is empty because an earlier fetch was interrupted by a temporary provider or budget condition, **When** the user triggers a new analysis for that ticker, **Then** the system re-attempts the fetch rather than continuing to serve the empty result for the remainder of the cache window.
2. **Given** the provider currently has financial statement data for a ticker, **When** an analysis run fetches that ticker's financials, **Then** the stock detail page displays the fetched statements.
3. **Given** a ticker's financials were already successfully fetched and populated within the current cache window, **When** the user revisits the stock detail page, **Then** the previously fetched data is shown without triggering a redundant fetch.

---

### User Story 2 - Distinguish "confirmed no data" from "temporarily unavailable" (Priority: P2)

When a financials fetch comes back empty, the system should be able to tell apart two different situations: the provider genuinely has no financial statements for this ticker, versus the fetch was cut short by a temporary condition (rate/budget limit, momentary provider restriction). Only the first case should be treated as a settled result for the full cache window.

**Why this priority**: Without this distinction, every empty result — regardless of cause — is locked in for the full cache window, silently hiding data that becomes available again. This is the root cause of User Story 1 and needs to hold generally, not just for the one reported ticker.

**Independent Test**: Simulate a fetch where the provider call is interrupted by a temporary condition partway through. Confirm the resulting empty data is treated differently (eligible for retry sooner) than a fetch where the provider affirmatively returned no data for every statement type.

**Acceptance Scenarios**:

1. **Given** a financials fetch is interrupted by a temporary provider or budget condition for one or more statement types, **When** the fetch completes, **Then** the result is not treated as a confirmed "no data available" outcome for those statement types.
2. **Given** a financials fetch completes with the provider affirmatively reporting no records for a statement type, **When** the fetch completes, **Then** that outcome is treated as settled for the normal cache window.

---

### Edge Cases

- What happens when the provider has data for some statement types (e.g., income statement) but genuinely has none for others (e.g., ratios) in the same fetch? Each statement type's outcome must be evaluated independently.
- What happens if a ticker's fetch is retried repeatedly and keeps hitting the same temporary condition on every analysis run (e.g., the provider still doesn't cover that ticker weeks later)? The system must keep degrading gracefully (no crash, no blocked analysis run) on each attempt — retrying every run is acceptable because triggering is manual/per-ticker, not automatic, so volume stays bounded by user behavior and the existing per-minute/daily budget guard.
- What happens to a ticker's financials that were empty under the old behavior before this fix ships — do they require a manual trigger, or do they self-correct on the next scheduled/triggered analysis?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST re-fetch a ticker's not-yet-confirmed financial statement types on every subsequent analysis run for that ticker, when the most recently cached result for those statement types was produced under a temporary provider or budget condition, rather than continuing to serve the empty result for the remainder of the cache window. No additional cooldown is applied beyond the existing per-minute/daily budget guard.
- **FR-002**: System MUST distinguish, per statement type, between "provider confirmed no data" and "fetch did not complete due to a temporary condition" when deciding whether a result is eligible for retry.
- **FR-003**: System MUST continue to serve a confirmed successful fetch (populated or genuinely empty) from cache for the remainder of the standard cache window, without redundant provider calls.
- **FR-004**: System MUST continue to fail soft on provider or budget errors — a fetch that hits a temporary condition MUST NOT crash the analysis run or block other tickers in the same run.
- **FR-005**: Stock detail pages MUST display currently available financial statements for a ticker once a successful fetch has occurred, without requiring a manual cache-clearing step by the user.
- **FR-006**: System MUST rely on the existing per-minute and daily-budget guards as the sole limits on retry volume — no separate per-ticker retry cooldown is required, since analysis is only triggered manually per ticker rather than automatically.

### Key Entities

- **Financials Cache Entry**: The stored result of a financials fetch for a ticker, covering multiple statement types (income, balance sheet, cash flow, ratios, key metrics, growth). Needs an outcome per statement type (confirmed data, confirmed no data, or incomplete/temporary) in addition to the fetched values themselves.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A ticker whose financials were previously empty due to a temporary condition shows populated financial statements within one analysis run after the provider's data becomes available, instead of after the full cache window elapses.
- **SC-002**: Tickers with a confirmed successful fetch continue to load financial statements from cache with no observable increase in page load time or provider call volume.
- **SC-003**: Zero analysis runs fail or abort due to a financials fetch hitting a temporary provider or budget condition.
- **SC-004**: Daily provider call volume attributable to financials fetches does not increase beyond what is needed to retry genuinely incomplete results.

## Assumptions

- Confirmed (not assumed): the reported case is a fetch, on 2026-08-09, where FMP returned 402 ("not covered on this plan") for all seven BSX statement types; that all-empty result has been served from the 90-day cache since, and today's re-analysis runs never retried it because the cache still looked "warm." This is a cache-retry problem, not a display/parsing problem.
- "Temporary condition" covers the two cases already surfaced in the current fetch path: the provider not covering a symbol on the current plan (confirmed as the cause here), and the daily call budget being exceeded mid-fetch (not currently active in this deployment — `fmp_daily_soft_cap` defaults to disabled — but still a designed-for scenario per the existing fail-soft budget guard). Any other error types encountered during planning should be classified into one of the two outcome buckets (confirmed vs. temporary) rather than left ambiguous.
- The existing 90-day cache window for confirmed results is out of scope to change; only the handling of temporary/incomplete outcomes changes.
- Retry cadence for temporary/incomplete outcomes needs no separate cooldown: analysis is only triggered manually per ticker (never on a schedule), so retrying a not-yet-confirmed statement type on every run is bounded by the user's own trigger frequency and the existing per-minute/daily budget guard.
