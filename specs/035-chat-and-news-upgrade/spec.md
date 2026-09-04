# Feature Specification: Chat AI & News Platform Upgrade

**Feature Branch**: `035-chat-and-news-upgrade`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: "1. I need the chat AI to search the news data I have, so that might mean saving the news to the database and the blurb on in addition to the title and date. 2. On the output for the chat AI if a ticket[r] is in the output it should be clickable. 3. The chat AI should be reviewing the semantic model against a question to generate the mongo query — I don't think its always doing that. I might need a more verbose semantic model to help, so the model can understand how to do aggregations on fields if it needs. 4. I want to save the chat history. I want a sidebar on the chat page that shows the chat history, and I want to be able to delete a chat. The sidebar should display a title that is very short but descriptive of what happened, with a date. 5. Move the top traded stocks to the main sidebar in the app. It currently has the watchlist, so it should now have the watchlist and the top traded stocks. Make each list scrollable in case they get too long. 6. In the news tab it should be a mix of general news and stock news, plus FMP editorial articles (three distinct upstream news feeds: general market news, FMP articles, and stock-specific news). All of this needs to be queryable in the database for the chat AI." *(Source URLs and API keys from the original request are intentionally omitted from this spec; see the news-provider integration referenced in the codebase for connection details.)*

## Clarifications

### Session 2026-08-25

- Q: How far back should the launch news backfill reach for each of the three sources? → A: Fixed recent window (last 30 days)
- Q: When the same news story is fetched again on a later refresh, what keeps it from being stored or shown twice? → A: Source URL is the uniqueness key
- Q: How should embedded HTML in a story's body text (lists, bold, etc.) be handled when displayed? → A: Rendered as sanitized HTML, preserving basic formatting
- Q: Should a chat answer's news citation also be a clickable link, like tickers are? → A: Yes, link to the source article
- Q: How should the short, descriptive title for each saved conversation be generated? → A: Summarized by the chat AI itself after the first exchange

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable, Semantic-Grounded Answers (Priority: P1)

As a user asking the chat AI questions about my stock data, I want the AI to always consult the data's semantic model when deciding how to query the database — including how to aggregate (sum, average, group) fields — so that I get correct, data-backed answers instead of guesses, errors, or silent failures.

**Why this priority**: This is the trust foundation for every other chat capability in this feature. If query generation is inconsistent today, news search (US3) and clickable tickers (US4) just make an unreliable answer look more polished.

**Independent Test**: Ask the assistant a mix of questions — a simple lookup, a question requiring aggregation across records (e.g., "what's the average X for tickers with a bullish signal"), and a question of a shape that previously failed — and confirm each one is correctly translated into a query and answered from live data.

**Acceptance Scenarios**:

1. **Given** a question that requires filtering and grouping data across multiple fields, **When** the user submits it, **Then** the assistant's answer reflects a real aggregation over the underlying data rather than a partial or guessed result.
2. **Given** a question that cannot be mapped to anything in the semantic model, **When** the user submits it, **Then** the assistant tells the user it cannot answer rather than fabricating a result.

---

### User Story 2 - Company & Market News Captured for Search and Browsing (Priority: P1)

As a user, I want all three of my news sources — general market news, FMP editorial articles, and company-specific stock news — saved with enough content (title, date, source, and body/blurb text) so both the chat AI and the News tab can use it.

**Why this priority**: Nothing in US1/US3 (news-aware chat) or the News tab overhaul is possible without the underlying content actually being captured and stored first.

**Independent Test**: Trigger a news refresh and confirm stored records include title, publish date, publisher/source, body or blurb text, and a link for all three source types, and that stock-specific and FMP-article items carry their associated ticker(s).

**Acceptance Scenarios**:

1. **Given** the news refresh has run, **When** a general-market story (no associated ticker) is fetched, **Then** it is saved with title, date, publisher, body/blurb text, and link.
2. **Given** the news refresh has run, **When** a company-specific story or FMP article is fetched, **Then** it is saved with its associated ticker(s) alongside title, date, source, body/blurb text, and link.
3. **Given** the News tab is opened, **When** stories from all three sources exist, **Then** the user sees them interleaved in one recency-ordered stream, not siloed into unrelated tabs.

---

### User Story 3 - Chat Answers Draw on Stored News (Priority: P2)

As a user, I want to ask the chat AI things like "what's the latest news on NVDA" or "anything happening with tariffs this week" and have it search the stored news content, instead of me having to browse the News tab myself.

**Why this priority**: Delivers the original "search my news" request directly, built on US2's stored data.

**Independent Test**: With news stored (per US2), ask the assistant a news-related question referencing a ticker or topic and confirm the answer references specific stored stories (title/date) rather than declining or making something up.

**Acceptance Scenarios**:

1. **Given** news about a specific ticker exists in storage, **When** the user asks about that ticker's recent news, **Then** the response references the actual stored headline(s) and date(s).
2. **Given** no stored news matches the user's question, **When** the user asks, **Then** the assistant says it found no relevant news rather than inventing one.

---

### User Story 4 - Clickable Tickers in Chat Answers (Priority: P2)

