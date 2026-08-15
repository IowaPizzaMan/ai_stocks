# Feature Specification: The Strat Price-Action Rule Engine

**Feature Branch**: `011-the-strat`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Import of the hand-written knowledge spec `specs/the-strat-spec.md` (Rob Smith's Price Discovery System / The Strat methodology) into spec-kit format, covering bar classification, actionable signals, time frame continuity, and broadening formations used by this app's technical analysis engine."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bar Classification and Actionable Signal Detection (Priority: P1)

A trader reviewing a stock wants to know, for any timeframe, what type of price bar just formed (Inside, Directional Up, Directional Down, or Outside) and whether any objectively-defined actionable signal (hammer, shooting star, inside-bar breakout, kicking pattern, Rev Strat) is currently "in force," so they can act on a specific, rules-based setup instead of subjective chart reading.

**Why this priority**: This is the foundational capability everything else in the methodology depends on — every reversal pattern, combination, and checklist item is expressed in terms of bar type and signal state. Without it, nothing downstream works.

**Independent Test**: Can be fully tested by feeding a sequence of historical OHLC bars for one timeframe into the engine and confirming every closed bar receives exactly one of the four classifications, and that hammer/shooting star/inside-breakout/kicking signals are flagged with correct trigger levels and in-force status.

**Acceptance Scenarios**:

1. **Given** a closed bar whose high is ≤ the previous bar's high and whose low is ≥ the previous bar's low, **When** the bar closes, **Then** the system classifies it as an Inside Bar (Type 1) and marks it "Still Inside" (unconfirmed) until close.
2. **Given** a bar that makes both a higher high and a lower low than the previous bar, **When** the bar closes, **Then** the system classifies it as an Outside Bar (Type 3) and additionally identifies whether it is a Bullish Engulfing, Bearish Engulfing, or Regular Outside Bar based on where the open/close fall relative to the prior bar's range.
3. **Given** a hammer or shooting star candle has formed, **When** price subsequently trades beyond the trigger level (above the hammer's high, or below the shooting star's low), **Then** the system marks the signal "in force" and computes its stop/level-of-defense per the applicable execution rule.
4. **Given** a signal is in force, **When** the triggering bar's time period closes without the level of defense being violated, **Then** the signal remains in force into the next period; **When** price violates the level of defense, **Then** the signal is marked no longer in force.

---

### User Story 2 - Time Frame Continuity Assessment (Priority: P2)

A trader wants to know whether the major participation groups (the timeframes this app tracks) are aligned in the same direction (Full Time Frame Continuity) or in conflict, and which group is currently in control, so they can gauge the conviction behind a move before acting.

**Why this priority**: Time Frame Continuity is the primary filter the methodology uses to decide whether a signal is worth taking; it is consumed directly by every trade-checklist evaluation but sits one layer above raw bar classification.

**Independent Test**: Can be fully tested by supplying open/close data for each tracked timeframe on a given date and confirming the system correctly reports each timeframe's color (bullish/bearish), the overall Full TFC status (bullish/bearish/conflict), and which group is identified as in control.

**Acceptance Scenarios**:

1. **Given** the last sale is above the opening price of every tracked major timeframe, **When** TFC is evaluated, **Then** the system reports Bullish Full TFC.
2. **Given** one or two tracked timeframes differ in color from the rest, **When** TFC is evaluated, **Then** the system reports a Conflict state rather than Full TFC.
3. **Given** the shortest two tracked timeframes are confirming each other, **When** TFC is evaluated, **Then** the system treats those two as overriding the longer timeframes for the "currently in control" determination.

---

### User Story 3 - Broadening Formation and Reversal Context (Priority: P3)

A trader wants to see whether a stock is inside a Broadening Formation, which of the 4 canonical reversal patterns (if any) just completed, and a projected magnitude for the current move, so they can size risk and set expectations for how far a signal might run.

**Why this priority**: This adds risk-sizing and target context on top of a detected signal; valuable but the trade is still actionable without it since P1/P2 already identify the signal and its direction.

**Independent Test**: Can be fully tested by feeding a bar sequence that contains a known outside bar and confirming the system flags the fractal Broadening Formation, identifies the correct reversal pattern (2-1-2, 2-2, Failed-2-Goes-3, or 3-1-2) when one occurs, and produces a measured-move projection sized to the prior swing.

**Acceptance Scenarios**:

1. **Given** an outside bar has formed, **When** the lower timeframe is inspected, **Then** the system flags that a fractal Broadening Formation exists at that level.
2. **Given** a directional (2) bar in one direction is immediately followed by a directional bar in the opposite direction, **When** evaluated, **Then** the system classifies this as a 2-2 Reversal.
3. **Given** an actionable signal triggers immediately after a quick prior advance or decline, **When** a measured-move projection is requested, **Then** the system projects a continuation move approximately equal in size to the prior move, from the trigger point.

---

### User Story 4 - Pre-Trade Checklist and Risk Guidance (Priority: P3)

A trader evaluating whether to take a specific setup wants a single consolidated view answering the methodology's standard pre-trade questions (signal count/stack, direction vs. participation-group control, momentum-vs-retracement context, time to exhaustion, stop/level-of-defense, and confirmation from correlated instruments), so they don't have to manually reconcile multiple charts before deciding.

**Why this priority**: This is a synthesis/reporting layer over the P1–P3 capabilities; useful for decision support but not required for the underlying signals to exist and be correct.

**Independent Test**: Can be fully tested by requesting the checklist output for a ticker with at least one in-force signal and confirming all applicable checklist fields are populated (or explicitly marked not applicable) without requiring the user to consult additional charts.

**Acceptance Scenarios**:

1. **Given** a ticker with one or more in-force actionable signals, **When** the pre-trade checklist is generated, **Then** it reports the count and type of stacked signals across tracked timeframes.
2. **Given** a signal's stop/level-of-defense, **When** the checklist is generated, **Then** it reports the specific stop level and the entry trigger per the applicable execution rule for that signal type.
3. **Given** a correlated broader-market instrument (e.g., an index or sector ETF) is in conflict with the ticker's own signal direction, **When** the checklist is generated, **Then** it surfaces this conflict as a caution flag ("natural buyer/seller" context).

---

### Edge Cases

- What happens when a bar is still forming (has not closed) but its range would currently qualify it as an Inside Bar? It MUST be reported as "Still Inside"/unconfirmed, not as a finalized Type 1 classification, until the bar closes.
- How does the system handle an Outside Bar occurring without a preceding directional (2) bar in the same fractal sequence? Per the methodology this cannot happen (a Type 3 bar always follows a Type 2 attempt); any apparent violation should be treated as a data quality issue rather than a new pattern.
- What happens when a 1-Bar Rev Strat closes as a hammer or shooting star? The new actionable trigger becomes the hammer/shooting star's level, not the original inside bar's level, while the pattern is still recorded as countering the original equilibrium.
- What happens when multiple consecutive inside bars form ("multi-inside bar")? The system flags elevated chop risk and increased likelihood of a Rev Strat rather than a clean breakout.
- What happens when this app has no intraday price feed available? 60-minute and shorter intraday timeframes, the Flip, and Uncoupling calculations are out of scope for this app's automated engine; Full TFC is evaluated over the timeframes the app does have available (see FR-030).
- What happens when an inside bar forms in the middle (not near an extreme) of its Mother Bar's range? The system flags the setup as lower-quality ("avoid") rather than a clean actionable breakout.
- How does the system handle VIX-ETN-class instruments (e.g., volatility ETNs) versus normal equities for Broadening Formation entries? These instruments follow a different entry/cover rule set (entries only from BF highs, no "buy the bottom" reclaim assumption) because they structurally decay over time; see FR-040–FR-042.

## Requirements *(mandatory)*

### Functional Requirements

**Bar classification**

- **FR-001**: System MUST classify every closed price bar, on every tracked timeframe, into exactly one of four types — Inside (1), Directional Up (2U), Directional Down (2D), or Outside (3) — based on how its high/low compare to the immediately preceding bar's high/low.
- **FR-002**: System MUST NOT finalize a bar's classification until the bar has closed; a bar still forming that currently qualifies as Inside MUST be reported as unconfirmed ("Still Inside").
- **FR-003**: System MUST further classify every Outside Bar as one of: Bullish Engulfing (gaps below the prior low, closes above the prior high), Bearish Engulfing (gaps above the prior high, closes below the prior low), or Regular Outside Bar (breaches both the prior high and low, but open and/or close remain within the prior bar's range).

**Actionable signals and candlestick formations**

- **FR-004**: System MUST detect and flag Hammer formations (open and close in the top third of the bar's range, following a Directional Down bar) and mark the signal in force once price trades above the hammer's high.
- **FR-005**: System MUST detect and flag Shooting Star formations (open and close in the bottom third of the bar's range, following a Directional Up bar) and mark the signal in force once price trades below the shooting star's low.
- **FR-006**: System MUST distinguish a "Momentum" Hammer/Shooting Star (forming in the direction of an existing strong trend, expected to trigger immediately) from a "Regular" Hammer/Shooting Star (forming as a potential reversal after an opposing trend), and apply the correct entry/stop rule for each.
- **FR-007**: System MUST detect Bullish and Bearish Kicking Patterns (an opposite-colored bar that gaps beyond the entirety of the prior bar's range) and treat the signal as in force only while price remains beyond the second bar's opening price.
- **FR-008**: System MUST maintain a signal's "in force" state from the moment its trigger level is breached until either its time period closes or its level-of-defense is violated, whichever comes first.
- **FR-009**: System MUST distinguish "universal truth" signals (Inside Bar Breakout, Rev Strat, Broadening Formation) — which are always objectively true when their trigger conditions are met — from conditional/non-universal signals (Hammer, Shooting Star, Kicking Pattern) that require additional confirming signals before being acted on.

**Inside bars**

- **FR-010**: System MUST classify an inside-bar breakout as "momentum" when the prior bar was bullish (green) and the inside bar sits in the upper half of that bar's range and breaks upward, and as "retracement" when the prior bar was bearish (red) and the inside bar breaks upward (and the mirrored case for downward breaks).
- **FR-011**: System MUST identify the "Mother Bar" (the bar immediately preceding an inside bar) and flag as lower-quality any inside-bar setup that forms near the middle, rather than near an extreme, of the Mother Bar's range.
- **FR-012**: System MUST flag "multi-inside bar" conditions (two or more consecutive inside bars) as elevated-chop/Rev-Strat-likely conditions.
- **FR-013**: System MUST compute the entry trigger for bullish and bearish inside-bar breakouts as price trading beyond the inside bar's high or low respectively (see FR-038 for stop placement).

**Reversals and Rev Strat**

- **FR-014**: System MUST recognize all four canonical reversal patterns — 2-1-2 Reversal, 2-2 Reversal, Failed-2-Goes-3, and 3-1-2 Reversal — as the only recognized ways price can reverse on any tracked timeframe.
- **FR-015**: System MUST only classify a Rev Strat (2-bar or 1-bar) when it follows an Inside Bar; a reversal-shaped pattern not preceded by an inside bar MUST NOT be labeled a Rev Strat.
- **FR-016**: System MUST distinguish the 2-Bar Rev Strat (inside bar → hammer/shooting star → confirmation) from the 1-Bar Rev Strat (inside bar breaks one side then reverses to break the other side within the same bar).
- **FR-017**: System MUST flag every 1-Bar Rev Strat as carrying immediate Broadening Formation risk, since the reversing bar is itself an outside bar.
- **FR-018**: System MUST identify a "Soft Rev Strat" (one side breached, but open and close remain within the inside bar's range) as a lower-conviction variant that should be flagged for combination with an additional signal rather than traded alone.

**Combinations and measured moves**

- **FR-019**: System MUST identify when a shorter-timeframe signal triggers concurrently with, or confirms, a longer-timeframe signal already in force (cross-timeframe combination).
- **FR-020**: System MUST identify when a Hammer immediately follows a Shooting Star (or vice versa) and reclassify the second signal as a Momentum-type continuation of the reversal.
- **FR-021**: System MUST, when an actionable signal triggers following a quick prior advance or decline, project a measured-move continuation target approximately equal in magnitude to that prior move, from the trigger point.

**Time Frame Continuity**

- **FR-022**: System MUST determine, for each tracked timeframe, whether the current price is above or below that timeframe's opening price (its "color"/direction).
- **FR-023**: System MUST report Full Time Frame Continuity (bullish or bearish) only when all tracked major timeframes agree in direction, and MUST report a Conflict state when one or two timeframes disagree with the rest.
- **FR-024**: System MUST determine which tracked timeframe(s) are currently "in control," applying the rule that when the two shortest tracked timeframes confirm each other, they override the longer timeframes for control purposes.
- **FR-025**: System MUST flag "natural buyer/seller" conditions when an individual ticker's Full TFC direction is in complete conflict with a correlated broader index or sector ETF's Full TFC direction.

**Broadening Formations**

- **FR-026**: System MUST recognize that every Outside Bar constitutes a Broadening Formation on a fractal basis, and surface the lower-timeframe "fractal triangle" for magnitude assessment where lower-timeframe data is available.
- **FR-027**: System MUST recognize the Inside → Outside → Inside bar sequence (contraction → expansion → contraction) and, when the second inside bar goes in force, flag the corresponding extreme of the outside bar as the next expansion level to watch.
- **FR-028**: System MUST treat any actionable signal that reverses price back into a previously broken range ("reclaiming the range") as a potential Broadening-Formation-failure signal and flag the opposite side of the range as a new potential target.
- **FR-029**: System MUST retain prior Broadening Formation highs/lows as reference support/resistance levels for future signal evaluation.

**Application-specific scope adjustment**

- **FR-030**: Because this application has no intraday price feed, System MUST compute Full Time Frame Continuity using only the weekly, monthly, quarterly, and yearly timeframes, MUST exclude the daily timeframe from the Full TFC alignment determination itself, and MUST exclude 60-minute/intraday timeframes, the Flip, and Uncoupling entirely.
- **FR-031**: System MUST still classify the daily bar and separately surface any "notable" daily candle (hammer, shooting star, outside bar, kicking pattern, or reversal pattern) alongside the Full TFC result, without that daily classification affecting the Full TFC alignment outcome.

**Pre-trade checklist and risk guidance**

- **FR-032**: System MUST, on request for a given ticker, report the count and types of currently stacked actionable signals across all tracked timeframes for that ticker.
- **FR-033**: System MUST report, for each in-force signal, its entry trigger level and its computed stop/level-of-defense per the applicable execution rule for that signal type (see FR-036–FR-039).
- **FR-034**: System MUST classify signal conviction ("Level of Defense") as looser (wider stop tolerance) when more corroborating evidence is stacked (multiple signals, Full TFC alignment, Broadening Formation alignment) and tighter as a signal approaches time-based exhaustion.
- **FR-035**: System MUST prevent an "add to position" recommendation unless (a) the existing position is not currently stopped out, and (b) the new setup's stop is such that both the original and added legs combined would remain profitable if both were stopped out.

**Entry and stop-placement rules**

- **FR-036**: System MUST place the stop for a Regular Hammer entry (buy above the hammer's high) one cent below the low of the bar that triggers the hammer, and for a Regular Shooting Star entry (sell below the shooting star's low) one cent above the high of the bar that triggers it.
- **FR-037**: System MUST place the stop for a Momentum Hammer or Momentum Shooting Star (both expected to trigger immediately) one cent below the bid for a long entry, or one cent above the offer for a short entry, rather than referencing the triggering bar.
- **FR-038**: System MUST place the stop for a Bullish Inside Bar Breakout one cent below the low of the bar that breaks the inside bar, and for a Bearish Inside Bar Breakout one cent above the high of the bar that breaks the inside bar.
- **FR-039**: System MUST place the stop for a 2-Bar or 1-Bar Rev Strat (bullish or bearish) one cent below the bid (bullish) or one cent above the offer (bearish) immediately at entry, and MUST never move any computed stop away from the direction of price once set.

**Instrument-class-specific rules (VIX ETNs)**

- **FR-040**: System MUST apply a distinct rule set for volatility ETN instruments: entries are only considered from price coming down off Broadening Formation highs (never off broadening-formation lows/bottoms).
- **FR-041**: System MUST NOT treat a volatility ETN reaching the bottom of its Broadening Formation as a cover/exit signal by default, since these instruments are expected to structurally decay to progressively lower ranges rather than reclaim prior ranges like typical equities.
- **FR-042**: System MUST flag a cover/exit recommendation for a volatility ETN position when any of the following occur: broader-market Full TFC turns bearish, a backwardation condition is detected/reported, or the position's unrealized return goes negative.

### Key Entities *(include if feature involves data)*

- **Bar**: A single OHLC price observation for one timeframe; carries a classification (1, 2U, 2D, 3), an outside-bar subtype when applicable, and a "closed" vs. "still forming" state.
- **Timeframe / Participation Group**: One of the tracked chart periods (e.g., monthly, quarterly, weekly, daily, yearly, in this app's configuration) representing a distinct group of market participants; has a color (bullish/bearish) and a control status.
- **Actionable Signal**: A detected pattern (Hammer, Shooting Star, Kicking Pattern, Inside Bar Breakout, Rev Strat, Broadening Formation) with a type, direction, trigger level, level of defense (stop), an "in force" boolean, and a universal-truth flag.
- **Rev Strat**: A specific actionable signal subtype that only exists relative to a preceding Inside Bar; has a 1-bar/2-bar variant and a soft/full strength flag.
- **Time Frame Continuity (TFC) Result**: The aggregated alignment state across tracked timeframes for a ticker on a given evaluation date — bullish Full TFC, bearish Full TFC, or Conflict — plus which timeframe(s) are in control.
- **Broadening Formation**: A range-expansion structure anchored to specific high/low levels, used as ongoing support/resistance and magnitude reference.
- **Pre-Trade Checklist Result**: The synthesized report of stacked signals, TFC direction, stop/level-of-defense, and correlated-instrument confirmation for a candidate trade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any complete historical OHLC bar series, 100% of closed bars receive exactly one of the four bar classifications, with no ambiguous or unclassified bars.
- **SC-002**: A trader can retrieve the current in-force actionable signals, their trigger levels, and stop levels for a given ticker in a single query, without manually inspecting raw price charts.
- **SC-003**: Full Time Frame Continuity status is available for 100% of tracked tickers on every scheduled analysis run, correctly reflecting the tracked-timeframe scope adjustment for this app (FR-030/FR-031).
- **SC-004**: A trader evaluating a candidate setup can obtain all applicable pre-trade checklist datapoints (signal stack, TFC direction, stop level, correlated-instrument confirmation) in one consolidated report.
- **SC-005**: Rev Strat patterns are never reported without a preceding Inside Bar in the same sequence (zero false-positive Rev Strat classifications in validation testing).

## Assumptions

- This app's technical analysis engine has access to daily, weekly, monthly, quarterly, and yearly OHLC data, but not intraday (sub-daily) data; all intraday-only concepts from the source methodology (60-minute Full TFC, the Flip, Uncoupling, Sideways 30, and Turnaround Tuesday's intraday component) are out of scope for automated evaluation in this app and are documented here for completeness only.
- "Quarterly" and "yearly" timeframes, while not part of the original methodology's 4 canonical participation groups, are included in this app's Full TFC calculation as a deliberate substitute for the unavailable 60-minute/intraday groups, reflecting this app's longer-horizon swing/position trading use case.
- The one-cent stop offsets described in the source methodology (a day-trading convention) are preserved as the documented execution rule; this app's actual order-placement behavior, if any, is out of scope for this spec.
- Ex-dividend, halted, or otherwise data-quality-compromised bars are excluded from classification upstream of this rule engine (handled by data ingestion, not by this feature).
