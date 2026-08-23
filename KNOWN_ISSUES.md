# Known Issues & Limitations

> Running log of bugs, design limitations, and upstream constraints — updated as
> they're found or fixed (started 2026-08-02, during Phase 6). Fixed items move
> to the bottom rather than being deleted, so we don't rediscover them.

## Open bugs

- **`analyst-estimates` FMP call is malformed — every earnings snapshot loses
  forward estimates.** `get_earnings_data` requests
  `analyst-estimates?symbol=X&limit=4`, which the stable API rejects with 400
  Bad Request (observed for BSX in the 2026-08-15 agent-runner log; the stable
  endpoint requires a `period` parameter). The section fail-softs to `[]`, so
  every ticker silently gets no forward estimates. Separate from the
  018 cache bug; fix belongs in `tools/financials.py`.
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
- **One backend FMP call site still bypasses the daily budget counter, so
  `fmp_usage` under-reports real spend.** `backend/earnings_data.py::_fmp_get`
  calls FMP with a bare `requests.get` and never increments `fmp_usage` — only
  the agent-runner (`tools/fmp_client.py`), `backend/fmp.py` (from
  `specs/022-market-news-feed`), and `backend/price_store.py` (from
  `specs/024-delta-data-pulls`) do. The agent-runner's soft cap therefore
  throttles against a number slightly lower than the true daily total. Found
  2026-08-16 while planning 022. **Partly fixed 2026-08-17**: 024 rewrote
  `backend/routers/price.py` onto the price store, which routes through
  `backend.fmp.fmp_get`, so that call site now counts. Remaining fix is
  mechanical: route `earnings_data.py::_fmp_get` through `backend.fmp.fmp_get`
  too.
- **No Ollama call anywhere passes a timeout — a hung model hangs the caller
  indefinitely.** `agent-runner/llm.py` builds its client as
  `ollama.Client(host=settings.ollama_url)` (`llm.py:24-31`) and calls
  `client.chat(...)` (`llm.py:34-60`, `:63-76`) without a `timeout` kwarg on
  either the constructor or the call. Grep confirms no `timeout=` on any Ollama
  path in the repo. Retries (`retries: int = 1`, so 2 attempts) only cover
  `JSONDecodeError`, not a stall — if Ollama accepts the connection and then
  never finishes generating, the worker blocks forever with no ceiling. Today
  that costs a stuck crew run; it becomes user-visible the moment an HTTP
  request handler calls the model (e.g. the chat endpoint in
  `specs/031-semantic-layer-chat/`), where it would hang the request until the
  client gives up. Found 2026-08-23 while planning 031. Fix is mechanical: pass
  an explicit timeout and treat expiry as the existing `LLMError` degrade path.

- **bmo/amc inference trusts yfinance timestamps.** `_reaction_move` classifies
  a report as before-open when the timestamp's hour is < 12. When Yahoo doesn't
  know the time it can report midnight → misclassified as bmo → the move is
  measured one session early for what was actually an after-close print.

## Design limitations (accepted for now)

- **MongoDB runs with no authentication, and port 27017 is published to the
  host.** `docker-compose.yml` starts mongo as `mongod --quiet` with no `--auth`
  and no `MONGO_INITDB_ROOT_USERNAME`/`PASSWORD`, mounts no init script, and
  publishes `27017:27017`. Every connection string in the repo is
  credential-free (`.env`, `.env.example`, both compose service blocks, both
  `settings.py` defaults). Anything that can reach the host's port 27017 has
  full read/write on `stockai` — including drop. Consistent with the
  local-first, single-user posture in constitution Principle V, and fine while
  the stack is bound to a trusted machine; it stops being fine the moment the
  host is on an untrusted network or the port is forwarded. The practical
  consequence today is that **no database-level read-only role exists**, so any
  feature promising "read-only" enforcement (e.g. the chat query guard in
  `specs/031-semantic-layer-chat/`) can only enforce it in application code —
  a validator bug is a hole, with nothing behind it. Found 2026-08-23 while
  planning 031. Fixing it is a breaking change: enable `--auth`, add an init
  script creating an app user plus a `read`-role user, then update `MONGO_URI`
  in `.env`, both compose blocks, and both `settings.py` defaults.

