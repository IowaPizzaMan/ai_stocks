# Feature Specification: Earnings Transcripts

**Feature Branch**: `007-earnings-transcripts`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Ingest and parse earnings call transcripts; sentiment analysis (management tone, guidance confidence); keyword tracking (e.g., 'headwinds,' 'accelerating,' 'cautious'); compare tone across quarters." (from StockAI product spec, Core Feature Areas #7)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Earnings Call Sentiment for a Stock (Priority: P1)

A user researching a stock wants to know, without reading a full earnings call transcript themselves, whether management's tone was confident or cautious and how confident their guidance sounded.

**Why this priority**: This is the core value of the feature — a fast read on management tone; everything else (keyword tracking, cross-quarter comparison) is an elaboration of this base signal.

**Independent Test**: Can be fully tested by viewing a stock's most recent earnings call and confirming a management tone score/label and a guidance confidence indicator are both displayed.

**Acceptance Scenarios**:

1. **Given** a stock with a processed earnings call transcript, **When** the user views its earnings sentiment, **Then** the system displays an overall management tone reading for that call.
2. **Given** a processed earnings call, **When** the user views its sentiment, **Then** the system displays a separate indicator of guidance confidence.
3. **Given** a stock whose most recent earnings call transcript hasn't been processed yet, **When** the user views its earnings sentiment, **Then** the system indicates it is not yet available rather than showing stale or blank data as if current.

---

### User Story 2 - See Notable Keywords from the Call (Priority: P2)

A user wants to see which notable words or phrases (e.g., "headwinds," "accelerating," "cautious") came up in the call and how often, to get texture beyond a single tone score.

**Why this priority**: Adds interpretive depth to the tone reading from User Story 1, but is a secondary lens a user checks after seeing the headline sentiment, not the first thing they look for.

**Independent Test**: Can be fully tested by viewing a call's keyword breakdown and confirming tracked keywords and their frequency are shown, independent of the overall tone score.

**Acceptance Scenarios**:

1. **Given** a processed earnings call, **When** the user views its keyword tracking, **Then** the system shows which tracked keywords/phrases appeared and how often.
2. **Given** keyword tracking results, **When** the user views them, **Then** the system distinguishes keywords generally associated with positive tone (e.g., "accelerating") from those associated with negative/cautious tone (e.g., "headwinds," "cautious").

---

### User Story 3 - Compare Tone Across Quarters (Priority: P3)

A user wants to see how management's tone has shifted from one quarter's call to the next, to spot an improving or deteriorating trend that a single call in isolation wouldn't reveal.

**Why this priority**: A trend-level view that depends on multiple processed calls already existing (User Story 1 repeated over time); valuable for longer-horizon research but not needed to get value from a single quarter's read.

**Independent Test**: Can be fully tested by viewing a stock with multiple processed quarters of earnings calls and confirming a tone comparison across those quarters is displayed.

**Acceptance Scenarios**:

1. **Given** a stock with two or more processed earnings calls, **When** the user views its tone history, **Then** the system displays how tone has changed quarter to quarter.
2. **Given** a tone history, **When** the user views a specific quarter, **Then** the system indicates whether that quarter's tone improved, worsened, or stayed flat relative to the prior quarter.

---

### Edge Cases

- What happens when a transcript isn't available for a given quarter (e.g., a company that doesn't hold a public call)? System should indicate no transcript is available for that period rather than showing a blank or defaulting to a neutral score.
- What happens when a transcript is available but only partially parseable (e.g., poor audio-to-text quality)? System should indicate reduced confidence in that period's sentiment reading rather than presenting it as equally reliable.
- How does the system handle sarcasm, hedged language, or contradictory statements within the same call (e.g., cautious language paired with raised guidance)? The system should present the tone and guidance-confidence readings as best-effort signals, not an infallible verdict, so the user isn't misled into full reliance on the score alone.
- What happens when a tracked keyword appears but in a context that reverses its usual meaning (e.g., "no longer facing headwinds")? This is a known limitation of keyword-frequency tracking; system should present keyword counts as a texture signal alongside the tone score, not as a standalone verdict.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST ingest and process earnings call transcripts for tracked companies.
- **FR-002**: System MUST display an overall management tone reading for each processed earnings call.
- **FR-003**: System MUST display a guidance confidence indicator, separate from the overall tone reading, for each processed earnings call.
- **FR-004**: System MUST indicate when a stock's earnings sentiment has not yet been processed or is unavailable for a period, rather than presenting incomplete data as current.
- **FR-005**: System MUST track occurrences of notable keywords/phrases (e.g., "headwinds," "accelerating," "cautious") within each processed call.
- **FR-006**: System MUST display keyword occurrence frequency per call, distinguishing keywords generally associated with positive tone from those associated with negative/cautious tone.
- **FR-007**: System MUST display how a stock's management tone has changed across quarters for stocks with two or more processed calls.
- **FR-008**: System MUST indicate whether a given quarter's tone improved, worsened, or held flat relative to the prior quarter.

### Key Entities

- **Earnings Call Transcript**: The ingested source text for a company's earnings call for a specific period (quarter).
- **Earnings Sentiment Reading**: A derived result for a processed transcript — includes an overall management tone score/label and a separate guidance confidence indicator.
- **Tracked Keyword**: A word or phrase monitored across calls (e.g., "headwinds," "accelerating," "cautious"), each associated with a general tone polarity (positive/negative), with an occurrence count per call.
- **Tone History**: A per-stock, time-ordered series of sentiment readings across quarters, used to derive quarter-over-quarter tone change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can determine management's overall tone for a stock's latest earnings call without reading the transcript themselves.
- **SC-002**: A user can identify the most notable keywords from a call and their frequency in a single view.
- **SC-003**: A user can tell, for any given quarter, whether tone improved or worsened relative to the prior quarter without comparing raw scores manually.
- **SC-004**: A user is never shown a sentiment reading for a call that hasn't actually been processed yet.

## Assumptions

- The specific list of tracked keywords is illustrative in the source ("e.g., 'headwinds,' 'accelerating,' 'cautious'") rather than an exhaustive fixed set; this spec requires keyword tracking exist and be shown with polarity, without freezing the exact keyword list, since expanding it later is not a scope change.
- The precise tone-scoring methodology (e.g., a numeric score vs. a categorical label) is an implementation-level decision; this spec requires an overall tone reading and a separate guidance-confidence reading exist and be shown, without prescribing their exact scale or format.
- Sentiment and tone readings are treated as best-effort, assistive signals rather than a guaranteed-accurate verdict — consistent with the known limitations of automated tone/keyword analysis (e.g., sarcasm, contradictory statements) noted in Edge Cases.
