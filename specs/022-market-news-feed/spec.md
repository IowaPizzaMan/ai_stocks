# Feature Specification: Market News Feed on the Stocks Page

**Feature Branch**: `022-market-news-feed`

**Created**: 2026-08-16

**Status**: Draft

**Input**: User description: "It looks like the API route I used initially to get news was just for all stocks. Lets put that one on the stocks page below the stock grid, make it so it doesn't scroll infinitely, just put the most recent 20 articles in there. I can get these when I go to the page and I don't need to save these to history. Now for each individual stock the API route it calls should be `news/stock?symbols=CAH` — this will get the news for the specific stock."

## Clarifications

### Session 2026-08-16

- Q: What should the 20 articles on the Stocks page actually be about? → A: All-market stock news — the market-wide latest-stock-news source, each article tagged with its ticker so headlines link through, including names the user doesn't track yet.
- Q: When the Stocks page is filtered (ticker, signal, sector, conviction), should the news section filter too? → A: No — the news section is always all-market and ignores the grid's filters, so it stays useful even when a filter narrows the grid to a handful of stocks.
- Q: How fresh should the market news be on each visit? → A: Reuse retrieved articles for ~60 minutes (one provider call per hour at most), prioritizing budget headroom over minute-level freshness.

**Post-analysis correction (2026-08-16, `/speckit-analyze` finding F1)**: FR-011 (60-minute reuse) was originally filed under User Story 3 "Resilience and budget" but is built as part of the freshness behavior, so it now sits with US2's requirements. US3 narrowed to graceful degradation only, and its Independent Test no longer claims to verify caching it cannot reach on its own.

## Context: what is already true

The per-stock news built in [spec 021](../021-stock-page-redesign/spec.md) **already calls the per-symbol route** the user names here (`news/stock?symbols={TICKER}`), and it already scopes results to the ticker being viewed. No change is required for that half of the request — this feature only adds the market-wide section. The distinction:

| Surface | Scope | Source | Persistence |
|---------|-------|--------|-------------|
| Stock detail → News tab (spec 021, built) | One ticker | per-symbol news route | Saved with the analysis, refreshed on Pull |
| Stocks page → Market news (this feature) | Whole market | market-wide latest-news route | Not saved to history; fetched when the page is opened |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Market News Below the Stock Grid (Priority: P1)

A user scrolling the Stocks page past their analysis grid finds a market news section showing the 20 most recent stories across the whole market. Each entry shows its headline, source, publish time, and the ticker it concerns (when the story is about a specific company), and links out to the original article. The list ends after 20 — it does not grow as the user keeps scrolling.

**Why this priority**: This is the entire feature; without it there is nothing to test.

**Independent Test**: Open the Stocks page, scroll past the grid, and confirm exactly 20 dated articles appear with headline, source, and ticker, and that scrolling further loads nothing more.

**Acceptance Scenarios**:

1. **Given** the Stocks page with analyses present, **When** the user scrolls below the stock grid, **Then** a market news section shows the 20 most recent market-wide articles, newest first.
2. **Given** the market news section, **When** the user continues scrolling to the bottom, **Then** no additional articles load and the list visibly ends.
3. **Given** an article about a specific company, **When** the user views its entry, **Then** the associated ticker is shown and leads to that ticker's detail page.
4. **Given** an article entry, **When** the user selects the headline, **Then** the original article opens in a new tab.

---

### User Story 2 - Fresh on Visit, Not Kept as History (Priority: P1)

The market news reflects current market coverage when the user opens the Stocks page — refreshed at most once an hour — rather than whatever was captured during some past analysis run. These articles are transient: they are not written into any ticker's saved analysis, and they do not accumulate as a permanent archive.

**Why this priority**: The user explicitly asked for visit-time freshness and no history retention; getting this wrong would either show stale news or pollute the analysis history.

