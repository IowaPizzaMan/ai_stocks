# Feature Specification: Weekly Strategy Buy/Short Picks in AI Chat

**Feature Branch**: `032-weekly-strategy-picks`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "with my AI Chat I want to be able to answer questions like this \"Per my trading strategies, what 10 stocks should I buy for each strategy this coming week and at what prices should I buy\" and \"Per my trading strategies, what 10 stocks should I short for each strategy this coming week and at what prices should I buy\""

## Clarifications

### Session 2026-08-23

- Q: Should the chat compute a full multi-strategy weekly picks answer synchronously within that one turn, or is it acceptable for the chat to kick off the calculation and have the user check back for the completed answer? → A: Async — the chat acknowledges the request immediately and the user checks back (or is notified) once the picks are ready, rather than waiting inline for the full computation.
- Q: Once the chat has acknowledged the request and is computing it, how should the user get the finished answer, given the app avoids frontend polling and live-update connections? → A: The chat shows a visible "thinking/working" indicator while it computes, then presents the completed picks in place within that same reply once ready — the user doesn't re-ask, revisit later, or click a refresh control.
- Q: If one strategy's scan fails or errors while computing the picks, should the reply still show the other strategies' completed lists with a note about the failure, or should the whole request fail? → A: Partial success — show whichever strategies completed, with a plain note that one strategy's result is temporarily unavailable.
- Q: Should this feature support the user asking for a different number of picks per strategy (e.g., "give me the top 5"), or is exactly 10 the only count this feature needs to handle? → A: User-specified count — parse a number like "top 5" or "top 20" out of the question and use that instead of 10, defaulting to 10 when no count is given.
- Q: Market Flow's own rule spec says it reads market-wide breadth (NYMO/NAMO — the same value for every ticker on a given day) and isn't a stock picker; it can't independently rank a universe the way The Strat and Gap Analysis do. How should it participate? → A: Breadth filter/gate, not its own list — Market Flow's market-wide reading is applied as a shared filter and caveat across The Strat's and Gap Analysis's own candidate lists (can suppress a candidate when breadth strongly conflicts with the individual signal), rather than producing an independent 3rd top-N list.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Weekly buy picks per strategy (Priority: P1)

A user asks the AI Chat, in their own words, something like "Per my trading strategies, what 10 stocks should I buy for each strategy this coming week and at what prices?" The chat shows a visible "thinking/working" indicator while it computes, then presents, in that same reply, one ranked list per strategy (up to 10 tickers each, or a different count if the user asked for one), and for every ticker a specific suggested price at which to buy.

**Why this priority**: This is the exact capability requested and delivers the core value: turning the system's existing strategy logic into an actionable weekly buy shortlist, which is the primary reason to use the chat over browsing the screener manually.

**Independent Test**: Can be fully tested by asking the buy-picks question in the chat and verifying the response contains a distinct list per strategy, each list has at most the requested count (10 by default) of tickers, and every ticker has an accompanying price — deliverable and demonstrable without the short-picks capability existing yet.

**Acceptance Scenarios**:

1. **Given** current screener data exists for the tracked universe, **When** the user asks for this week's buy picks per strategy, **Then** the chat shows a thinking/working indicator while computing, and once ready, presents in the same reply a separate section per strategy, each listing up to 10 tickers (or the count the user asked for) with a specific suggested buy price for each.
2. **Given** a strategy has fewer qualifying candidates than the requested count this week, **When** the user asks for buy picks, **Then** that strategy's section lists only the qualifying candidates (not padded to the requested count).
3. **Given** a strategy has zero qualifying candidates this week, **When** the user asks for buy picks, **Then** that strategy's section explicitly states no candidates currently qualify, rather than being omitted or showing stale results.

---

### User Story 2 - Weekly short picks per strategy (Priority: P2)

A user asks the AI Chat something like "Per my trading strategies, what 10 stocks should I short for each strategy this coming week and at what prices?" The chat shows a thinking/working indicator while it computes, then presents, in that same reply, one ranked list per strategy that supports short-side signals, up to 10 tickers each (or a different count if the user asked for one), with a specific suggested short-entry price per ticker.

**Why this priority**: Mirrors User Story 1 for the short side, which the user explicitly asked for as a second, equally-named capability — but it depends on the same underlying per-strategy ranking and pricing mechanism, so it naturally follows P1.

**Independent Test**: Can be fully tested by asking the short-picks question and verifying the response format matches User Story 1's structure (per-strategy lists, up to the requested count of tickers, explicit prices), independent of whether buy picks are asked for in the same session.

**Acceptance Scenarios**:

1. **Given** current screener data exists for the tracked universe, **When** the user asks for this week's short picks per strategy, **Then** the response contains a separate section per strategy that supports short signals, each listing up to 10 tickers with a specific suggested short-entry price.
2. **Given** a strategy does not currently produce short-side signals, **When** the user asks for short picks, **Then** the response states plainly that this strategy has no short-side candidates for the week, rather than silently skipping it or fabricating one.

