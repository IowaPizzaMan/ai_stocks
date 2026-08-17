# Tasks: Stock Page Redesign

**Input**: Design documents from `specs/021-stock-page-redesign/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included — constitution Principle I (Test-First & Comprehensive Coverage) is NON-NEGOTIABLE for this project: pytest for agent-runner tools/agents and backend routers, Vitest + RTL for frontend components/logic.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to spec.md user stories (US1–US8)
- Every task names an exact file path

## Path Conventions (from plan.md)

- Backend: `backend/routers/`, `backend/tests/`
- Agent runner: `agent-runner/tools/`, `agent-runner/agents/`, `agent-runner/tests/`
- Frontend: `frontend/src/components/stock/`, `frontend/src/lib/`, `frontend/src/pages/`

---

## Phase 1: Setup

**Purpose**: Shared contract/cache scaffolding needed before any story's real logic is written.

- [X] T001 Add `STOCK_NEWS_CACHE` and `BENEFICIAL_OWNERSHIP_CACHE` collection name constants + TTL index setup (24h / 7d) in `agent-runner/tools/db.py`, following the existing cache-collection pattern (e.g. `INSTITUTIONAL_CACHE`)
- [X] T002 [P] Extend `frontend/src/api/types.ts` with `NewsReport`, `InsiderQuarterStats`, `BeneficialFiling`, and `ChangesSinceLast` interfaces, and add the new optional fields (`sub_reports.news`, `insider.quarterly_stats`, `institutional.beneficial_filings`, `institutional.beneficial_direction`, top-level `changes_since_last`) per [contracts/analysis-subreports.md](./contracts/analysis-subreports.md) — all new fields optional so pre-021 analyses still type-check

**Checkpoint**: Shared data contract exists; every subsequent story can extend it without touching the same lines twice.

---

## Phase 2: Foundational (Blocking Prerequisites for the Charts Tab)

**Purpose**: Infrastructure shared by US1, US2, and US3 (the Charts tab group, delivered together as the P1 MVP). Not required by US4–US8.

**⚠️ CRITICAL**: US1/US2/US3 implementation cannot start until this phase is complete.

- [X] T003 [P] Add `yearly` resolution to `backend/routers/price.py`: `RESOLUTIONS["yearly"] = ("15y", "1y")`, extend `_fetch_history` to resample with `"YE"` when `interval == "1y"`
- [X] T004 [P] Update `frontend/src/lib/strat/displayWindow.ts`: add `"yearly"` to `TIMEFRAME_RESOLUTION` for the `"1Y"`-equivalent yearly panel, and set `DISPLAY_COUNT` so the monthly panel shows ~36 bars and the yearly panel shows ~15 bars (introduce a distinct yearly `Timeframe` entry per [contracts/price-endpoint.md](./contracts/price-endpoint.md) — do not reuse the existing `"1Y"` daily-resolution entry)
- [X] T005 [P] Create `CandlestickChart` component in `frontend/src/components/stock/CandlestickChart.tsx`: Recharts `ComposedChart` + a range `Bar` (`[low, high]`) with a custom `shape` drawing the high-low wick and open-close body (emerald up / red down), reusing `CHART_DEFAULTS` colors and the existing tooltip/axis conventions from `PriceChart.tsx`
- [X] T006 Remove the always-rendered `TFCChartGrid` block and the "Deep dive" `PriceChart` block from `frontend/src/pages/StockDetail.tsx` (both currently render above the tab bar) — leaves a compile error at the tab-content switch until T012 fills it in, which is expected at this checkpoint

**Checkpoint**: Backend yearly data, corrected display windows, and a working candlestick renderer exist; Deep Dive/always-on charts are gone. Ready for US1.

---

## Phase 3: User Story 1 - Charts Tab as the Default View (Priority: P1) 🎯 MVP

**Goal**: Charts (D/W/M/Y candles + ROC panels) live inside a Charts tab that is the default view; no chart content renders outside it.

**Independent Test**: Open any ticker's detail page — Charts tab is active with no hash, shows four candlestick panels + Price/Volume ROC, and no Deep Dive section exists anywhere.

### Tests for User Story 1

- [X] T007 [P] [US1] Vitest: `StockDetail` defaults to the Charts tab when `location.hash` is empty, and `#overview` still opens Overview, in `frontend/src/pages/StockDetail.test.tsx`
- [X] T008 [P] [US1] Vitest: `ChartsTab` renders four `CandlestickChart` panels (D/W/M/Y) followed by Price ROC and Volume ROC, in `frontend/src/components/stock/ChartsTab.test.tsx`

