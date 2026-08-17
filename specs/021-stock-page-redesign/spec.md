# Feature Specification: Stock Page Redesign

**Feature Branch**: `021-stock-page-redesign`

**Created**: 2026-08-16

**Status**: Draft

**Input**: User description: "Alter the stock page: move charts into a default Charts tab; fix monthly/yearly chart aggregation; remove the Deep Dive chart but keep Price ROC and Volume ROC; add MACD, z-score, and two more per-timeframe indicators; format long text blocks for readability; remove the Position Management section from Overview; upgrade the Institutional tab with FMP institutional-ownership and beneficial-ownership data plus net-flow visuals; upgrade the Insider tab with FMP insider-trading statistics plus net buy/sell visuals; add an AI-reviewed News section with per-article summaries and a bullish/bearish keyword timeline; revisit the Sentiment tab so a viewer gets the picture at a glance; on AI Summary remove the Market Timing graph (keep caveat notes) and add a news-informed stance."

## Clarifications

### Session 2026-08-16

- Q: Where should the news summaries and bullish/bearish keyword timeline live? → A: Both places — a dedicated News tab holds the article summaries and the timeline; the Sentiment tab also renders the keyword timeline to support its at-a-glance gauge.
- Q: When should news articles, AI summaries, and the sentiment timeline refresh? → A: Only on Pull — all news content (articles, keyword timeline, AI summaries, news stance) is fetched and generated during a ticker analysis pull; the News tab shows the last pull's content labeled with its as-of date.
- Q: Should the four timeframe charts (D/W/M/Y) be line charts or candlestick charts? → A: Candlesticks — each bar shows open/high/low/close so the charts visually match the Strat bar-type logic (inside/outside bars, candle color).
- Q: Which two indicators should join MACD and z-score for each timeframe? → A: Stochastic oscillator + ATR% — stochastic for overbought/oversold swing timing, ATR% for the volatility regime as a percentage of price.
- Q: How much news history should the News tab keep? → A: A full month. The initial 50-article cap collapsed to ~4 days of coverage on mega-caps, so the "30-day trend" wasn't one. The fetch now pages through the whole 30-day window (FR-021); AI summaries stay capped at the 15 newest so LLM cost is unchanged.
- Q: Should MACD render on the yearly timeframe? → A: No — drop MACD from the yearly panel. Yearly MACD needs ~35 years of history to clear warm-up, which almost no ticker has, so it would always show "insufficient history" and never provide a real reading. MACD stays on daily, weekly, and monthly; yearly keeps z-score, stochastic, and ATR%.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Charts Tab as the Default View (Priority: P1)

When a user opens a stock's detail page, they land on a **Charts** tab that contains everything chart-related: the four timeframe charts (daily, weekly, monthly, yearly) at the top, followed by the Price ROC and Volume ROC panels below them. The standalone "Deep Dive" chart section is removed entirely, and charts no longer render above the tab bar — all chart content lives inside the Charts tab.

**Why this priority**: Charts are the first thing the user looks at on every visit; today they're split between an always-on header area and a busy Deep Dive section. This is the core reorganization the rest of the feature builds on.

**Independent Test**: Open any ticker's detail page. The Charts tab is selected by default, shows the four timeframe charts with Price ROC and Volume ROC below them, and no Deep Dive section exists anywhere on the page.

**Acceptance Scenarios**:

1. **Given** a ticker with price history, **When** the user navigates to its detail page with no tab specified, **Then** the Charts tab is active and shows the four timeframe charts (D/W/M/Y) with Price ROC and Volume ROC below them.
2. **Given** the redesigned page, **When** the user scans the whole page, **Then** no "Deep Dive" section is present and no charts render outside the Charts tab.
3. **Given** a ticker with no analysis yet but with price data, **When** the user opens its page, **Then** the Charts tab still renders the price charts (charts do not depend on an analysis existing).

---

### User Story 2 - Correct Monthly and Yearly Chart Aggregation (Priority: P1)

