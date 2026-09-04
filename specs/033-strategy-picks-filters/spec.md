# Feature Specification: Combined Strategy Picks & Screener Filters in AI Chat

**Feature Branch**: `033-strategy-picks-filters`

**Created**: 2026-08-23

**Status**: Draft

## Clarifications

### Session 2026-08-23

- Q: Should a single strategy-picks question be able to combine more than one extra filter condition at once (e.g. "liked stocks in the consumer staples sector"), or does this feature only need to handle exactly one extra condition per question? → A: Multiple AND-combined conditions — the feature parses out all extra conditions in the question and ANDs them together before ranking.
- Q: If translating an extra condition into a query technically fails (e.g. the model call for that step errors out or times out) — different from FR-007's "condition doesn't correspond to any field" case — how should the chat respond? → A: Treat it the same as an unrecognized condition — tell the user that condition couldn't be applied and still answer whichever part of the question doesn't depend on it.
- Q: This feature's new condition filter and specs/032's existing Market Flow breadth filter both narrow a strategy's candidates before ranking — should they be treated as independent filters applied together (order doesn't matter), or does one need to run before the other? → A: Independent filters, order doesn't matter — a candidate is included only if it survives both.

**Input**: User description: "I want to pay for the extra ollama call. I want to be able to ask it general questions, for example I said \"Per my trading strategies, what stocks should I buy this week and at what prices, and only use the stocks I have liked\" it didn't understand what I meant when I said \"only use the stocks I have liked\" If ollama would have done that inital pass it would have been able to run it up against the semantic schema and tried to generate a query. Any other ideas for how I can make this better so i can ask genreal questions. like what are the most popular stocks in the consumer staples and which are ready for me to buy per my strategy, I will come up with a lot of questions like that but I want the LLM to try and udnerstand the prompt and convert it into a query using the semtanci model and then run that. do that and lets see how it comes out if there are any other things that you can do to make it better lets do it."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Narrowing strategy picks with an extra condition (Priority: P1)

A user asks the AI Chat a strategy-picks question (specs/032-weekly-strategy-picks) that also names one or more additional conditions in the same sentence — e.g. "per my trading strategies, what should I buy this week, only using stocks I've liked" or "...in the consumer staples sector" or "...with a market cap over $10B" or a combination such as "...liked stocks in the consumer staples sector". The chat recognizes the strategy-picks part and every additional condition present, restricts the candidate universe to stocks meeting all of those conditions together (AND), and returns strategy picks (with prices) drawn only from that narrowed set.

**Why this priority**: This is the exact capability requested — today the strategy-picks answer silently ignores any condition beyond direction/count/strategy name, which is confusing and makes the feature feel broken for the compound questions a user naturally asks.

**Independent Test**: Ask a strategy-picks question with one extra condition that's expressible against the existing screening data (sector, liked status, financial trend, etc.); verify the returned picks are a subset of stocks meeting that condition, not the full unfiltered list. Also ask a question combining two such conditions at once (e.g. liked status AND sector) and verify the returned picks meet both conditions together, not just one.

**Acceptance Scenarios**:

