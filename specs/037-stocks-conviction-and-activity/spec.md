# Feature Specification: Stocks Page Organization, Conviction Rework & Activity Trail

**Feature Branch**: `037-stocks-conviction-and-activity`

**Created**: 2026-09-04

**Status**: Draft

**Input**: User description: "On the stocks page, I have so many stocks I need a better way to organize them, I'm thinking alphabetically within each category bullish, neutral, and bearish. Then I want to rework how the conviction works as most of the stuff is ending up a 3. If it's high conviction that means I want to buy it. I only want to buy when all my strategies say to buy and the stock is in the lower quartile of the daily and weekly z-score metric. Also I want to factor in their revenue. If they are growing revenue YOY then that is good. If they are losing MOM that is bad type of inclusion. So help me figure this out. Then the last update I want is I want to see on the stocks page a notifications area that will show stocks I recently added and updated. Just show the last 100, make it paging. It should say something like 'AVB was added on 9/4' and the ticker should be a link to the stock page. The last update I'm looking to make is I want some breadcrumbs I can follow so help me figure that out."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Surface the best ideas first, then find any stock by position (Priority: P1)

The user has grown their tracked universe to the point where scanning the Stocks board is slow. Within each signal group (Bullish, Neutral, Bearish) the tiles currently appear in an order that is not predictable. The user wants each group ordered by conviction first — highest-conviction tickers on top — and then alphabetically by ticker within the same conviction level, so the strongest ideas are always at the top of a group and "Load more" pages down into progressively lower-conviction names.

**Why this priority**: This is a small, low-risk presentation change that removes friction the user hits on every visit, and it makes the reworked conviction (US2) immediately useful by putting the actionable stocks where they are seen first. It delivers value even if nothing else in this feature ships.

**Independent Test**: Load the Stocks page with enough tracked tickers to fill several rows in each group; confirm that within Bullish, within Neutral, and within Bearish the tiles run high-conviction first, then medium, then low, with tickers in A→Z order inside each conviction level, and that the three groups still appear in the fixed order Bullish, Neutral, Bearish.

**Acceptance Scenarios**:

1. **Given** the Bullish group contains MSFT (high), AVB (high), GOOG (medium), and AAPL (low), **When** the Stocks page renders, **Then** the tiles appear in the order AVB, MSFT, GOOG, AAPL (conviction descending, then A→Z within a level).
2. **Given** tickers are spread across all three signal groups, **When** the page renders, **Then** the groups appear top-to-bottom as Bullish, then Neutral, then Bearish, each independently ordered by conviction-then-ticker.
3. **Given** a filter (sector, industry, sentiment, conviction) is applied, **When** the filtered results render, **Then** the surviving tiles are still grouped by signal and ordered by conviction-then-ticker within each group.
4. **Given** more results exist than are loaded, **When** the user clicks "Load more", **Then** the newly loaded tiles all sort at or after the last already-visible tile in conviction-then-ticker order, and no already-visible tile changes position.
5. **Given** two Bullish tickers both rated medium, **When** the page renders, **Then** they appear adjacent in A→Z order with no high- or low-conviction tile between them.

---

### User Story 2 - A high-conviction rating means "buy this now" (Priority: P1)

Today almost every analyzed stock is rated high conviction (3 of 3 on the meter), so the rating carries no information. The user wants "high conviction" to be a rare, decisive signal that means: every one of my stock-picking strategies (`the_strat`, `accumulation`, `gap_analysis`) is calling buy, the stock is currently cheap on its own recent history (bottom quartile of both the daily and the weekly z-score), and its revenue trend is not working against the thesis. Anything short of all those conditions is at most medium, and a stock with a broken revenue trend or that is not oversold cannot be high. Market-wide timing (`market_flow`) and position-management guidance are shown as context but do not raise or lower the rating.

**Why this priority**: The conviction rating is the single number the user acts on. While it is stuck at the top for everything, the user cannot use the board to prioritize. This is the core of the request.

