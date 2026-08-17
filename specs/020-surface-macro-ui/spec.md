# Feature Specification: Decouple Macro Analysis From Ticker Research and Surface It in the UI

**Feature Branch**: `020-surface-macro-ui`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "I just want a feature created for the fact that the macro isn't reaching the UI. See if you can think of a good way to display that. Maybe Rename the feed page and put the macro data above the stock data but below the NYMO data"

## Problem

Every per-ticker analysis run produces a macro read — inflation trend and its sector impact, Fed rate direction and valuation impact, growth/recession backdrop from the yield curve, consumer backdrop, sector-rotation signal, and an overall macro signal with confidence. That read is computed, cached per sector, and stored with every analysis, but **no screen in the app ever displays it** — the user is paying for analysis work whose output is invisible.

On top of that, macro data is data about the economy — it isn't specific to the stock a given ticker analysis is researching. Running it as part of every single ticker's analysis pipeline conflates two different concerns: stock-specific research and economy-wide context. The fix is not just to display the existing per-ticker macro reads, but to separate macro analysis from ticker research entirely and give it its own home in the UI.

## Clarifications

### Session 2026-08-15

- Q: What should the renamed home page be called in the navigation and browser title? → A: (superseded — see below) Market
- Q: Where should the per-ticker macro read appear? → A: Not on the stock detail page — add a dedicated "Macro" page to the main navigation (alongside Feed/Market, Institutional Flow, Sectors, Earnings).
- Q: Should macro analysis stay coupled to each ticker's analysis pipeline (feeding the final verdict), or be fully decoupled? → A: Fully decouple — ticker analysis stops calling the macro analyst entirely; macro becomes its own independent process that refreshes per sector on its own schedule, feeding only the Macro page; the final verdict (portfolio strategist) no longer factors in macro at all.
- Q: What happens to the pinned NYMO/market-breadth divergence cards once a Macro nav page exists? → A: Move them to the Macro page — they're market-wide, non-stock-specific context, same as the macro reads.
- Q: Home page rename — "Market" or "Stocks"? → A: Stocks (supersedes the earlier "Market" answer) — distinguishes it from the new Macro page (stock-specific vs. economy-wide context).
- Q: Does the renamed Stocks page keep a compact macro-regime banner? → A: No — with breadth cards moved off it and macro fully decoupled, the Stocks page goes back to being just the filter bar and stock tile board. All market-wide context (breadth cards and macro reads) lives on the Macro page.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ticker research no longer runs macro/economic analysis (Priority: P1)

As the user, when I trigger analysis for a stock, I don't want that run to also perform economy-wide macro analysis — macro data describes the economy, not the stock, so it doesn't belong in a single ticker's research pipeline. Each ticker's analysis should be faster and cheaper, and its stored record should only contain stock-specific findings.

**Why this priority**: This is the first thing the user asked for in this session — stock research is currently doing economy-wide work it shouldn't. Fixing it changes what gets computed and stored, which every other part of this feature builds on.

**Independent Test**: Trigger analysis for any ticker and confirm no macro/economic analysis is performed as part of that run, and the resulting stored analysis has no per-ticker macro entry.

**Acceptance Scenarios**:

1. **Given** a ticker analysis is triggered, **When** the analysis pipeline runs, **Then** no macro/economic analysis is performed as part of that specific ticker's run.
2. **Given** a completed ticker analysis, **When** its stored sub-reports are inspected, **Then** there is no macro entry among them — macro data is no longer duplicated into every ticker's stored record.
3. **Given** the final buy/sell verdict (signal, conviction, summary) is produced for a ticker, **When** it synthesizes the other analyst findings, **Then** macro is not among the inputs it weighs.
4. **Given** macro reads are still needed for the Macro page (User Story 2), **When** they get computed, **Then** that computation happens independently of any specific ticker's analysis request.

---

### User Story 2 - Dedicated Macro page showing economy-wide context (Priority: P1)

