# Feature Specification: Semantic Layer Chat Assistant

**Feature Branch**: `031-semantic-layer-chat`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Lets build out that sementic layer offically. I am going to want a tab on the nav bar called chat where I can ask a question and the LLM will use this senentic layer to figure out my question. I might want to ask a follow up question. I don't need to store a history of previous chats at this time. Use the mango mcp to make sure all mongo collections are built efficently and that my sementic layer is accurate. I might ask what stocks are at the bottom of their daily z score rang but moving up on the weekly with improving financials and have more free cash flow than debt. if you find any collections in my mongo database that are not used delete them. I'm going to want to increase the size of this database by 15x so make sure it will handle it."

## Clarifications

### Session 2026-08-23

- Q: When you ask a question in chat, how should the system decide what data to pull — should the model choose from a fixed set of pre-built screening functions, or should it write database queries itself on the fly? → A: The model writes queries itself from a description of the semantic layer (text-to-query).
- Q: Should the screening values (range position, weekly trend, FCF-vs-debt) already be stored as ready-to-query fields, or calculated at the moment the question is asked? → A: Pre-computed and stored during data pulls; queries filter on the stored fields.
- Q: Should chat be strictly read-only, and should that be technically enforced? → A: Yes — strictly read-only, structurally enforced so writes cannot occur.
- Q: Amend the constitution to allow a shared package, or keep the services separate? → A: Neither — narrow the scope so the semantic layer lives only in the service that serves chat; the worker writes pre-computed fields using its existing patterns. No shared package, no amendment.
- Q: How much should chat show about how it derived an answer? → A: Both, layered — plain-language criteria and match counts always shown, with the exact query available behind a toggle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a research question in plain English (Priority: P1)

As an investor using the platform, I want to ask a plain-English question about the stocks I track (e.g., "what stocks are near the bottom of their daily price range but trending up on the weekly, with improving financials and more free cash flow than debt") and get a direct answer grounded in the platform's real, current data, so I don't have to manually cross-reference multiple pages and reports myself.

**Why this priority**: This is the entire value proposition of the feature. Without a working, data-grounded question-and-answer flow, there is no chat feature.

**Independent Test**: Open the new Chat tab, submit a screening-style question referencing metrics the platform tracks, and verify the returned ticker(s) are consistent with what querying the same criteria directly against the underlying data would produce.

**Acceptance Scenarios**:

1. **Given** the Chat tab is open, **When** the user submits a question referencing data the platform tracks (price trend, financial health, ownership activity, etc.), **Then** the system returns a direct answer naming specific ticker(s) or a clear "no matches" result, backed by real data rather than a generic or fabricated response.
2. **Given** the user asks a question about something the platform does not track, **When** submitted, **Then** the system plainly states it cannot answer that with available data instead of guessing.
3. **Given** an answer has been returned, **When** the user reads it, **Then** the criteria actually applied and the number of matches at each step are shown in plain language alongside the answer, and the exact query that produced it is available on demand.
4. **Given** the user's question was misinterpreted, **When** they read the stated criteria, **Then** the misinterpretation is visible from the criteria alone without needing to inspect the underlying query.

---

### User Story 2 - Ask a follow-up question (Priority: P2)

As a user who just received an answer, I want to ask a follow-up question (e.g., "which of those has the highest market cap?") without repeating the full original question, so the exchange feels like a real conversation.

**Why this priority**: Explicitly requested; needed for the feature to feel conversational rather than a one-shot search box.

**Independent Test**: Ask an initial question, then ask a shorter follow-up that depends on the prior answer, and confirm the response correctly resolves the reference using the conversation so far.

**Acceptance Scenarios**:

1. **Given** a prior question/answer exchange is still visible, **When** the user asks a follow-up referencing "those," "it," or "the top one," **Then** the system resolves the reference using the current session's conversation.
2. **Given** the user navigates away from or refreshes the Chat tab, **When** they return, **Then** the previous conversation is not restored (no history is persisted).

---

### User Story 3 - Trustworthy, complete underlying data (Priority: P3)

As a user relying on chat answers for research, I need the platform's underlying data model to be complete, consistently structured, and free of stale or unused data sources, so chat answers (and the rest of the app) reflect reality instead of gaps or dead weight.

**Why this priority**: Chat answers are only as good as the data queried; this underpins the accuracy of User Story 1.

**Independent Test**: Compare a sample of chat answers against directly querying the source data for the same tickers/metrics, and verify no unused or dead data sources remain in the system.

**Acceptance Scenarios**:

