# Research: FMP Paid-Tier Migration & Admin Data Operations

**Feature**: `017-fmp-migration-admin` · **Date**: 2026-08-15

Phase 0 output. Each decision resolves an unknown from the Technical Context or spec assumption. Web-sourced facts below were checked 2026-08-15 against FMP's public pricing/docs pages and third-party reviews; anything tier-gated is treated as *unverified until probed* (D1).

---

## D1 — Plan-tier entitlements: resolve empirically with a probe, not by assumption

**Decision**: Build a small **entitlement probe** into the new `fmp_client.py`: a function (runnable as a script and as the first admin job, `fmp_entitlement_probe`) that issues one minimal request per endpoint family against the live key and records `entitled | payment_required (402/403) | error` plus a sample-response fingerprint into a `fmp_entitlements` collection and a human-readable section of [fmp-gap-review.md](fmp-gap-review.md). All migration fallbacks (D2) and gap-review adoptions (D8) key off probe results, not plan-name assumptions.

**Rationale**: FMP gates dataset families by tier and the docs don't map families→tiers precisely. Public info (2026-08): **Starter ≈ $22/mo, 300 calls/min, ~5 years history, 20GB/30-day bandwidth, US coverage, fundamentals/prices/profiles/news**; ownership datasets (13F, insider trades, ETF/fund holdings, congressional trading) and transcripts are documented as higher-tier (Premium ~$79, Ultimate ~$149–199). The repo's own `tools/institutional.py` comment ("402/403 on this key (paid tier)") shows FMP already refused an ownership endpoint on this account once. The user said only "paid tier" — probing is cheaper and more reliable than asking them to decode FMP's plan matrix, and it self-heals if they upgrade later.

**Alternatives considered**: (a) Assume Starter and hard-code its entitlements — breaks silently if the user actually bought Premium, or if FMP reshuffles plans. (b) Ask the user which plan — they may not know the endpoint implications; the probe answers the *real* question (what does this key return?) directly.

**Consequences**: Endpoint families that probe as `payment_required` are auto-marked **defer (tier-gated)** in the gap review; migration call-sites with a tier-gated primary get the documented fallback from [contracts/fmp-migration-map.md](contracts/fmp-migration-map.md).

**Update (2026-08-15, user-verified)**: The user checked their subscription directly and settled the big families: **entitled** — insider trading, senate/house trading, ETF & fund holdings, market news, company info, economics route; **not entitled** — 13F, transcripts (both now out of scope by user decision, D11). The probe job is retained but demoted to a verification/regression tool for the still-ambiguous families (batch quotes, intraday resolutions, analyst grades) and for detecting future plan changes.

---

## D2 — Migration mapping: 8 yfinance call-site groups → FMP stable API

**Decision**: Migrate per call site against FMP's **stable** base (`https://financialmodelingprep.com/stable/` — already the base in `tools/financials.py`; the legacy `v3/v4` paths in `specs/DATA_SOURCES.md` are outdated and get rewritten under FR-007). The authoritative per-call-site table (endpoint, params, response-shape notes, fallback when tier-gated) is [contracts/fmp-migration-map.md](contracts/fmp-migration-map.md). Summary:

| Call site | Today (yfinance) | Target (FMP stable) |
|---|---|---|
| `agent-runner/tools/price.py` | `Ticker.history(period, interval)` | `historical-price-eod/full` (daily) + `historical-chart/{interval}` (intraday) |
| `agent-runner/tools/breadth.py` | batched `yf.download` universe closes + SPY | batch quote (comma-separated symbols) if entitled, else throttled per-symbol EOD delta (D4) |
| `agent-runner/data_fetcher.py` §1 price | `yf.download` max/delta | `historical-price-eod/full` delta-append (D3) |
| `agent-runner/data_fetcher.py` §5 earnings dates | `Ticker.get_earnings_dates` | `earnings` (per-symbol) / `earnings-calendar` (windowed) |
| `agent-runner/data_fetcher.py` §6 + `tools/institutional.py` | yfinance holder tables | FMP ownership endpoints if probe says entitled; else keep current stored data + documented drop of live refresh (FR-003 disposition) |
| `agent-runner/tools/earnings_calendar.py` | `get_earnings_dates` + `history` | `earnings-calendar` + `historical-price-eod/full` |
| `agent-runner/tools/financials.py` earnings block | yfinance estimates/recs | FMP analyst estimates/grades family (probe-gated; Finnhub stays fallback for anything not entitled) |
| `agent-runner/crew.py` existence check | yfinance lookup | `quote` (cheap, 1 call) — empty/404 ⇒ delisted-candidate, same semantics |
| `backend/routers/price.py` chart bars | `Ticker.history` per resolution | same EOD/intraday endpoints, served through the cache layer instead of direct fetch |