As the user, I want a "Macro" entry in the main navigation (alongside Stocks, Institutional Flow, Sectors, and Earnings) that opens a page showing the full economy-wide picture — the market-breadth (NYMO/NAMO) divergence signals plus each sector's macro read (inflation impact, rate impact, growth/recession backdrop, consumer backdrop, sector-rotation signal, overall signal), so this is the one place in the app for context that isn't about any single stock.

**Why this priority**: Decoupling macro from ticker research (User Story 1) makes the problem worse, not better, unless macro analysis still lands somewhere visible. This page is where all of that economy-wide output — old and newly independent — actually reaches the user, which was the original point of this feature.

**Independent Test**: Click "Macro" in the main navigation and confirm the page shows the market-breadth divergence cards and every analyzed sector's macro read with its sector-specific commentary and freshness.

**Acceptance Scenarios**:

1. **Given** the app is open, **When** the user looks at the main navigation, **Then** a "Macro" entry appears alongside the existing pages, and clicking it opens the Macro page.
2. **Given** at least one sector has a macro read, **When** the user opens the Macro page, **Then** each available sector's read is visible, including: inflation impact on that sector, rate impact on valuation, growth/recession backdrop, consumer backdrop, sector-rotation signal, overall macro signal, and confidence, plus supporting numeric context (latest CPI, Fed funds rate, yield-curve spread) where available.
3. **Given** each sector read has its own refresh timestamp, **When** the user views the Macro page, **Then** every sector's read shows when it was produced, so a stale read is visibly stale.
4. **Given** market-breadth (NYMO/NAMO) divergence events exist, **When** the user opens the Macro page, **Then** the pinned breadth-divergence cards (formerly shown on the stock page) appear there instead.
5. **Given** no macro read exists yet (fresh install, or before the independent macro process has run for the first time), **When** the user opens the Macro page, **Then** it shows a clear empty state — no error.

---

### User Story 3 - Stocks page simplified to stock-specific content only (Priority: P2)

As the user, now that Macro has its own place in the navigation, I want the renamed "Stocks" page (formerly "Feed") to only show stock-specific content — the filter bar and the analysis tile board — without the market-breadth cards that used to sit above it, so each page has one clear job: Stocks for individual stocks, Macro for the economy.

**Why this priority**: This is a cleanup that depends on User Story 2 existing (the breadth cards need somewhere to go before they can leave the Stocks page); it's lower-stakes than Stories 1 and 2 since it changes presentation, not what's computed.

**Independent Test**: Open the app's landing page and confirm the navigation and browser tab title read "Stocks", the URL is unchanged, and the page shows only the filter bar and stock tile board — no breadth cards, no macro content.

**Acceptance Scenarios**:

1. **Given** the app is open, **When** the user looks at the navigation link and the browser tab title for the landing page, **Then** both read "Stocks" (previously "Feed"), and the page's URL continues to work as before.
2. **Given** the Stocks page renders, **When** the user views it, **Then** it shows only the filter bar and the stock analysis tile board — no market-breadth/NYMO cards and no macro banner.
3. **Given** the user narrows the page with a filter (ticker, sector, signal, or conviction), **When** the filtered view renders, **Then** filtering behavior is unchanged from today (this story removes breadth cards, not filtering).

---

### Edge Cases

