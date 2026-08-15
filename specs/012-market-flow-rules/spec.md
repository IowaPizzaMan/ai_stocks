# Feature Specification: Market Breadth Timing Signals (NYMO/NAMO)

**Feature Branch**: `012-market-flow-rules`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Import of the hand-written knowledge spec `specs/market_flow_rules.md` (NYMO/NAMO McClellan Oscillator market-breadth timing rules driving the app's RecommenderAgent) into spec-kit format."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Market Timing Guidance for Existing Positions (Priority: P1)

A user with active or watchlisted positions wants clear guidance on whether current overall market breadth conditions favor adding to positions, holding, or trimming/selling, so they can time actions on stocks they already like around the broader market environment rather than acting on stock-specific signals alone.

**Why this priority**: This is the core purpose of the breadth-timing capability — every other capability in this feature (divergence detection, cross-signal combination) exists to sharpen this core recommendation.

**Independent Test**: Can be fully tested by feeding a sequence of daily breadth-oscillator readings into the engine and confirming each reading maps to the correct recommendation zone and buy-more/start-selling guidance per the documented thresholds.

**Acceptance Scenarios**:

1. **Given** the breadth oscillator reading is -60 or lower, **When** a recommendation is generated for a held position, **Then** the system does not recommend reducing or selling based on the breadth reading alone, and treats the reading as a potential add opportunity.
2. **Given** the breadth oscillator is above +60 after an extended uptrend, **When** a recommendation is generated, **Then** the system suggests trimming/reducing rather than adding.
3. **Given** the breadth oscillator is between -20 and +20 (a neutral zone), **When** a recommendation is generated, **Then** the system defers to per-stock signals rather than issuing a strong breadth-driven call.
4. **Given** the user's fundamental thesis on a position has broken (as determined by another analysis capability), **When** a recommendation is generated, **Then** the sell guidance from that other capability takes precedence regardless of the current breadth reading.

---

### User Story 2 - Divergence Detection for High-Conviction Buy Signal (Priority: P2)

A user wants the system to detect when the market makes a "double bottom" on price while the breadth oscillator makes a higher low (a bullish divergence), so they can identify the highest-conviction buy windows the methodology defines, rather than reacting to a single oscillator reading alone.

**Why this priority**: This is the strongest signal in the rulebook and meaningfully increases conviction beyond a single extreme reading, but the feature is still useful without it (P1 already provides baseline guidance).

**Independent Test**: Can be fully tested by feeding a price/oscillator series containing a known double-bottom-with-higher-low pattern and confirming the system flags it, and confirming it does not flag divergence when the pattern is absent.

**Acceptance Scenarios**:

1. **Given** the market price retested a prior low while the breadth oscillator made a higher low versus its prior trough, **When** evaluated, **Then** the system flags a strong-buy/aggressive-add divergence signal.
2. **Given** no such price/oscillator divergence pattern exists in the recent window, **When** evaluated, **Then** the system does not report a divergence signal.
3. **Given** an extreme single-reading oversold condition (oscillator at -80 or lower) occurs without a divergence pattern, **When** evaluated, **Then** the system still flags a buy/add signal, distinct from and lower-conviction than the divergence case.

---

### User Story 3 - Cross-Signal Confirmation with Per-Stock Gap Context (Priority: P3)

A user wants breadth timing combined with per-stock gap-analysis signals (from the companion gap-analysis feature) so that recommendations reflect both "is the market environment favorable" and "is this specific stock's setup favorable," rather than either signal in isolation.

**Why this priority**: This raises precision and conviction on top of the P1/P2 baseline but is not required for the core timing guidance to function.

**Independent Test**: Can be fully tested by supplying a breadth reading alongside a per-stock gap signal/score and confirming the combined recommendation matches the documented combination rules.

**Acceptance Scenarios**:

1. **Given** breadth is oversold (-60 or lower) and a stock has a qualifying down-gap long setup, **When** combined, **Then** the system reports a "strong buy — act" combined recommendation.
2. **Given** breadth is overbought (above +60) and a stock shows an up-gap exhaustion pattern, **When** combined, **Then** the system reports a reduce/exit combined recommendation.
3. **Given** breadth is neither overbought nor at an extreme, **When** combined with a per-stock signal, **Then** the system follows the per-stock signal at normal conviction rather than amplifying or muting it.

---

### Edge Cases

- What happens when NYMO and NAMO strongly disagree (one at an extreme, the other mild)? The system flags the NASDAQ-specific extreme separately (relevant to tech/growth holdings) rather than letting the milder broad-market reading mask it.
- What happens when both NYMO and NAMO are simultaneously at extremes? The system treats this as the highest-confidence combined breadth condition.
- What happens when source market-breadth index data (the specific NYSE/NASDAQ oscillator symbols) is unavailable from this app's market data providers? The system computes an equivalent oscillator locally from proxy universes (see Assumptions); computed readings may deviate from any externally published reference values.
- What happens when a user's fundamental thesis on a position has broken? Sell guidance from that determination overrides breadth-based hold/add guidance unconditionally.
- What happens when the breadth oscillator is crossing back up from oversold (was ≤ -60, now above -40)? The system reports a confirm-buy signal distinct from the initial oversold flag.
- How does prior 1–10 day market direction affect a per-stock down-gap combination? A market that has been down hard recently delays the expected reversal call; a market that was recently up speeds it up (see the companion Gap Analysis Rules feature).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute a market-breadth oscillator reading (for both a broad/NYSE-style universe and a NASDAQ-style universe) on each scheduled run and classify the current reading into one of the documented zone bands: above +60 (overbought/euphoric), +20 to +60 (bullish momentum), 0 to +20 (neutral/mild bullish), 0 to -40 (mild weakness), -40 to -60 (moderate oversold), -60 to -80 (oversold/fear), -80 to -100 (extreme oversold), and below -100 (panic/volatility extreme).
- **FR-002**: System MUST NOT interpret a deeply oversold reading as a reason to reduce or sell; deep oversold readings MUST be treated as a potential buy/add opportunity setup.
- **FR-003**: System MUST flag a buy/add signal whenever the oscillator drops to -80 or lower (an "extreme oversold single reading"), and MUST represent this as a scale-in (not max-size) recommendation.
- **FR-004**: System MUST detect the bullish divergence pattern where the market price retests a prior low while the oscillator forms a higher low versus its own prior trough, and MUST flag this as the highest-conviction "strong buy/aggressive add" signal in the rule set.
- **FR-005**: System MUST flag a "confirm buy" signal when the oscillator was at -60 or lower and subsequently crosses back above -40.
- **FR-006**: System MUST flag a "trim/reduce" signal (not a hard sell) when the oscillator is above +60 following an extended uptrend.
- **FR-007**: System MUST evaluate "should I buy more of this position" using the oscillator's current value, applying: no (don't chase) above +40; yes (normal adds) between 0 and +40 with an intact trend; cautiously yes (scale in small) between -40 and -60; yes (oversold zone) at -60 or lower; and strong yes (max conviction) at -80 or lower with a confirmed higher-low divergence present.
- **FR-008**: System MUST evaluate "should I start selling/reducing" using: consider trimming 25–50% when the oscillator is above +60 in an extended trend; reduce meaningfully when an exhaustion gap signal (per the companion Gap Analysis Rules feature) coincides with an overbought oscillator reading; watch closely and reduce risk when the oscillator crosses from positive to negative; and sell regardless of the oscillator reading whenever the fundamental thesis on the position has broken.
- **FR-009**: System MUST use the broad/NYSE-style oscillator as the primary market-timing signal and the NASDAQ-style oscillator as a secondary signal specifically for assessing tech/growth exposure.
- **FR-010**: System MUST flag the highest-confidence combined condition when both the broad and NASDAQ-style oscillators are simultaneously at an extreme reading.
- **FR-011**: System MUST combine the current breadth zone with a per-stock gap-analysis signal (per the companion Gap Analysis Rules feature) to produce a combined action per the documented combination table (e.g., oversold breadth plus a qualifying down-gap long setup escalates to "strong buy — act"; overbought breadth plus an up-gap exhaustion or short-pattern signal escalates to "reduce/exit"; neutral breadth defers to the per-stock signal at normal size).
- **FR-012**: System MUST factor prior 1–10 day market direction into the timing of a down-gap reversal call when combined with breadth context, without altering breadth-only signals themselves.
- **FR-013**: System MUST produce, per ticker, a structured recommendation containing at minimum: the current broad and NASDAQ-style oscillator readings, the current zone label, a divergence-detected flag, any combined per-stock gap context available, a recommendation value, a conviction level, a plain-language rationale, and any relevant caveats.
- **FR-014**: System MUST restrict the recommendation value to an enumerated set: BUY_MORE, HOLD, TRIM, START_SELLING, AVOID_ADD, or WATCH.
- **FR-015**: System MUST treat breadth-based signals as a market-timing overlay only, never as a standalone stock-picking signal, and MUST always present them alongside per-stock analysis from other capabilities of this app.
- **FR-016**: System MUST support recalibrating the oscillator's zone-boundary thresholds over time (without changing the underlying zone/signal logic) to correct for any systematic deviation between the app's computed reading and external reference values.

