# Feature Specification: Gap Analysis Trading Signals

**Feature Branch**: `013-gap-analysis-rules`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Import of the hand-written knowledge spec `specs/gap_analysis_rules.md` (price-gap detection, classification, scoring, Power Earnings Gap watchlist, and PEG Red-to-Green day-trade rules used by the app's TechnicalAnalyst) into spec-kit format."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gap Detection, Classification, and Signal Scoring (Priority: P1)

A user reviewing a stock wants to know whether it gapped up or down, what type of gap it is (breakaway, runaway, exhaustion, or common/noise), and a scored long/short signal reflecting how likely the gap is to continue or reverse, so they get an objective read on the gap instead of guessing from the chart alone.

**Why this priority**: This is the foundational capability every other capability in this feature builds on — gap type, candle color, volume, and moving-average context all feed into a single scored signal that downstream capabilities (PEG, R2G) depend on.

**Independent Test**: Can be fully tested by feeding historical daily OHLCV data containing known gap-up and gap-down days and confirming the system correctly detects the gap, applies the noise filters, classifies its type, and computes the documented 1–5 score.

**Acceptance Scenarios**:

1. **Given** today's low is above yesterday's high, **When** evaluated, **Then** the system flags an up gap and computes its size as a percentage move; **Given** today's high is below yesterday's low, **When** evaluated, **Then** the system flags a down gap and computes its size analogously.
2. **Given** a candidate gap fails a noise filter (an ex-dividend date coincides with the gap, dollar volume is under $5M on the gap day, or share volume is under 100K on the gap day), **When** evaluated, **Then** the system excludes it from actionable signal scoring.
3. **Given** a down gap scores 3 or higher on the documented down-gap scoring criteria, **When** evaluated, **Then** the system surfaces it as an actionable long signal candidate; **Given** it scores 2 or lower, **Then** the system marks it skip/paper-trade-only.
4. **Given** an up gap occurs after an extended prior trend at an extreme price, **When** evaluated, **Then** the system classifies it as an Exhaustion gap and does not recommend trading in the gap direction.

---

### User Story 2 - Power Earnings Gap (PEG) Watchlist Generation (Priority: P2)

A user wants the system to identify earnings-driven gaps that show clear institutional buying (strong close, huge volume), score and prioritize them by short-interest amplification and market/sector context, and add qualifying candidates to a swing-trade watchlist for entry days-to-weeks later.

**Why this priority**: PEG detection is a distinct, high-value watchlist-generation strategy built on top of basic gap detection; valuable on its own but depends on P1's gap-detection foundation.

**Independent Test**: Can be fully tested by feeding a known earnings-gap day's OHLCV and volume data plus a short-interest value and confirming the system correctly qualifies/disqualifies the PEG candidate and computes the documented priority score.

**Acceptance Scenarios**:

1. **Given** a stock gaps up on an earnings report, closes at or near its session high, and posts volume significantly above average, **When** evaluated, **Then** the system qualifies it as a Power Earnings Gap candidate.
2. **Given** a gap-up earnings candle reverses and closes red, **When** evaluated, **Then** the system does not add it to the PEG watchlist, regardless of volume.
3. **Given** a qualifying PEG candidate has short interest of 10% or higher, **When** scored, **Then** the system raises its expected-move tier and watchlist priority.
4. **Given** the PEG signal score is 4 or higher, **When** evaluated, **Then** the system marks it a high-priority watchlist add; **Given** the broader market is overbought at that time, **Then** the system still adds it to the watchlist but flags a hold-off-on-entry caution.

---

### User Story 3 - PEG Red-to-Green (R2G) Day Trade Signal (Priority: P3)

A user wants the system to flag the next-session setup after a confirmed PEG — a small red open reversing to green — as a same-day momentum entry trigger, distinct from the multi-day/week PEG swing entry.

**Why this priority**: This is a narrower, faster-turnaround variant that depends on a PEG already having been confirmed (P2); valuable for day traders specifically but not required for the swing-trade watchlist to function.

**Independent Test**: Can be fully tested by feeding a confirmed-PEG day followed by a next-session open/intraday sequence and confirming the system only flags the R2G setup when all documented setup requirements are met, with the correct entry trigger, stop, and target.

**Acceptance Scenarios**:

1. **Given** a stock had a confirmed PEG the previous session, **When** the next session opens slightly red (a small give-back, not a large gap down), **Then** the system watches for a red-to-green cross as the day-trade entry trigger.
2. **Given** the next session opens down significantly after a PEG, **When** evaluated, **Then** the system does not flag the R2G setup (sellers are considered in control).
3. **Given** price crosses from below to above the prior session's close while the R2G setup is active, **When** evaluated, **Then** the system flags the long entry trigger with a stop just below that session's opening low and identifies the nearest higher round-number or historical resistance level as an initial target.

---

### Edge Cases

- What happens when an intraday opening gap fills within the first 30 minutes of the session? Continuation in the gap direction is not expected for that session. If it has not filled within 30 minutes, continuation in the gap direction is favored for the remainder of the session.
- What happens when a gap has not closed within 3 trading days? The system must not treat this as a trend-continuation signal — this is explicitly not a reliable predictor per the source methodology.
- What happens when 500 or more stocks gap in the same direction on the same day (a "high gap day")? The system applies the market-context day-1-versus-day-2+ continuation/reversal rule in addition to the single-stock rule.
- What happens when a gap is small, illiquid, or filtered out by the noise filters? It is ignored — not scored or surfaced as a signal.
- What happens when the R2G red open is several dollars red rather than a small give-back? The system must not flag the R2G setup; a large red open indicates sellers are in control.
- How does prior market direction affect an up-gap signal? Per the source rules, prior market direction has little effect on up-gap signals and is not used to adjust them — only down-gap timing is adjusted (see FR-016).
- What happens when three consecutive rising gaps (windows) remain unclosed? The system flags an overbought condition and treats the unclosed gap ranges as candidate support zones (for rising gaps) or resistance zones (for falling gaps).

## Requirements *(mandatory)*

### Functional Requirements

**Gap detection and filtering**

- **FR-001**: System MUST detect an up gap when the current session's low is above the prior session's high, and a down gap when the current session's high is below the prior session's low, and MUST compute the gap size as a percentage move between the two sessions.
- **FR-002**: System MUST exclude from actionable scoring any gap that coincides with an ex-dividend date, has dollar volume under $5M on the gap day, or has share volume under 100K on the gap day.
- **FR-003**: System MUST separately track opening gaps that fill within the same session, distinct from gaps that remain open at the close.

**Gap type classification**

- **FR-004**: System MUST classify each qualifying gap as one of: Breakaway (out of a prior consolidation/range), Runaway/Measuring (occurring mid-trend), Exhaustion (occurring after an extended trend at an extreme price), or Common (small/illiquid — not actionable).
- **FR-005**: System MUST treat Breakaway and Runaway/Measuring gaps as continuation signals in the gap's direction, and Exhaustion gaps as reversal signals that must not be traded in the gap direction.
- **FR-006**: For Runaway/Measuring gaps, System MUST project a continuation target by adding the distance from the trend's starting price to the gap price, applied forward from the gap price.

**Baseline return pattern**

- **FR-007**: System MUST apply the documented baseline expectation that price tends to move lower on Day 1 following any gap (up or down); that down gaps tend to reverse upward by Day 3 or later (a long signal); and that up gaps tend to show negative returns through Day 10 before recovering by Day 30 (a short signal for Days 1–10, long by Day 30).

**Candle color context**

- **FR-008**: System MUST evaluate the color (close-versus-open) of both the pre-gap bar and the gap-day bar and classify the combination into the documented patterns — Black/Down/Black, Black/Down/White, White/Down/Black, White/Up/White, Black/Up/White — each carrying its own documented long/short/avoid signal.
- **FR-009**: System MUST apply the rule that when the pre-gap bar is bearish (black) and a gap occurs, the expected reaction is upward regardless of the gap's direction.

**Volume rules**

- **FR-010**: System MUST classify gap-day volume relative to the 10-day average volume into Low (under 75%), Average (75–125%), High (over 125%), or Extreme (over 200%) bands.
- **FR-011**: System MUST apply the documented volume-conditioned signals: a low-volume down gap favors an immediate Day 1 long; a high-volume down gap favors waiting past Day 3 before going long (reversal expected by Day 5); a high or extreme-volume up gap favors a stronger short opportunity, with extreme volume on an up gap treated as a strong short signal.

**Moving average rules**

- **FR-012**: System MUST compute 10-day, 30-day, and 90-day simple moving averages and evaluate the gap price relative to each.
- **FR-013**: System MUST flag a down gap occurring above the 30-day moving average as the strongest documented long signal in the rule set, and an up gap occurring below its moving average — or more than 175% above it — as a strong documented short signal.

**Market context**

- **FR-014**: System MUST count same-direction gapping stocks across the market for a given session and classify a session as a "high gap day" when 500 or more stocks gap the same direction.
- **FR-015**: System MUST apply the documented high-gap-day rule: continuation in the gap direction on Day 1, reversal against the gap direction on Day 2 and later.
- **FR-016**: System MUST factor prior 1–10 day market direction into down-gap reversal timing only — delaying the expected long entry when the market has been down hard, and favoring a sooner long entry when the market has been trending up — and MUST NOT apply this adjustment to up-gap signals.

**Gap closing statistics**

- **FR-017**: System MUST NOT treat "gap unclosed after 3 days" as a trend-continuation signal.
- **FR-018**: System MUST apply the opening-gap rule that an intraday gap unfilled within the first 30 minutes of trading favors continuation in the gap direction for the remainder of that session.
- **FR-019**: System MUST flag 3 consecutive unclosed rising gaps as an overbought condition, and MUST treat prior unclosed rising/falling gap ranges as candidate support/resistance zones respectively.

**Signal scoring**

- **FR-020**: System MUST compute a 1–5 point score for down-gap (potential long) candidates from the documented conditions (gap size over 1%, prior bar black, gap above the 30-day moving average, low volume, market recently up or neutral), and a separate 1–5 point score for up-gap (potential short) candidates from its own documented conditions (gap size over 1%, White/Up/White pattern, gap below the moving average, high or extreme volume, exhaustion-gap context).
- **FR-021**: System MUST treat a score of 3 or higher as actionable, and a score of 2 or lower as skip/paper-trade-only.

**Power Earnings Gap (PEG) watchlist**

- **FR-022**: System MUST qualify a candidate as a Power Earnings Gap only when all three criteria are met: an earnings-driven gap up, a close at or near the session high, and volume significantly above average.
- **FR-023**: System MUST disqualify a PEG candidate whose gap-up candle reverses and closes red, regardless of volume.
- **FR-024**: System MUST incorporate short interest into PEG prioritization, escalating the expected-move tier as short interest rises through the documented bands (under 10% standard, 10–20% ideal, 20–30% aggressive squeeze likely, over 30% explosive potential).
- **FR-025**: System MUST apply contextual filters before adding a PEG candidate to the watchlist: overall market health (via the companion Market Breadth Timing Signals feature), sector strength, and the absence of a structurally-breaking macro/geopolitical event.
- **FR-026**: System MUST NOT recommend entry on the PEG gap day itself; entry is only recommended after a subsequent qualifying consolidation pattern (e.g., bull flag, pennant, ascending wedge) that holds above the gap-day close.
- **FR-027**: System MUST compute a PEG signal score from the documented weighted conditions (a strong close position, volume at or above 200% of the 10-day average, short interest at or above 10%, sector in an uptrend, market breadth not overbought), and classify it as high-priority (4 or higher), lower-conviction watchlist (2–3), or skip (1 or lower).

**PEG Red-to-Green (R2G) day trade**

- **FR-028**: System MUST only flag an R2G day-trade setup when all three setup requirements hold: a confirmed PEG the prior session, a small red (below prior close) open the next session, and that red open is not a large gap-down.
- **FR-029**: System MUST flag the R2G long entry trigger at the moment price crosses from below to above the prior session's close, with a stop placed just below that session's opening low.
- **FR-030**: System MUST identify an initial profit target from the nearest higher round-number price level and/or nearest higher historical resistance level.
- **FR-031**: System MUST represent the R2G setup as a same-session, intraday-timeframe signal distinct from the multi-day/week PEG swing-entry setup, and MUST NOT conflate the two entry timings in its output.

### Key Entities *(include if feature involves data)*

- **Gap Event**: A detected up/down gap for a ticker on a date; carries gap size, type classification, candle-color pattern, volume band, moving-average context, and computed score.
- **PEG Candidate**: A gap event that has passed Power Earnings Gap qualification criteria; carries short-interest tier, PEG signal score, and watchlist priority tier.
- **R2G Setup**: A day-trade-specific state derived from a PEG candidate's following session; carries entry trigger, stop, and target levels.
- **Market Gap Context**: Aggregate same-day gap breadth across the market (count and direction), used for the high-gap-day rule.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of qualifying gaps (those passing liquidity/ex-dividend filters) receive a type classification and a numeric score without manual review.
- **SC-002**: PEG candidates that close red on the gap day are never present on the resulting watchlist output (zero false qualifications in validation testing).
- **SC-003**: Users can retrieve a ticker's full gap analysis — type, score, PEG status, and R2G eligibility — in a single report rather than manually checking volume, moving averages, and candle color separately.
- **SC-004**: R2G setups are only surfaced during the single session immediately following a confirmed PEG (never surfaced multiple days later).

## Assumptions

- Short-interest data is available from an existing data source used elsewhere in this app, with sufficient recency to apply the short-interest amplifier tiers (FR-024).
- The "overall market health" contextual filter for PEG qualification (FR-025) is provided by the companion Market Breadth Timing Signals feature (spec 012); this spec does not redefine breadth thresholds.
- Round-number and historical resistance levels used for R2G targets (FR-030) are derived from the same OHLC price history already used elsewhere in this app; no new external data source is assumed.
- The R2G setup (FR-028–FR-031) inherently requires intraday (sub-daily) price granularity to detect the red-to-green cross and manage the trade; this is treated as a data requirement specific to this one setup, distinct from the rest of this feature (and from the companion Strat feature) which otherwise operates on daily-or-longer bars.