### Implementation for User Story 1

- [X] T009 [US1] Create `ChartsTab` component in `frontend/src/components/stock/ChartsTab.tsx`: TFC banner (moved from the old `TFCChartGrid`) + four `CandlestickChart` panels (D/W/M/Y, using `useStockPriceHistory`) + `RateOfChangeChart` price/volume panels below them (depends on T003–T006)
- [X] T010 [US1] Add a `"charts"` entry as the first item in the `TABS` array in `frontend/src/pages/StockDetail.tsx`, wire it to render `ChartsTab`, and change `activeTab` fallback from `"overview"` to `"charts"` (depends on T009)

**Checkpoint**: US1 independently functional — Charts tab is default, four panels + ROC render, Deep Dive is gone.

---

## Phase 4: User Story 2 - Correct Monthly and Yearly Chart Aggregation (Priority: P1)

**Goal**: Monthly panel shows ~36 one-candle-per-month points over 3 years; yearly panel shows 10–15 one-candle-per-year points.

**Independent Test**: On AAPL, count monthly candles (~36) and yearly candles (10–15); confirm hover labels identify the correct month/year; a short-history ticker shows partial data without error.

### Tests for User Story 2

- [X] T011 [P] [US2] pytest: yearly resample produces one bar per calendar year with correct OHLCV aggregation (open=first, high=max, low=min, close=last, volume=sum) from a synthetic multi-year daily fixture; 20-year fixture returns ≤15 bars; 2-year fixture returns all bars with no error, in `backend/tests/test_price.py`
- [X] T012 [P] [US2] Vitest: given a long-history fixture, `ChartsTab`'s monthly panel renders ~36 candles and yearly panel renders 10–15 candles; given a 2-year fixture, both panels render all available candles without throwing, in `frontend/src/components/stock/ChartsTab.test.tsx`

### Implementation for User Story 2

- [X] T013 [US2] Verify/adjust the `"monthly"` entry in `RESOLUTIONS` in `backend/routers/price.py` so it slices to 3 years (`("3y", "1mo")`) instead of `"max"`, matching the ~36-candle target (depends on T003)
- [X] T014 [US2] Add resolution-aware hover-tooltip date formatting to `CandlestickChart.tsx` (full month name for monthly, year only for yearly) so FR-004/FR-005's "each candle represents that period" is visible on hover (depends on T005)

**Checkpoint**: Monthly/yearly candle counts and date semantics verified correct — US1+US2 together deliver the full Charts tab MVP.

---

## Phase 5: User Story 3 - Expanded Per-Timeframe Indicators (Priority: P2)

**Goal**: z-score, stochastic, and ATR% render for all four timeframes; MACD renders for daily/weekly/monthly only.

**Independent Test**: Open a ticker's Charts tab; verify all four indicator rows render with correct timeframe scoping and an "insufficient history" state where warm-up isn't met.

### Tests for User Story 3

- [X] T015 [P] [US3] Vitest: MACD (12/26/9 EMA) fixture values incl. null during warm-up (<35 bars), in `frontend/src/lib/indicators/macd.test.ts`
- [X] T016 [P] [US3] Vitest: Stochastic %K(14)/%D(3) fixture values, output clamped to [0,100], in `frontend/src/lib/indicators/stochastic.test.ts`
- [X] T017 [P] [US3] Vitest: ATR% (Wilder ATR14 ÷ close × 100) fixture values incl. null during warm-up (<15 bars), in `frontend/src/lib/indicators/atrPercent.test.ts`
- [X] T018 [P] [US3] Vitest: Z-score ((close−SMA20)/σ20) fixture values incl. null during warm-up (<20 bars), in `frontend/src/lib/indicators/zscore.test.ts`
- [X] T019 [P] [US3] Vitest: `IndicatorPanel` renders 4 timeframe columns for z-score/stochastic/ATR%, exactly 3 (no yearly) for MACD, and an "insufficient history" state when warm-up isn't met, in `frontend/src/components/stock/IndicatorPanel.test.tsx`

