# StockAI — Data Sources Spec

> Extracted from the main `SPEC.md`. This is the authoritative reference for all external data sources, API endpoints, rate limits, and the coverage map.

---

## yfinance (Yahoo Finance) — RETIRED

**Retired 2026-08-15** (specs/017-fmp-migration-admin) — the paid FMP subscription fully replaced yfinance as the price/breadth/earnings/institutional data source; `yfinance` was removed from both services' dependencies and zero live code paths reference it. See "Switching Primary Price Data Source" (now resolved, see below) and `specs/017-fmp-migration-admin/contracts/fmp-migration-map.md` for the full per-call-site disposition (what moved to FMP, what was dropped, and why).

**What was dropped, not migrated** (FR-003 dispositions): options chains (`option_chain` — never wired into any view), real-time WebSocket streaming (never used; the app's no-polling design doesn't need it), ESG scores (`get_sustainability` — not consumed anywhere; may return via FMP's ESG family if a consuming view is ever built), and live institutional-holder refresh (`get_institutional_holders`/`get_mutualfund_holders`/`get_major_holders` — FMP's 13F/ownership family is **not entitled** on the current plan; `agent-runner/tools/institutional.py` now serves only its pre-migration cached data, read-only, flagged `stale: true`).

---

## Financial Modeling Prep (FMP)

