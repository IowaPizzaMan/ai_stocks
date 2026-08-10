# Known Issues & Limitations

> Running log of bugs, design limitations, and upstream constraints — updated as
> they're found or fixed (started 2026-08-02, during Phase 6). Fixed items move
> to the bottom rather than being deleted, so we don't rediscover them.

## Open bugs

- **LLM JSON parsing failures fall back to templated theses.** When Ollama returns
  malformed JSON, the system retries once (2 attempts total), then defaults to a
  templated thesis line instead of a generated one. Observed in production
  (2026-08-02/08-03 logs). Affects thesis quality for top candidates but
  doesn't block the scan. Fix belongs in the LLM retry/timeout logic or prompt
  validation.
- **Stale earnings scans are never recovered.** `work_queue` jobs stuck in
  `running` get reset to `pending` on agent-runner startup
  (`queue_worker.recover_stale_jobs`), but `earnings_scans` docs have no such
  sweep — if the agent-runner dies mid-scan, the doc stays `running` forever
  and the frontend polls it indefinitely (no client-side timeout either).
  Workaround: manually flip the doc's status in Mongo. Fix belongs in
  `earnings_scan_worker.py` + a poll cap in `useEarningsScan`.
- **1M price chart looks wrong — weekly-change and monthly-change values appear
  swapped.** Reported by Neal while using the app (2026-08-03); not yet
  root-caused in code. `PriceChart.tsx`'s `1M` timeframe renders daily candles
  over a 30/21-day display window (`displayWindow.ts`), so the bug is more
  likely in wherever weekly/monthly % change stats are computed/labeled for
  display than in the candle data itself — needs a repro in the running app
  to pin down which component reads the wrong field.
- **bmo/amc inference trusts yfinance timestamps.** `_reaction_move` classifies
  a report as before-open when the timestamp's hour is < 12. When Yahoo doesn't
  know the time it can report midnight → misclassified as bmo → the move is
  measured one session early for what was actually an after-close print.

## Design limitations (accepted for now)

- **Scan enrichment caps at the top 40 by market cap** (`MAX_CANDIDATES`).
  Peak weeks screen 900+ companies, so mid-caps below the cut — often the
  biggest post-earnings movers — never get scored. Narrow the window (1–2
  days) during peak weeks to get deeper coverage.
- **Scan wall time is ~2–3 min, not the spec's 30–45 s.** The Finnhub client
  paces to 1.05 s/call (free tier: 60/min) and each candidate costs 2 insider
  calls. The frontend copy says "takes a couple of minutes"; the spec number
  assumed endpoints we don't have.
- **`eps_revision` silently defaults to `"flat"` (10/20 pts)** when yfinance
  revisions are unavailable or errored — a data gap scores the same as a
  genuine mixed read. Same shape of issue for missing history: 0 quarters →
  0 move/beat points, indistinguishable from a genuinely flat name.
- **Only the top 10 candidates get LLM-written theses**; ranks 11–40 get a
  templated line (also the fallback whenever Ollama errors).
- **Insider lookback is 90 days** (`tools/insider.py::LOOKBACK_DAYS`), not the
  60 days the scanner spec describes — the scan reuses the crew's tool as-is.
- **The UI market-cap dropdown filters client-side only.** The backend screen
  is fixed at $500M (`MIN_MARKET_CAP`); choosing ≥$1B just hides rows after
  scoring — it doesn't rescan or free up enrichment slots for larger names.
- **Nasdaq screener API is unofficial.** The whole pre-screen (cap/name/sector)
  rides on `api.nasdaq.com/api/screener/stocks` with a browser UA. If it breaks
  or blocks, scans fail with "Nasdaq screener returned no usable rows" (there's
  no fallback source wired). Same class of risk as the Wikipedia/slickcharts
  breadth scrape.
- **Fetch layer duplicated between containers.** `backend/earnings_data.py`
  mirrors `agent-runner/tools/earnings_calendar.py` by hand (they share only
  Mongo), like the `db.py` collection constants. Divergence risk on every edit.
- **NYMO/NAMO zone thresholds (±60) are uncalibrated** against StockCharts —
  computed locally per the breadth spec, never validated.
- **Superinvestor/Dataroma requires Playwright**, which is Docker-only; local
  venv runs degrade to `available: False`.