The monthly chart shows one candle per calendar month going back about 3 years (~36 candles). The yearly chart shows one candle per calendar year going back 10–15 years (subject to available history). Each candle represents that period's open, high, low, and close.

**Why this priority**: The user has identified the monthly chart as visibly wrong — points don't correspond to months. A chart that misrepresents its timeframe is worse than no chart.

**Independent Test**: Open a ticker with long history (e.g., AAPL). Count points on the monthly chart (~36, one per month) and the yearly chart (10–15, one per year), and confirm hover/axis labels identify the month or year each point represents.

**Acceptance Scenarios**:

1. **Given** a ticker with 3+ years of history, **When** the user views the monthly chart, **Then** each candle represents one calendar month (open/high/low/close) and roughly 36 months are shown.
2. **Given** a ticker with 15+ years of history, **When** the user views the yearly chart, **Then** each candle represents one calendar year (open/high/low/close) and 10–15 years are shown.
3. **Given** a recently listed ticker with only 2 years of history, **When** the user views the monthly and yearly charts, **Then** the charts show all available complete periods without error and without misleading padding.

---

### User Story 3 - Expanded Per-Timeframe Indicators (Priority: P2)

Below the ROC panels in the Charts tab, the user sees additional indicators computed **per timeframe**: price z-score, stochastic oscillator, and ATR% (volatility as a percentage of price) for daily, weekly, monthly, and yearly; MACD for daily, weekly, and monthly only (yearly MACD needs history almost no ticker has — see Assumptions). Each indicator is visually grouped so the user can compare the same indicator across timeframes at a glance.

**Why this priority**: Adds analytical depth, but depends on the Charts tab structure (US1) existing first.

**Independent Test**: Open a ticker's Charts tab and verify z-score, stochastic, and ATR% each render for all four timeframes, MACD renders for daily/weekly/monthly only, and all values are sensible (e.g., stochastic between 0–100).

**Acceptance Scenarios**:

1. **Given** a ticker with sufficient history, **When** the user scrolls the Charts tab, **Then** z-score, stochastic, and ATR% appear for each of the four timeframes, and MACD appears for daily, weekly, and monthly (not yearly).
2. **Given** a timeframe with insufficient history to compute an indicator (e.g., monthly MACD on a 1-year-old ticker), **When** the user views that indicator, **Then** it shows a clear "insufficient history" state rather than a misleading or empty chart.
3. **Given** any indicator panel, **When** the user hovers a point, **Then** the value and its date are shown.
4. **Given** the stochastic panel, **When** values are rendered, **Then** they stay within 0–100 with overbought/oversold zones visually marked.

---

### User Story 4 - Readable Long-Form Text and Overview Cleanup (Priority: P2)

Long text blocks — the Overview verdict, narratives on the AI Summary tab, and any other multi-sentence prose sections — are formatted for readability: broken into short paragraphs or bullets, with key signals (direction words, tickers, levels, percentages) visually emphasized instead of rendering as a single dense wall of text. The Position Management section is removed from the Overview tab.

**Why this priority**: Readability directly affects whether the user actually absorbs the analysis, but it doesn't block any other story.

**Independent Test**: Open a ticker whose verdict is 4+ sentences. Confirm the text renders as structured, scannable content (paragraph breaks and/or bullets with emphasized key terms), and that no Position Management section appears on Overview.

**Acceptance Scenarios**:

1. **Given** an analysis with a long verdict, **When** the user views the Overview tab, **Then** the verdict is broken into visually distinct chunks rather than one paragraph block.
2. **Given** the AI Summary tab's technical and fundamental narratives, **When** the user views them, **Then** they use the same readable formatting treatment.
3. **Given** any analysis, **When** the user views the Overview tab, **Then** no Position Management section is present.

---

### User Story 5 - News Tab with AI Summaries and Sentiment Timeline (Priority: P2)