**Rationale**: Every mapping stays inside the one provider being paid for; intraday entitlement (which resolutions Starter includes) is probe-verified before the router migration locks resolutions in.

**Alternatives considered**: Keeping yfinance as silent fallback — rejected; the spec mandates full removal (FR-002), and a half-dead dependency is how silent breakage hides.

---

## D3 — Historical price continuity: preserve Mongo history, delta-append from FMP, reconcile adjustment convention

**Correction (found during implementation, 2026-08-15)**: `agent-runner/tools/price.py` — the actual live price path `crew.py` uses — has never persisted price bars to Mongo; it fetches fresh from the provider on every call, no cache layer. The `price_history` Mongo collection with a `(ticker, date)` unique index described below was written only by `agent-runner/data_fetcher.py`, which turned out to be dead code (zero live imports, confirmed and deleted — see tasks.md T029) — likely an earlier persisted-cache design that `tools/price.py` superseded without the Mongo layer ever being wired to a live caller. `backend/routers/price.py`'s separate `price_cache` collection is a real cache, but 1-hour TTL, not a growing archive — no deep-history-loss risk there either. **Net effect**: there is no live deep price history sitting in Mongo to reconcile against. The decision below (delta-append, drift-check, provenance tag) is retained as the design *if/when* a persistent price cache is added, but is **not implemented** as part of this migration — doing so would be new caching infrastructure beyond "swap the provider," which constitution Principle V says not to add ahead of demonstrated need. The migration therefore keeps `tools/price.py`'s existing fetch-fresh-each-call behavior, only swapping the source from yfinance to FMP.

**Decision**: Existing `price_history` documents (sourced from yfinance, `auto_adjust=True` = split+dividend adjusted) are **kept as-is**. FMP fetches use the dividend-and-split-adjusted EOD variant to match that convention. On each ticker's *first* FMP delta fetch, compare the overlap window (last ~5 stored trading days vs FMP's values); if relative drift in adjusted close exceeds 0.5%, re-backfill the ticker across FMP's full available window (≤ plan depth) and log the correction; deeper-than-FMP history stays untouched. Record `source: "fmp"` on new documents (D9 provenance).

**Rationale**: Starter's ~5-year depth is *shallower* than the 20+ years already cached from Yahoo — refetching would destroy data (violates FR-006). Adjusted-close conventions differ subtly between providers mainly around recent dividends/splits; a bounded overlap check catches material divergence without a full audit. 0.5% is above float/rounding noise but below any real adjustment event.

**Alternatives considered**: (a) Full re-backfill from FMP — loses deep history on Starter. (b) No reconciliation — risks a visible seam in charts and skewed indicators exactly at the migration date.

---

## D4 — Breadth universe closes: batch quotes when entitled, throttled per-symbol delta otherwise

**Decision**: `breadth.py` first tries FMP's batch quote form (multiple comma-separated symbols per call) for the daily close sweep. If the probe shows batch endpoints tier-gated, fall back to per-symbol `historical-price-eod` **delta** fetches through the shared throttle (D5): steady-state is 1 missing day per symbol, ~600 calls, ≤5 min at a 200/min effective ceiling. First-run backfill uses the same path (one call per symbol returns the full window, so call count is identical — only payload size grows).

**Rationale**: This was the scariest call-volume consumer under the free tier; at 300 calls/min it's routine. Cache-first (constitution IV) means the expensive shape only happens once. SPY series migrates identically.

**Alternatives considered**: Ultimate-tier bulk EOD files — not assumable; index ETF proxies instead of true universes — changes the breadth math, violates SC-003 (no regression in computed signals).