- **Dataroma flow events carry scan time as `filed_at`.** The moves.php text
  extraction (`tools/superinvestor.py`) doesn't capture per-move dates, so the
  feed shows when we saw the move, not when the fund made it. Dedup uses a
  7-day per-ticker window with a fuzzy (normalized containment) fund-name
  match, ignoring action — the LLM re-extraction words fund names and actions
  differently run to run (live: a re-scan slipped 9 of 61 events past exact
  matching before this) — so a fund genuinely making two moves on the same
  ticker within a week is collapsed into one event, and sufficiently
  different name variants can still slip through as dupes.
- **Dataroma extraction coverage is partial per scan.** `tools/superinvestor.py`
  truncates page text to 8,000 chars and the LLM extracts an incomplete,
  varying subset of the moves each run (live: three scans of the same page
  yielded 61, 9, then 5 distinct events). Repeated scans converge on full
  coverage thanks to dedup, but a single daily scan misses moves. Fix belongs
  in the extraction (chunk the page / raise the char cap), not the worker.
- **Dataroma "buy"/"sell" actions are ambiguous** — moves.php uses Buy/Sell
  for both opens/adds and trims/exits; the scanner maps buy→add and sell→trim
  unless the extraction explicitly says new_position/exit, so some position
  opens will show as "Add".
- **13F flow events describe the *current* position, not the trade.**
  yfinance holder rows carry position size (`Shares`/`Value`) plus a QoQ
  `pctChange`; the traded delta and % of the fund's portfolio aren't available
  (`pct_of_portfolio` is always null). Also `Date Reported` is the quarter
  end, so the 13F side scans a fixed 100-day lookback (deduped) rather than
  the since-last-scan window — new filings appear in one daily batch whenever
  yfinance's holder tables refresh, dated to the quarter end.
- **Divergence swing detection is crude.** `tools/breadth.py::detect_divergence`
  splits a fixed 10-session window in half and takes each half's min/max as
  the swing anchors — they aren't true pivots, and a divergence that develops
  over more than ~10 sessions is invisible. The anchors it reports (and the
  chart draws) are therefore "extreme of each half", not necessarily the
  swing a chartist would pick.
- **The market-flow feed card's thumbnail shows *current* breadth, not the
  event's snapshot.** `MarketFlowCard` passes live `/market/breadth` data to
  the chart, so an event from a week ago renders today's series and today's
  divergence state. The card's headline/body/NYMO reading are the real
  snapshot; only the chart is live. Events age out of the feed after 14 days,
  which bounds the mismatch.
- **`nymo`/`namo` mean two different shapes.** In the agent-runner's
  `get_market_breadth` payload they're objects (`history`/`current`/`zone`/
  `trend`) feeding the LLM agents; in `GET /market/breadth` they're flat
  `[{date, value}]` arrays for charting. Same key names, same domain, two
  schemas — easy to confuse when editing either side.
- **Flow notability is heuristic keyword scoring** — passive/high-conviction
  fund lists are short hardcoded substrings in
  `agents/institutional_flow_scanner.py`; an unlisted index vehicle scores
  like an active manager.
## Unbuilt / unfinished features

- **Admin page was never scaffolded into a route.** Spec exists
  (`Admin.md`), no `frontend/src/pages/Admin.tsx` and no route in `App.tsx`.
- *(nothing currently outstanding beyond the Admin page)*

## Upstream / API-tier constraints (facts, not fixable in code)

- **FMP** (free tier, post-2025 key — stable API only, legacy `/api/v3` 403s):
  - fundamentals 402 for symbols outside the free universe (AAPL 200 vs
    APP 402, same key/day) → `get_financials` degrades that endpoint to `[]`
    and the crew leans on yfinance,
  - quarterly statements 402 beyond ~4 periods → `limit=4`,
  - `earnings-calendar` truncates to ~15 rows → calendar comes from Finnhub,
  - `company-screener` and constituent endpoints 402 → Nasdaq screener /
    Wikipedia / slickcharts scrapes,
  - insider + all 13F endpoints 402/403 → Finnhub insider + yfinance holders,
  - 250 calls/day (tracked in `fmp_usage`; non-essential endpoints skipped
    near the ceiling).
- **Finnhub** (free tier): candles 403 premium (moves come from yfinance),
  transcripts 403 premium (sentiment reads news + EPS surprises; transcript
  path dormant), 60 calls/min (client paces 1.05 s + one 429 retry).
- **yfinance**: unofficial and per-ticker flaky — every consumer degrades
  sections to empty on failure; `stock/earnings` on Finnhub reports fiscal
  period ends, so report dates must come from yfinance `get_earnings_dates`.
