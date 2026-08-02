# Known Issues & Limitations

> Running log of bugs, design limitations, and upstream constraints — updated as
> they're found or fixed (started 2026-08-02, during Phase 6). Fixed items move
> to the bottom rather than being deleted, so we don't rediscover them.

## Open bugs

- **Stale earnings scans are never recovered.** `work_queue` jobs stuck in
  `running` get reset to `pending` on agent-runner startup
  (`queue_worker.recover_stale_jobs`), but `earnings_scans` docs have no such
  sweep — if the agent-runner dies mid-scan, the doc stays `running` forever
  and the frontend polls it indefinitely (no client-side timeout either).
  Workaround: manually flip the doc's status in Mongo. Fix belongs in
  `earnings_scan_worker.py` + a poll cap in `useEarningsScan`.
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