**Independent Test**: Pick a stock where all strategy signals are "buy", both z-scores sit in their bottom quartile, and revenue is growing year over year; confirm it is rated high. Then change any one of those inputs (one strategy flips to hold, or a z-score rises out of the bottom quartile, or revenue turns to a sequential decline) and confirm the rating drops to medium or lower. Confirm the meter on the Stocks board and the rating shown on the stock detail page agree.

**Acceptance Scenarios**:

1. **Given** all of a stock's strategy signals say buy, its daily z-score and its weekly z-score are both in the bottom quartile, and its revenue is growing year over year, **When** conviction is computed, **Then** the stock is rated **high**.
2. **Given** a stock meets every high-conviction condition except that one strategy signal is not "buy", **When** conviction is computed, **Then** the stock is rated **medium** or lower and is never rated high.
3. **Given** a stock's strategies all say buy and both z-scores are in the bottom quartile, but its most recent reported revenue fell versus the prior period, **When** conviction is computed, **Then** the stock is not rated high, and the revenue drag is stated in the rationale.
4. **Given** a stock's daily z-score is in the bottom quartile but its weekly z-score is not, **When** conviction is computed, **Then** the stock is not rated high (both timeframes are required).
5. **Given** a stock has insufficient price history or missing revenue data to evaluate a condition, **When** conviction is computed, **Then** that stock is not rated high and the rating explains which input was unavailable.
6. **Given** a batch of previously analyzed stocks, **When** the reworked conviction is applied across the board, **Then** materially fewer stocks carry a high rating than under the old behavior, and the rating distribution is visibly spread across high / medium / low.
7. **Given** a stock is rated high conviction, **When** the user opens its detail page, **Then** the reasons it qualified (strategies aligned, z-score position, revenue trend) are shown in plain language.

---

### User Story 3 - See what I recently added or changed (Priority: P2)

The user adds and re-analyzes stocks frequently and loses track of what has entered the board recently. They want an activity area on the Stocks page listing the most recent additions and updates as short lines — for example "AVB was added on 9/4" or "AVB was updated on 9/4" — with the ticker as a link to that stock's page. The list shows the 100 most recent events and is paged so the user can step back through them.

**Why this priority**: Useful and self-contained, but the page is still usable without it; it depends on nothing in stories 1 and 2.

**Independent Test**: Add a new ticker and confirm an "added" line appears at the top of the activity area dated today with a working link to the stock page. Re-run analysis on an existing ticker and confirm an "updated" line appears. Confirm the area shows at most one page of events at a time, that paging moves through up to 100 events total, and that older events beyond 100 are not shown.

**Acceptance Scenarios**:

1. **Given** a ticker was newly registered today, **When** the user views the Stocks page activity area, **Then** the first entry reads like "AVB was added on 9/4" with "AVB" linking to the AVB stock page.
2. **Given** an existing ticker was just re-analyzed, **When** the activity area refreshes, **Then** an entry reads like "AVB was updated on 9/4" and links to the AVB stock page.
3. **Given** a re-analysis changed a ticker's conviction from medium to high, **When** the activity area renders, **Then** its "updated" entry is visually flagged as a change and notes "conviction medium→high"; a re-analysis that changed nothing shows an unflagged "updated" entry.
4. **Given** more than one page of events exists, **When** the user advances the paging control, **Then** the next set of older events is shown and the user can page back to the newest.
5. **Given** there have been more than 100 add/update events historically, **When** the user pages to the end, **Then** no more than 100 events total are reachable, newest first.
6. **Given** the same ticker was added and later updated, **When** the activity area renders, **Then** both events appear as separate dated lines in chronological position.
7. **Given** the activity area is empty (fresh install, no events yet), **When** the page renders, **Then** a short empty-state message is shown instead of a blank panel.

---

### User Story 4 - Follow a breadcrumb trail while navigating (Priority: P3)

The user wants a navigational breadcrumb trail shown near the top of each page (for example `Stocks / AVB / News`) where each ancestor segment is a link back to that level, so the user always knows where they are and can step back up without using the browser back button. (Per Clarification Q3, the user also wants a per-stock change-history trail — that is User Story 5.)