### Key Entities *(include if feature involves data)*

- **Breadth Oscillator Reading**: A daily computed value for a given universe (broad/NYSE-style or NASDAQ-style), with an associated zone label and trend direction.
- **Divergence Event**: A detected bullish price/oscillator divergence, with the two trough dates/levels and the higher-low magnitude.
- **Gap Context Reference**: A per-stock gap signal/score, sourced from the companion Gap Analysis Rules feature, used as an input to combined recommendations.
- **Recommendation**: The structured per-ticker output — oscillator readings, zone, divergence flag, gap context, recommendation value, conviction, rationale, and caveats.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A breadth-based recommendation is generated for 100% of positions and watchlist tickers on every scheduled run.
- **SC-002**: Given any oscillator value, the zone classification and buy-more/start-selling guidance match the documented thresholds 100% of the time (deterministic, no manual interpretation required).
- **SC-003**: In backtested historical scenarios containing a documented double-bottom-with-higher-low pattern, the divergence signal is identified without requiring manual chart review.
- **SC-004**: Users can read the plain-language rationale behind any recommendation and understand which conditions drove it without needing to inspect raw oscillator charts.

## Assumptions

- The specific market-breadth index symbols referenced by the source methodology are not available through this app's market data providers; the oscillator is instead computed locally from proxy universes (a broad large-cap universe as the NYSE-style proxy, a NASDAQ-oriented large-cap universe as the NASDAQ-style proxy). Because these are large-cap proxies rather than full-exchange breadth, absolute oscillator values are expected to deviate somewhat from any externally published reference and may need periodic threshold recalibration (see FR-016).
- The zone-boundary thresholds documented in this spec are the starting defaults carried over from the source methodology; ongoing recalibration against external reference values is an operational/data-quality activity, not a change to the underlying rule structure.
- The per-stock gap-analysis scoring referenced in FR-011/FR-012 is defined by the companion Gap Analysis Rules feature (spec 013); this spec does not redefine gap scoring, only how breadth combines with it.
- Fundamental-thesis-driven sell decisions produced by other analysis capabilities of this app always take precedence over breadth-based hold/add guidance (FR-008).