**Independent Test**: Open the Stocks page, note the newest headline, and confirm no market-news articles were added to any stored ticker analysis. Re-open the page repeatedly and confirm the provider is not contacted every time.

**Acceptance Scenarios**:

1. **Given** a user opening the Stocks page, **When** the section loads, **Then** the articles reflect market coverage from within the last hour rather than the last per-ticker analysis run.
2. **Given** market news has been displayed, **When** any ticker's stored analysis is inspected, **Then** it contains no market-wide news articles.
3. **Given** the user navigates away and returns to the Stocks page, **When** the section reloads, **Then** it displays current articles without the user taking any refresh action.
4. **Given** the user leaves the Stocks page open, **When** time passes, **Then** the section does not poll or auto-refresh on a timer.
5. **Given** a user opens the Stocks page several times in quick succession, **When** each visit loads, **Then** the provider is contacted at most once per hour and the remaining visits reuse those articles.

---

### User Story 3 - Graceful Degradation (Priority: P2)

The market news section never breaks the Stocks page. If news cannot be retrieved — the provider is down, or the day's request budget is spent — the section shows a clear, non-alarming message while the stock grid above it continues to work normally.

**Why this priority**: The Stocks page is the app's home screen; a news failure must not degrade it.

**Independent Test**: Simulate a provider failure and confirm the grid still renders normally with a news-specific message rather than a page error; exhaust the budget cap and confirm previously retrieved articles are shown marked as not current. (The hourly reuse behavior itself belongs to US2 — this story only covers what happens when a refresh *fails*.)

**Acceptance Scenarios**:

1. **Given** the news provider is unreachable, **When** the user opens the Stocks page, **Then** the stock grid renders normally and the news section shows a brief unavailable message.
2. **Given** the daily provider budget is exhausted, **When** the user opens the Stocks page, **Then** the most recently retrieved articles are shown with an indication that they are not current, rather than an error.
3. **Given** the news section is still loading, **When** the page renders, **Then** the stock grid is already usable and the news area shows a loading state.

---

### Edge Cases

- Provider returns fewer than 20 articles: the section shows all available and does not pad or error.
- An article has no associated ticker (general market commentary): it renders without a ticker link rather than being dropped.
- An article's ticker is not in the user's tracked universe: the ticker still displays; following it leads to that ticker's page, which offers a Pull if no analysis exists.
- Duplicate stories syndicated across outlets: near-identical headlines may appear; deduplication is not required for v1.
- Very long headlines or missing images: entries stay on a single readable row and never break the page layout.
- The user has no analyses yet (empty stock grid): the market news section still renders, giving the empty page something useful.

## Requirements *(mandatory)*

### Functional Requirements

**Market news section (US1)**

- **FR-001**: The Stocks page MUST display a market-wide news section positioned below the stock grid.
- **FR-001a**: The section MUST show all-market stock news — stories from across the market, including tickers the user does not track — rather than general macro commentary or a portfolio-only digest.
- **FR-001b**: The section MUST ignore the Stocks page filter bar (ticker, signal, sector, conviction); the same all-market articles appear regardless of how the grid is filtered.
- **FR-002**: The section MUST show at most the 20 most recent articles, ordered newest first.
- **FR-003**: The section MUST NOT paginate or infinitely scroll; the list ends at 20 with no "load more" affordance.
- **FR-004**: Each article MUST display its headline, source, and publish date/time.
- **FR-005**: Each article associated with a company MUST display that ticker, linked to the ticker's detail page.
- **FR-006**: Selecting an article's headline MUST open the original article in a new tab.

**Freshness and retention (US2)**

- **FR-007**: Market news MUST be retrieved when the user opens the Stocks page, not during ticker analysis runs.
- **FR-008**: Market news articles MUST NOT be written into any ticker's stored analysis document.
- **FR-009**: Market news MUST NOT be retained as a permanent history; only enough is kept to satisfy FR-011's budget protection.
- **FR-010**: The section MUST NOT poll or auto-refresh while the page sits open.
- **FR-011**: Repeated visits to the Stocks page MUST NOT trigger a provider call each time; retrieved articles MUST be reused for approximately 60 minutes, so the provider is contacted at most once per hour regardless of how often the page is opened.