**Why this priority**: A navigation convenience that improves orientation but changes no data and blocks nothing else.

**Independent Test**: Navigate from the Stocks page into a stock detail page and then into one of its tabs; confirm a breadcrumb trail shows the path, that clicking an ancestor segment returns to that level, and that the trail is consistent across the main pages of the app.

**Acceptance Scenarios**:

1. **Given** the user is on a stock detail page reached from the Stocks board, **When** the page renders, **Then** a breadcrumb trail shows `Stocks / <TICKER>` with "Stocks" linking back to the board.
2. **Given** the user is on a sub-tab of a stock detail page, **When** the page renders, **Then** the trail shows `Stocks / <TICKER> / <Tab>` and each earlier segment is a working link.
3. **Given** the user is on a top-level page (e.g. Stocks, Macro, News), **When** the page renders, **Then** the trail shows just that page name with no dangling separator.
4. **Given** the user clicks the `<TICKER>` segment while on a sub-tab, **When** the navigation completes, **Then** the user lands on that stock's default view.

---

### User Story 5 - Trace why a stock's verdict changed over time (Priority: P3)

The user wants a per-stock "breadcrumb" history: an ordered trail, on the stock detail page, of the meaningful changes to that stock's verdict — when it was added, and each time its signal or conviction changed, with the reason. For example: "9/1 added · 9/3 conviction low→medium (weekly z-score entered bottom quartile) · 9/4 conviction medium→high (all strategies aligned, revenue +8% YoY)". This lets the user follow the reasoning trail rather than only seeing the current state.

**Why this priority**: Adds explanatory depth and pairs naturally with the reworked, rule-based conviction (the rules make a real "reason" available), but the board is fully usable without it and it depends on nothing else here.

**Independent Test**: Re-analyze a stock across two runs where an input changes enough to move its conviction or signal; confirm the stock detail page shows a dated trail entry for the change with a human-readable reason, and that the trail is capped and ordered newest- or oldest-first consistently.

**Acceptance Scenarios**:

1. **Given** a stock's conviction changed from medium to high on the most recent analysis, **When** the user opens its detail page, **Then** the change-history trail shows a dated entry "conviction medium→high" with the reason drawn from the conviction rules.
2. **Given** a stock's signal changed from neutral to bullish, **When** the trail renders, **Then** a dated entry records the signal change.
3. **Given** a re-analysis produced no change in signal or conviction, **When** the trail renders, **Then** no new entry is added for that run.
4. **Given** a stock was just added, **When** the trail renders, **Then** its first entry is the dated "added" event.
5. **Given** a long-tracked stock with many changes, **When** the trail renders, **Then** it shows at most a bounded number of the most recent entries (see Assumptions) with older ones truncated.

---

### Edge Cases

- **Ties and casing in sorting**: within a conviction level, ticker symbols are compared case-insensitively; identical symbols cannot occur because each ticker appears once per board. A tile whose conviction is missing/unknown sorts after all rated tiles in its signal group.
- **Conviction changes reorder the board**: when a re-analysis changes a stock's conviction, its tile moves to the correct conviction block within its signal group on the next board load — position is a function of current conviction, not arrival order.
- **Unrecognized signal group**: tiles whose signal is not one of bullish / neutral / bearish continue to appear in their existing "Unrecognized" group, ordered by the same conviction-then-ticker rule (most such tiles have no conviction, so they fall back to A→Z).
- **Quartile boundary**: "bottom quartile" is inclusive of the 25th-percentile value; a stock exactly on the boundary counts as in the bottom quartile.
- **Quartile reference set**: the quartile is computed over the stock's own recent z-score history, not across the whole universe (see Assumptions) — a stock with too short a history to establish quartiles cannot be rated high.
- **Partial strategy coverage**: if one of the three entry strategies produces no signal at all for a stock (not enough data), that is treated as "not a buy" for the all-strategies-agree test, not skipped.
- **Revenue data gaps**: a stock with no reported revenue history is treated as failing the revenue condition for high conviction, and the rationale says so; it can still be medium or low.
- **Conflicting revenue signals**: year-over-year growth but a sequential period-over-period decline — the decline blocks high conviction (the "losing ground" case the user called out).
- **Activity area vs. removed tickers**: if a ticker was added and later removed from the board, its historical "added"/"updated" lines still render but the link points to a page that shows the removed state.
- **Same-day multiple updates**: multiple re-analyses of one ticker on the same day each produce their own entry; the date label is the same but ordering follows event time.
- **Breadcrumb on a deep link**: if the user opens a stock sub-tab URL directly (no in-app navigation history), the breadcrumb trail is still fully populated from the current location, not from history.
- **Change history for a brand-new stock**: a stock added but not yet analyzed shows only its "added" entry; a stock analyzed once shows "added" plus its initial verdict, with no "old→new" transition.
- **Reason unavailable for an old change**: change entries recorded before the deterministic conviction rules existed (back-fill) may carry a generic reason; the trail must still render them without error.