1. **Given** the platform's data store, **When** reviewed, **Then** every retained data collection has at least one active reader or writer in the running system, and any collection with none is removed.
2. **Given** a fresh data pull for the day, **When** the chat is asked a question touching that data, **Then** the answer reflects the newly pulled data rather than a snapshot older than its intended freshness window.

---

### User Story 4 - Platform scales to a much larger dataset (Priority: P4)

As the platform owner, I plan to grow the tracked dataset by roughly 15x, and I need chat and the rest of the app to keep working correctly at that scale without a later redesign.

**Why this priority**: Forward-looking capacity requirement. Lower priority than shipping the working feature today, but must be validated before or alongside launch so the launched design doesn't need to be redone.

**Independent Test**: Simulate or dry-run the data layer at roughly 15x current volume and confirm response times and correctness stay within acceptable bounds.

**Acceptance Scenarios**:

1. **Given** a dataset roughly 15x current size, **When** a chat question is asked, **Then** it returns within acceptable time and with correct results.
2. **Given** a dataset roughly 15x current size, **When** routine data is read or written, **Then** no per-record size limits or query timeouts are hit.

---

### Edge Cases

- What happens when a question has no matching data (empty result)?
- How does the system handle an ambiguous question that could map to more than one metric or interpretation?
- What happens if the data needed to answer a question is currently stale or mid-refresh?
- What happens if a collection flagged for removal turns out to have a reader that automated analysis didn't detect?
- How does the system respond to a question that requires a screening signal the platform doesn't currently pre-compute?
- What happens when the generated query is malformed, invalid, or fails to execute?
- What happens when a generated query is syntactically valid but semantically wrong (returns a plausible-looking but incorrect set)?
- What happens when a generated query attempts a write, delete, or other non-read operation?
- What happens when a generated query would return an unusably large result set or run past a reasonable time limit?
- What happens when a question references a stock or field that does not exist in the tracked universe?
- What happens when pre-computed signals are missing for a stock (e.g., newly added, or insufficient price history to compute a trend)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add a "Chat" entry to the main navigation that opens a conversational question-and-answer interface.
- **FR-002**: System MUST let a user submit a free-text question and receive a natural-language answer grounded in the platform's tracked stock and market data.
- **FR-003**: System MUST support at least one follow-up question within the same active session that can reference the prior question or answer.
- **FR-004**: System MUST NOT persist chat conversation history beyond the active session.
- **FR-005**: System MUST answer using one consistent representation per domain concept (a ticker's price history, financials, insider activity, institutional activity, congressional trades, macro indicators, etc.) rather than inconsistent, ad hoc logic per data source.
- **FR-006**: System MUST identify data collections with no active reader or writer and remove them, after the removal list is confirmed accurate (see Assumptions).
- **FR-007**: System MUST clearly tell the user when a question cannot be answered with currently available data rather than fabricating an answer.
- **FR-008**: System MUST continue returning correct, timely answers when the tracked dataset grows to roughly 15x its current size (see Assumptions for what "15x" measures).
- **FR-009**: System MUST be able to answer questions that combine multiple signal types in one request — for example, a short-term price-range position, a longer-term price trend, a financial-health trend, and a comparison between two financial metrics.
- **FR-010**: System MUST pre-compute and store the screening signals needed by FR-009 (relative position within a recent price range, multi-period trend direction, financial-trend direction, and free-cash-flow-versus-debt comparison) as directly queryable values on each tracked stock, refreshed as part of the routine data-refresh cycle.
- **FR-011**: System MUST derive the data lookup for each question by generating a query from a description of the semantic layer, rather than selecting from a fixed set of pre-built screening functions.
- **FR-012**: System MUST restrict all chat-initiated data access to read-only operations, enforced structurally so that a write, delete, drop, or other modifying operation cannot be executed even if generated. Attempts MUST be rejected before execution and surfaced as an error rather than silently ignored.
- **FR-013**: System MUST display, alongside every answer, the criteria actually applied and the number of matches, in plain language.
- **FR-014**: System MUST make the exact query used to produce an answer available to the user on demand, without showing it by default.
- **FR-015**: System MUST handle a failed, invalid, or rejected query by telling the user the question could not be answered, rather than presenting an empty or partial result as if it were a valid answer.
- **FR-016**: System MUST bound the cost of any single chat-initiated query so that a question cannot return an unusably large result set or run indefinitely.

### Key Entities *(include if feature involves data)*

- **Ticker**: A tracked stock symbol with identity/registry info (name, sector, industry).
- **Price Series**: Historical daily price bars for a symbol; spans both individually tracked tickers and the broader market universe used for market-wide comparisons.
- **Financial Snapshot**: A ticker's fundamental metrics (revenue, margins, cash, debt, free cash flow) as of a point in time, with enough history to assess trend direction.
- **Insider Activity**: Recorded insider buy/sell transactions for a ticker.
- **Institutional Ownership / Flow**: Recorded institutional holdings and notable institutional buy/sell moves, both per-ticker and market-wide.
- **Congressional Trade**: A recorded trade disclosure by a member of Congress, optionally linked to a ticker.
- **Macro Indicator**: Market-wide economic, rate, or breadth data not tied to a single ticker.
- **Analysis**: A generated research summary/signal for a ticker, combining several of the above.
- **Screening Signal**: A pre-computed, directly queryable value attached to a ticker, derived from its price and/or financial history — relative position within a recent price range, trend direction over a given period, financial-trend direction, and free-cash-flow-versus-debt standing. Refreshed on the routine data cycle; may be absent for tickers with insufficient history.
- **Semantic Layer Description**: The machine-readable account of available entities, their queryable fields (including Screening Signals), and their meanings, which is what the model consults to construct a query.
- **Chat Exchange**: One question-and-answer pair within an active, non-persisted conversation session, including the criteria applied, match counts, and the query used to produce it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user gets an answer to a data-grounded question within 10 seconds for the majority of questions asked.
- **SC-002**: Users can ask at least one follow-up question that correctly builds on the prior answer without repeating context, in 100% of tested conversation flows.
- **SC-003**: Zero data collections without an active reader or writer remain in the platform's data store after cleanup.
- **SC-004**: Core stock-analysis features (price lookups, financials, chat) continue to return correct results with dataset volume at roughly 15x today's size, with no noticeable increase in response time for typical use.
- **SC-005**: When asked a question outside the scope of available data, the system states it cannot answer in 100% of such cases rather than producing an unsupported answer.
- **SC-006**: Every answer displays the criteria applied and match counts, allowing a user to identify a misinterpreted question without inspecting the underlying query, in 100% of answers returned.
- **SC-007**: Zero chat-initiated operations modify stored data, verified by testing that generated modifying operations are rejected before execution.
- **SC-008**: Pre-computed screening signals are available for at least 95% of tracked stocks with sufficient history, and their absence for the remainder is reported rather than silently treated as a non-match.

## Assumptions

- The Chat UI is a new tab/page within the existing frontend navigation, consistent with the app's current look and feel.
- "Follow-up question" support means conversation context is retained for the duration of the active browser session; it does not require server-side chat history storage, per explicit instruction.
- Screening signals are pre-computed and stored during the routine data-refresh cycle rather than derived at question time, so generated queries filter on ready-made fields. The set of pre-computed signals is therefore a bounded, known list; a question needing a signal outside that list cannot be answered until that signal is added.
- The semantic layer is scoped to the service that serves chat. The background worker writes the pre-computed signal fields using its existing patterns; no shared code package is introduced between services, and no constitution amendment is required. This supersedes an earlier design discussion that had proposed a shared top-level package.
- Chat responses stream incrementally as they are produced, following standard chat conventions, so perceived responsiveness does not depend on total generation time.
- "15x growth" is treated as growth in the number of individually tracked tickers (today ~65) and/or the broader price-history universe (today ~556 symbols) and their historical depth together — the data layer must not assume today's row/document counts are a ceiling in any of these dimensions.
- Removing unused collections applies only to collections confirmed to have zero live reader or writer via both code inspection and direct database inspection (already identified as of this writing: `transcripts_cache`, `fund_holdings`, `sector_performance`, `stock_news`, `market_news`) — not to collections that are simply small or reserved for a planned-but-unbuilt feature. The confirmed list is presented for review before deletion, since deleting data is not reversible.
- The LLM used to answer chat questions is the same class of model/provider already used elsewhere in the platform for generating analysis, unless a different choice is later justified.
- Chat is available to the same audience already using the rest of the app; no new authentication/authorization model is introduced.
- "Efficiently built" collections means indexes and document shapes appropriate to the query patterns the semantic layer and existing app actually use — not premature optimization beyond what current or projected (15x) volume warrants. Because generated queries are not known in advance, indexing targets the pre-computed screening-signal fields and the established access patterns rather than every possible generated filter.
- **Known deviation from project constitution**: Principle III ("Deterministic Core, LLM at the Edges") states that the model interprets while deterministic code computes. Generating queries with the model (FR-011) places query construction inside the model's responsibility, which diverges from that principle. This was a deliberate, explicit choice. The constitution requires such a deviation be recorded with justification in the relevant `plan.md` or resolved by amendment — `/speckit-plan` MUST address this rather than proceed silently. Mitigations already specified: computation of screening values remains deterministic and pre-computed (FR-010), access is structurally read-only (FR-012), and every answer is auditable (FR-013, FR-014).
