# StockAI — Data Sources Spec

> Extracted from the main `SPEC.md`. This is the authoritative reference for all external data sources, API endpoints, rate limits, and the coverage map.

---

## yfinance (Yahoo Finance)

**Access:** No API key required · No enforced rate limit · Python library  
**Primary use:** Price history, market breadth signals, basic fundamentals  

| Method / Property | Data Returned |
|---|---|
| `.history(period, interval)` | OHLCV bars (open, high, low, close, volume, adj close), dividends, splits — any interval from 1m to 1mo |
| `.get_info()` | Quote metadata: market cap, P/E, beta, sector, industry, exchange, 52-wk range, avg volume |
| `.get_fast_info()` | Lightweight real-time snapshot: last price, market cap, shares outstanding |
| `.get_income_stmt(freq)` | Income statement (yearly or quarterly): revenue, gross profit, EBIT, EBITDA, net income, EPS |
| `.get_balance_sheet(freq)` | Balance sheet (yearly or quarterly): cash, total assets, total liabilities, equity, debt |
| `.get_cash_flow(freq)` | Cash flow statement (yearly or quarterly): operating, investing, financing cash flows, free cash flow |
| `.get_earnings(freq)` | Earnings summary per period (revenue + EPS, yearly/quarterly/trailing) |
| `.get_earnings_dates(limit)` | Upcoming + historical earnings dates with EPS estimate, reported EPS, surprise % |
| `.get_earnings_estimate()` | Forward EPS estimates for 0Q, +1Q, 0Y, +1Y with analyst count, low/high/avg/growth |
| `.get_revenue_estimate()` | Forward revenue estimates for 0Q, +1Q, 0Y, +1Y |
| `.get_eps_trend()` | EPS trend revisions: current vs 7/30/60/90 days ago |
| `.get_eps_revisions()` | Analyst revision counts (up/down) over last 7 and 30 days |
| `.get_growth_estimates()` | Growth estimates for stock, industry, sector, index (0Q through +5Y) |
| `.get_analyst_price_targets()` | Price target: current, low, high, mean, median |
| `.get_recommendations()` | Analyst rec counts by period: strongBuy, buy, hold, sell, strongSell |
| `.get_upgrades_downgrades()` | Firm-level upgrades/downgrades with from/to grade and action |
| `.get_institutional_holders()` | Top institutional holders: name, shares, date reported, % out |
| `.get_mutualfund_holders()` | Top mutual fund holders: name, shares, date reported, % out |
| `.get_insider_purchases()` | Insider purchase summary: insider buys/sells counts and share totals |
| `.get_insider_transactions()` | Individual insider transactions: name, shares, value, date, type |
| `.get_insider_roster_holders()` | Insider roster: names, positions, share counts, % ownership |
| `.get_major_holders()` | % shares held by institutions, insiders, public float |
| `.get_shares_full(start, end)` | Historical share count time series (up to 18 months) |
| `.get_valuation_measures(freq)` | Market cap, P/E, P/S, P/B, EV/EBITDA, EV/Revenue (quarterly/monthly/yearly) |
| `.get_sustainability()` | ESG scores: environmental, social, governance, total ESG, controversy level |
| `.get_calendar()` | Next earnings date, ex-dividend date, dividend date |
| `.get_sec_filings()` | List of recent SEC filings with type, date, and URL |
| `.get_dividends()` / `.get_splits()` | Historical dividend amounts and split ratios |
| `.get_news(count, tab)` | Recent news articles: headline, URL, publisher, publish time |
| `.option_chain(date)` | Options chains: calls/puts with strike, bid/ask, IV, OI, delta, gamma |
| `yf.download(universe_tickers)` (batched) | Daily closes for the S&P 500 / NASDAQ-100 universes — used to **compute** the McClellan Oscillator (NYMO/NAMO) locally. ⚠️ The `$NYMO`/`$NAMO` StockCharts symbols are NOT on Yahoo (verified 2026-08-02: `$NYMO`, `^NYMO`, `$NAMO`, `^NYAD`, `^TRIN` all return no data); see `component-specs/agent-runner/tools/breadth.md` |
| `.live()` / `WebSocket` | Real-time streaming price via WebSocket (up to any number of symbols) |

---

## Financial Modeling Prep (FMP)

**Access:** API key required · 250 calls/day (free tier) · Cache aggressively — re-fetch quarterly only  
**Base URL:** `https://financialmodelingprep.com/api/`  
**Primary use:** Comprehensive financials, ratios, insider filings, 13F institutional data  