### Implementation for User Story 3

- [X] T020 [P] [US3] Implement `frontend/src/lib/indicators/macd.ts`
- [X] T021 [P] [US3] Implement `frontend/src/lib/indicators/stochastic.ts`
- [X] T022 [P] [US3] Implement `frontend/src/lib/indicators/atrPercent.ts`
- [X] T023 [P] [US3] Implement `frontend/src/lib/indicators/zscore.ts`
- [X] T024 [US3] Create `IndicatorPanel` component in `frontend/src/components/stock/IndicatorPanel.tsx`: one indicator row rendered across its applicable timeframes (all 4, or 3 for MACD), hover tooltip with date, "insufficient history" empty state (depends on T020–T023)
- [X] T025 [US3] Add the indicator grid (z-score, stochastic, ATR%, MACD in that stacking order) to `ChartsTab.tsx` below the ROC panels (depends on T009, T024)

**Checkpoint**: All four indicator rows render with correct per-timeframe scoping (FR-007).

---

## Phase 6: User Story 4 - Readable Long-Form Text and Overview Cleanup (Priority: P2)

**Goal**: Long prose renders as structured, scannable content with key terms emphasized; Position Management is removed from Overview.

**Independent Test**: Open a ticker with a 4+ sentence verdict — text is chunked/emphasized, not a single block; no Position Management section on Overview.

### Tests for User Story 4

- [X] T026 [P] [US4] Vitest: `lib/prose.ts` splits sentences, groups into ≤2-sentence paragraphs (or bullets at ≥4 sentences), and wraps price/percentage/direction-term emphasis spans, in `frontend/src/lib/prose.test.ts`
- [X] T027 [P] [US4] Vitest: `FormattedProse` renders the grouped/emphasized structure for a multi-sentence fixture, in `frontend/src/components/stock/FormattedProse.test.tsx`
- [X] T028 [P] [US4] Vitest: `OverviewTab` renders no Position Management section even when `analysis.position_management` is present, in `frontend/src/pages/StockDetail.test.tsx`

### Implementation for User Story 4

- [X] T029 [US4] Implement `frontend/src/lib/prose.ts` (sentence-split, paragraph/bullet grouping, key-term emphasis regex for price levels, percentages, tickers, direction vocabulary)
- [X] T030 [US4] Create `FormattedProse` component in `frontend/src/components/stock/FormattedProse.tsx` (depends on T029)
- [X] T031 [US4] Apply `FormattedProse` to the Overview verdict and delete the Position Management `<Section>` block in `OverviewTab` in `frontend/src/pages/StockDetail.tsx` (depends on T030)
- [X] T032 [US4] Apply `FormattedProse` to the technical/fundamental narrative paragraphs in `AISummaryTab` in `frontend/src/pages/StockDetail.tsx` (depends on T030)
- [X] T033 [P] [US4] Apply `FormattedProse` to narrative text in `TechnicalsTab`, `FundamentalsTab`, `InsiderTab`, `InstitutionalTab`, `SentimentTab` in `frontend/src/components/stock/tabs.tsx` (depends on T030)

**Checkpoint**: Prose is scannable everywhere; Position Management UI is gone but the underlying payload is untouched (SC-004, SC-006).

---

## Phase 7: User Story 5 - News Tab with AI Summaries and Sentiment Timeline (Priority: P2)

**Goal**: A News tab shows AI-summarized recent articles with a bullish/bearish keyword timeline, generated during a pull.

**Independent Test**: Pull a ticker with recent coverage; the News tab shows dated summaries and a timeline whose trend direction is visually obvious.

### Tests for User Story 5