- **Independent macro refresh cadence**: with no ticker analysis left to trigger it, macro reads need their own recurring refresh (at most weekly per sector). If that process hasn't run yet for a sector, the Macro page simply omits that sector rather than erroring.
- **Stale sector read**: the Macro page still shows the most recent read it has even if it's past its normal refresh window; the freshness indicator makes the age visible rather than hiding it.
- **Historical analyses with an embedded macro sub-report**: analyses stored before this change may still contain a per-ticker macro entry. The UI simply stops reading it; no migration or cleanup of old records is required for this feature to work.
- **No sector-breadth data yet** (fresh install, independent macro process hasn't run): Macro page shows a clear empty state; no error.
- **Partially formed macro read** (missing optional numeric context like the latest CPI value): the Macro page renders the fields it has and omits the missing ones without breaking layout.
- **Filters active on the Stocks page**: since the Stocks page no longer shows any market-wide cards, there is nothing macro-related left to hide when a filter is applied.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Ticker analysis MUST NOT perform macro/economic analysis as part of processing a single ticker.
- **FR-002**: A ticker analysis's stored sub-reports MUST NOT include a macro entry.
- **FR-003**: The final verdict (signal, conviction, summary) produced for a ticker MUST be synthesized without macro as an input.
- **FR-004**: Macro analysis MUST run as its own independent process, decoupled from any specific ticker's analysis request, computing/refreshing a read per sector on a recurring schedule (at most weekly per sector).
- **FR-005**: The main navigation MUST gain a "Macro" entry that opens a dedicated Macro page.
- **FR-006**: The Macro page MUST display every available sector's macro read — including sector-specific commentary (inflation impact, rate impact on valuation, growth backdrop, consumer backdrop, sector-rotation signal, overall signal, confidence) and each read's freshness — with a clear empty state when none exist yet.
- **FR-007**: The Macro page MUST also display the market-breadth (NYMO/NAMO) divergence cards, moved from the Stocks page.
- **FR-008**: The home page (formerly "Feed") MUST be renamed to "Stocks" in the navigation and browser title; its existing URL MUST continue to work.
- **FR-009**: The Stocks page MUST no longer display market-breadth/NYMO cards or any macro content — it shows only the filter bar and the stock analysis tile board.
- **FR-010**: Existing Stocks-page behavior unrelated to breadth/macro (filtering, infinite scroll, empty states) MUST be unchanged.

### Key Entities

- **Macro read**: a per-sector economic report — inflation impact (trend + sector commentary), rate impact (direction + valuation commentary), growth backdrop (recession signal + commentary), consumer backdrop, sector-rotation signal, overall macro signal, confidence, and supporting numeric context (latest CPI, Fed funds rate, yield-curve spread/inversion). Produced by an independent process decoupled from ticker analysis, refreshed at most weekly per sector.
- **Market-breadth divergence event**: an existing market-wide signal (NYMO/NAMO based) previously pinned above the stock tile board; relocates to the Macro page under this feature with no change to how it's computed.
- **Stocks page (renamed from "Feed")**: the app's landing page — filter bar and the per-stock analysis tile board only.
- **Macro page (new)**: top-level page reached from the main navigation — presents market-breadth divergence cards and every available sector's macro read with per-read freshness.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view the current macro regime (inflation direction, Fed direction, recession signal) and market-breadth divergence signals within a single click from anywhere in the app, via the Macro nav entry.
- **SC-002**: 100% of the macro read's fields are viewable on the Macro page — today that number is 0%.
- **SC-003**: Per-ticker analysis runs make zero macro/economic analysis calls and store zero macro data — measured by comparing each ticker analysis's sub-report keys and LLM call counts before vs. after this change.
- **SC-004**: Macro reads continue to refresh automatically (at most weekly per sector) with zero ticker analyses required to trigger that refresh.
- **SC-005**: All pre-existing Stocks-page behavior not related to breadth-card placement (filtering, infinite scroll, empty states) is unchanged — pre-existing tests for that behavior still pass.

## Assumptions

- **Which sector reads appear on the Macro page**: all sectors that have a stored read, each labeled and independently timestamped — there is no single "the" macro read once decoupled, since sector reads refresh independently of one another.
- **Independent refresh mechanism**: macro analysis needs its own recurring trigger now that no ticker analysis performs it — analogous in spirit to the existing independent market-breadth refresh, but the exact mechanism is an implementation choice for the plan phase.
- **No backfill required**: historical analyses that already have a per-ticker macro entry are left as-is; this feature only changes behavior going forward and does not migrate or purge old records.
- **Portfolio strategist behavior change is intentional**: removing macro as a synthesis input is an accepted tradeoff of decoupling, not an oversight — the final verdict was previously described as weighing macro as "a mild concern unless fundamentals are deteriorating"; that consideration is dropped, not relocated elsewhere in the verdict logic.
- **Single-user, local-first scope** (per constitution): no personalization, no per-user preferences for the Macro or Stocks page; no live/polling updates — both refresh on navigation like the rest of the app.