- **A stock split silently invalidates stored price history until someone
  presses Full Refresh.** As of `specs/024-delta-data-pulls`, delta retrieval is
  the default: a pull appends only the trading days it is missing. But a split
  or dividend re-adjustment rewrites the values of bars *already stored*, and
  nothing detects it — there is no drift detection and no scheduled
  re-baselining anywhere in the system (FR-010). The stored series stays quietly
  wrong, charts included, until the operator triggers a full refresh on that
  stock. Nothing warns them, so there is no signal to act on other than noticing
  a chart looks off. This was a deliberate choice made during
  `/speckit-clarify` on 2026-08-17 (Q4/Q5) to keep the default path as fast and
  as simple as possible, taken with the failure mode understood. The remedy is
  `Full Refresh ⟳` on the stock page. Revisit if it bites in practice — the
  design is written so detect-and-flag can be added additively.
- **Insider transactions changed order as a side effect of 024.**
  `get_insider_activity` now returns transactions newest-first. Merging a stored
  set with a fetched one destroys provider order, so an explicit sort became
  necessary; descending was chosen because `agents/insider_analyst.py` truncates
  to `transactions[:15]` and publishes them as `recent_transactions`, which
  arbitrary provider order never actually guaranteed. Behavior change, not a
  bug, but noted here since it alters what the LLM sees.

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
- **Fetch layer duplicated between containers — and now genuinely diverged, not
  just duplicated.** `backend/earnings_data.py` mirrors
  `agent-runner/tools/earnings_calendar.py` by hand (they share only Mongo),
  like the `db.py` collection constants. As of specs/025-earnings-page-filters
  the two sides no longer even agree on a provider: the backend calendar now
  sources from FMP `stable/earnings-calendar` (actuals + surprise, no
  bmo/amc), while the agent-runner's scanner stays on Finnhub (forward-only,
  no actuals) because the scan's only frontend caller was removed and
  widening the change into the scanner was out of scope. The two write
  distinctly-shaped `earnings_cache` docs on purpose —
  `{"type": "calendar_range", "from", "to"}` (backend) vs.
  `{"type": "calendar", "days": N}` (agent-runner) — specifically so this
  divergence can't silently corrupt either side's cache (constitution
  Principle VI). If the scanner is ever revived, deciding whether it should
  move onto the same FMP source is an open question, not a foregone one — it
  would also need to pick up the actuals/surprise fields that FMP has and
  Finnhub-with-agent-runner does not.
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
- **The earnings scan lifecycle is dormant — reachable by API, not by UI.**
  specs/025-earnings-page-filters removed the earnings page's manual "Scan
  Earnings" button (and `ScanControls`/`EarningsCalendarTable`/
  `EarningsCandidateCard`) in favor of an auto-loading filtered calendar.
  `POST /earnings/scan`, `GET /earnings/scan/{scan_id}`,
  `earnings_scan_worker.py`, and `agents/earnings_scanner.py` were deliberately
  left in place (025's spec scoped their deletion out) but now have no
  frontend caller. `POST /earnings/analyze` and `GET /earnings/history/{ticker}`
  remain reachable — the first from the new table's Queue button, the second
  with no current UI consumer either. Reviving the scan UI, or removing the
  dead endpoints outright, is an open decision for a future feature.

## Upstream / API-tier constraints (facts, not fixable in code)

- **FMP** (free tier, post-2025 key — stable API only, legacy `/api/v3` 403s):
  - fundamentals 402 for symbols outside the free universe (AAPL 200 vs
    APP 402, same key/day) → `get_financials` degrades that endpoint to `[]`
    and the crew leans on yfinance,
  - quarterly statements 402 beyond ~4 periods → `limit=4`,
  - ~~`earnings-calendar` truncates to ~15 rows → calendar comes from Finnhub~~
    **no longer reproduces as of 2026-08-17.** Live probes on the current key
    returned 789 rows for `from=2026-08-15&to=2026-08-19` and 2,347 rows for
    `from=2026-08-10&to=2026-08-15`, with `epsActual`/`revenueActual` populated
    on 2,146 / 1,697 of the past-window rows. Either the key's entitlement
    changed or FMP lifted the limit. `specs/025-earnings-page-filters` moves the
    backend calendar onto this endpoint because Finnhub's calendar carries no
    actuals; note it returns **no bmo/amc time field**, so that column is lost
    in the move (research.md D4). The agent-runner's scanner stays on Finnhub,
    so the two services now use different providers for the same concept and
    write different cache-key shapes into `earnings_cache` (research.md D7),
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

- ~~App shell causes horizontal page scroll at phone widths (~390px)~~ — fixed
  via `specs/030-stock-page-overflow/`. The fixed-width Watchlist `<aside>`
  (`w-56 shrink-0` in `Sidebar.tsx`) never collapsed, and `<main>` (a `flex-1`
  child in `App.tsx`) had no `min-w-0`, so it couldn't shrink below its
  content's intrinsic width, forcing the whole page wider than the viewport.
  Fixed by adding `min-w-0` to `<main>` and hiding the sidebar below the `md`
  breakpoint (`hidden md:block`) instead of letting it force width at phone
  sizes; `StockDetail.tsx`'s ticker/company-name header also got `min-w-0` +
  `truncate` so an unusually long company name can't do the same thing
  locally. `FilterBar`'s inputs (the other contributor named when this was
  originally found) already carry explicit `w-*` widths and `flex-wrap` by
  the time of this fix, so no separate change was needed there.