## Requirements *(mandatory)*

### Functional Requirements

#### Stocks page organization

- **FR-001**: The Stocks board MUST display tickers grouped by signal in the fixed order Bullish, Neutral, Bearish (with any Unrecognized group last), unchanged from today.
- **FR-002**: Within each signal group, tiles MUST be ordered by conviction descending (high → medium → low), and then alphabetically (A→Z, case-insensitive) by ticker symbol among tiles of the same conviction level. A tile with no/unknown conviction sorts after all rated tiles in its group.
- **FR-003**: The board MUST deliver each signal group already in its final (conviction descending, ticker ascending) order and page through it in that order, so that "Load more" only ever appends tiles that sort at or after the last already-shown tile and no already-visible tile changes position. Sorting a partially-loaded page into a different order than subsequent pages (causing visible tiles to reflow on "Load more") does NOT satisfy this.
- **FR-004**: The conviction-then-ticker ordering MUST be preserved when any combination of the existing filters (ticker, signal, sector, industry, sentiment, conviction) is applied.

#### Conviction rework

- **FR-005**: The system MUST compute a stock's conviction rating deterministically from defined inputs, not as a free-form model judgment. The rating levels remain high / medium / low (see Assumptions on keeping the 3-level scale).
- **FR-006**: A stock MUST be rated **high** conviction only when ALL of the following hold at once:
  - each of the three stock-specific entry strategies (`the_strat`, `accumulation`, `gap_analysis`) resolves to a bullish / buy call for the stock; a strategy that produces no directional call (insufficient data, or a non-directional verdict such as "watch" / "hold" / "neutral") counts as **not** a buy,
  - the stock's daily z-score is in the bottom quartile of its recent history, AND its weekly z-score is in the bottom quartile of its recent history,
  - the stock's revenue trend is favorable: revenue is growing year over year (most recent reported quarter versus the same quarter a year earlier) AND the most recent reported quarter is not a decline versus the immediately prior quarter (no quarter-over-quarter sequential decline).
- **FR-006a**: The system MUST define, for each of the three entry strategies, an explicit and documented mapping from that strategy's output to one of {buy, not-buy, no-call}, so the "all three say buy" test in FR-006 is deterministic and testable. `no-call` and `not-buy` both fail the test.
- **FR-006b**: `market_flow` (market-wide breadth timing) and `position_management` (trailing-stop guidance) MUST NOT gate the conviction rating. An unfavorable `market_flow` timing read for the stock MUST be surfaced as a caveat in the rationale (FR-010), not as a downgrade.
- **FR-007**: If any single high-conviction condition in FR-006 is not met, the stock MUST NOT be rated high; it is rated medium or low by the graded rules in FR-008.
- **FR-008**: The system MUST define medium and low ratings so that the three levels are meaningfully distributed (e.g. medium = at least two of the three entry strategies call buy and at least one z-score timeframe is bottom-quartile and revenue is not in sequential decline; low = everything else). Exact medium/low thresholds are a planning detail but MUST be documented and testable.
- **FR-009**: A stock with insufficient data to evaluate any FR-006 condition (too little price history for quartiles, no strategy signal, no revenue history) MUST NOT be rated high, and the rating output MUST record which input was missing.
- **FR-010**: The conviction rating MUST carry a plain-language rationale listing which conditions passed and which failed, including an explicit note when a revenue decline or a non-oversold z-score blocked a higher rating.
- **FR-011**: "Bottom quartile" MUST be evaluated against the stock's own recent z-score distribution for that timeframe (see Assumptions), inclusive of the 25th-percentile boundary value.
- **FR-012**: The reworked conviction MUST be the value shown by the conviction meter on the Stocks board, by the conviction filter, and by the rating on the stock detail page — all three MUST agree for a given stock at a given time.
- **FR-013**: Applying the reworked rules across the existing analyzed universe MUST reduce the share of stocks rated high compared to current behavior (the "everything is a 3" problem is resolved).
- **FR-014**: The conviction rating MUST update whenever a stock is re-analyzed and whenever its underlying strategy signals or z-score inputs are refreshed.

