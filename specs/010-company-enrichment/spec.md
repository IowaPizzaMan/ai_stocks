# Feature Specification: Company Enrichment

**Feature Branch**: `010-company-enrichment`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Company logos next to tickers across the UI; company website scraping for qualitative signal financial statements don't carry (deferred, unresearched)." (from StockAI product spec, Core Feature Areas #10)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See Company Logos Alongside Tickers (Priority: P1)

A user scanning search results, feed cards, watchlist rows, or a stock's own detail header wants to see the company's logo next to its ticker, so they can visually recognize companies faster than reading ticker text alone.

**Why this priority**: This is the only concretely decided, ready-to-build piece of this feature area; the other named idea (website scraping) is explicitly undecided in the source. A logo is also a small, self-contained enhancement that stands alone.

**Independent Test**: Can be fully tested by viewing any surface that lists a ticker (search results, feed cards, watchlist rows, stock detail header) and confirming the company's logo is shown next to it.

**Acceptance Scenarios**:

1. **Given** a company with an available logo, **When** its ticker is shown anywhere in the app (search results, feed cards, watchlist rows, stock detail header), **Then** the company's logo is displayed alongside the ticker.
2. **Given** a company without an available logo, **When** its ticker is shown, **Then** the system displays a reasonable fallback (e.g., a placeholder or the ticker's initials) instead of a broken image or empty gap.
3. **Given** a logo that fails to load (e.g., a broken or unreachable image), **When** the ticker is displayed, **Then** the system falls back gracefully rather than showing a broken-image icon.

---

### Edge Cases

- What happens when a company's logo image is very large, mismatched in aspect ratio, or otherwise inconsistent in size/format across companies? Logos should display consistently sized within each surface regardless of the source image's native dimensions.
- What happens when a newly tracked ticker is added to the system before its logo has been fetched? The fallback (placeholder/initials) should show immediately rather than leaving a blank space until the logo becomes available.
- What happens when a company rebrands and its logo changes? This spec does not require active change-detection; showing the most recently available logo is sufficient.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a company's logo next to its ticker wherever a ticker is shown standalone in the app, including at minimum: search results, feed cards, watchlist rows, and the stock detail header.
- **FR-002**: System MUST display a consistent fallback (e.g., placeholder graphic or ticker initials) when a company has no available logo, instead of a blank space or broken image.
- **FR-003**: System MUST display the same fallback behavior when a logo fails to load, rather than surfacing a broken-image state to the user.
- **FR-004**: System MUST display logos at a consistent size within a given surface, regardless of the source image's native dimensions or aspect ratio.

### Key Entities

- **Company Logo**: An image associated with a company/ticker, used wherever that ticker is displayed; may be unavailable, in which case a fallback is shown.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can visually distinguish companies by logo, not just ticker text, on every surface where tickers are listed.
- **SC-002**: No ticker display ever shows a broken image, regardless of whether that company's logo is available.

## Assumptions

- Logo sourcing is expected to already be substantially covered by existing company profile data the app fetches for other purposes (per the source: "likely already covered... needs a quick verification spike rather than a new integration"); this spec treats logo *display* as the decided, in-scope requirement, while the underlying sourcing/verification work is an implementation concern, not a product requirement to specify further here.
- **Company website scraping** (pulling a company's website/IR page for qualitative signal beyond financial statements) is explicitly described in the source as "deferred, unresearched," with no scoring, extraction design, or user-facing behavior decided. Per the instruction to reflect genuinely deferred/unresearched scope honestly rather than inventing requirements, this spec does **not** include it as a user story or functional requirement. It is noted here only as a known, explicitly out-of-scope future idea: no acceptance criteria, data behavior, or UI surface for it should be assumed from this spec.