A dedicated **News** tab shows recent articles for the ticker, each with a short AI-generated summary. Above the article list, a timeline chart plots bullish vs. bearish language counts per article over time (e.g., an article on Jan 1 had 6 bullish / 2 bearish terms; one on Apr 1 had 0 bullish / 6 bearish), with a visible trend so the user can see sentiment direction shifting at a glance.

**Why this priority**: Entirely new capability the user explicitly wants; it also feeds the Sentiment revisit (US6) and AI Summary stance (US8).

**Independent Test**: Open a ticker with recent news coverage. The News tab shows dated article summaries and a timeline chart of bullish/bearish keyword counts with a trend indication.

**Acceptance Scenarios**:

1. **Given** a ticker with recent news, **When** the user opens the News tab, **Then** each article shows its date, source, headline, and a 1–3 sentence AI summary.
2. **Given** the same ticker, **When** the user views the sentiment timeline, **Then** each article/date contributes a bullish count and a bearish count, and the chart makes the recent trend direction (bullish, bearish, mixed) visually obvious.
3. **Given** a ticker with no recent news, **When** the user opens the News tab, **Then** a clear empty state explains no coverage was found.

---

### User Story 6 - Sentiment Tab at a Glance (Priority: P3)

The Sentiment tab is reorganized so a viewer gets the overall picture in seconds: a prominent headline gauge (bullish / neutral / bearish with strength), the news sentiment timeline (the same chart shown on the News tab), and the supporting detail (tone evidence, keyword pills, earnings-surprise read) below it. Article summaries stay on the News tab; Sentiment borrows only the timeline so its gauge has visual support.

**Why this priority**: Improves an existing tab; depends on the news timeline (US5) existing.

**Independent Test**: Open a ticker's Sentiment tab and confirm the top-of-tab gauge plus timeline convey the sentiment picture without reading any body text; the detail sections remain available below.

**Acceptance Scenarios**:

1. **Given** an analyzed ticker, **When** the user opens the Sentiment tab, **Then** the first screenful shows the overall sentiment signal and the news sentiment timeline.
2. **Given** the reorganized tab, **When** the user scrolls, **Then** tone evidence, bullish/cautious keyword detail, and the earnings-surprise read are still present.

---

### User Story 7 - Institutional and Insider Flow Visuals (Priority: P3)

The Institutional tab is backed by the designated institutional-ownership and beneficial-ownership data sources and gains visuals answering "is this name being net bought or net sold by institutions?" — e.g., a net-flow indicator and a chart of ownership/position changes across recent filing periods, plus notable beneficial-ownership (activist/5%+) filings. The Insider tab is backed by the designated insider-trading statistics source and gains equivalent visuals: net buy vs. sell by quarter, buy/sell ratio trend, and a clear net-direction verdict.

**Why this priority**: Valuable enrichment, but the tabs already function today; this upgrades data fidelity and adds visuals.

**Independent Test**: Open a widely held ticker (e.g., AAPL). The Institutional tab shows a net bought/sold verdict with a supporting chart across filing periods; the Insider tab shows quarterly buy-vs-sell visuals with a net-direction verdict.

**Acceptance Scenarios**:

1. **Given** a ticker with institutional filings, **When** the user opens the Institutional tab, **Then** a clear net bought / net sold indicator and a period-over-period chart are shown.
2. **Given** a ticker with a recent beneficial-ownership (5%+) filing, **When** the user views the Institutional tab, **Then** that filing is surfaced with filer name, date, and stake.
3. **Given** a ticker with insider activity, **When** the user opens the Insider tab, **Then** quarterly acquired-vs-disposed visuals and a buy/sell ratio trend are shown alongside the existing transaction table.
4. **Given** a ticker with no institutional or insider data, **When** the user opens those tabs, **Then** a clear empty state appears instead of empty charts.

---

### User Story 8 - AI Summary Refresh (Priority: P3)