As a user reading a chat AI answer, I want any stock ticker it mentions to be a clickable link to that stock's page, so I can jump straight to more detail.

**Why this priority**: Small, self-contained polish that makes every existing and future chat answer more actionable.

**Independent Test**: Ask a question whose answer mentions one or more tickers and confirm each is rendered as a working link to that stock's detail page, while ticker-shaped text that isn't actually a tracked stock is left as plain text.

**Acceptance Scenarios**:

1. **Given** the assistant's answer mentions a ticker that exists in the app, **When** the answer renders, **Then** that ticker displays as a link to its stock page.
2. **Given** the assistant's answer contains a word that looks like a ticker but isn't a tracked stock, **When** the answer renders, **Then** that word is not turned into a broken link.

---

### User Story 5 - Persistent, Manageable Chat History (Priority: P2)

As a user, I want my past conversations with the chat AI saved and listed in a sidebar on the chat page, each with a short auto-generated title and a date, so I can revisit or delete past conversations.

**Why this priority**: Turns the chat AI from a stateless one-off tool into a durable assistant whose past answers stay reachable.

**Independent Test**: Have a conversation, navigate away and back to the chat page, and confirm it appears in the sidebar with a title and date; reopen it to see the prior messages; delete it and confirm it disappears and its messages are no longer retrievable.

**Acceptance Scenarios**:

1. **Given** a new conversation has at least one exchange, **When** the user returns to the chat page, **Then** the sidebar lists it with a short descriptive title and the date it occurred.
2. **Given** a past conversation is open, **When** the user selects a different (or new) conversation, **Then** the message pane switches to that conversation's messages.
3. **Given** a conversation exists in the sidebar, **When** the user deletes it, **Then** it disappears from the sidebar and its messages are no longer retrievable.

---

### User Story 6 - Watchlist and Top Traded Stocks Together in the Main Sidebar (Priority: P3)

As a user, I want the app's main sidebar to show both my Watchlist and the Top Traded Stocks list, each independently scrollable, so both are visible no matter what page I'm on.

**Why this priority**: A navigation convenience — valuable but blocks nothing else in this feature.

**Independent Test**: Open any page that has the main sidebar and confirm both the Watchlist and Top Traded Stocks sections are present and populated; confirm scrolling one list doesn't move the other list or the page.

**Acceptance Scenarios**:

1. **Given** the main sidebar is visible, **When** the page loads, **Then** both the Watchlist and Top Traded Stocks sections are present with current data.
2. **Given** a list (Watchlist or Top Traded Stocks) has more entries than fit in its allotted space, **When** the user scrolls within that list, **Then** only that list's contents scroll.

---

### Edge Cases

- What happens when the chat AI's generated query would need a field not described in the semantic model? System should decline that specific question rather than erroring out or guessing.
- What happens when the same underlying event is covered by more than one of the three news sources (e.g., an FMP article and a stock-specific story about the same company)? Both are stored and shown as distinct items — no cross-source deduplication is attempted.
- What happens when the user deletes the chat conversation that's currently open? The message pane clears to an empty/new-chat state.
- What happens when an upstream news source fails or is rate-limited? Falls back to the existing cache-first, fail-soft behavior already used for market news.
- What happens when backfilling historical news would exceed the daily API budget? Backfill paces itself across multiple days/runs and resumes where it left off, respecting the same budget guard used elsewhere, rather than exhausting the day's quota in one attempt.
- What happens when Top Traded Stocks or the Watchlist is empty? Its section of the sidebar shows the existing empty-state messaging.
- What happens when a chat answer mentions a ticker that was removed from the market? It still links to that stock's page, consistent with how the app already treats removed-from-market tickers elsewhere.

## Requirements *(mandatory)*

### Functional Requirements

**News capture & search**

- **FR-001**: System MUST store, for every ingested news item, at minimum: title, publish date/time, source/publisher, body text or blurb, and a source URL.
- **FR-001a**: System MUST treat a news item's source URL as its uniqueness key, so re-fetching the same story on a later refresh updates or skips the existing record instead of creating a duplicate.
- **FR-002**: System MUST ingest general market news (not tied to any specific ticker) as a distinct news type.
- **FR-003**: System MUST ingest FMP editorial articles, including their associated ticker(s), as a distinct news type.
- **FR-004**: System MUST ingest company-specific stock news, associated with the relevant ticker, as a distinct news type.
- **FR-005**: The News tab MUST display items from all three news types together in a single, recency-ordered stream.
- **FR-006**: The News tab MUST let users tell which type a given story is (general market, FMP article, or stock-specific).
- **FR-006a**: Wherever a story's body/blurb text is displayed (News tab or chat answer), any embedded HTML formatting (lists, bold, emphasis, links) MUST be rendered through a sanitizer that strips scripts and unsafe attributes, so source formatting is preserved without introducing an injection risk.
- **FR-007**: The chat AI MUST be able to search stored news content (title and body/blurb) to answer user questions about recent news.
- **FR-008**: When the chat AI answers a news-related question, it MUST reference the specific stored story (title/date) it drew from rather than producing an unsupported claim, and that reference MUST render as a clickable link to the story's source URL — consistent with how tickers are made clickable (FR-013).
- **FR-009**: When no stored news matches a question, the chat AI MUST say it found nothing rather than inventing an answer.
- **FR-023**: System MUST relocate the Top Traded Stocks list into the main app sidebar and remove it from its current location on the Stocks page — the sidebar becomes its sole location.
- **FR-024**: News ingestion MUST backfill historical stories from all three sources (general market, FMP articles, stock-specific) covering the 30 days prior to launch, in addition to capturing new stories going forward, so the News tab and chat search have depth from day one.