#### Recently added / updated activity area

- **FR-015**: The Stocks page MUST show an activity area listing recent "added" and "updated" events for tracked stocks.
- **FR-016**: Each entry MUST render as a short human-readable line naming the ticker, the event type (added / updated), and the event date, e.g. "AVB was added on 9/4".
- **FR-017**: The ticker in each entry MUST be a link to that stock's detail page.
- **FR-018**: An "added" event MUST be recorded when a ticker is first registered on the board; an "updated" event MUST be recorded on every completed re-analysis of a ticker, whether or not the verdict changed.
- **FR-018a**: An "updated" entry whose re-analysis changed the stock's signal or conviction MUST be visually flagged (distinct from an unchanged re-analysis) and SHOULD note what changed (e.g. "conviction medium→high"); an unchanged re-analysis appears without the flag.
- **FR-019**: The activity area MUST show events newest-first and MUST expose no more than the 100 most recent events in total.
- **FR-020**: The activity area MUST be paged, showing one page of entries at a time with controls to move forward to older entries and back to newer ones within the 100-event window.
- **FR-021**: When there are no events to show, the activity area MUST display a brief empty-state message rather than an empty container.
- **FR-021a**: On first release, the event log MUST be back-filled with one "added" event per already-tracked ticker, dated from that ticker's recorded first-seen date. "Updated" events are NOT back-filled — they accrue from the first re-analysis after release. Back-filled "added" events beyond the most-recent-100 window are subject to the same cap as any other event.
- **FR-022**: The activity area MUST not cause the Stocks page to grow beyond its bounded, viewport-relative layout — it lives within the page's own scrollable region, consistent with the current page design.

#### Breadcrumbs — navigational trail (User Story 4)

- **FR-023**: The application MUST display a navigational breadcrumb trail near the top of its main content pages showing the path from a top-level page down to the current view.
- **FR-024**: Every breadcrumb segment except the current (last) one MUST be a link that navigates to that level.
- **FR-025**: On a top-level page the trail MUST show only that page's name, with no trailing separator or empty segment.
- **FR-026**: The breadcrumb trail MUST be derived from the current location so that directly opening a deep link produces the full, correct trail without relying on in-app navigation history.

#### Breadcrumbs — per-stock change history (User Story 5)

- **FR-027**: The stock detail page MUST show a per-stock change-history trail: an ordered list of dated entries covering the stock's "added" event and each subsequent change to its signal or conviction rating.
- **FR-028**: Each change entry MUST state the date, what changed (signal old→new and/or conviction old→new), and a short human-readable reason. For conviction changes, the reason MUST be derived from the deterministic conviction rules (which condition changed), not a free-form restatement.
- **FR-029**: A re-analysis that leaves both signal and conviction unchanged MUST NOT add a change entry.
- **FR-030**: The change-history trail MUST be capped at a bounded number of most-recent entries (see Assumptions), newest changes clearly distinguishable from older ones, and MUST render a brief empty/near-empty state for a stock that has only just been added.

### Key Entities *(include if data involved)*