1. **Given** the user has marked some tracked stocks "liked", **When** they ask "per my trading strategies, what should I buy this week using only stocks I've liked", **Then** every returned candidate is a "liked" stock, and any of the user's strategy candidates that aren't "liked" are left out without being mentioned as an error.
2. **Given** a sector name is included in the question, **When** the user asks "what should I buy this week in the consumer staples sector per my strategies", **Then** every returned candidate belongs to that sector.
3. **Given** the extra condition matches zero of a strategy's otherwise-qualifying candidates, **When** the user asks such a question, **Then** that strategy's section says plainly that nothing qualifies under the combined criteria, rather than showing unfiltered results or silently returning nothing.
4. **Given** the user names a condition that isn't expressible from the data this system has (e.g. a concept with no matching field), **When** they ask a combined question using it, **Then** the chat explains it can't apply that specific condition, while still being able to answer the parts of the question it can (or saying plainly it can't answer any of it, if the whole thing depends on the missing condition).
5. **Given** the user's question names two extra conditions (e.g. "liked stocks in the consumer staples sector"), **When** they ask it per their trading strategies, **Then** every returned candidate satisfies both conditions at once, not just one of them.

---

### User Story 2 - Reliable recognition of a strategy-picks question, any phrasing (Priority: P2)

A user asks a strategy-picks-shaped question that doesn't happen to include a recognizable keyword (e.g. "give me 10 stocks to buy and 10 to short" — no mention of "strategy", "The Strat", "Gap Analysis", or "Market Flow"). The chat still recognizes it as a strategy-picks request and answers accordingly, instead of treating it as an ordinary screener question and declining because no such field exists.

**Why this priority**: This is a concrete, reported failure — a natural phrasing of the exact same request the feature is built for was silently misrouted. Fixing it makes the whole feature dependable regardless of exact wording, which is a prerequisite for User Story 1 mattering at all.

**Independent Test**: Ask several differently-worded strategy-picks questions that avoid any of today's trigger keywords; verify each one is still recognized and answered as a strategy-picks question.

**Acceptance Scenarios**:

1. **Given** a question asking to buy and short a number of stocks with no strategy-related keyword in it, **When** it's clearly asking for the same kind of picks-per-approach answer this feature provides, **Then** the chat recognizes and answers it as a strategy-picks question.
2. **Given** an ordinary screener question with no strategy-picks intent at all, **When** the user asks it, **Then** the chat still answers it exactly as before (unaffected by this feature) — recognizing more phrasings of strategy-picks questions must not cause ordinary questions to be misclassified as strategy-picks ones.

---

### User Story 3 - Graceful handling when a condition has no matching data (Priority: P3)

A user asks a compound question using a concept this system doesn't actually track in a comparable way — e.g. "what are the most popular stocks in consumer staples that are ready to buy per my strategy," where "most popular" doesn't correspond to any single existing field. The chat says plainly which part of the question it couldn't apply as asked, rather than guessing at a stand-in meaning and presenting it as if it were exactly what was asked for.

**Why this priority**: Lower priority than Stories 1–2 because it's a fallback/edge-case path, not the common case — but without it, an unanswerable condition would either silently be dropped (misleading) or crash the request.

**Independent Test**: Ask a compound question using a condition with no reasonable corresponding data field; verify the response explains the limitation rather than fabricating a match or failing the request outright.

**Acceptance Scenarios**:

1. **Given** a condition that doesn't correspond to any field this system tracks, **When** the user asks a combined question using it, **Then** the chat's answer explicitly says that condition couldn't be applied, and still answers the rest of the question if any of it stands on its own (e.g. the plain strategy-picks part, without that condition).

---

### Edge Cases

- What happens when the user gives a condition that touches multiple strategies differently (e.g. "liked stocks" — a stock could be liked and qualify for The Strat but not Gap Analysis, or vice versa)? Each strategy's list is filtered independently — a stock only needs to be liked, not liked *and* present in every strategy's list.
- What happens when the extra condition alone (without the strategy-picks part) would already be answerable by the existing free-form screener chat? The combined question still returns a strategy-picks-shaped answer (grouped by strategy, with prices) — it doesn't fall back to a flat screener answer just because part of the question could stand alone.
- What happens when the same condition text could plausibly map to more than one field (e.g. "large cap" for market cap threshold)? The system makes its best reasonable interpretation using the data available and states the interpretation it used, rather than silently guessing without disclosing it.
- What happens now that every question pays for the intent-detection call — does an ordinary screener question get slower? Some added latency is an accepted, explicit tradeoff of this feature (see Assumptions), not a regression to guard against.
- What happens when the step that translates an extra condition into a query technically fails (model error, timeout) rather than the condition simply having no matching field? It's handled the same way as an unrecognized condition (FR-007): the chat says that condition couldn't be applied and still answers whatever part of the question doesn't depend on it, rather than failing the whole request.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The chat MUST run its strategy-picks intent-recognition step on every question, not only on questions containing a specific keyword — removing today's keyword pre-filter that skips this step to avoid its cost.
- **FR-002**: The chat MUST recognize, within a single strategy-picks question, both the strategy-picks intent (direction, count, named strategy — per specs/032-weekly-strategy-picks) and any additional filtering condition(s) expressed in the same question — a question MAY name more than one extra condition at once (e.g. "liked stocks in the consumer staples sector"), and all such conditions found MUST be recognized, not just the first one.
- **FR-003**: When one or more additional filtering conditions are present, the system MUST restrict each strategy's candidate universe to stocks meeting *all* of those conditions together (a logical AND) *before* ranking and selecting the top candidates, so a filtered-out stock never displaces a candidate that does meet every condition. This condition filter and specs/032's existing Market Flow breadth filter (FR-017–FR-019 there) are independent inclusion checks over the same candidate set — a candidate MUST survive both to be included, and the two filters MAY be evaluated in either order or together since neither depends on the other's outcome.
- **FR-004**: Each additional filtering condition MUST be evaluated using the same general question-to-query mechanism the existing free-form screener chat already uses (specs/031-semantic-layer-chat) — not a hardcoded list of recognized filter phrases — so that any condition expressible against the data this system already exposes for screening can be used in a strategy-picks question without engineering a new special case for it. Multiple conditions in one question are combined into a single AND'd query against that mechanism rather than requiring separate sequential requests.
- **FR-005**: A user's per-stock "liked"/"disliked" preference MUST be one of the conditions available to this mechanism (it is not today), since it's the concrete condition this capability was requested for.
- **FR-006**: When the additional condition results in zero qualifying candidates for a strategy, that strategy's section MUST state so plainly (consistent with specs/032's existing zero-candidate handling), not show unfiltered results and not silently omit the strategy.
- **FR-007**: When an additional condition doesn't correspond to any field or concept this system can evaluate, *or* when the step that translates it into a query technically fails (e.g. the underlying model call errors or times out), the chat MUST say so explicitly rather than ignoring the condition silently, fabricating a match, or failing the entire request, and MUST still answer whatever part of the question doesn't depend on that condition.
- **FR-008**: When the system's interpretation of a condition is ambiguous (multiple reasonable readings), the answer MUST state which interpretation was used.
- **FR-009**: Recognizing more phrasings of a strategy-picks question (FR-001) MUST NOT change how an ordinary, non-strategy-picks screener question is answered (specs/032's FR-011 still holds) — this feature only widens recognition and adds filtering, it doesn't alter unrelated behavior.
- **FR-010**: Every response produced by this combined path MUST still include the informational disclaimer required by specs/032's FR-010, and every returned candidate MUST still carry a specific entry price per specs/032's FR-004.

### Key Entities

- **Strategy Picks Filter Condition**: One of possibly several free-form conditions parsed from a strategy-picks question (e.g. "only stocks I've liked", "in the consumer staples sector"). When a question names more than one, all of them are translated into a single combined (AND'd) query against the same data the general screener chat already queries, and applied together to narrow each strategy's candidate universe before ranking.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can ask a single question combining a strategy-picks request with one or more additional conditions (e.g. liked stocks, a sector, a financial-trend condition, or a combination such as liked stocks in a given sector) and receive picks correctly restricted to all of those conditions together, without rephrasing into separate questions.
- **SC-002**: A set of test questions phrased without any of today's specific trigger words (e.g. "give me 10 stocks to buy and 10 to short", "what should I add to my portfolio this week") are all still recognized and answered as strategy-picks questions, not declined as out-of-scope.
- **SC-003**: An unrecognized or unanswerable condition never silently produces a wrong or misleading answer — the response always discloses when a condition couldn't be applied as asked.
- **SC-004**: The existing screener chat and existing plain strategy-picks questions (specs/031, specs/032) continue to behave exactly as before for questions that don't combine the two.

## Assumptions

- Removing the keyword pre-filter (FR-001) means every chat question now pays for the extra intent-recognition model call, and a question with an additional filtering condition pays for one further model call to translate that condition into a query — both are accepted latency/cost tradeoffs made explicitly by the user requesting this feature, not something this spec treats as a regression to avoid.
- "Liked"/"disliked" stock preference is currently stored per ticker but not exposed to the chat's screening data; this feature includes exposing it (FR-005) as a natural extension of the same mechanism, not a separate feature.
- Concepts with no existing corresponding data — such as a genuine per-sector "most popular" measure (this system has no per-sector trading-activity dataset) — are handled via FR-007's graceful-limitation path, not by building new data collection for them. The system does not fabricate a stand-in meaning without disclosing it (FR-008 covers the case where a reasonable stand-in exists and is used, e.g. a general activity ranking or market cap as a rough size proxy).
- This feature extends specs/032-weekly-strategy-picks's chat path specifically; it does not change how the general free-form screener chat (specs/031) answers a question that has no strategy-picks intent at all (FR-009).
- No new user-facing controls (buttons, filters UI) are introduced — this is entirely a chat-question-understanding improvement.