- ~~Analysis documents never got a `sector`, so `/sectors` stayed empty
  forever~~ — fixed via `specs/029-company-profile-tweaks`. `GET /sectors`
  (`backend/routers/sectors.py`) rolled up analyses whose `sector` field was
  set, and `GET /analysis/sector/{sector}` filtered on it too, but
  `Crew.run()` never set `sector` on the document it returned — none of its
  sub-agents fetched a company's sector, and nothing carried the registry's
  copy into the analyses collection. Net effect: the Sectors page's empty
  state was permanent. Fixed by adding a company-profile fetch
  (`agent-runner/tools/company_profile.py`, sourced from FMP's `profile`
  endpoint) to every pull, which denormalizes `sector`/`industry` onto
  `ticker_index` — the single sector source `GET /sectors`, the feed's
  sector filter, and `macro_worker.py`'s per-sector sweep all read now.
  `analyses.sector` itself is no longer read anywhere; a tracked stock
  without a profile yet groups into a reserved "Unclassified" bucket rather
  than vanishing, until its next pull fetches one.
- ~~Empty financials from a temporary FMP condition are cached as settled for
  90 days~~ — fixed 2026-08-15. A fetch where every statement type 402s ("not
  covered on this plan") wrote an all-empty `financials_cache` doc that then
  short-circuited every later analysis run — confirmed live with BSX (402 on
  all 7 endpoints 2026-08-09; FMP had the data again by 2026-08-15 but the app
  kept serving the empty cache) and reproduced identically for ticker J (all
  7 endpoints empty since 2026-08-04). Fixed via
  `specs/018-fix-financials-cache-gap/`: each statement key now carries a
  per-key `outcomes` marker (`confirmed` vs `unavailable`); only `unavailable`
  keys are re-fetched on a warm cache hit, promoting to `confirmed` once FMP
  returns 200, while confirmed keys (even genuinely empty ones) stay settled
  for the full 90-day window.
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