- **Ticker registry entry**: represents a tracked stock on the board. Key attributes: symbol, the date it was first added to the board, the date of its most recent activity, current status (active / removed). Basis for "added" activity events (including the first-release back-fill) and the ticker component of the board sort key.
- **Analysis result**: the latest synthesized verdict for a ticker. Key attributes: signal (bullish / neutral / bearish), conviction rating (high / medium / low) with its rationale, timestamp of the analysis. Basis for board grouping and "updated" activity events.
- **Strategy call set**: the buy / not-buy / no-call resolution for each of the three stock-specific entry strategies (`the_strat`, `accumulation`, `gap_analysis`) for a ticker, used to gate the conviction rating. Key attributes: one resolved call per strategy, as-of time. The `market_flow` timing read and `position_management` guidance are also carried for the rationale but are not part of the gate.
- **Z-score reading**: the stock's daily and weekly z-score values and each timeframe's recent distribution, used to decide bottom-quartile membership.
- **Revenue trend**: the stock's year-over-year revenue change (latest quarter vs. same quarter a year prior) and its quarter-over-quarter sequential change (latest quarter vs. prior quarter), used as the revenue condition.
- **Activity event**: one "added" or "updated" occurrence. Key attributes: ticker, event type, event date/time, and for "updated" a changed flag plus (when changed) the signal/conviction transition. Rendered as the activity-area lines; capped at the most recent 100.
- **Verdict change entry**: one dated change to a stock's signal and/or conviction. Key attributes: ticker, date, signal old→new, conviction old→new, reason. Rendered as the per-stock change-history trail; capped per stock.
- **Breadcrumb trail**: the ordered list of ancestor views for the current page, each with a label and a navigation target.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The highest-conviction tickers in each signal group are visible without scrolling on first load, and a user looking for a known ticker can locate it by its conviction-then-alphabetical position in under 5 seconds without visually scanning the whole group.
- **SC-002**: After the conviction rework, no more than 25% of analyzed stocks carry a "high" rating at any given time (down from the current near-universal high), and all three rating levels are represented whenever the board has 20+ stocks.
- **SC-003**: For any stock rated "high", 100% of the FR-006 conditions can be shown to be satisfied from its displayed rationale; for any stock rated below "high", the rationale names at least one failing condition.
- **SC-004**: Flipping any single FR-006 input for a stock that was "high" causes its rating to drop within one analysis/refresh cycle, verifiable in an automated test.
- **SC-005**: A newly added ticker appears as the top entry in the activity area with a correct date and working link within one page refresh of being added.
- **SC-006**: The activity area never displays more than 100 events, and paging reaches the oldest of those 100 without error.
- **SC-007**: From any stock sub-tab, a user can return to the Stocks board in a single click on the breadcrumb trail, and the trail is correct even when the page was opened by direct link.
- **SC-008**: The Stocks page with the activity area present still requires no horizontal or whole-window scrolling at standard desktop widths.
- **SC-009**: For any stock whose conviction changed between two analyses, the change-history trail shows a dated entry naming the transition and a reason, and no entry is added when a re-analysis changes neither signal nor conviction — both verifiable in an automated test.

## Assumptions

