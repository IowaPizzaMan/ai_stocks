# Research: Stock Page Redesign (021)

All unknowns from Technical Context resolved. Decisions numbered D1–D10.

## D1 — FMP endpoint entitlements (verified live, 2026-08-16)

**Decision**: Use `news/stock`, `insider-trading/statistics`, and `acquisition-of-beneficial-ownership` (all HTTP 200 on the current key). Do NOT call `institutional-ownership/latest` (HTTP 402 — not entitled, matching specs/017's user-verified 13F finding).

**Rationale**: Probed each endpoint once with the live key during planning. Designing against an un-entitled endpoint would burn budget on guaranteed 402s and violate Principle IV's fail-soft posture.

**Alternatives considered**: FMP plan upgrade (user decision, out of scope); SEC EDGAR 13F (documented future option in specs/017/fmp-gap-review.md, deferred).

**Observed response shapes** (drive data-model.md):
- `insider-trading/statistics?symbol=X` → array of `{symbol, cik, year, quarter, acquiredTransactions, disposedTransactions, acquiredDisposedRatio, totalAcquired, totalDisposed, averageAcquired, averageDisposed, totalPurchases, totalSales}` — quarterly, newest first.
- `acquisition-of-beneficial-ownership?symbol=X` → array of `{cik, symbol, filingDate, nameOfReportingPerson, amountBeneficiallyOwned, percentOfClass, typeOfReportingPerson, url, ...}` — 13D/G filings, newest first.
- `news/stock?symbols=X&limit=N` → array of `{symbol, publishedDate, publisher, title, image, site, text, url}` — `text` carries article body text, enabling real keyword scanning, not just headlines.

## D2 — Institutional "net bought/sold" without 13F

**Decision**: Derive the Institutional tab's net-direction verdict and period visuals from (a) beneficial-ownership filings — same filer's `percentOfClass` / `amountBeneficiallyOwned` across successive `filingDate`s → stake increased/decreased, and (b) the existing read-only cached 13F snapshot (`top10_increasing` / `top10_decreasing` via `institutional.recent_activity_direction`). Label both with as-of dates and the existing `stale` flag where applicable.

**Rationale**: These are the only entitled institutional signals. Filer-stake deltas answer "net bought or sold?" for the 5%+ holders that actually move the name; the cached snapshot supplies breadth (how many holders up vs down) even if stale.

**Alternatives considered**: Calling `institutional-ownership/latest` anyway (guaranteed 402 — rejected); dropping institutional visuals entirely (spec FR-013 requires them — rejected).

## D3 — Chart timeframes and the monthly/yearly fix

**Decision**: The four Charts-tab panels become resolution-true: **D** = daily bars (~90 shown), **W** = weekly bars (~78), **M** = monthly bars (~36, one candle per calendar month), **Y** = yearly bars (10–15, one candle per calendar year). Backend `routers/price.py` gains a `yearly` resolution: `("15y", "1y")` → pandas `resample("YE")` over full EOD history, sliced to 15 years. Frontend `displayWindow.ts` maps the panel timeframes to `daily/weekly/monthly/yearly` and sets display counts M=36, Y=15.

**Rationale**: The current "1M" panel renders ~21–30 *daily* bars (a one-month window), which is why the user sees "points that don't represent months." Making resolution match the panel label fixes the semantic bug. Existing `_resample` already handles weekly/monthly; yearly is one more rule. FMP `historical-price-eod/full` returns full listing history, so 10–15 years exists for mature tickers, with `dropna` handling short histories (FR-006).

**Alternatives considered**: Client-side aggregation of daily bars into months/years (duplicates pandas logic in TS, harder to test against the same truth — rejected); changing display windows only (doesn't fix the resolution mismatch — rejected).

## D4 — Candlestick rendering in Recharts

**Decision**: Render candles with a Recharts `ComposedChart` + `Bar` whose `dataKey` is the `[low, high]` range and a **custom `shape` component** that draws the wick (low→high line) and body (open→close rect, emerald up / red down) from the bar's payload. Keep BF zones, reference lines, and tooltips from the existing PriceChart machinery.

**Rationale**: Recharts has no native candlestick, but the custom-shape-on-range-Bar pattern is the established way to get one without adding a dependency; the stack constraint (constitution Technology Stack) rules out lightweight-charts/ApexCharts. All data (OHLC) is already in `OHLCVBar`.

**Alternatives considered**: `lightweight-charts` (TradingView) — better candles but a new dependency + imperative API, constitution violation without amendment (rejected); SVG hand-rolling outside Recharts (loses shared tooltip/axis/zone infrastructure — rejected).

## D5 — Where indicators are computed

**Decision**: Compute MACD (12/26/9), stochastic %K/%D (14, 3), ATR% (14-period Wilder ATR ÷ close × 100), and price z-score (close vs 20-bar rolling mean/σ) **client-side** in `frontend/src/lib/indicators/`, one module per indicator, Vitest-tested against known fixtures. Each indicator runs on the already-fetched bars of each timeframe (daily/weekly/monthly/yearly), so "per-timeframe" falls out naturally with zero extra requests. **MACD is scoped to daily/weekly/monthly only** (clarified 2026-08-16) — its 12/26/9 warm-up needs ~35 periods, i.e. ~35 years on the yearly timeframe, which essentially no ticker has; z-score/stochastic/ATR% render on all four timeframes since their warm-ups (20/14/14 periods) are reachable even yearly.

**Rationale**: This matches the existing display-analytics pattern (`movingAverages.ts`, `RateOfChangeChart`, `broadeningFormations.ts` are all frontend TS with tests). These values feed the UI only — nothing downstream in agents reads them (agents already get pandas-ta indicators via `price_tool.get_technical_indicators`), so Principle III's "deterministic core in Python" isn't implicated; Principle V argues against new backend endpoints.

**Alternatives considered**: Backend indicator endpoint with pandas-ta (new endpoint + cache + serialization for display-only data — rejected as complexity); computing in agent-runner and storing on the analysis (indicators must react to fresh price data even without a pull — rejected).

## D6 — News pipeline shape

**Decision**: New `agent-runner/tools/news.py`: fetch `news/stock?symbols={ticker}&limit=50` via `fmp_client.fmp_get`, filter to the last 30 days, cache raw articles in `stock_news_cache` (per-ticker doc, `fetched_at`, 24h TTL index like other caches). Deterministic functions in the same module: per-article bullish/bearish term tally over `title + text` (extending the keyword lists in `sentiment_analyst.py`), and a date-aggregated timeline with a trailing net-sentiment trend label (`bullish` / `bearish` / `mixed` from the sign of recent net counts). New `agents/news_analyst.py` LLM pass summarizes the **15 newest** articles (1–3 sentences each) and emits a structured stance `{direction, reasoning}` grounded in those summaries. Everything lands in a new `news` sub-report on the analysis document at pull time (clarification: refresh only on Pull).

**Rationale**: `text` bodies (confirmed in D1) make keyword counting meaningful. Counting/aggregation is pure Python → pytest-exhaustive (Principle I/III); the LLM touches only summaries/stance. Riding the analysis document means the frontend needs no new fetch path and the as-of label is the pull timestamp (FR-022a). The 50/15 caps bound both FMP payload and local-LLM time.

**Alternatives considered**: Separate backend `/stocks/{t}/news` endpoint with its own refresh (violates the on-Pull clarification and adds a fetch path — rejected); LLM-detected sentiment per article (non-deterministic, untestable, slow ×50 — rejected; keywords stay deterministic with the LLM only writing prose); a single shared keyword list module imported by both services (constitution explicitly prefers duplicated constants over shared packages — keyword lists are defined in agent-runner only, which is the only place that counts them).

## D7 — Sentiment tab integration

**Decision**: `SentimentTimeline` is one frontend component rendered by both the News tab (above article list) and the Sentiment tab (below the headline gauge). It reads `analysis.sub_reports.news.timeline`. The Sentiment tab's gauge is the existing `overall_sentiment_signal` made visually primary; existing keyword pills / tone evidence / earnings-surprise sections move below it unchanged. `sentiment_analyst` additionally receives the news timeline in its prompt context so its tone read and the chart agree.

**Rationale**: Clarification Q1 chose "both places"; sharing one component and one data source keeps the two renderings consistent by construction (Principle VI in spirit).

**Alternatives considered**: Duplicate chart implementations per tab (drift risk — rejected).

## D8 — Long-form text formatting

**Decision**: New `FormattedProse` component backed by a pure `lib/prose.ts`: split text into sentences, group into ≤2-sentence paragraphs (or bullets when ≥4 sentences), and wrap emphasis spans around price levels (`$123.45`, `123.45`), percentages, tickers, and direction vocabulary (bullish/bearish/support/resistance/etc.) via regex. Applied to Overview verdict, AI Summary narratives, and the narrative bodies in Fundamentals/Insider/Institutional/Sentiment sections. Vitest-tested on representative verdict fixtures (SC-004's "no block > ~3 sentences" is the assertion).

**Rationale**: Deterministic and retrofit-safe — works on all existing stored analyses without schema changes or re-pulls. Asking the LLM to emit markdown would require schema/prompt changes and doesn't fix old documents.

**Alternatives considered**: LLM-generated markdown (rejected above); CSS-only line-height/width tweaks (doesn't create structure — rejected).

## D9 — "What changed since last analysis"

**Decision**: At pull time, `crew.py` reads the previous analysis document for the ticker (before writing the new one) and computes a deterministic `changes_since_last` top-level field: previous/current signal, previous/current conviction, flags added/removed, and previous timestamp. Pure function + pytest. AI Summary renders it when present; absent for first-ever pulls.

**Rationale**: Write-time diffing is deterministic, testable, and requires no new endpoint or frontend history fetch. The analyses collection already stores per-run documents keyed by ticker+timestamp.

**Alternatives considered**: Frontend fetches last-two analyses and diffs (new endpoint/param + client logic for a server-known fact — rejected); LLM-written change narrative (Principle III — rejected).

## D10 — Tab structure, default, and removals

**Decision**: Tab order: **Charts (default) · Overview · Technicals · Fundamentals · Insider · Institutional · News · Sentiment · AI Summary**. Active tab = `location.hash`, falling back to `charts` for empty or unknown hashes (FR-027). The always-rendered TFC grid + Deep Dive block above the tab bar are removed; `TFCChartGrid`/Deep Dive usage is replaced by `ChartsTab` (TFC banner moves into the Charts tab). Overview loses its Position Management section (payload untouched — spec 015 output still computed/stored). AI Summary drops `BreadthDivergenceChart` + NYMO/NAMO line but keeps recommendation caveats; the component is deleted only if nothing else imports it.

**Rationale**: Direct application of clarified FR-001/002/003, FR-011, FR-023, FR-027. Keeping stored payloads intact preserves other consumers (feed cards, spec 015) — UI-only removal.

**Alternatives considered**: Charts rendered above tabs (spec says charts live *in* the tab, FR-003 — rejected); deleting position_management from the pipeline (other specs consume it — rejected).