**Access:** API key required · **Paid tier as of 2026-08-15** (upgraded from the 250 calls/day free tier — see specs/017-fmp-migration-admin) · 250 calls/min soft throttle (headroom under the plan's actual limit), configurable daily soft cap (disabled by default; set to 225 to survive a downgrade back to free-tier without code changes) · Cache-first via `agent-runner/tools/fmp_client.py`  
**Base URL:** `https://financialmodelingprep.com/stable/` — the legacy `v3`/`v4` paths below are **outdated** (they 403 on accounts created after FMP's 2025 API migration); kept struck through for historical reference only until each row is re-verified against `stable/`.  
**Primary use:** Price history (primary, replacing yfinance), comprehensive financials, ratios, earnings, insider filings, congressional trading, ETF/fund holdings, news, company info, economics data. **Not entitled on this plan:** 13F institutional ownership, earnings-call transcripts (both excluded per user decision — see `specs/017-fmp-migration-admin/fmp-gap-review.md`).

| Endpoint | Data Returned |
|---|---|
| ~~`v3/income-statement/{symbol}?period=annual\|quarter`~~ → `stable/income-statement?symbol=&period=` | Revenue, COGS, gross profit, R&D, EBIT, EBITDA, net income, EPS (diluted/basic) |
| ~~`v3/balance-sheet-statement/{symbol}?period=annual\|quarter`~~ → `stable/balance-sheet-statement?symbol=&period=` | Cash, receivables, inventory, PP&E, total assets, debt, equity, working capital |
| ~~`v3/cash-flow-statement/{symbol}?period=annual\|quarter`~~ → `stable/cash-flow-statement?symbol=&period=` | Operating/investing/financing cash flows, capex, free cash flow, dividends paid |
| ~~`v3/income-statement-growth/{symbol}`~~ → `stable/income-statement-growth?symbol=` | YoY growth rates for revenue, EBITDA, EPS, net income |
| ~~`v3/ratios/{symbol}?period=`~~ → `stable/ratios?symbol=&period=` | P/E, P/B, P/S, EV/EBITDA, debt/equity, current ratio, ROE, ROA, gross/net margin |
| ~~`v3/key-metrics/{symbol}?period=`~~ → `stable/key-metrics?symbol=&period=` | FCF yield, ROIC, revenue per share, net cash/debt, PE ratio, dividend yield |
| `stable/historical-price-eod/full?symbol=` | **Primary price source (replaces yfinance).** Full daily OHLCV, dividend/split adjusted; agent-runner and backend each fetch this once per ticker and derive weekly/monthly/quarterly/yearly by local resample |
| `stable/historical-chart/{1min\|5min\|15min\|30min\|1hour\|4hour}?symbol=` | Intraday bars — entitlement not yet fully probed (see `fmp-gap-review.md`) |
| `stable/quote?symbol=` (comma-separated for batch) | Real-time/delayed quote — used for the cheap ticker-existence/delisting check (replaces yfinance's `fast_info` check) |
| `stable/earnings?symbol=&limit=` | Per-ticker earnings dates + EPS actual/estimate — feeds both the post-earnings reaction-move calculation and the fundamental analyst's earnings snapshot (replaces yfinance's `get_earnings_dates`) |
| `stable/analyst-estimates?symbol=&limit=` | Forward EPS/revenue estimates (replaces yfinance's `get_earnings_estimate`) |
| `stable/grades?symbol=&limit=` | Analyst upgrade/downgrade actions — used both as the analyst-recs feed and, aggregated, as a proxy for EPS-revision direction (yfinance's `get_eps_revisions` had no clean FMP equivalent; documented substitution) |
| `stable/insider-trading/latest` | Market-wide insider transaction feed — **entitled**, adopted |
| `stable/senate-latest`, `stable/house-latest` | Congressional trading disclosures — **entitled**, adopted |
| `stable/etf/holdings?symbol=` (and fund equivalents) | ETF & mutual-fund holdings — **entitled**, adopted; replaces the retired Dataroma superinvestor scraper (not a like-for-like signal — see fmp-gap-review.md) |
| `stable/profile?symbol=` | Company profile: name, description, sector, industry, exchange, CEO, employees, website URL, logo image URL — **entitled**, adopted for per-ticker company info |
| `stable/sector-performance-snapshot`, `stable/biggest-gainers` / `biggest-losers` / `most-actives` | Sector performance, market movers — market-wide, adopted |
| `stable/economic-calendar`, `stable/treasury-rates`, `stable/market-risk-premium` | Economics data — adopted; FRED remains canonical for its existing 12 macro series (no duplicate storage) |
| ~~`v4/insider-trading?symbol=`~~, ~~`v3/form-thirteen/{cik}`~~ | 13F institutional ownership — **NOT entitled on this plan** (user-verified 2026-08-15); institutional holder data now served read-only from pre-migration cache, flagged stale |
| ~~`v3/stock-screener`~~ | Screen stocks by market cap, sector, volume, price, country, etc. (unchanged status — not yet migrated to `stable/`) |

### Field Notes & Data Quality Caveats (from reviewing a real payload — see `FundamentalsTab.md` for the full chart-by-chart breakdown)
- **Duplicate fields across endpoints** — `ratios` and `key_metrics` both return several identical values: `enterpriseValueMultiple` (`ratios`) === `evToEBITDA` (`key_metrics`); `priceToFreeCashFlowRatio` (`ratios`) is the inverse of `freeCashFlowYield` (`key_metrics`); `currentRatio` appears identically in both. Pick one canonical source per metric rather than fetching/storing both.
- **SG&A sub-line inconsistency** — `generalAndAdministrativeExpenses` and `sellingAndMarketingExpenses` flip between `0` and a real populated value across years for the same company, purely from FMP filing-categorization changes, not an actual business shift. Use the combined `sellingGeneralAndAdministrativeExpenses` field for anything trend-charted.
- Same categorization-noise pattern hits `accruedExpenses` / `taxPayables` on the balance sheet.
- **`interestCoverageRatio` reports `0`** (not null) when net interest expense is near-zero — treat as "N/A," not literal zero coverage.
- **`priceToEarningsGrowthRatio` (PEG) is unstable** in low/negative-growth years since it divides by a near-zero growth rate — don't trend it without a sanity clamp.
- **`returnOnEquity` and `debtToEquityRatio` can look distorted for heavy buyback companies** — shrinking `totalStockholdersEquity` from repurchases can push ROE past 100% or make leverage look like it's falling when debt is actually flat. Not a data bug; needs a caption/tooltip wherever shown.

---

## Finnhub

**Access:** API key required · 60 calls/min (free tier) · WebSocket for real-time (50 symbols)  
**Base URL:** `https://finnhub.io/api/v1/`  
**Primary use:** Real-time quotes, news sentiment, insider sentiment (MSPR), earnings transcripts  

| Endpoint | Data Returned |
|---|---|
| `quote?symbol=` | Real-time price, open, high, low, prev close, % change, timestamp |
| `stock/candle?symbol=&resolution=&from=&to=` | OHLCV bars at any resolution (1, 5, 15, 30, 60, D, W, M) |
| `company-news?symbol=&from=&to=` | News articles: headline, summary, URL, source, datetime, sentiment category |
| `news?category=general\|forex\|crypto\|merger` | General market news feed |
| `news-sentiment?symbol=` | Aggregated news sentiment: bullish/bearish article counts, buzz score |
| `stock/insider-transactions?symbol=` | Insider buy/sell: name, shares, price, value, date, filing date, type |
| `stock/insider-sentiment?symbol=&from=&to=` | MSPR (insider sentiment ratio, -100 to +100) by month — leading signal for 30–90 day moves |
| `calendar/earnings?symbol=&from=&to=` | Earnings dates with EPS estimate, reported, surprise % |
| `stock/earnings?symbol=` | Historical EPS: estimate vs actual, surprise, quarter |
| `stock/financials-reported?symbol=` | As-reported financial statements from SEC filings |
| `stock/metric?symbol=&metric=all` | 90+ fundamental metrics: PE, PB, PS, beta, revenue TTM, margins, debt/equity, etc. |
| `stock/revenue-breakdown?symbol=` | Revenue by segment and geography |
| `stock/recommendation?symbol=` | Monthly analyst recommendation trend (strong buy → strong sell counts) |
| `stock/price-target?symbol=` | Price target: last updated, low, high, mean, median |
| `transcript?symbol=&year=&quarter=` | Full earnings call transcript text |
| `transcript/list?symbol=` | List of available earnings call transcripts |
| `stock/social-sentiment?symbol=&from=&to=` | Reddit/Twitter mention counts, positive/negative ratio by day |
| `stock/sec-sentiment?symbol=` | Sentiment extracted from SEC filings (10-K, 10-Q) |
| WebSocket `wss://ws.finnhub.io` | Real-time trade stream: price, volume, timestamp, conditions |

---

## FRED (Federal Reserve Economic Data)

**Access:** Free API key required · No rate limits · ~800,000 economic series  
**Base URL:** `https://api.stlouisfed.org/fred/`  
**Primary use:** All macro economic indicators — CPI, PCE, rates, GDP, unemployment, yield curve  

| Endpoint | Key Series IDs | Data Returned |
|---|---|---|
| `series/observations?series_id=` | CPIAUCSL | CPI (all items, urban consumers), monthly |
| | PCEPI | PCE price index (Fed's preferred inflation measure), monthly |
| | FEDFUNDS | Federal funds effective rate, daily/monthly |
| | DFEDTARL / DFEDTARU | Fed funds target rate lower/upper bound |
| | UNRATE | Civilian unemployment rate, monthly |
| | GDP | Gross domestic product, quarterly |
| | GDPC1 | Real GDP (inflation-adjusted), quarterly |
| | DGS10 | 10-year treasury yield, daily |
| | DGS2 | 2-year treasury yield, daily |
| | T10Y2Y | 10Y–2Y yield curve spread (inversion signal), daily |
| | T10Y3M | 10Y–3M yield spread (recession predictor), daily |
| | MORTGAGE30US | 30-year fixed mortgage rate, weekly |
| | INDPRO | Industrial production index, monthly |
| | RETAILSMNSA | Retail sales (not seasonally adjusted), monthly |
| | UMCSENT | University of Michigan consumer sentiment, monthly |
| | VIXCLS | CBOE VIX volatility index, daily |
| `series/search?search_text=` | — | Search for series by keyword |
| `series?series_id=` | — | Metadata for a series: title, units, frequency, seasonal adjustment |
| `releases` | — | All data releases (BLS, BEA, Census, etc.) with release dates |
| `release/dates?release_id=` | — | Schedule of upcoming data releases |
| `category/series?category_id=` | — | All series in a category (e.g., Prices & Inflation) |

---

## SEC EDGAR

**Access:** Free · No API key · Rate limit: 10 req/sec · Required header: `User-Agent: YourName email@domain.com`  
**Base URLs:** `https://data.sec.gov/` and `https://efts.sec.gov/`  
**Primary use:** Raw Form 4 insider filings, 13F institutional holdings — fallback when FMP budget runs low  

| Endpoint | Data Returned |
|---|---|
| `data.sec.gov/submissions/CIK{cik10}.json` | Full filing history for a company: all form types (10-K, 10-Q, 8-K, Form 4, 13F-HR, etc.) with filing dates, accession numbers, and document URLs |
| `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` | Every XBRL-tagged financial fact across all filings — single call returns complete financial history |
| `data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json` | All values for one specific concept (e.g., Revenues, NetIncomeLoss, Assets) across all reporting periods |
| `data.sec.gov/api/xbrl/frames/us-gaap/{concept}/USD/CY{year}Q{n}I.json` | Cross-company snapshot: all filers' values for one concept in one period — useful for sector comparisons |
| `efts.sec.gov/LATEST/search-index?q={query}&forms=4` | Full-text search across Form 4 filings — find insider transactions by keyword |
| `efts.sec.gov/LATEST/search-index?q={ticker}&forms=13F-HR` | Search 13F filings by ticker to find who holds it |
| **Form types** | **4** = insider buy/sell (fields: filer CIK, issuer, shares, price, transaction type, date); **13F-HR** = institutional holdings (fund name, ticker, shares, value, discretion type); **10-K** = annual report; **10-Q** = quarterly report |

---

## Quiver Quantitative

> ⚠️ **DEFERRED — Do not implement yet.** Placeholder for a future phase.  

**Access:** $30/month · API token header: `Authorization: Token <TOKEN>`  
**Base URL:** `https://api.quiverquant.com/beta/`  
**Python:** `pip install quiverquant` · `quiver = quiverquant.quiver("<TOKEN>")`  
**Primary use:** Congressional trades, government contracts, lobbying, dark pool data, alternative signals  

| Method / Endpoint | Data Returned |
|---|---|
| `quiver.congress_trading(ticker)` | Congressional trades: politician name, party, chamber, ticker, transaction type (buy/sell), amount range, disclosure date, trade date |
| `quiver.congress_trading(name, politician=True)` | All trades by a specific politician |
| `quiver.insiders(ticker)` | SEC Form 4 insider transactions (alternative to FMP/EDGAR) |
| `quiver.sec13FChanges(ticker)` | Hedge fund changes in holdings by ticker: fund name, shares added/removed, value, quarter |
| `quiver.sec13F(owner)` | Full 13F portfolio for a named fund: all positions, shares, values |
| `quiver.top_shareholders(ticker)` | Top shareholders by ticker with share count and % ownership |
| `quiver.executive_compensation(ticker)` | Executive pay: name, title, total compensation, cash, stock, year |
| `quiver.corporate_donors(ticker)` | Corporate PAC/election donations: recipient, amount, date, party |
| `quiver.lobbying(ticker)` | Corporate lobbying spend: issue, amount, quarter, filing date |
| `quiver.gov_contracts(ticker)` | Government contracts: agency, contract value, date, description |
| `quiver.offexchange(ticker)` | Off-exchange/dark pool short volume: daily short shares, total volume, short % |
| `quiver.wikipedia(ticker)` | Daily Wikipedia page view counts (alternative sentiment proxy) |
| `quiver.patents(ticker)` | Corporate patent filings: title, filing date, patent number |
| `quiver.news(ticker)` | Curated stock news feed |

---

## Dataroma (Superinvestor Portfolios)

**Access:** Scraped — no official API · Respectful crawl rate required  
**Scraping tool:** Playwright (headless Chromium) — site requires JS rendering  
**Base URL:** `https://dataroma.com`  
**Primary use:** Superinvestor (Berkshire, Pershing, etc.) portfolio tracking  

| URL Pattern | Data Available |
|---|---|
| `/m/home.php` | List of all tracked superinvestors with fund name, portfolio value, number of holdings |
| `/m/holdings.php?m={fund_id}` | Full portfolio for a fund: ticker, company name, % of portfolio, shares, value, recent activity |
| `/m/moves.php` | Recent buys/sells across all superinvestors: fund, ticker, shares, action, date |
| `/m/moves.php?date={YYYY-MM-DD}` | Moves on or after a specific date — use to fetch only new activity since last run |
| `/m/overlap.php` | Stock overlap analysis: which tickers appear in multiple top portfolios |
| **Data fields** | Fund name, fund ID, ticker, company, # shares held, value (USD), % of portfolio, quarter reported, buy/add/reduce/sell action, # superinvestors holding a stock |

**Incremental fetch strategy:** Store the timestamp of the last successful Dataroma pull in MongoDB. On each run, pass that date to `moves.php?date=` to fetch only new activity — avoids re-scraping data already in the database. Full portfolio re-fetch (`holdings.php`) only needed when a new fund is added or quarterly on a schedule.

---

## Company Logos

> ⚠️ **UNRESEARCHED — needs a quick spike, not a full phase.** Likely already solved by FMP.

**Candidate source:** FMP `v3/profile/{symbol}` returns an `image` field — a hosted logo URL — as part of the company profile call already needed for name/sector/industry/website. If that URL proves reliable (uptime, coverage across the ticker universe, no extra API cost beyond the profile call already budgeted), no dedicated logo API is needed. Fallback candidates if FMP's coverage has gaps: Clearbit Logo API (`logo.clearbit.com/{domain}`, free, no key, keyed off the company website domain — see "Company Website" below) or `financialmodelingprep.com/image-stock/{symbol}.png` (undocumented CDN path FMP also serves logos from).

**Where it'd be used:** `Navbar` search results, `AnalysisCard`, `Sidebar` watchlist rows, `StockDetail` header — anywhere a ticker is shown standalone, a small logo reduces scanning time vs. ticker text alone.

## Company Website Scraping

> ⚠️ **DEFERRED — not researched, no scoring/extraction design yet.** Placeholder for a future phase, same status as Quiver Quantitative above.

**Idea:** Pull each company's website URL from FMP's `v3/profile/{symbol}` (`website` field), then crawl it with Playwright (already a project dependency for Dataroma scraping — see `component-specs/agent-runner/tools/superinvestor.py`) to pull qualitative signal that structured financial data doesn't capture — investor relations pages, press releases, product announcements. Open questions before this becomes a real spec: what pages to crawl (IR page? full site?), what to extract (raw text for the chunker/summarizer pipeline, same pattern as `superinvestor.py`'s Ollama extraction?), how to avoid re-crawling unchanged pages, and respectful crawl-rate limits per site (same concern noted for the Dataroma scraper).

## Switching Primary Price Data Source — RESOLVED

**Resolved 2026-08-15** (specs/017-fmp-migration-admin): FMP fully replaced yfinance as the price source — not a per-ticker fallback, a wholesale switch, per the user's explicit "switch everything" direction. The original budget concern (FMP's 250/day free-tier ceiling competing with financials/ratios/insider calls) is moot now that the subscription is paid; the new `fmp_client.py` throttle (250 calls/min soft limit, configurable daily soft cap) replaces the old per-call quota anxiety. See `specs/017-fmp-migration-admin/contracts/fmp-migration-map.md` for the full migration and `fmp-gap-review.md` for what else the paid tier unlocked.

---

## Coverage Map — What Each Source Owns

| Data Need | Primary Source | Backup |
|---|---|---|
| Price history (OHLCV) | **FMP** (`stable/historical-price-eod/full`) | — |
| Real-time quotes | Finnhub | FMP `quote` |
| Income / balance / cash flow | FMP (cached) | SEC EDGAR (XBRL) |
| Key ratios (PE, EV/EBITDA, FCF yield, etc.) | FMP | — |
| Earnings estimates & surprises | FMP (`earnings`, `analyst-estimates`) | Finnhub |
| Earnings call transcripts | Finnhub | — (FMP transcripts **not entitled** on this plan) |
| Insider transactions (Form 4) | FMP (per-ticker + market-wide `insider-trading/latest`) · Finnhub | SEC EDGAR · Quiver |
| Insider sentiment (MSPR) | Finnhub | — |
| 13F institutional holdings | **Not entitled on current FMP plan** — `institutional.py` serves pre-migration cache read-only, flagged stale | SEC EDGAR · Quiver (future) |
| ETF & fund holdings | FMP (`etf/holdings`) — replaces Dataroma superinvestor tracking (not a like-for-like signal) | — |
| Superinvestor portfolios | Dataroma (scraped) — **being retired**, see specs/017-fmp-migration-admin | Quiver sec13F (future) |
| Congressional trades | FMP (`senate-latest`, `house-latest`) | Quiver (limited) |
| Macro indicators (CPI, PCE, rates, GDP) | FRED | — |
| Yield curve data | FRED (long history) · FMP `treasury-rates` (full daily curve snapshot — different shape, same underlying data) | — |
| Market breadth (NYMO, NAMO) | Computed locally from per-symbol FMP EOD closes over S&P 500 / NASDAQ-100 universes (`breadth.py`) | Constituent lists: FMP `sp500-constituent`/`nasdaq-constituent`, fallback Wikipedia/slickcharts scrape |
| Sector performance | FMP `sector-performance-snapshot` | — |
| Market movers (gainers/losers/actives) | FMP `biggest-gainers`/`biggest-losers`/`most-actives` | — |
| Economic calendar / market risk premium | FMP | — |
| News & news sentiment | FMP (articles, market-wide + per-ticker) · Finnhub (sentiment aggregates, MSPR) | Quiver news |
| Social sentiment (Reddit/Twitter) | Finnhub | Quiver (WSB) |
| Government contracts | Quiver | — |
| Dark pool / off-exchange volume | Quiver | — |
| ESG scores | — (dropped with yfinance; no consuming view) | FMP ESG family (entitlement unprobed) |
| Analyst ratings & price targets | FMP (`grades`) · Finnhub | — |
| Company info / profile | FMP `profile` — per-ticker, 90-day refresh | — |
| Company logo | FMP `profile.image` | Clearbit Logo API · FMP CDN image path |
| Company website / IR page content | FMP `profile.website` + Playwright crawl (deferred — see "Company Website Scraping") | — |

---

*Last updated: 2026-08-15 (specs/017-fmp-migration-admin)*