---

### User Story 3 - Follow-up refinement in the same conversation (Priority: P3)

After receiving a strategy picks answer, the user asks a natural follow-up in the same chat, such as "just show me the Gap Analysis ones" or "why did you pick that one," and the chat answers using the same underlying computed lists without the user having to restate the full original question.

**Why this priority**: Nice-to-have conversational polish that improves usability but isn't required for the core buy/short picks capability to deliver value; the feature is usable turn-by-turn without it.

**Independent Test**: Can be tested by asking a full picks question, then a narrowing or "why" follow-up, and confirming the chat's answer stays consistent with the prior turn's computed lists.

**Acceptance Scenarios**:

1. **Given** the user just received a full per-strategy buy-picks answer, **When** they ask to narrow it to one named strategy, **Then** the chat responds with just that strategy's list from the same underlying computation.

---

### Edge Cases

- What happens when the user names a strategy that doesn't exist in the system (e.g., asks for "my momentum strategy" picks)? Chat should say it doesn't recognize that strategy and list the strategies it does support.
- What happens when screener/price data needed to compute a candidate's entry price is missing or stale for an otherwise-qualifying ticker? That ticker is excluded from the list rather than shown with a guessed or last-known-stale price.
- How does the system handle a tie in ranking when more stocks qualify for a strategy than the requested count? Ties are broken deterministically (e.g., by a fixed secondary sort key) so repeated asks on the same data return the same top candidates in the same order.
- What happens if the user asks for a count that isn't a positive whole number, or an unreasonably large one (e.g., "top 0" or "top 500")? Chat should ask for a sensible count or fall back to the default of 10 rather than erroring or returning an unbounded list.
- What happens if the user asks for picks with no direction specified (neither "buy" nor "short")? Chat should ask which direction they mean, or state which one it defaulted to, rather than guessing silently.
- What happens when the user asks the same question again shortly after (data unchanged)? The chat should return the same lists and prices, since the ranking and pricing are deterministic given the same underlying data.
- What happens when one strategy's computation errors while the others succeed? The reply still shows the successful strategies' lists, with a plain note that the failed strategy's result is temporarily unavailable.
- What happens when the market-wide breadth reading needed for the Market Flow filter is unavailable? Each strategy's list is still returned from its own signals, with a note that the market-condition filter/caveat couldn't be applied this time.
- What happens when the user asks for "Market Flow" picks by name, expecting an independent list? Chat explains Market Flow is a market-condition filter applied across the other two strategies' lists, not its own list.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The chat MUST recognize natural-language requests for weekly buy or short-sell stock recommendations "per my trading strategies" (or equivalent phrasing) as a distinct capability, in addition to its existing free-form screener question-answering.
- **FR-002**: For a buy-recommendation request, the system MUST return a separate ranked list of up to the requested count of candidate stocks (10 by default when the user doesn't specify a count) for each of the system's two independently-ranked screening strategies (The Strat, Gap Analysis), rather than one merged list across strategies.
- **FR-003**: For a short-recommendation request, the system MUST return a separate ranked list of up to the requested count of candidate stocks for each strategy that supports short-side signals, and MUST explicitly state when a given strategy does not currently support short-side candidates rather than omitting it without explanation.
- **FR-004**: For every recommended stock in any list, the response MUST include a specific suggested entry price (a buy price for buy lists, a short-entry price for short lists) derived from that strategy's own price-level logic (e.g., a breakout/trigger level, gap-fill level, or support/resistance level), not merely the most recent closing price.
- **FR-005**: The candidate universe scanned by each strategy MUST be the full set of tickers currently present in the system's existing screener data, with no separate watchlist restriction.
- **FR-006**: When fewer stocks meet a strategy's qualifying criteria for the week than the requested count, the system MUST return exactly the qualifying set rather than padding the list with non-qualifying stocks.
- **FR-007**: When zero stocks qualify for a strategy in the requested direction, the system MUST state that plainly for that strategy rather than omitting it or fabricating a result.
- **FR-008**: The ranking used to select each strategy's top candidates MUST be computed deterministically from that strategy's own signal output, with ties broken by a fixed rule; the chat's language model composes the prose response from these computed lists but MUST NOT itself decide which stocks appear on a list.
- **FR-009**: "This coming week" MUST be interpreted as the next 5 trading days from the date the question is asked, and recommendations MUST be computed fresh at ask-time from current data rather than served from a stale cached answer.
- **FR-010**: Every strategy-picks response MUST include a plain-language disclaimer that the output is informational analysis, not an executed trade or licensed financial advice.
- **FR-011**: The chat's existing screener question-answering behavior MUST continue to work unchanged; this feature is additive to it.
- **FR-012**: If a strategy cannot compute a defensible entry price for an otherwise-qualifying candidate (e.g., required price-level data is missing), that candidate MUST be excluded from the list rather than shown with a guessed or approximate price.
- **FR-013**: If the user's question names a strategy the system does not recognize, the chat MUST say so and list the strategies it does support, rather than guessing which strategy was meant.
- **FR-014**: When a strategy-picks request needs computation beyond what completes instantly, the chat MUST show a visible thinking/working indicator while it computes and then present the completed picks in that same reply — the user MUST NOT need to re-ask, revisit the chat later, or trigger a manual refresh to see the result.
- **FR-015**: If computing one strategy's candidate list fails (e.g., a data issue affecting only that strategy), the response MUST still present the other strategies' completed lists, with a plain note that the failed strategy's result is temporarily unavailable, rather than failing the entire request.
- **FR-016**: If the user's question specifies a desired count (e.g., "top 5"), the system MUST use that count instead of the default of 10; if the specified count is not a positive whole number or is unreasonably large, the system MUST fall back to the default of 10 rather than erroring or returning an unbounded list.
- **FR-017**: The current market-wide breadth reading (Market Flow's market-timing signal) MUST be applied as a shared filter across both strategies' candidate lists: a candidate MUST be excluded from a buy list when the market-wide reading strongly conflicts with buying (e.g., a start-selling/avoid-add condition), and excluded from a short list under the mirrored strongly-bullish condition; where the reading doesn't override inclusion, it MUST still be surfaced as a caveat alongside the candidate rather than silently ignored.
- **FR-018**: If the market-wide breadth reading needed for FR-017 is unavailable, the system MUST still return each strategy's candidate list computed from that strategy's own signals, with a note that the market-condition filter/caveat could not be applied — a breadth data gap MUST NOT block the individual strategies' picks.
- **FR-019**: If the user's question specifically asks for "Market Flow" picks as though it were an independent buy/short list, the chat MUST explain that Market Flow is applied as a market-condition filter across The Strat's and Gap Analysis's lists rather than producing its own list, rather than returning an empty or fabricated Market Flow section.

### Key Entities

- **Strategy Picks Request**: A chat question interpreted as asking for buy or short candidates, across one or more strategies, for the coming week, optionally specifying how many candidates per strategy (defaults to 10).
- **Strategy Candidate List**: A per-strategy, per-direction (buy or short) ranked list of up to the requested count of stocks (10 by default) for the current week; each entry carries a ticker, a suggested entry price, and any market-condition caveat from the breadth filter.
- **Strategy**: One of the system's two independently-ranked rule-based screening modules (The Strat, Gap Analysis), each exposed for this feature with a defined buy-candidate scan, and — where supported — a short-candidate scan and an entry-price computation.
- **Market Condition Filter**: The system's current market-wide breadth reading (Market Flow / NYMO-NAMO), applied across both strategies' candidate lists as a shared inclusion filter and caveat rather than as its own independent strategy list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user gets a complete weekly buy-recommendation answer — every strategy's list, up to the requested count of stocks each (10 by default), with prices — from a single chat question, in that same reply, without needing to re-ask, revisit later, or manually refresh anything.
- **SC-002**: A user gets a complete weekly short-recommendation answer under the same conditions as SC-001.
- **SC-003**: 100% of stocks appearing in a strategy-picks response include a specific suggested price, not just a ticker symbol.
- **SC-004**: Re-asking the same strategy-picks question after the underlying screener data changes reflects updated candidates and prices without any code or configuration change.
- **SC-005**: For every strategy referenced in a response, a user can tell from the response text alone whether that strategy had qualifying candidates, had none, or doesn't support the requested direction — never silence or an unexplained gap.

## Assumptions

- "My trading strategies" refers to the system's existing built-in screening strategies (The Strat, Gap Analysis) rather than user-authored or per-user custom strategies. This is a single-tenant, no-auth tool, so "my" strategies means the strategies configured in the system, not a personal profile.
- Market Flow is not one of the per-strategy buy/short lists: its own rule spec (`specs/market_flow_rules.md`) reads market-wide breadth (NYMO/NAMO), which is the same value for every ticker on a given day, and states plainly that it "is not a stock picker" — it has no way to independently rank a universe of tickers. It's applied instead as a shared market-condition filter/caveat across The Strat's and Gap Analysis's candidate lists (FR-017–FR-019).
- Position Management is not one of the per-strategy buy/short lists in this feature: per the existing spec, it manages trailing stops on already-open positions rather than screening new entries, so it has no natural "buy candidate" output.
- The Portfolio Strategist's combined synthesized signal is not treated as an additional strategy bucket for this feature, to avoid double-counting stocks already covered by the rule-based strategies it's built on. It remains out of scope here.
- No trade execution, brokerage integration, or tracking of positions actually taken is part of this feature; all output is advisory/informational only.
- Suggested entry prices require new deterministic price-level computation per strategy that does not exist in the system today (only last close and a user-supplied entry price for existing open positions exist currently); this specification states the requirement, not the computation method, which is a planning-phase concern.
- The existing AI Chat's read-only, single-collection query approach is being extended, not replaced; this feature adds a second recognized question pattern alongside the existing screener Q&A.