| Endpoint | Data Returned |
|---|---|
| `v3/income-statement/{symbol}?period=annual\|quarter` | Revenue, COGS, gross profit, R&D, EBIT, EBITDA, net income, EPS (diluted/basic) |
| `v3/balance-sheet-statement/{symbol}?period=annual\|quarter` | Cash, receivables, inventory, PP&E, total assets, debt, equity, working capital |
| `v3/cash-flow-statement/{symbol}?period=annual\|quarter` | Operating/investing/financing cash flows, capex, free cash flow, dividends paid |
| `v3/income-statement-growth/{symbol}` | YoY growth rates for revenue, EBITDA, EPS, net income |
| `v3/cash-flow-statement-growth/{symbol}` | YoY growth rates for free cash flow, capex, operating cash flow |
| `v3/ratios/{symbol}?period=annual\|quarter` | P/E, P/B, P/S, EV/EBITDA, debt/equity, current ratio, ROE, ROA, gross/net margin |
| `v3/key-metrics/{symbol}?period=annual\|quarter` | FCF yield, ROIC, revenue per share, net cash/debt, PE ratio, dividend yield |
| `v3/enterprise-values/{symbol}` | Market cap, EV, EV/EBITDA, EV/Revenue by quarter |
| `v3/analyst-estimates/{symbol}` | Forward EPS + revenue estimates with analyst counts, low/avg/high |
| `v3/analyst-stock-recommendations/{symbol}` | Analyst rating trends (buy/hold/sell counts by month) |
| `v3/quote/{symbol}` | Real-time/delayed quote: price, change, volume, market cap, PE, 52-wk range |
| `v3/historical-price-full/{symbol}` | Full OHLCV daily history with adjusted prices |
| `v3/earning_calendar` | Upcoming earnings dates with EPS estimates |
| `v4/insider-trading?symbol={symbol}` | Insider transactions: name, title, shares, price, value, date, type (Form 3/4/5) |
| `v4/insider-trading-rss-feed` | RSS feed of latest insider filings across all tickers |
| `v3/cik_list` | All registered institutional managers with CIK numbers |
| `v3/cik-search/{name}` | Look up CIK by fund/institution name |
| `v3/form-thirteen/{cik}?date=` | 13F holdings for a fund on a given date: ticker, shares, value, % |
| `v3/form-thirteen-date/{cik}` | All 13F filing dates for a given fund |
| `v3/stock-screener` | Screen stocks by market cap, sector, volume, price, country, etc. |
| `v3/profile/{symbol}` | Company profile: name, description, sector, industry, exchange, CEO, employees, website URL, and a hosted **company logo image URL** (`image` field) — no separate logo API needed, see "Company Logos" below |

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

## Switching Primary Price Data Source

> Under consideration, not yet decided.

yfinance (current primary, see above) doesn't cover every ticker the user wants tracked — some tickers return empty/errored history. FMP's `v3/historical-price-full/{symbol}` is a viable replacement and is already paid for at $20/mo, but switching wholesale would materially increase FMP call volume against the 250/day (free tier) or paid-tier budget, competing with the financials/ratios/insider calls FMP already serves. Needs: (1) a coverage comparison — which tickers yfinance actually fails on, and whether FMP covers those specifically, (2) a decision on whether FMP replaces yfinance entirely for price or only backfills the gap tickers (keeping yfinance primary, FMP as a per-ticker fallback — consistent with the "Backup" column pattern already used elsewhere in the Coverage Map below). Also worth a broader pass on what else the $20/mo FMP tier unlocks beyond price data, since the plan tier isn't fully mapped in this doc yet.

---

## Coverage Map — What Each Source Owns

| Data Need | Primary Source | Backup |
|---|---|---|
| Price history (OHLCV) | yfinance | FMP |
| Real-time quotes | Finnhub | yfinance fast_info |
| Income / balance / cash flow | FMP (cached) | yfinance · SEC EDGAR (XBRL) |
| Key ratios (PE, EV/EBITDA, FCF yield, etc.) | FMP | yfinance |
| Earnings estimates & surprises | yfinance · Finnhub | FMP |
| Earnings call transcripts | Finnhub | — |
| Insider transactions (Form 4) | FMP · Finnhub | SEC EDGAR · Quiver |
| Insider sentiment (MSPR) | Finnhub | — |
| 13F institutional holdings | FMP · Quiver | SEC EDGAR |
| Superinvestor portfolios | Dataroma (scraped) | Quiver sec13F |
| Congressional trades | Quiver | Finnhub (limited) |
| Macro indicators (CPI, PCE, rates, GDP) | FRED | — |
| Yield curve data | FRED | yfinance (DGS tickers) |
| Market breadth (NYMO, NAMO) | Computed locally from batched yfinance closes over S&P 500 / NASDAQ-100 universes (`breadth.py`) | Constituent lists: FMP `sp500_constituent`/`nasdaq_constituent`, fallback Wikipedia |
| News & news sentiment | Finnhub | Quiver news |
| Social sentiment (Reddit/Twitter) | Finnhub | Quiver (WSB) |
| Government contracts | Quiver | — |
| Dark pool / off-exchange volume | Quiver | — |
| ESG scores | yfinance | — |
| Analyst ratings & price targets | yfinance · Finnhub · FMP | — |
| Company logo | FMP `profile.image` (unresearched — see "Company Logos") | Clearbit Logo API · FMP CDN image path |
| Company website / IR page content | FMP `profile.website` + Playwright crawl (deferred — see "Company Website Scraping") | — |

---

*Last updated: 2026-08-03*