**Query generation grounded in the semantic model**

- **FR-010**: The chat AI MUST consult the semantic data model to determine correct fields and relationships before generating a database query for every question that requires querying stored data.
- **FR-011**: The semantic data model MUST describe how to perform aggregations (e.g., grouping, averaging, summing) over relevant fields so the chat AI can answer analytical questions correctly.
- **FR-012**: When the chat AI cannot map a question to the semantic model, it MUST tell the user it cannot answer rather than returning a fabricated or misleading result.

**Clickable tickers**

- **FR-013**: Any ticker recognized in a chat AI answer that corresponds to a tracked stock MUST render as a clickable link to that stock's detail page.
- **FR-014**: Text that resembles a ticker but does not correspond to a tracked stock MUST NOT be rendered as a link.

**Chat history**

- **FR-015**: System MUST persist each chat conversation, including its messages in order, so it can be retrieved after the user navigates away.
- **FR-016**: System MUST generate a short, descriptive title for each saved conversation — via the chat AI summarizing the conversation after its first exchange, not a mechanical truncation of the user's message — and record the date it occurred.
- **FR-017**: The chat page MUST display a sidebar listing saved conversations, each showing its title and date, ordered by most recent activity first.
- **FR-018**: Users MUST be able to select a saved conversation from the sidebar to view or resume its messages.
- **FR-019**: Users MUST be able to delete a saved conversation from the sidebar; once deleted, it MUST no longer appear or be retrievable.
- **FR-020**: Users MUST be able to start a new conversation from the chat page without losing access to previously saved ones.

**Main sidebar**

- **FR-021**: The app's main sidebar MUST display both the Watchlist and the Top Traded Stocks list.
- **FR-022**: Each list in the main sidebar (Watchlist, Top Traded Stocks) MUST scroll independently once its contents exceed the available space, without scrolling the page or the other list.

### Key Entities *(include if feature involves data)*

- **News Item**: One piece of news content from any of the three sources. Key attributes: source type (general market / FMP article / stock-specific), title, published date/time, publisher or author, body text or blurb, source URL, image URL (if available), and associated ticker(s) (absent for general market news).
- **Chat Conversation**: A saved chat thread. Key attributes: short auto-generated title, the date/time it occurred, and its ordered messages.
- **Chat Message**: One turn within a conversation. Key attributes: who sent it (user or assistant), its text, and its timestamp. Assistant messages may reference tickers or news items that should render as links/citations.
- **Semantic Field Description**: The (expanded) description of a queryable field or relationship in the data model, including how it can be aggregated, used to ground the chat AI's query generation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In testing with a representative set of analytical questions (including ones requiring aggregation), the assistant produces a correct, data-backed answer — rather than declining or guessing — at least 95% of the time.
- **SC-002**: When relevant stored news exists for a user's question, the assistant's answer references at least one real, dated story from storage.
- **SC-003**: 100% of tracked-stock tickers mentioned in a chat answer are clickable, and 0% of ticker-lookalike text that isn't a tracked stock is incorrectly linked.
- **SC-004**: A returning user can find and reopen a conversation from a previous session within 2 clicks of landing on the chat page.
- **SC-005**: Deleting a saved conversation removes it from the sidebar immediately, and it does not reappear after a page reload.
- **SC-006**: On any page showing the main sidebar, users can see both their Watchlist and Top Traded Stocks without navigating away, and scrolling one long list never displaces the rest of the page.
- **SC-007**: The News tab reflects newly published stories from all three sources within the same freshness window the app already promises for market news today.
- **SC-008**: At launch, a user opening the News tab or asking the chat AI about news sees historical stories from the 30 days before the feature shipped, not just stories published afterward.

## Assumptions

- This remains a single-user, local-first application (per project scope) — chat history has no per-user access control; it's a single shared history.
- Ticker recognition for clickable links (US4) uses the app's existing tracked-ticker universe, the same one already used elsewhere (e.g., watchlist, stock pages).
- Conversation titles are generated automatically (e.g., summarized from the first exchange); users are not required to name conversations manually.
- News body/blurb text is stored as supplied by its source (raw HTML included where the source provides it) rather than being re-summarized at ingestion time; it is sanitized at display time per FR-006a.
- Newly ingested news reuses the existing cache-first, budget-conscious fetch pattern already established for market news, rather than introducing a new fetch strategy; the launch backfill is paced across multiple runs to stay within the same daily provider budget rather than fetched in one burst.
- No cross-source deduplication of near-identical stories is required for this feature; stories from different source types are shown as distinct items even if they cover the same event.
