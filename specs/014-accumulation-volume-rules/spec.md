# Feature Specification: Accumulation Volume Detection

**Feature Branch**: `014-accumulation-volume-rules`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Import of the hand-written knowledge spec `specs/accumulation_volume_rules.md` (institutional accumulation/distribution volume-pattern rules used by the app's InstitutionalAnalyst and TechnicalAnalyst) into spec-kit format."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detect Institutional Accumulation via Volume Asymmetry (Priority: P1)

A user researching a stock wants the system to flag when it shows a sustained asymmetry between up-day and down-day volume — heavy volume on up days, light volume on down days — since this is the footprint large institutional buyers leave behind, so they can weight it as a bullish conviction signal.

**Why this priority**: This is the foundational detection capability everything else in this feature builds on — the sustained-pattern check, PEG amplifier, and distribution-warning capabilities all depend on this core up/down volume comparison existing first.

**Independent Test**: Can be fully tested by feeding daily OHLCV history containing a known sustained up/down volume asymmetry and confirming the system computes the correct ratio, volume-spike detection, and resulting score band.

**Acceptance Scenarios**:

1. **Given** the 20-day average up-day volume divided by the average down-day volume exceeds 3.0, **When** evaluated, **Then** the system reports "strong accumulation — institutional interest confirmed."
2. **Given** that ratio is below 1.5, **When** evaluated, **Then** the system reports no accumulation signal.
3. **Given** at least one up day in the last 20 trading days had volume exceeding 3x the 50-day average daily volume, **When** evaluated, **Then** the system flags a strong institutional-footprint event on that day.

---

### User Story 2 - Confirm Sustained Pattern vs. One-Off Spike (Priority: P2)

A user wants the system to require the volume asymmetry to persist over multiple weeks — not just a single day — before treating it as a confirmed institutional signal, distinguishing an early/forming pattern from a confirmed one.

**Why this priority**: This prevents false positives from a single volume spike and is what makes the P1 detection trustworthy enough to act on, but the underlying ratio/spike detection from P1 must already exist.

**Independent Test**: Can be fully tested by feeding volume history representing both a short-lived spike and a multi-week sustained pattern and confirming the system labels them EARLY_ACCUMULATION and confirmed ACCUMULATION respectively.

**Acceptance Scenarios**:

1. **Given** the asymmetric volume pattern has been present less than 1 week, **When** evaluated, **Then** the system labels it EARLY_ACCUMULATION rather than a confirmed signal.
2. **Given** at least 60% of up days over a rolling 20-day window have volume at or above 1.5x average daily volume, no more than 2–3 high-volume down days occurred in that window, and the pattern has persisted 3 or more weeks, **When** evaluated, **Then** the system confirms the accumulation signal.

---

### User Story 3 - Amplify Conviction Following a Power Earnings Gap (Priority: P3)

A user wants accumulation volume appearing in the weeks after a qualifying Power Earnings Gap to be treated as elevated or maximum conviction, so the highest-quality setups — a confirmed earnings gap plus sustained institutional buying afterward — are surfaced distinctly from either signal alone.

**Why this priority**: This is a cross-signal enhancement on top of P1/P2 that increases conviction; valuable but not required for the base accumulation signal to be useful on its own.

**Independent Test**: Can be fully tested by feeding a ticker's history containing both a qualifying gap event and a subsequent sustained accumulation pattern and confirming the amplifier is applied and reflected in the score.

**Acceptance Scenarios**:

1. **Given** a ticker had a qualifying Power Earnings Gap event within the last 60 days and currently shows accumulation volume, **When** scored, **Then** the accumulation score includes the PEG amplifier point, reaching its highest tier when combined with a sustained pattern.
2. **Given** back-to-back Power Earnings Gap events with sustained accumulation volume between them, **When** evaluated, **Then** the system labels this the highest-conviction institutional interest case.

---

### User Story 4 - Detect Distribution (Sell-Side) Warning (Priority: P3)

A user wants the inverse pattern — heavy down-day volume with light up-day volume — flagged as a distribution warning, especially when it appears right after a period of accumulation, so a potential institutional exit can be caught early rather than discovered after the stock has already fallen.

**Why this priority**: This is the mirror-image capability to P1's core detection; equally important for risk management but addressable as a separate slice from the buy-side signal.

**Independent Test**: Can be fully tested by feeding a volume history showing the inverse asymmetry and confirming the system flags DISTRIBUTION_WARNING, including the case where it follows a prior accumulation period.

**Acceptance Scenarios**:

1. **Given** the up/down volume ratio over the rolling window falls below 0.7, **When** evaluated, **Then** the system flags DISTRIBUTION_WARNING.
2. **Given** distribution volume appears immediately after a period previously scored as accumulation, **When** evaluated, **Then** the system explicitly notes the rotation-out context in its output rationale.

---

### Edge Cases

- What happens when there is not yet 50 trading days of history (e.g., a new listing)? The average-daily-volume comparison (Rule 2) cannot be computed reliably; the system flags insufficient history rather than reporting a score.
- What happens when a stock has exactly one very large volume spike but no sustained asymmetry? It is not scored as confirmed accumulation; at most it is flagged EARLY_ACCUMULATION pending more history.
- What happens when the accumulation score is high but there is no matching institutional (13F-style) filing yet? The system still reports the accumulation score; the filing-based convergence signal is an additional confirmation layer, not a prerequisite, since volume evidence can lead filings by a quarter or more.
- What happens when both an accumulation pattern and a distribution pattern could plausibly apply within the same lookback window (a regime change mid-window)? The more recent sub-pattern takes precedence, with the transition itself surfaced in the output rationale.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute, over a rolling 20-trading-day window, the average volume on up days (close greater than open) and the average volume on down days (close less than open), and their ratio.
- **FR-002**: System MUST classify the up/down volume ratio into bands: below 1.5 (no signal), 1.5–2.0 (mild accumulation), 2.0–3.0 (moderate accumulation), and above 3.0 (strong accumulation).
- **FR-003**: System MUST compute, for each up day, that day's volume relative to the 50-day average daily volume, and classify into bands: below 1.5x (normal), 1.5x–2x (elevated), 2x–3x (accumulation signal), and above 3x — especially on a gap-up day — (strong institutional footprint, flagged immediately).
- **FR-004**: System MUST require the pattern to be sustained — at least 60% of up days in the rolling 20-day window at or above 1.5x average daily volume, no more than 2–3 high-volume down days in that window, and persistence of at least 3 weeks — before classifying a confirmed ACCUMULATION signal.
- **FR-005**: System MUST classify a pattern that has been present less than 1 week as EARLY_ACCUMULATION rather than confirmed.
- **FR-006**: System MUST apply a Power Earnings Gap amplifier: when a qualifying gap event (per the companion Gap Analysis Rules feature, gap score of 3 or higher) occurred within the trailing 60 days and accumulation volume is present, treat conviction as elevated; and treat back-to-back qualifying gap events with sustained accumulation between them as the highest-conviction case.
- **FR-007**: System MUST compute a 0–5 point accumulation score from the documented weighted conditions — ratio above 1.5, ratio above 2.5, at least one up day above 3x average daily volume, sustained for 3 or more weeks, follows a qualifying gap event — and classify it per the documented interpretation bands: 0–1 no meaningful accumulation, 2 mild/worth watching, 3 moderate/add to watchlist, 4 strong/institutional interest confirmed, 5 maximum conviction.
- **FR-008**: System MUST detect the inverse (distribution) pattern — high volume on down days, light volume on up days, with the up/down ratio falling below 0.7 — and flag it as DISTRIBUTION_WARNING.
- **FR-009**: System MUST explicitly note in its output when a distribution pattern follows a previously-scored accumulation period, since this represents a probable institutional exit/rotation.
- **FR-010**: System MUST cross-reference the volume-based accumulation score with institutional-filing data where available, and flag a "strong convergence" condition when the accumulation score is 3 or higher and newly-appearing institutional positions are present, while still reporting the accumulation score independently when filing data is not yet available, since filings can lag volume evidence by a quarter or more.
- **FR-011**: System MUST combine the accumulation score with the current market-breadth timing signal (per the companion Market Breadth Timing Signals feature) to produce an elevated combined recommendation when accumulation is strong and market timing is favorable, and a "hold off" recommendation when accumulation is strong but the market is overbought.
- **FR-012**: System MUST produce, per ticker, a structured output including the accumulation score, the up/down volume ratio, the maximum single-day volume spike relative to average daily volume, the pattern duration in days, a Power-Earnings-Gap-amplifier flag, a signal label (ACCUMULATION, EARLY_ACCUMULATION, NEUTRAL, or DISTRIBUTION_WARNING), a distribution-warning flag, and a plain-language rationale.

### Key Entities *(include if feature involves data)*

- **Volume Day Sample**: A single trading day's volume and up/down classification (close versus open) for a ticker.
- **Accumulation Window**: The rolling 20-trading-day aggregate — average up/down volume, ratio, and count of high-volume days — used to evaluate the sustained-pattern test.
- **Accumulation Score Result**: The computed 0–5 score, up/down ratio, maximum volume spike, pattern duration, PEG-amplifier flag, and signal label for a ticker.
- **Distribution Warning Event**: A detected inverse (distribution) pattern, with its ratio and whether it follows a prior accumulation period.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An accumulation score is computed for 100% of tickers with at least 50 trading days of history on each scheduled run.
- **SC-002**: A confirmed ACCUMULATION signal is never issued for a pattern shorter than 3 weeks (zero false confirmations in validation testing) — such patterns are instead reported as EARLY_ACCUMULATION.
- **SC-003**: Users can see, in one output per ticker, both the accumulation score and a plain-language rationale explaining which conditions drove it, without needing to inspect raw daily volume bars themselves.
- **SC-004**: Tickers transitioning from accumulation to distribution are flagged within the same run in which the distribution threshold is crossed, with no detection lag beyond the rolling window itself.

## Assumptions

- Daily OHLCV history of at least 50 trading days is available for the tickers this feature evaluates; tickers with less history are excluded from scoring rather than scored with partial data (see Edge Cases).
- Institutional-filing data (FR-010) and short-interest-style external data are supplied by other existing capabilities of this app; this spec only defines how accumulation-volume evidence combines with them, not how they are sourced.
- The rolling-window parameters carried over from the source methodology (20 trading days, a 3-week sustained-pattern minimum, 50-day average daily volume) are the default starting values and may be tuned operationally without changing the underlying rule structure.
- The Power-Earnings-Gap qualification referenced in FR-006 is defined by the companion Gap Analysis Rules feature (spec 013); this spec does not redefine gap qualification, only how accumulation volume combines with it.