On the AI Summary tab, the Market Timing section's breadth-divergence graph is removed (it duplicates the Macro page) while the caveat notes (e.g., gap-fill warnings) are kept. A new **News Stance** section reads the latest article summaries and states a stance — bullish / neutral / bearish — with brief reasoning grounded in specific articles. The tab also surfaces "what changed since the last analysis" when a prior analysis exists.

**Why this priority**: Refinement of an existing tab; the news stance depends on US5.

**Independent Test**: Open a ticker's AI Summary tab: no breadth/market-timing graph is present, caveat notes still render, and a News Stance section states a direction with article-grounded reasoning.

**Acceptance Scenarios**:

1. **Given** an analysis with market-timing caveats, **When** the user opens AI Summary, **Then** the caveats render but no breadth-divergence chart does.
2. **Given** a ticker with recent news, **When** the user opens AI Summary, **Then** a News Stance section states bullish/neutral/bearish with reasoning referencing at least one specific article.
3. **Given** a ticker analyzed more than once, **When** the user opens AI Summary, **Then** a short "what changed since last analysis" note highlights signal or conviction changes.

---

### Edge Cases

- Ticker with short history (IPO'd recently): monthly/yearly charts and long-lookback indicators show partial data or "insufficient history" states, never errors or misleading fills.
- External data budget exhausted (rate-limited provider): institutional, insider, and news sections serve the most recent cached data with a staleness indicator rather than failing or burning quota.
- Articles with no recognized bullish/bearish terms: they appear in the summaries list but contribute a neutral (0/0) point — the timeline must not treat "no terms" as bearish.
- Very high news volume (mega-caps): a month of a heavily covered name is several hundred articles (AAPL measured at ~630 over 30 days, 2026-08-16). All of them are retained and counted in the timeline; the article list reveals a page at a time so the tab stays readable.
- Deep-linking to a removed tab or the old default: old links (e.g., `#overview` as implicit default) still resolve — unknown/removed tab anchors fall back to the Charts tab.
- Non-open-market insider transactions (awards, exercises, gifts): excluded or visually distinguished in net buy/sell visuals so they don't masquerade as conviction buying.

## Requirements *(mandatory)*

### Functional Requirements

**Charts tab (US1, US2, US3)**

- **FR-001**: The stock detail page MUST have a Charts tab, and it MUST be the default active tab when no tab is specified.
- **FR-002**: The Charts tab MUST contain, top to bottom: the four timeframe charts (daily, weekly, monthly, yearly), then Price ROC and Volume ROC panels, then the per-timeframe indicator panels.
- **FR-002a**: The four timeframe charts MUST render as candlestick (open/high/low/close) charts, with each candle representing one period of that timeframe (one day, week, month, or year), so bar structure matches the Strat rule engine's view of the data.
- **FR-003**: The Deep Dive chart section MUST be removed, and no chart content may render outside the Charts tab.
- **FR-004**: The monthly chart MUST plot one candle per calendar month covering approximately the last 3 years of available history.
- **FR-005**: The yearly chart MUST plot one candle per calendar year covering the last 10–15 years of available history.
- **FR-006**: When available history is shorter than a chart's target lookback, the chart MUST show all complete available periods without error.
- **FR-007**: The Charts tab MUST show price z-score, stochastic oscillator, and ATR% for each of the four timeframes (daily, weekly, monthly, yearly), and MACD for daily, weekly, and monthly only (not yearly), grouped for cross-timeframe comparison.
- **FR-008**: Any indicator lacking sufficient history for a timeframe MUST display an explicit "insufficient history" state.
- **FR-009**: Chart content MUST render for any ticker with price data, independent of whether an analysis exists.

**Text readability & Overview (US4)**

- **FR-010**: Long-form prose (Overview verdict, AI Summary narratives, and other multi-sentence sections) MUST be rendered as structured, scannable content — short paragraphs and/or bullets — with key terms (signal direction, price levels, percentages) visually emphasized.
- **FR-011**: The Position Management section MUST be removed from the Overview tab.

**Institutional (US7)**

- **FR-012**: Institutional ownership data MUST come from the designated institutional-ownership and beneficial-ownership sources (see Data Sources), through the existing cache-first data layer.
- **FR-013**: The Institutional tab MUST display a net bought / net sold verdict and a visual of institutional position changes across recent filing periods, derived from the entitled sources (beneficial-ownership filings and the existing cached holder snapshot); full 13F flow is out of reach until the provider plan is upgraded.
- **FR-014**: The Institutional tab MUST surface recent beneficial-ownership (5%+/activist) filings with filer, date, and stake when present.

**Insider (US7)**

- **FR-015**: Insider activity statistics MUST come from the designated insider-trading statistics source (see Data Sources), through the existing cache-first data layer.
- **FR-016**: The Insider tab MUST display quarterly acquired-vs-disposed visuals, a buy/sell ratio trend, and a net-direction verdict, alongside the existing transaction detail.
- **FR-017**: Net buy/sell visuals MUST exclude or visually distinguish non-open-market transactions.

**News & Sentiment (US5, US6)**

- **FR-018**: The page MUST include a dedicated News tab showing recent articles (date, source, headline) each with a short AI-generated summary, with the bullish/bearish keyword timeline above the article list.
- **FR-019**: The system MUST scan article text for bullish and bearish terms and plot per-article/per-date bullish and bearish counts on a timeline chart that makes the recent trend direction visually obvious.
- **FR-020**: The Sentiment tab MUST lead with an at-a-glance view: overall sentiment signal plus the same news sentiment timeline rendered on the News tab, with existing detail (tone evidence, keyword pills, earnings-surprise read) below; article summaries appear only on the News tab.
- **FR-021**: The system MUST retain a full 30-day window of articles — every article in the window, not a truncated newest-N slice — so the timeline reflects a month of tone rather than however many days the newest page happens to cover. Heavily covered names run into the hundreds of articles; the article list MUST page/expand rather than render them all at once, while the timeline always summarizes the whole window.
- **FR-021a**: News-dependent sections MUST state how many days of the window actually had coverage, so a thinly covered ticker doesn't imply a month of data it doesn't have.
- **FR-022**: A ticker with no recent news MUST show a clear empty state in news-dependent sections.
- **FR-022a**: All news content (article list, keyword timeline, AI summaries, news stance) MUST be fetched and generated during a ticker analysis pull — never on page load — and the News tab MUST label the content with the pull's as-of date.

**AI Summary (US8)**

- **FR-023**: The Market Timing breadth-divergence chart MUST be removed from the AI Summary tab; market-timing caveat notes MUST be retained.
- **FR-024**: The AI Summary tab MUST include a News Stance section stating bullish/neutral/bearish with reasoning that references specific recent articles.
- **FR-025**: When a prior analysis exists, the AI Summary tab MUST note material changes since the last analysis (signal, conviction, or key-flag changes).

**Cross-cutting**

- **FR-026**: All new external data access MUST respect the provider's daily request budget, serving stale cached data with a staleness indicator when the budget is exhausted.
- **FR-027**: Existing deep links to tab anchors MUST keep working; unknown or removed anchors MUST fall back to the Charts tab.

### Key Entities

- **News Article**: A dated, sourced article about a ticker — headline, source, publish date, body text, AI summary, bullish term count, bearish term count.
- **Sentiment Timeline Point**: A date with aggregated bullish and bearish term counts (from one or more articles) contributing to a trend view.
- **Institutional Flow Snapshot**: A filing period's aggregate institutional position data for a ticker — total shares/positions, change vs. prior period, derived net bought/sold direction.
- **Beneficial Ownership Filing**: A 5%+/activist ownership disclosure — filer name, filing date, stake size.
- **Insider Statistics Period**: A quarter's insider activity aggregates — acquired vs. disposed transaction counts and share volumes, buy/sell ratio.
- **Timeframe Indicator Series**: A per-timeframe computed series (z-score, stochastic, ATR% for all four timeframes; MACD for daily/weekly/monthly only) with values and dates.

### Data Sources

The following provider endpoints were designated by the user (keys supplied via existing configuration, never stored in specs or code):

- Institutional ownership: FMP `stable/institutional-ownership/latest` — **verified NOT entitled on the current plan (HTTP 402, checked 2026-08-16**, consistent with specs/017's 13F finding). Institutional visuals therefore derive from beneficial-ownership filings plus the existing cached 13F snapshot; revisit if the plan is upgraded.
- Beneficial ownership: FMP `stable/acquisition-of-beneficial-ownership?symbol=...` (verified entitled 2026-08-16)
- Insider statistics: FMP `stable/insider-trading/statistics?symbol=...`
- Stock news: FMP `stable/news/stock?symbols=...`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Opening any ticker page lands on the Charts tab with all four timeframe charts visible within 2 seconds on cached data.
- **SC-002**: On a ticker with 15+ years of history, the monthly chart shows ~36 monthly candles and the yearly chart shows 10–15 yearly candles — verifiable by counting.
- **SC-003**: A user can determine each of the following in under 10 seconds without reading body text: overall sentiment direction (Sentiment tab), institutional net bought/sold (Institutional tab), and insider net direction (Insider tab).
- **SC-004**: 100% of long-form prose sections on Overview and AI Summary render as structured content (no single text block longer than ~3 sentences without a visual break).
- **SC-005**: For a ticker with recent coverage, the News tab shows summaries and a sentiment timeline whose trend direction matches a human read of the same articles in at least 8 of 10 spot-checks.
- **SC-006**: Zero occurrences of the removed sections (Deep Dive, Overview Position Management, AI Summary breadth chart) anywhere on the page.
- **SC-007**: A full day of normal browsing (including news/institutional/insider refreshes) stays within the external provider's daily request budget.

## Assumptions

- **Two additional indicators (clarified 2026-08-16)**: Stochastic oscillator (overbought/oversold swing timing, pairs well with Strat-style swing logic) and ATR% (volatility regime, complements the Strat-based range logic) join MACD and z-score.
- **Yearly MACD dropped (clarified 2026-08-16)**: MACD's standard 12/26/9 settings need ~35 periods to clear warm-up — on a yearly timeframe that's ~35 years of history, which almost no ticker has. Rather than a panel that (almost) always shows "insufficient history," MACD is scoped to daily/weekly/monthly; yearly keeps z-score, stochastic, and ATR%, all of which are meaningful with far less history.
- **News placement (clarified 2026-08-16)**: News gets its own dedicated tab (article summaries + keyword timeline); the Sentiment tab remains and also renders the keyword timeline beneath its gauge. The timeline is one shared visual rendered in two places.
- **Bullish/bearish term detection** reuses and extends the existing keyword approach already present in the sentiment sub-report (bullish/cautious term lists), applied per-article with dates, rather than inventing a parallel mechanism.
- **"Yearly" chart** means one candle per calendar year (annual open/high/low/close); 10–15 years shown when history allows, fewer otherwise.
- **Position Management is hidden, not deleted upstream**: the section is removed from the Overview UI; the underlying analysis output continues to exist (other consumers/specs, e.g. spec 015, still reference it).
- **Overview remains a tab** (no longer default); its verdict/trends/flags content is unchanged apart from formatting and the Position Management removal.
- **News freshness (clarified 2026-08-16)**: All news content — article fetch, keyword timeline, AI summaries, and news stance — is produced during a ticker analysis pull, consistent with how other AI narrative content works today. The News tab reflects the last pull and is labeled with its as-of date; refreshing news means pulling a new analysis.
- **Beneficial-ownership and institutional-ownership data** may lag by filing period (13F/13D/G cadence); the UI labels data with its as-of date rather than implying real-time flow.