- **Conviction scale**: the existing three-level scale (high / medium / low, shown as 3 / 2 / 1 dots) is kept; the user's "ending up a 3" refers to that meter. The rework changes how a level is earned, not the number of levels. If the user wants a wider numeric scale (e.g. 1–5), that is a separate change.
- **Deterministic computation**: per the project's "deterministic core, LLM at the edges" principle, the conviction level is produced by rule logic over the strategy signals, z-scores, and revenue figures; any model involvement is limited to phrasing the rationale, not choosing the level.
- **Strategy set for "all strategies say buy"**: the three stock-specific entry strategies `the_strat`, `accumulation`, `gap_analysis` gate the **high** rating — every one must resolve to a bullish / buy call, and a non-directional or "insufficient data" verdict counts as not-a-buy. A per-skill output→call mapping must be defined and tested (FR-006a). `market_flow` (market-wide breadth) and `position_management` are computed and shown as rationale/caveat context but do not gate the rating (FR-006b) — this refines the earlier "all five rule-engine skills" answer so that a normal or overbought market does not make **high** unreachable.
- **Board ordering** (resolved, Q6): within a signal group the order is conviction descending, then ticker A→Z. This replaces the originally-specified pure-alphabetical order. The board is delivered and paged in this final order so "Load more" pages down into lower-conviction names without reflowing visible tiles.
- **Z-score source**: the daily and weekly z-score metrics already computed for the stock's price are reused; no new indicator is introduced.
- **Quartile reference window**: "bottom quartile" is measured against the trailing window of that stock's own z-score values for the timeframe (a rolling recent history), not a cross-sectional quartile across all tracked stocks. The exact window length is a planning detail with a sensible default (e.g. ~1 year of readings) and must be documented.
- **Revenue cadence** (resolved, Q2 → A): "YOY" = most recent reported quarter's revenue versus the same quarter a year earlier (favorable when growing). "Losing ground" = most recent reported quarter's revenue lower than the immediately prior quarter's (quarter-over-quarter sequential decline); this blocks a "high" rating even when YoY is positive. No monthly-revenue data source is assumed.
- **"Updated" event trigger** (resolved, Q5): an "updated" activity event is recorded on every completed re-analysis of a ticker's synthesized analysis document (not on background data cache refreshes). Entries whose re-analysis moved the signal or conviction are visually flagged and annotated with the transition; unchanged re-analyses appear unflagged. The activity feed is therefore a superset of the per-stock change history (US5).
- **Activity persistence** (resolved, Q7): activity events live in a lightweight append-only event log. On first release it is back-filled with one "added" event per existing ticker from its registry first-seen date; "updated" events are not back-filled and start accruing from the first post-release re-analysis. Only the most recent 100 events need to be retained/served.
- **Breadcrumbs** (resolved, Q3 → A and B): the feature delivers both a navigational breadcrumb trail (User Story 4 / FR-023–FR-026) and a per-stock verdict change-history trail on the stock detail page (User Story 5 / FR-027–FR-030). The navigational trail covers the app's main pages plus the stock detail page and its tabs in v1.
- **Change-history cap**: the per-stock change-history trail retains and shows a bounded number of the most recent change entries per stock (planning detail, sensible default e.g. the last 20); older entries are truncated, not paged, in v1.
- **Scope boundaries**: no change to which stocks are analyzed, to the analysis pipeline's other outputs, to filters themselves (only their result ordering), or to the stock detail page beyond showing the reworked conviction rationale, the change-history trail, and the breadcrumb trail. Mobile layout tuning is out of scope for v1.
- **Local-first, single user**: no notifications outside the app (no email/push); the "notifications area" is an in-page list only.

## Clarifications

### Session 2026-09-04

- Q1: Which strategies must all agree for "high" conviction? → All rule-engine skills, later refined (see Q4 below) to the **three stock-specific entry strategies** `the_strat`, `accumulation`, `gap_analysis`.
- Q2: What does "losing MOM" mean for revenue? → **A** — most recent reported quarter's revenue lower than the immediately prior quarter's (quarter-over-quarter sequential decline).
- Q3: What are "breadcrumbs"? → **A and B** — deliver both a navigational breadcrumb trail and a per-stock "what changed and when" history trail.
- Q4: Do `market_flow` (market-wide breadth) and `position_management` gate the **high** rating? → No. Only `the_strat`, `accumulation`, `gap_analysis` gate it; `market_flow` timing appears as a rationale caveat, `position_management` as context — so a normal/overbought market does not make **high** unreachable.
- Q5: Should the activity feed log "updated" on every re-analysis or only on real changes? → Every completed re-analysis, with entries that changed the signal/conviction visually flagged and annotated with the transition.
- Q6: How are tiles ordered within a signal group, given "Load more" paging? → Conviction descending, then ticker A→Z (replacing pure alphabetical). The board is delivered and paged in this final order so "Load more" appends lower-conviction names without reordering visible tiles.
- Q7: Does the activity feed start empty or get back-filled? → Back-fill one "added" event per existing ticker from its first-seen date; "updated" events accrue only from the first re-analysis after release.