- **$NYMO/$NAMO aren't fetchable anywhere free** — computed locally from
  scraped constituent lists.
- **pandas-ta is gone from PyPI** — indicators are hand-rolled in
  `tools/price.py::compute_indicators`.

## Fixed

- ~~`GET /stocks/{ticker}/price` 500s whenever a bar has a NaN OHLC value~~ —
  fixed 2026-08-09. Found via `logs/backend/backend.log.2026-08-09`: repeated
  crashes on `GET /stocks/INTC/price`
  (`ValueError: Out of range float values are not JSON compliant: nan`).
  `price.py`'s bar-building guarded `volume` against NaN but not
  `open`/`high`/`low`/`close`, so a NaN from yfinance reached
  `json.dumps(..., allow_nan=False)` (Starlette's default) and crashed before
  the cache write, so every retry re-fetched and re-crashed. Bars with a NaN
  in any OHLC field are now dropped before serializing.
- ~~TFC "all participation groups aligned" only covered Daily/Weekly/Monthly~~
  — fixed 2026-08-09, per user request: `get_price_history()` now also
  resamples Quarterly and Yearly frames from the monthly fetch (no separate
  yfinance calls; 60-min is still out of scope — no intraday feed). Full TFC
  alignment (`the_strat.py::_tfc`/`run`, `strat_result.tfc.status`) is
  computed over **Weekly/Monthly/Quarterly/Yearly only** — Daily is
  deliberately excluded from the alignment check itself (also per user
  request: it's the noisiest group and shouldn't be able to single-handedly
  flip "all groups agree" to a conflict). Daily isn't dropped, though — it's
  still classified and checked for a **notable candle** (hammer/shooting
  star/outside bar/kicking/reversal — anything beyond a plain inside-bar
  equilibrium setup), surfaced as `strat_result.daily_notable_candle` and
  folded into the `tfc_narrative` LLM prompt as a separate callout,
  independent of the alignment status. `TFCChartGrid.tsx` still shows a 1D
  visual panel (a zoom window, not an alignment group) that plays no part in
  the banner status, while Quarterly/Yearly (no panel of their own) can flip
  it to "In Conflict" — see `TFCChartGrid.md` → "Note on Strat Alignment" if
  that mismatch is confusing in practice.
- ~~SPY/NYMO divergence was described in prose but never drawn~~ — built
  2026-08-09 (spec: `BreadthDivergenceChart.md`). `detect_divergence` now
  returns the swing anchors, SPY closes are cached on the nyse `breadth_cache`
  rows, `breadth_divergences` tracks open/resolved transitions with SPY
  follow-through, `breadth_worker.py` guarantees a daily pass, and
  `GET /market/breadth` + `/market/flow-events` serve it. The two-pane chart
  (price over oscillator, opposite-sloping dashed trend lines), ±60 zone
  shading, ▲/▼ resolution markers and the pinned market-flow feed card all
  shipped with it. Verified against live data — it caught the same bearish
  divergence the Market Timing text was describing.
- ~~Sectors page/router unbuilt (fell through the cracks between phases)~~ —
  built 2026-08-03: `GET /sectors` rollup + `/sectors/{sector}` alias in the
  backend, and the full Sectors page (signal-mix summary chart, sector cards,
  conviction-weighted heatmap + sorted list, "View in Feed" cross-links).
- ~~Institutional flow scans registered AND enqueued every event ticker~~
  (spec'd auto-ingest — the first live scan queued 26 crew runs at agent-runner
  startup) — removed 2026-08-02 at the user's request, same deviation as the
  earnings calendar below: scans are feed-only and each flow card has a Queue
  button (`POST /queue/{ticker}`). Cleanup deleted the 20 still-pending jobs
  and the 18 auto-registered, never-analyzed tickers from `ticker_index`.
- ~~`GET /earnings/calendar` registered AND enqueued every screened ticker~~
  (spec'd auto-ingest — 600–900 crew jobs from one call during earnings
  season) — removed 2026-08-02 at the user's request: the endpoint is now
  read-only and the EarningsScan page shows the calendar with a per-row
  Queue button (`POST /earnings/analyze`, one ticker at a time).
- ~~FMP 402 on a restricted symbol sank the whole crew run~~ — fixed in Phase
  6.5 (`get_financials` catches 402/403 per endpoint, returns `[]`, run
  proceeds on yfinance data).
- ~~`parallel_prefetch` flag on work_queue jobs was ignored~~ — queue worker
  passes it through to `crew.run` since Phase 6.2.