---

## D5 — Budget guard redesign: per-minute throttle + configurable soft daily cap, fail-soft

**Decision**: Replace the 250/day counter warning in `financials.py` with a guard inside the new shared `fmp_client.py`: (1) a **token-bucket per-minute throttle**, default `fmp_calls_per_minute=250` (headroom under Starter's 300); (2) an optional **soft daily cap** `fmp_daily_soft_cap` (default 0 = disabled; set 225 to survive a downgrade to free tier via env alone); (3) unchanged fail-soft semantics — over-budget ⇒ serve stale cache, log a warning, never raise into an analysis run; (4) a daily call/byte counter logged for bandwidth awareness (20GB/30-day Starter limit). All FMP callers in agent-runner route through this client; `backend/routers/price.py` goes through the cache layer so the backend needs no separate guard.

**Rationale**: FR-005 requires paid-tier limits, config-only downgrade, and fail-soft. Centralizing in one client fixes today's scattering (each tool half-implements budget logic) without adding infrastructure.

**Alternatives considered**: Keeping per-tool counters — inconsistent and already drifting; an external rate-limit service — grossly violates Principle V.

---

## D6 — Admin jobs ride `work_queue` with a `job_type` discriminator

**Decision**: Extend `work_queue` documents with `job_type` (absent/`"ticker_analysis"` = today's behavior; new values per the final registry in [contracts/admin-jobs-api.md](contracts/admin-jobs-api.md): `"breadth_refresh"`, `"earnings_calendar_scan"`, `"fmp_entitlement_probe"`, `"sector_performance_pull"`, `"market_movers_pull"`, `"economics_pull"`, `"congress_trades_pull"`, `"insider_feed_pull"`, `"fund_holdings_pull"`, `"market_news_pull"`). `queue_worker.claim_and_run_next` dispatches on `job_type` via a handler table; admin jobs have no `ticker`. Duplicate-run guard reuses the existing pattern: refuse enqueue when a `{job_type, status ∈ pending|running}` document exists. Failure recording reuses the existing `error` field (FR-012); stale-running recovery applies unchanged.

**Rationale**: Constitution V — all triggering flows through `work_queue`, and a second queue is explicitly listed as infrastructure-not-yet-needed. The existing lifecycle (pending→running→done/failed, stale recovery, error capture) is exactly what admin jobs need; only dispatch changes.

**Alternatives considered**: (a) Separate `admin_jobs` collection+loop — duplicate queue machinery, constitutional violation. (b) Direct synchronous execution from the backend — blocks HTTP requests for minutes-long scrapes and splits execution across two services (breaks VI: agent-runner owns collection work).

**Note**: The existing daily timer loops (`institutional_scan_hour_utc`, `breadth_refresh_hour_utc`) remain; the admin job for breadth simply enqueues the same underlying refresh on demand. Timer and manual paths converge on one function per job. `superinvestor_pull` was in the draft registry but is dropped — the Dataroma scraper is retired (D11).

---

## D7 — Admin API + frontend page

**Decision**: New backend router `routers/admin.py`: `GET /admin/jobs` (static registry of job definitions merged with last/current run info aggregated from `work_queue`), `POST /admin/jobs/{job_name}/run` (enqueue; 409-style response when already pending/running), `GET /admin/jobs/{job_name}/runs?limit=` (recent run history). Job registry is a small constant list duplicated in both services (name, description, dataset fed, collection written) — contract-pinned. Frontend `Admin.tsx` + `useAdminJobs.ts`: job cards with description, last-run time/outcome, trigger button, disabled+reason when running; status updates on navigation and a manual refresh button only (`refetchInterval: false`).

**Rationale**: Matches FR-008–FR-012 with the thinnest possible surface; run history is derived from `work_queue` documents (add index on `job_type, created_at`) instead of a new bookkeeping collection.

**Alternatives considered**: WebSocket/live progress — constitution V forbids; polling with TanStack `refetchInterval` — constitution frontend rule forbids.

---

## D8 — Gap review: seeded document, finalized against probe output

**Decision**: [fmp-gap-review.md](fmp-gap-review.md) was seeded in Phase 1 with provisional decisions; the user then reviewed their live subscription and **finalized the review (2026-08-15)**. Final adopts: sector performance, market movers, economics route (treasury rates, indicators, releases, market risk premium — scoped per D13), earnings calendar, senate/house trading, market-wide insider feed, **ETF & fund holdings** (replacing Dataroma, D11), **market + per-ticker news** (D12), **company info** (D14), plus the migration families (EOD, intraday, batch quotes probe-gated). Final rejects: crypto (mandated), forex (extrapolated — user may veto), technical indicators (computed locally, Principle III), transcripts and news *from other providers where FMP now owns them* — see D12 for the news canonical-source flip. Final defers: **13F and transcripts (not entitled — user will source outside FMP later)**, ESG, executive comp, M&A, IPO/dividend/split calendars, Commitment of Traders.

**Rationale**: FR-013 wants a complete reviewed inventory with decisions; the user's direct subscription check is stronger evidence than plan-name inference, and the probe (D1) still guards the remaining ambiguous families.

**Alternatives considered**: Doing the review purely in planning — couldn't be honest about entitlements; the user's verification resolved it faster than the probe would have.

---

## D9 — Provenance & freshness metadata: uniform envelope on market-wide collections

**Decision**: Every market-wide collection document set carries `source: "fmp" | "dataroma" | ...` and `collected_at` (UTC); each dataset additionally maintains one summary row in a small `dataset_meta` collection (`dataset`, `last_success_at`, `last_run_status`, `record_count`) written by the collector at the end of a run. Frontend freshness badges and empty states read `dataset_meta` (one cheap query) rather than aggregating raw collections.

**Rationale**: FR-015/FR-018 need freshness display and never-collected detection; a per-dataset meta row is the cheapest queryable shape and doubles as the admin page's "last outcome" source for data-level truth (queue documents give run-level truth).

**Alternatives considered**: Inferring freshness with max(`collected_at`) scans per page load — repeated collection scans for a constant answer; TTL-expiring data — wrong, this data should persist.

---

## D10 — Visualization: one Market Overview page + existing-page extensions

**Decision**: A new `MarketOverview.tsx` page hosts the market-wide visuals: sector performance (ranked bar, day/period toggle), market movers (gainers/losers/actives lists with % change), economic calendar (upcoming-events timeline), congressional trading feed (recent trades table with ticker links) — each section rendering only when its dataset probes entitled+adopted, each with freshness badge and admin-pointing empty state (FR-017/018), each ticker mention linking to `StockDetail` (FR-019). Ticker-scoped adopted datasets (analyst grades etc.) extend the existing `StockDetail` tabs instead. Existing pages (`Sectors.tsx`, `InstitutionalFlow.tsx`) are left in place; if sector-performance overlaps `Sectors.tsx`, the new FMP dataset feeds that existing page rather than duplicating it — resolved at implementation by checking what `Sectors.tsx` currently renders. The `dataviz` skill is loaded before building any chart component.

**Rationale**: FR-017's "reachable without first selecting a ticker" points at one aggregating page; reusing existing pages where they already own a concept avoids two homes for one dataset (FR-016 spirit, applied to UI).

**Alternatives considered**: Scattering new datasets across existing pages only — leaves no "what is the market doing?" single view (US4's core ask); a dashboard-builder framework — Principle V violation.

---

## D11 — Dataroma retired; ETF & fund holdings replace it (user decision, 2026-08-15)

**Decision**: The Dataroma Playwright scraper (`tools/superinvestor.py`) is **retired**: no admin job, no new collection runs. Its stored data (`SUPERINVESTOR_MOVES_CACHE`, `DATAROMA_META`) stays readable wherever currently consumed, marked stale in the UI via the D9 freshness envelope. A new `fund_holdings_pull` admin job collects FMP's ETF & fund holdings into `fund_holdings`. The Playwright dependency becomes removable (it was Dataroma-only per the constitution's stack list) — flagged as a follow-up constitution amendment, not done in this feature.

**Rationale**: User's explicit call: "rather than using data-o-rama I would rather use this." Also removes the most fragile collector in the system (headless scrape + LLM extraction).

**Honest trade-off (flagged to user)**: FMP ETF/fund holdings covers *funds'* portfolios (ETFs, mutual funds) — it is **not** the same signal as Dataroma's superinvestor 13F portfolios (Berkshire, Pershing et al.), and 13F is not entitled on this plan. True superinvestor tracking pauses until 13F is sourced elsewhere (user accepted; future feature).

**Alternatives considered**: Keeping Dataroma alongside fund holdings — two sources for adjacent concepts plus the scrape fragility; user chose replacement.

---

## D12 — News: FMP owns articles; per-ticker on retrieval + market-wide job (user decision)

**Decision**: Adopt FMP news on both axes. (1) **Per-ticker**: fetching recent stock news becomes part of the existing per-ticker retrieval flow (crew data prefetch), cached into `stock_news` with a short TTL-style delta rule (fetch only articles newer than the last stored `published_at` per ticker); shown as a simple list on `StockDetail`. (2) **Market-wide**: `market_news_pull` admin job into `market_news`; the existing `Feed.tsx` page gains a market-news section reading it. The full feed-page redesign is **out of scope** (user: "I will create a feed page redesign later"). Canonical-source note (FR-016): FMP owns news *articles*; Finnhub keeps what it uniquely provides (news-*sentiment* aggregates, MSPR) — no article storage from Finnhub, so no duplicate.

**Rationale**: User asked for exactly this split ("for each stock when I retrieve its data… overall market news on my feed page"). Delta-fetch keeps per-ticker news within cache discipline (constitution IV).

**Alternatives considered**: News as an agent/LLM summarization input — out of scope here; articles are stored and displayed raw, summarization stays a future idea.

---

## D13 — Economics route: adopt all four datasets, FRED stays canonical for its existing series

**Decision**: One `economics_pull` admin job collects the FMP economics family: **economic data releases** (calendar) → `economic_calendar_events` (as already designed), **market risk premium** → `market_risk_premium`, **treasury rates** → `treasury_rates` (full-curve daily snapshot: all maturities per date), **economic indicators** → only series **not already served by FRED** land in a `economic_indicators` collection. FRED remains canonical for the 12 series `tools/macro.py` already fetches (CPIAUCSL, PCEPI, FEDFUNDS, UNRATE, GDP, GDPC1, DGS10, DGS2, T10Y2Y, T10Y3M, VIXCLS, UMCSENT) and the existing macro views don't change. The treasury-rates *snapshot* is treated as a distinct dataset from FRED's per-series history (different shape/purpose: today's full yield curve for Market Overview vs long single-series history for the macro tab) — the coverage map documents this seam explicitly.

**Rationale**: User wants the economics info ("I want to get all that infor"), and FR-016 forbids competing duplicates. FRED is free/unlimited with deep history — retiring it for FMP copies of the same series would spend paid budget to re-buy owned data. The only true overlap (DGS10/DGS2 values appearing inside curve snapshots) is granularity-scoped and documented, not a second store of the same series. **User veto option**: if they'd rather consolidate all macro on FMP and retire FRED, that's a one-decision flip recorded here.

**Alternatives considered**: (a) Wholesale FRED→FMP macro migration — pays for free data, reworks working macro views, no user ask. (b) Rejecting treasury/indicators as duplicates — under-delivers the explicit "get all that" instruction.

---

## D14 — Company info: per-ticker collection joins the retrieval flow

**Decision**: A `company_info` collection stores FMP's company-info/profile route output (name, description, sector, industry, exchange, CEO, employees, website, logo URL, float/shares data as provided), fetched during per-ticker retrieval with a long cache TTL (90-day refresh, matching financials discipline). Spec `010-company-enrichment` overlaps this concept but has no implemented storage today (verified: no profile constants/collections in either service) — implementation reconciles with that spec's intent, and `010`'s spec gets a pointer note rather than a parallel build.

**Rationale**: User asked for the company-info route; profile data was already budgeted in the DATA_SOURCES logo/profile notes. One collection, per-ticker flow, no admin job needed (it's ticker-scoped).

**Alternatives considered**: Market-wide bulk profile pull — bulk endpoints are Ultimate-tier; per-ticker on retrieval matches actual need.