- [X] T034 [P] [US5] pytest: per-article keyword tally (extends `sentiment_analyst`'s bullish/cautious lists), date-aggregated timeline, and trend label (`bullish`/`bearish`/`mixed` from 7-day net sign), including the zero-terms-is-neutral edge case, in `agent-runner/tests/test_news.py`
- [X] T035 [P] [US5] pytest: `tools/news.get_stock_news` fetches via `fmp_client.fmp_get`, caches in `stock_news_cache`, caps at 50 articles / 30 days, and serves stale cache on `FmpBudgetExceededError`, in `agent-runner/tests/test_news.py`
- [X] T036 [P] [US5] pytest: `agents/news_analyst.run` summarizes only the 15 newest articles and returns a `stance` citing at least one headline (structured-output schema validated), in `agent-runner/tests/test_phase5_agents.py`
- [X] T037 [P] [US5] Vitest: `SentimentTimeline` renders bullish/bearish bars per date and surfaces the `trend` visually, in `frontend/src/components/stock/SentimentTimeline.test.tsx`
- [X] T038 [P] [US5] Vitest: `NewsTab` renders the timeline above dated article summaries, and shows the empty state when `articles` is empty, in `frontend/src/components/stock/NewsTab.test.tsx`

### Implementation for User Story 5

- [X] T039 [US5] Create `agent-runner/tools/news.py`: `get_stock_news(ticker, db)` — fetch `news/stock?symbols={ticker}&limit=50` via `fmp_client.fmp_get`, filter to last 30 days, cache in `stock_news_cache` (depends on T001)
- [X] T040 [US5] Add `tally_keywords(article)` and `build_timeline(articles)` (with `trend`) deterministic functions to `agent-runner/tools/news.py` (depends on T039)
- [X] T041 [US5] Create `agent-runner/agents/news_analyst.py`: LLM structured-output call producing `ai_summary` for the 15 newest articles plus `stance: {direction, reasoning}` (depends on T040)
- [X] T042 [US5] Wire `news` prefetch job + `news_analyst.run` into `agent-runner/crew.py`, assembling the `news` sub-report (articles, timeline, trend, stance, news_count, as_of) per [contracts/analysis-subreports.md](./contracts/analysis-subreports.md) (depends on T041)
- [X] T043 [P] [US5] Create `SentimentTimeline` component in `frontend/src/components/stock/SentimentTimeline.tsx` reading `{date, bullish, bearish}[]` + `trend`
- [X] T044 [US5] Create `NewsTab` component in `frontend/src/components/stock/NewsTab.tsx`: `SentimentTimeline` + dated article summary list + empty state (depends on T043)
- [X] T045 [US5] Add a `"news"` entry to `TABS` in `frontend/src/pages/StockDetail.tsx` rendering `NewsTab` from `latest.sub_reports?.news` (depends on T044, T002)

**Checkpoint**: A pull produces the `news` sub-report; the News tab renders it end-to-end (US5 independently testable).

---

## Phase 8: User Story 6 - Sentiment Tab at a Glance (Priority: P3)

**Goal**: Sentiment tab leads with the gauge + shared timeline; existing detail moves below.

**Independent Test**: Open Sentiment tab — gauge and timeline are in the first screenful; tone evidence/keyword pills/earnings-surprise read remain, scrolled below.

### Tests for User Story 6

- [X] T046 [P] [US6] Vitest: `SentimentTab` renders the overall-signal gauge and `SentimentTimeline` before tone evidence/keyword pills/earnings-surprise sections, in `frontend/src/components/stock/tabs.test.tsx`

### Implementation for User Story 6

- [X] T047 [US6] Reorder `SentimentTab` in `frontend/src/components/stock/tabs.tsx`: promote the signal gauge and add `SentimentTimeline` (fed by `sentiment sub_report`'s parent `news.timeline`) to the top; keep tone evidence, keyword pills, and earnings-surprise read below (depends on T043)
- [X] T048 [US6] Pass the news keyword timeline into the `sentiment_analyst` prompt context in `agent-runner/agents/sentiment_analyst.py` and `agent-runner/crew.py` so the tone read and the chart agree (depends on T040)

**Checkpoint**: Sentiment tab conveys the picture at a glance (US6 independently testable, though richer with US5 present).

---

## Phase 9: User Story 7 - Institutional and Insider Flow Visuals (Priority: P3)

**Goal**: Insider tab gets quarterly acquired/disposed + ratio-trend visuals; Institutional tab gets beneficial-ownership filings + a net-direction verdict.

**Independent Test**: On AAPL, Insider tab shows quarterly bars + net-direction verdict; on a ticker with a 5%+ filing, Institutional tab surfaces filer/date/stake.

### Tests for User Story 7

- [X] T049 [P] [US7] pytest: `insider.get_insider_quarterly_stats` shapes `insider-trading/statistics` response into `quarterly_stats` (per [data-model.md](./data-model.md) §4), in `agent-runner/tests/test_phase5_tools.py`
- [X] T050 [P] [US7] pytest: `institutional.get_beneficial_ownership` fetches + caches in `beneficial_ownership_cache`, and `derive_beneficial_direction` computes `accumulating/distributing/mixed/null` from successive same-filer `percentOfClass` values, in `agent-runner/tests/test_phase5_tools.py`
- [X] T051 [P] [US7] Vitest: `InsiderFlowCharts` renders quarterly acquired-vs-disposed bars, ratio trend, and net-direction verdict; empty state when `quarterly_stats` is empty, in `frontend/src/components/stock/InsiderFlowCharts.test.tsx`
- [X] T052 [P] [US7] Vitest: `InstitutionalFlowVisuals` renders beneficial filings (filer/date/stake) and the combined net verdict (beneficial direction falling back to the cached 13F snapshot); empty state when both are absent, in `frontend/src/components/stock/InstitutionalFlowVisuals.test.tsx`

### Implementation for User Story 7

- [X] T053 [P] [US7] Add `get_insider_quarterly_stats(ticker, db)` to `agent-runner/tools/insider.py` using `fmp_client.fmp_get("insider-trading/statistics?symbol=...")`
- [X] T054 [P] [US7] Add `get_beneficial_ownership(ticker, db)` and `derive_beneficial_direction(filings)` to `agent-runner/tools/institutional.py`, caching raw filings in `beneficial_ownership_cache` (depends on T001)
- [X] T055 [US7] Wire `quarterly_stats` into `insider` sub-report and `beneficial_filings`/`beneficial_direction` into `institutional` sub-report via `agent-runner/agents/insider_analyst.py`, `agent-runner/agents/institutional_analyst.py`, and `agent-runner/crew.py` (depends on T053, T054)
- [X] T056 [P] [US7] Create `InsiderFlowCharts` component in `frontend/src/components/stock/InsiderFlowCharts.tsx`
- [X] T057 [P] [US7] Create `InstitutionalFlowVisuals` component in `frontend/src/components/stock/InstitutionalFlowVisuals.tsx`
- [X] T058 [US7] Render `InsiderFlowCharts` inside `InsiderTab` and `InstitutionalFlowVisuals` inside `InstitutionalTab` in `frontend/src/components/stock/tabs.tsx` (depends on T056, T057, T002)

**Checkpoint**: Both tabs show net-direction verdicts and supporting visuals (US7 independently testable).

---

## Phase 10: User Story 8 - AI Summary Refresh (Priority: P3)

**Goal**: AI Summary drops the breadth-divergence chart (keeps caveats), adds a News Stance section, and surfaces what changed since the last analysis.

**Independent Test**: Open AI Summary — no breadth chart, caveats still render, News Stance states a direction with article-grounded reasoning, and a "what changed" note appears on a re-pulled ticker.

### Tests for User Story 8

- [X] T059 [P] [US8] pytest: `changes_since_last` diff (signal/conviction from-to, flags added/removed) computed against a prior stored analysis; returns `None` when no prior analysis exists, in `agent-runner/tests/test_crew.py`
- [X] T060 [P] [US8] Vitest: `AISummaryTab` renders no `BreadthDivergenceChart`, still renders `recommendation.caveats`, renders a News Stance section from `sub_reports.news.stance`, and renders (or omits, when absent) the changes-since-last note, in `frontend/src/pages/StockDetail.test.tsx`

### Implementation for User Story 8

- [X] T061 [US8] Implement the `changes_since_last` diff function in `agent-runner/crew.py`, reading the prior analysis document for the ticker before writing the new one, attaching the result to the returned analysis
- [X] T062 [US8] Remove the `BreadthDivergenceChart` import/render and the NYMO/NAMO line from the Market Timing section in `AISummaryTab` in `frontend/src/pages/StockDetail.tsx`, keeping `recommendation.caveats`
- [X] T063 [US8] Add a News Stance section to `AISummaryTab` rendering `sub_reports.news.stance.direction`/`.reasoning` in `frontend/src/pages/StockDetail.tsx` (depends on T045)
- [X] T064 [US8] Add a "what changed since last analysis" section to `AISummaryTab` rendering `changes_since_last` (hidden when absent) in `frontend/src/pages/StockDetail.tsx` (depends on T061, T002)

**Checkpoint**: All 8 user stories independently functional and testable — full feature complete.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Validation and cleanup that spans multiple stories.

- [X] T065 [P] Run `ruff check backend/` and `ruff check agent-runner/ scripts/`; fix any findings (constitution quality gate)
- [X] T066 [P] Remove `BreadthDivergenceChart.tsx`/`.test.tsx` and `TFCChartGrid.tsx` if no longer imported anywhere after T006/T062 (verify with a repo-wide reference search before deleting)
- [ ] T067 Execute the [quickstart.md](./quickstart.md) manual scenarios 1–6 end-to-end against the running Docker Compose stack — **NOT RUN**: no containers were up during implementation. Partial live verification was done instead, without Docker: the yearly/monthly resample and the news pipeline were both exercised against the real FMP API (see notes below). The remaining gap is a real ticker pull through Ollama and the rendered UI.
- [ ] T068 Execute the quickstart.md budget-guard check (`FMP_DAILY_SOFT_CAP=1`) and confirm fail-soft behavior (FR-026), then restore the cap — **NOT RUN** (needs the stack). Fail-soft paths are covered by unit tests (`test_news.py`, `test_phase5_tools.py`) that raise `FmpBudgetExceededError` and assert stale-cache service.

### Live verification performed during implementation (no Docker required)

- `historical-price-eod/full` returns only ~5 years without a `from` date — the yearly panel came back with **6 candles instead of 10–15**. Fixed by requesting `from` when a resolution needs deep history; re-verified live: AAPL now returns 16 yearly candles (2011–2026). Locked in by two new tests.
- `news/stock` verified live for AAPL: 50 articles, 4 timeline points, trend `bearish`, per-article tone counts populated from real article bodies.
- ~~Note for T067: on mega-caps the 50-article cap collapses the window to ~4 days~~ — **resolved**: FR-021 was changed to keep a full month. `tools/news.py` now pages the whole 30-day window (`from`/`to` + `page`, 250/page, no overlap — verified live). Re-verified: AAPL 629 articles over 30/30 days (~3 calls, ~370 KB); a thinly covered name returns 29 articles over 16/30 days in a single call. AI summaries remain capped at the 15 newest, so LLM cost per pull is unchanged; the News tab reveals 25 articles at a time.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T002's types are referenced by T009+) — BLOCKS US1/US2/US3.
- **US1 (Phase 3)**: Depends on Foundational (Phase 2) completion.
- **US2 (Phase 4)**: Depends on Foundational (Phase 2); independently testable once US1's `ChartsTab` exists (T009) since it fixes the same panels' data.
- **US3 (Phase 5)**: Depends on US1's `ChartsTab` (T009) to have somewhere to mount the indicator grid; indicator math itself (T020–T023) has no dependency and can start anytime after Setup.
- **US4 (Phase 6)**: Depends only on Setup (T002) — independent of the Charts tab group; can run in parallel with US1–US3.
- **US5 (Phase 7)**: Depends only on Setup (T001, T002) — independent of the Charts tab group.
- **US6 (Phase 8)**: Depends on US5's `SentimentTimeline` (T043).
- **US7 (Phase 9)**: Depends only on Setup (T001, T002) — independent of every other story.
- **US8 (Phase 10)**: Depends on US5 (T045, for the news stance) for full richness; the `changes_since_last` diff (T061) and breadth-chart removal (T062) have no such dependency and can proceed earlier.
- **Polish (Phase 11)**: Depends on all desired stories being complete.

### Story Independence Summary

| Story | Hard dependency | Can start in parallel with |
|-------|-----------------|------------------------------|
| US1 | Foundational (Phase 2) | — (first Charts-tab story) |
| US2 | Foundational (Phase 2), US1's ChartsTab shell | US4, US5, US7 |
| US3 | US1's ChartsTab shell | US2, US4, US5, US7 |
| US4 | Setup only | US1, US2, US3, US5, US7 |
| US5 | Setup only | US1, US2, US3, US4, US7 |
| US6 | US5's SentimentTimeline | US7 |
| US7 | Setup only | US1–US5 |
| US8 | US5 (for news stance); diff/removal parts are Setup-only | US6, US7 |

### Parallel Opportunities

- T003, T004, T005 (Foundational) run in parallel — different files.
- Within US3, T020–T023 (four indicator math modules) run in parallel — different files.
- Within US4, T026–T028 (tests) and T033 (tabs.tsx narrative wiring) run in parallel with other stories' work.
- Within US5, T034–T038 (tests) run in parallel; T043 (SentimentTimeline) runs in parallel with T039–T042 (backend news pipeline).
- Within US7, T049–T052 (tests) and T053–T054/T056–T057 (backend vs. frontend implementation) run in parallel in their respective pairs.
- Once Setup is done, US4, US5, and US7 can all proceed in parallel with the Charts-tab group (US1→US2/US3) since none share files.

---

## Parallel Example: User Story 3 (indicator math)

```bash
Task: "Vitest MACD fixture values in frontend/src/lib/indicators/macd.test.ts"
Task: "Vitest Stochastic fixture values in frontend/src/lib/indicators/stochastic.test.ts"
Task: "Vitest ATR% fixture values in frontend/src/lib/indicators/atrPercent.test.ts"
Task: "Vitest Z-score fixture values in frontend/src/lib/indicators/zscore.test.ts"
# then, once tests exist and fail:
Task: "Implement frontend/src/lib/indicators/macd.ts"
Task: "Implement frontend/src/lib/indicators/stochastic.ts"
Task: "Implement frontend/src/lib/indicators/atrPercent.ts"
Task: "Implement frontend/src/lib/indicators/zscore.ts"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational).
2. Complete Phase 3 (US1): Charts tab exists and is default.
3. Complete Phase 4 (US2): monthly/yearly aggregation is correct.
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 against a live ticker.
5. Deploy/demo — this alone fixes the user's most visible complaint (the wrong monthly chart) and reorganizes the page.

### Incremental Delivery

1. Setup + Foundational → Charts-tab infrastructure ready.
2. US1 + US2 → Charts tab MVP → validate → demo.
3. US3 (indicators) → validate → demo.
4. US4, US5, US7 (independent of the Charts group and of each other) → any order, validate each → demo.
5. US6 (needs US5) → validate → demo.
6. US8 (richer with US5) → validate → demo.
7. Polish (Phase 11) → full quickstart pass, lint, cleanup.

### Parallel Team Strategy

With multiple developers, after Setup + Foundational:

- Developer A: US1 → US2 → US3 (Charts tab group, sequential — same files)
- Developer B: US4 (readability) then US7 (insider/institutional visuals) — no file overlap with A
- Developer C: US5 (news pipeline) → US6 (sentiment reorg) → US8 (AI Summary refresh) — each depends on the previous

---

## Notes

- [P] tasks touch different files with no unmet dependencies.
- Constitution Principle I: every implementation task above has a preceding test task in the same phase — write the test, watch it fail, then implement.
- Constitution Principle IV: all new FMP calls (T039, T053, T054) MUST route through `fmp_client.fmp_get`, never raw `requests` — this is what gives fail-soft budget behavior for free.
- Constitution Principle VI: T002's contract update is the single source of truth both Python services and the frontend follow — do not let a sub-report field's name or shape diverge between crew.py's output and types.ts.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently before continuing.