**Graceful degradation (US3)**

- **FR-012**: When news cannot be retrieved, the Stocks page and its stock grid MUST continue to render normally, with the failure confined to the news section.
- **FR-013**: When the daily provider budget is exhausted, the section MUST show the most recently retrieved articles marked as not current, rather than failing.

**Per-stock news (already satisfied — stated to prevent regression)**

- **FR-014**: Per-ticker news on the stock detail page MUST continue to use the per-symbol news route scoped to the viewed ticker, and MUST remain saved with that ticker's analysis and refreshed on Pull (spec 021 behavior). This feature MUST NOT change it.

### Key Entities

- **Market News Article**: A recent market-wide story — headline, source/publisher, publish timestamp, article link, and an optional associated ticker. Transient; not part of any ticker's analysis record.

### Data Sources

Provider endpoints (keys supplied via existing configuration, never stored in specs or code). Entitlement verified live 2026-08-16:

- Market-wide stock news: FMP `stable/news/stock-latest` — **entitled**. Returns market-wide articles each tagged with a `symbol`, which is what makes FR-005's ticker link possible.
- General market news: FMP `stable/news/general-latest` — **entitled**, but **not used**: the all-market stock source was chosen instead (Clarifications, 2026-08-16). Recorded here only so a future revisit knows it is available without re-probing.
- Press releases: FMP `stable/news/press-releases-latest` — **not entitled (HTTP 402)**; out of scope.
- Per-ticker news (unchanged, already in use): FMP `stable/news/stock?symbols={TICKER}`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user opening the Stocks page can see current market headlines without navigating anywhere else or taking any action.
- **SC-002**: The market news section shows exactly 20 articles when at least 20 are available, verifiable by counting; scrolling past the end loads nothing further.
- **SC-003**: The stock grid remains fully usable when news retrieval fails — 100% of grid functionality unaffected.
- **SC-004**: A day of normal browsing adds at most one provider call per hour for market news (≤24/day) regardless of how many times the Stocks page is opened.
- **SC-005**: Inspecting stored ticker analyses after viewing market news shows zero market-wide articles added to them.
- **SC-006**: Per-ticker news on the stock detail page continues to show only articles concerning that ticker (no regression from spec 021).

## Assumptions

- **The per-symbol route is already correct**: the stock detail page already calls `news/stock?symbols={TICKER}`. The user's concern that it might be fetching all stocks was checked against the code and the live API; no change is needed there, so this feature is additive only.
- **Ticker-tagged market news is the source (clarified 2026-08-16)**: `news/stock-latest` rather than `news/general-latest`, because its per-article `symbol` is what lets a headline link to a ticker page (FR-005) and surfaces names the user isn't tracking yet.
- **"Not saved to history" means no permanent archive, not zero caching (clarified 2026-08-16)**: articles are reused for ~60 minutes purely so repeat visits don't spend provider quota (FR-011), and are never added to analysis documents or kept as a growing record. The user chose the hour-long window over shorter ones, accepting that headlines may lag by up to an hour in exchange for budget headroom.
- **The news section is filter-independent (clarified 2026-08-16)**: the Stocks page filter bar narrows the grid only. This also avoids a dead-end where a narrow filter would otherwise leave the news section empty.
- **Fetch-on-navigation, never polling**: consistent with existing app behavior, the section loads when the page is opened and on manual navigation only.
- **20 is a fixed display cap**, not user-configurable in v1.
- **No AI summarization or sentiment scoring** is applied to market news — that treatment stays with per-ticker news, where it feeds a specific ticker's analysis. This section is a plain, scannable headline list.
- **The stock grid's own infinite scroll is unchanged**; the "no infinite scroll" requirement applies to the news section only.
