# StockAI — Product Spec

> Living document. Add to it as ideas develop.

---

## Vision

A stock research and tracking app that goes far beyond price. StockAI synthesizes economic data, company fundamentals, institutional behavior, insider activity, earnings transcripts, and curated external sources to surface insights a typical investor would never find manually.

---

## Core Feature Areas

### 1. Price Tracking
- Real-time and historical price data
- Customizable watchlists and portfolios
- Alerts (price targets, % moves, volume spikes)

### 2. Economic Data
- Macro indicators: CPI, PCE, interest rates, unemployment, GDP
- Fed decisions and commentary
- Yield curve tracking
- Sector rotation signals tied to macro regime

### 3. Company Financials
- Income statement, balance sheet, cash flow (annual + quarterly)
- Key ratios: P/E, EV/EBITDA, gross margin, FCF yield, debt/equity, etc.
- YoY and QoQ trend analysis
- Earnings estimates vs. actuals

### 4. Trend Recognition
- Pattern detection across price, volume, financials, and macro data
- Momentum, mean-reversion, and breakout signals
- Alerts when multiple signals align

### 5. Congressional Trading
- Track trades disclosed by members of Congress (via eFTIS / Quiver Quantitative or similar)
- Filter by party, committee membership, sector, ticker
- Flag unusual timing relative to legislation or hearings

### 6. Insider Activity
- SEC Form 4 filings (insider buys/sells)
- Cluster buying signals (multiple insiders buying near the same time)
- Distinguish open-market purchases vs. option exercises
- Track insider sentiment over time per ticker

### 7. Earnings Transcripts
- Ingest and parse earnings call transcripts
- Sentiment analysis (management tone, guidance confidence)
- Keyword tracking (e.g., "headwinds," "accelerating," "cautious")
- Compare tone across quarters

### 8. Superinvestor / Institution Tracking
- Scrape and parse [Dataroma](https://dataroma.com/m/home.php) for superinvestor portfolio activity
- Track 13F filings for major funds (Berkshire, Pershing, etc.)
- Identify stocks being accumulated or exited by multiple top investors
- Overlap analysis: which stocks appear in the most top portfolios?
- **Institutional Flow feed** — a standalone, market-wide live feed of these moves (not scoped to a single ticker), independent of the per-stock Institutional tab. See "Institutional Flow — Feature Design" below.

### 9. Earnings Calendar Scanner
- Sweep the upcoming earnings calendar (next 1–14 days) across all publicly traded companies
- Score each company for "earnings play" potential: post-earnings move history, IV crush setup, analyst estimate spread, recent momentum
- Surface the most interesting candidates as an interactive ranked list
- Conversational handoff: user selects a ticker → full multi-agent analysis runs automatically
- Data fetched in parallel across agents for speed
- Post-earnings tracking: after a company reports, log the actual price move and compare to the predicted setup

### 10. Company Enrichment (logos, website intel)
- **Company logos** next to tickers across the UI (search results, feed cards, watchlist rows, stock detail header) — likely already covered by FMP's `v3/profile/{symbol}` `image` field, needs a quick verification spike rather than a new integration. See `DATA_SOURCES.md` → "Company Logos."
- **Company website scraping** — pull each company's website/IR page via Playwright (reusing the Dataroma scraping pattern) for qualitative signal financial statements don't carry. Deferred, unresearched — see `DATA_SOURCES.md` → "Company Website Scraping."

### 11. [More to come]
- *(Placeholder for additional ideas)*

---

## Earnings Scanner — Workflow Design

The Earnings Scanner is a second run mode alongside the watchlist workflow. Instead of analyzing tickers the user already tracks, it sweeps the upcoming earnings calendar to find new opportunities before they report.

### Overview

```
Calendar Sweep → Score & Rank → Conversational Review → Full Analysis (parallel)
```

1. **Sweep**: Pull the earnings calendar for the next N days (FMP `v3/earning_calendar`, supplemented by Finnhub for surprise history). Get every company reporting in the window.
2. **Pre-screen**: Apply fast filters to cut the list down — skip micro-caps below a configurable market cap floor, skip tickers with no options (can't gauge IV), skip companies with fewer than 4 prior earnings events.
3. **Score**: For each remaining company, the `EarningsScannerAgent` scores it on the criteria below. This uses lightweight data only (no full financial fetch yet).
4. **Rank & present**: Return a ranked list of the top N candidates to the user as an interactive conversational response.
5. **Handoff**: User selects a ticker (or says "analyze the top 3"). The system enqueues a full crew analysis — all data fetched in parallel, then agents run.
6. **Post-earnings log**: After the company reports, the system captures the actual price move and stores it alongside the pre-earnings analysis for backtesting.

### Scoring Criteria (EarningsScannerAgent)

| Signal | Weight | Source |
|---|---|---|
| Average absolute post-earnings move (last 8 quarters) | High | Finnhub historical EPS + price data |
| Consistency of move direction (beat → up, miss → down) | Medium | Finnhub |
| Analyst estimate spread (high - low / consensus) — wide = uncertainty | Medium | FMP / yfinance |
| EPS estimate revision trend (analysts raising into earnings) | High | yfinance `get_eps_revisions()` |
| Insider activity in last 60 days (buys before earnings = signal) | High | FMP insider tool |
| Accumulation score trend (institutional buying heading into earnings) | Medium | accumulation skill |
| Revenue surprise rate (% of last 8 quarters where revenue beat) | Medium | Finnhub |
| Options IV vs. historical (if IV elevated → market expects big move) | Low (deferred) | Future phase |

Final score: 0–100. Top 10 displayed to user.

### Conversational Handoff Design

The earnings scanner runs as an **interactive conversation**, not a batch job:

```
User:  "Run the earnings scanner for this week"

Agent: "Found 47 companies reporting Mon–Fri. After pre-screening, here are
        the top 5 setups:

        1. NVDA (Wed)  — Score 87 | Avg move ±9.2% | Analysts raising estimates
           3 insider buys in last 30 days | Accumulation score 4/5
        2. COST (Thu)  — Score 81 | Avg move ±4.1% | 7/8 quarters beat revenue
           Strong momentum, no insider activity
        3. CRWD (Wed)  — Score 76 | Avg move ±11.4% | Wide estimate spread
           Estimate revisions up 3 of last 4 weeks
        ...

        Which would you like me to do a full deep dive on?"

User:  "Do NVDA and CRWD"

Agent: "Running full analysis on NVDA and CRWD — fetching all data in parallel now..."
       [enqueues both with parallel=True flag]
```

The conversational layer is handled by a dedicated `EarningsConversationAgent` that presents results, asks clarifying questions, and triggers the handoff.

### Parallel Data Fetching

When the full crew is triggered from an earnings scanner handoff, all data fetching runs in parallel before agents start:

```python
# crew.py — parallel pre-fetch (asyncio.gather or ThreadPoolExecutor)
import asyncio
from concurrent.futures import ThreadPoolExecutor

def prefetch_all(ticker: str) -> dict:
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            "price":         pool.submit(price_tool.get_price_history, ticker),
            "financials":    pool.submit(financials_tool.get_financials, ticker),
            "insider":       pool.submit(insider_tool.get_insider_activity, ticker),
            "institutional": pool.submit(institutional_tool.get_institutional_holdings, ticker),
            "sentiment":     pool.submit(sentiment_tool.get_earnings_sentiment, ticker),
            "breadth":       pool.submit(breadth_tool.get_market_breadth),
        }
        return { key: f.result() for key, f in futures.items() }
```

This cuts total fetch time from ~60s (sequential) down to ~15s (parallel, bottlenecked by the slowest source). Macro data is already cached from the calendar sweep phase so it doesn't add to the critical path.

### New Files Added by This Feature

```
agent-runner/
  agents/
    earnings_scanner.py         # Scores and ranks earnings candidates
    earnings_conversation.py    # Conversational presentation + handoff
  tools/
    earnings_calendar.py        # Fetches calendar from FMP + Finnhub

api/
  routers/
    earnings.py                 # GET /earnings/calendar, POST /earnings/scan

frontend/src/
  pages/
    EarningsScan.tsx            # Conversational earnings scanner UI
  components/
    earnings/
      EarningsCalendarTable.tsx # Ranked candidate table
      EarningsCandidateCard.tsx # Per-ticker score breakdown card
      ScanControls.tsx          # Days-ahead slider, market cap floor, scan button
```

### New API Endpoints

| Endpoint | Description |
|---|---|
| `GET /earnings/calendar?days=7` | Raw upcoming earnings calendar (pre-screened list) |
| `POST /earnings/scan` | Run the full scoring pass; returns ranked candidates |
| `GET /earnings/scan/{scan_id}` | Poll scan result (async — scanning can take 30–60s) |
| `POST /earnings/analyze` | Enqueue full crew analysis for selected tickers (parallel fetch) |
| `GET /earnings/history/{ticker}` | Post-earnings move log for a ticker |

---

## Institutional Flow — Feature Design

A standalone page showing a live feed of institutional and superinvestor activity across the **entire tracked universe** — not one ticker. It's the market-wide sibling of the per-ticker `InstitutionalAnalyst`/Institutional tab: same underlying data (13F filings, Dataroma superinvestor moves), reshaped as a stream of discrete events instead of a per-stock report.

### Why a separate page instead of just the Institutional tab
The existing Institutional tab on Stock Detail answers "what's smart money doing in *this* stock?" — useful, but only visible one ticker at a time. The Institutional Flow feed answers "what did smart money do today, anywhere?" so new 13F/Dataroma activity surfaces even for tickers not currently on the watchlist or open in a browser tab.

### Overview
```
Scheduled Scan (daily) → InstitutionalFlowScannerAgent → institutional_flow events (MongoDB)
                                                                    ↓
                                              GET /institutional/flow → Institutional Flow page
```

1. **Scan**: `InstitutionalFlowWorker` runs once daily (configurable), independent of the per-ticker `work_queue`. Pulls Dataroma's global moves page and re-checks 13F data for the tracked universe (watchlist ∪ any ticker with a prior analysis).
2. **Extract & score**: `InstitutionalFlowScannerAgent` turns raw filing/move text into discrete events — fund, ticker, action, size, and a notability score that separates high-conviction concentrated funds from passive/index noise.
3. **Store**: each move is written as its own document in a new `institutional_flow` collection (not appended to `analyses`, since it isn't tied to a completed per-ticker crew run).
4. **Serve**: `GET /institutional/flow` paginates the feed, newest filing first, filterable by action/fund/ticker/notability.
5. **Display**: `InstitutionalFlow.tsx` — same infinite-scroll shell as the home Analysis Feed, with `InstitutionalFlowCard` in place of `AnalysisCard`.
6. **Manual refresh**: consistent with the rest of the app's no-polling model, a "Scan Now" button (`POST /institutional/scan`) lets the user request a fresh pull instead of waiting for the daily schedule.

### New Files Added by This Feature
```
agent-runner/
  agents/
    institutional_flow_scanner.py   # Market-wide scan → scored, feed-ready events
  institutional_flow_worker.py      # Runs the scan on its own daily timer

api/
  routers/
    institutional_flow.py           # GET /institutional/flow, /institutional/flow/{ticker}, POST /institutional/scan
  models/
    institutional_flow.py           # InstitutionalFlowEvent, InstitutionalFlowResponse

frontend/src/
  pages/
    InstitutionalFlow.tsx           # /institutional-flow — live feed UI
  components/
    institutional/
      InstitutionalFlowCard.tsx     # Per-event card
      InstitutionalFlowFilterBar.tsx # Action/fund/ticker/notability filters + Scan Now
      ActionBadge.tsx                # New Position / Add / Trim / Exit pill
  hooks/
    useInstitutionalFlow.ts         # useInstitutionalFlow, useTickerFlow, useTriggerInstitutionalScan
```

### New API Endpoints

| Endpoint | Description |
|---|---|
| `GET /institutional/flow?page=&action=&fund=&ticker=&min_notability=` | Paginated market-wide flow feed |
| `GET /institutional/flow/{ticker}` | Flow history for one ticker (linked from the Stock Detail Institutional tab) |
| `POST /institutional/scan` | Manually trigger a fresh scan (mirrors "Pull All") |

### Navigation
Added to the top nav alongside Feed and Sectors, and linked from the Stock Detail Institutional tab ("See all institutional activity for {ticker} →") so users can cross from a per-stock snapshot into the raw feed behind it.

---

## Data Sources

> See **[DATA_SOURCES.md](./DATA_SOURCES.md)** for the full reference — all API endpoints, rate limits, method tables, and the coverage map.

---

## Deployment & Infrastructure

- **Runs locally** on Neal's machine — no cloud hosting required initially
- **Docker container** — fully containerized for portability and clean dependency management
- **Batch job, once daily** — runs on a schedule (e.g., after market close), not real-time
- **Database**: MongoDB Community Edition — document store (JSON/BSON), runs as a Docker service via `docker-compose`
- **API caching is critical** — financial statements and 13F data change quarterly; cache locally in MongoDB and skip re-fetch unless a new period is detected. This keeps FMP usage well within the 250 call/day limit.

---

## Exception Handling & Logging

Every component catches its own unhandled exceptions and records them — today to a local file, later to whatever production logging backend the app ends up on — without call sites changing when that switch happens.

### Local Today, Cloud-Ready Later
- **Today**: every exception, plus normal app-level logging, is written to a local file under a root `logs/` directory.
- **Later**: when this moves off Neal's machine, only the sink inside the shared logging helper changes (e.g., swap the file handler for a CloudWatch/Datadog/Sentry handler) — call sites (`logger.info(...)`, `logger.exception(...)`) never change.
- Achieved via one small `get_logger(component)` helper per Python service instead of the ad hoc `logging.getLogger(__name__)` + scattered `logging.basicConfig()` calls that exist today.

### Log Directory Layout
```
logs/
  agent-runner/
    agent-runner.log   # rotating; app events + logger.exception() tracebacks
  backend/
    backend.log        # rotating; app events + unhandled request exceptions
  frontend/
    frontend.log       # client-side errors, relayed through the backend (browsers can't write local files)
  scripts/
    scripts.log        # one-off scripts (backfill_financials.py, seed_watchlist.py)
```
- One folder per component, one rotating log file per component — never one shared file.
- Rotation: `TimedRotatingFileHandler` (daily, 14-day retention) — these are debugging dumps, not long-term storage or an audit trail.
- `logs/` lives at the repo root. Each service's `logging_config.py` resolves its log root as one directory above its own file (`<service>/../logs`), which in Docker (`WORKDIR /app`) lands at `/logs` — so both the `backend` and `agent-runner` containers bind-mount the whole tree with a single `./logs:/logs`, and each service only ever writes inside its own `logs/<component>/` subfolder. Entries persist on the host across restarts/rebuilds. The tree is git-ignored (`*.log` already is; each folder keeps a `.gitkeep` so it exists before first run).

### Reusable Logging Function
Each Python service (`agent-runner`, `backend`) gets its own `logging_config.py` (duplicated, not shared — the two are already independent services with their own `requirements.txt`/`Dockerfile`, matching how `settings.py` is already duplicated per component) exposing one function:

```python
# agent-runner/logging_config.py  (backend/logging_config.py is the same shape,
# with COMPONENT = "backend")
COMPONENT = "agent-runner"

def get_logger(name: str, component: str = COMPONENT) -> logging.Logger:
    """
    Single choke point for where logs go. Today: TimedRotatingFileHandler
    writing to logs/<component>/<component>.log, plus a stderr stream handler,
    attached once per component and shared by every logger under it. Swapping
    to a cloud backend later means changing the handler(s) registered here
    (e.g. based on a LOG_SINK=local|cloud env var) -- nothing else in the
    codebase changes.
    """
```
Call sites pass their own `__name__` (e.g. `logger = get_logger(__name__)`), which is namespaced under the component (`agent-runner.tools.institutional`) so log lines still show which module logged them. `component` only needs overriding by callers outside the owning service — `scripts/*.py` import agent-runner's `logging_config` (they already do `sys.path.insert` into `agent-runner/` to reach its `tools/`) but pass `component="scripts"` so their crashes land in `logs/scripts/` instead of `logs/agent-runner/`. Existing `logger = logging.getLogger(__name__)` + scattered `logging.basicConfig()` call sites across `agent-runner` and `backend` are replaced this way.

### Catching Exceptions Per Component

| Component | Where uncaught exceptions are caught | Behavior |
|---|---|---|
| `agent-runner` | `queue_worker.py` job loop, `institutional_flow_worker.py`, `earnings_scan_worker.py` | Each job/scan iteration is wrapped in try/except; `logger.exception(...)` records the full traceback, the job is marked `failed` (existing status field), and the worker keeps polling — one bad ticker never kills the process |
| `backend` (FastAPI) | Global `@app.exception_handler(Exception)` in `main.py` | Logs the traceback via `get_logger("backend")` and returns a generic 500, instead of an unhandled exception surfacing raw |
| `frontend` | Top-level React `ErrorBoundary` + `window.onerror` / `window.onunhandledrejection` | POSTs `{ message, stack, component, url, timestamp }` to `POST /logs/frontend`; the backend writes it to `logs/frontend/` via `get_logger("frontend")` — browsers can't write local files directly, so frontend errors are relayed through the API |
| `scripts` | `backfill_financials.py`, `seed_watchlist.py` | `main()` body wrapped in try/except, `logger.exception(...)`, exits non-zero |

### New API Endpoint

| Endpoint | Description |
|---|---|
| `POST /logs/frontend` | Accepts a client-side error report and writes it via `get_logger("frontend")` to `logs/frontend/` |

---

## AI Layer — CrewAI + Local LLM via Ollama

- **Framework**: CrewAI — multi-agent orchestration with defined roles, goals, and tool access
- **Model**: Ollama running locally (model TBD — e.g., LLaMA 3, Mistral, etc.)
- **Approach**: Specialized CrewAI agents, each with a defined role and a set of tools, analyze each stock from their domain. Results feed into a final synthesis agent.
- No cloud API calls for inference; everything stays on-device

### Agent Architecture

| Agent | Role | Tools |
|---|---|---|
| `TechnicalAnalyst` | Price patterns, indicators, momentum, accumulation volume | `get_price_history`, `get_technical_indicators`, `get_accumulation_score` |
| `FundamentalAnalyst` | Financials, ratios, earnings | `get_financials`, `get_earnings_data` |
| `MacroAnalyst` | Economic context, sector impact | `get_macro_data` |
| `InsiderAnalyst` | Form 4 filings, cluster signals | `get_insider_activity`, `get_congressional_trades` |
| `InstitutionalAnalyst` | 13F, superinvestor moves | `get_institutional_holdings`, `get_superinvestor_activity` |
| `SentimentAnalyst` | Earnings transcript tone, news | `get_earnings_sentiment` |
| `RecommenderAgent` | Market flow timing — when to buy more or start selling | `get_market_breadth`, `get_technical_indicators`, reads gap scores from MongoDB |
| `PortfolioStrategist` | Synthesizes all agent outputs | Reads agent outputs from MongoDB |
| `EarningsScannerAgent` | Scores and ranks upcoming earnings candidates | `get_earnings_calendar`, `get_earnings_history`, `get_insider_activity`, `get_accumulation_score` |
| `EarningsConversationAgent` | Presents ranked candidates conversationally, handles user selection, triggers handoff | Reads scanner output from MongoDB, calls `enqueue_analysis` |
| `InstitutionalFlowScannerAgent` | Market-wide (not per-ticker) scan of new 13F/superinvestor moves, scored by notability | `get_recent_13f_changes`, `get_recent_superinvestor_moves` |

### Skills (Pluggable Analytical Engines)

Skills are self-contained analytical modules that live in `agent-runner/skills/`. Each skill encapsulates a complete rule system — its own logic, scoring, and output format — and can be called by one or more agents as a tool. Skills are tested independently and can be composed freely.

| Skill | Source Spec | Used By | Output |
|---|---|---|---|
| `the_strat` | `the-strat-spec.md` | `TechnicalAnalyst`, `RecommenderAgent` | Bar type classification (1/2U/2D/3), active patterns (Rev Strat, 2-1-2, kicking, etc.), TFC state across timeframes, actionable signals in force |
| `accumulation` | `accumulation_volume_rules.md` | `TechnicalAnalyst`, `InstitutionalAnalyst` | Accumulation score (0–5), up/down volume ratio, max volume spike, pattern duration, PEG amplifier flag |
| `gap_analysis` | `gap_analysis_rules.md` | `TechnicalAnalyst` | Gap type, gap score, fill probability, follow-through signal |
| `market_flow` | `market_flow_rules.md` | `RecommenderAgent` | Buy-more / hold / trim / start-selling signal per ticker based on NYMO/NAMO readings |
| `position_management` | `position_management_agent_spec.md` | `RecommenderAgent`, `PortfolioStrategist` | Updated stair-step stop levels, trailing stop recommendations, position sizing guidance |

Each skill exposes a standard interface:
```python
# Every skill follows this pattern
result = skill.run(ticker, data)  # data = pre-fetched, pre-chunked inputs
# Returns a structured dict the calling agent appends to its context
```

---

### Tools (Python functions bound to CrewAI agents)

- `get_price_history(ticker, period)` → yfinance
- `get_technical_indicators(ticker)` → computed locally via pandas-ta or TA-Lib
- `get_accumulation_score(ticker, lookback_days=60)` → computed locally; returns score 0–5, up/down volume ratio, max volume spike, pattern duration, PEG amplifier flag (see `accumulation_volume_rules.md`)
- `get_financials(ticker)` → FMP (MongoDB cache, re-fetch quarterly)
- `get_earnings_data(ticker)` → FMP / Finnhub
- `get_macro_data(indicator)` → FRED
- `get_insider_activity(ticker)` → FMP / Finnhub
- `get_congressional_trades(ticker)` → Quiver Quantitative
- `get_institutional_holdings(ticker)` → FMP / SEC EDGAR
- `get_superinvestor_activity(ticker)` → Dataroma scraper
- `get_earnings_sentiment(ticker)` → transcript analysis
- `get_market_breadth()` → **computes** NYMO/NAMO locally (the `$NYMO`/`$NAMO` StockCharts symbols are not available via yfinance or any API in the stack — verified 2026-08-02). Ratio-adjusted McClellan Oscillator from advance/decline counts over S&P 500 (NYSE proxy) and NASDAQ-100 (NASDAQ proxy) universes, one batched yfinance download per day, cached in `breadth_cache`. Returns current readings + recent history for divergence detection. See `component-specs/agent-runner/tools/breadth.md`
- `get_earnings_calendar(days_ahead=7)` → FMP `v3/earning_calendar` + Finnhub for surprise history; returns pre-screened list of upcoming reporters
- `get_earnings_history(ticker, num_quarters=8)` → Finnhub historical EPS + post-earnings price moves; used by EarningsScannerAgent for scoring
- `get_recent_13f_changes(since, universe=None)` → FMP, re-checks the cached per-ticker 13F data across the tracked universe for changes filed since a timestamp; used by InstitutionalFlowScannerAgent
- `get_recent_superinvestor_moves(since)` → Dataroma `moves.php`, global (not ticker-scoped); used by InstitutionalFlowScannerAgent
- `query_db(collection, filter)` → MongoDB read
- `write_db(collection, data)` → MongoDB write

### RecommenderAgent Logic

The `RecommenderAgent` focuses on **market flow** — the "when" of trading, not the "what." It answers two questions for each position/watchlist ticker:

- **Should I buy more?** — Uses NYMO/NAMO oversold readings, divergence patterns (SPY double bottom + NYMO higher low), and gap analysis scores to identify high-conviction add opportunities
- **Should I start selling?** — Uses NYMO/NAMO overbought readings combined with exhaustion gap patterns to flag trimming/exit conditions

Rules are defined in `market_flow_rules.md` and `accumulation_volume_rules.md`. Key signal sources:
- NYMO and NAMO readings computed locally by `breadth.py` (McClellan Oscillator — NYSE and NASDAQ breadth; the `$NYMO`/`$NAMO` tickers themselves are StockCharts-only and not API-fetchable)
- Gap scores from `TechnicalAnalyst` (stored in MongoDB)

Output per ticker: `recommendation` (BUY_MORE / HOLD / TRIM / START_SELLING / AVOID_ADD / WATCH), `conviction` level, and plain-English `rationale`.

---

### LLM Output (per stock, written to MongoDB)

- Overall signal summary (bullish / bearish / neutral + reasoning)
- Key trends identified across the data
- Flags or alerts worth human attention
- Confidence level or caveat notes
- Per-agent sub-reports stored alongside the synthesis

---

---

## Full-Stack Architecture

### System Overview

```
[CrewAI Agents] → [MongoDB] ← [FastAPI] ← [React UI]
       ↑                          ↓
  [Ollama LLM]            [REST/WebSocket]
```

The agentic pipeline (CrewAI + Ollama) runs on a schedule and writes all analysis results to MongoDB. FastAPI sits between the database and the React frontend, exposing clean REST endpoints. The UI is a standalone React app that consumes the API — no server-side rendering needed.

---

### Backend: FastAPI

- **Language**: Python (same environment as CrewAI/Ollama — no context switching)
- **Role**: REST API layer between MongoDB and the React frontend
- **Runs locally** as a Docker service alongside MongoDB and the agent pipeline

#### Key API Endpoints

| Endpoint | Description |
|---|---|
| `GET /analysis/feed` | Latest analysis, newest first. Paginated. |
| `GET /analysis/{ticker}` | Full analysis history for a single stock |
| `GET /analysis/sector/{sector}` | All analyses grouped by sector |
| `GET /stocks/search?q=` | Ticker/name search for autocomplete |
| `GET /stocks/{ticker}/financials` | Cached financials for a ticker |
| `GET /stocks/{ticker}/signals` | Agent-level sub-reports (technical, insider, etc.) |
| `GET /macro` | Latest macro data (FRED) |
| `GET /watchlist` | User's watchlist |
| `POST /watchlist/{ticker}` | Add ticker to watchlist |
| `GET /sectors` | List of sectors with summary stats |
| `GET /institutional/flow` | Market-wide institutional/superinvestor flow feed. Paginated. |
| `GET /institutional/flow/{ticker}` | Flow history for a single ticker |
| `POST /institutional/scan` | Manually trigger a fresh institutional flow scan |
| `POST /logs/frontend` | Accepts a client-side error report, writes it to `logs/frontend/` (see "Exception Handling & Logging") |

---

### Frontend: React UI

**Stack**: React + Vite, Tailwind CSS, Recharts (charts), Framer Motion (animations), React Query (data fetching + caching)

**Design**: Clean dark mode — think premium fintech (Robinhood, Linear). Lots of whitespace, sharp typography, smooth transitions. Data-dense but never cluttered.

#### Layout & Navigation

```
┌───────────────────────────────────────────────────────────────────┐
│  [Logo]   Feed  |  Institutional Flow  |  Sectors  |  Search...  [Watch] │
├──────────┬────────────────────────────────────────────────────────┤
│ Sidebar  │  Main content area                                     │
│ Watchlist│                                                        │
│ Sectors  │                                                        │
└──────────┴────────────────────────────────────────────────────────┘
```

#### Views

**1. Analysis Feed** (default home view)
- Chronological stream of completed analyses, newest first
- Each card shows: ticker, sector, overall signal (bullish/bearish/neutral badge), conviction level, one-line summary, timestamp
- Infinite scroll with skeleton loaders
- Filter bar: signal type, sector, conviction level, date range
- Live indicator when a new analysis just landed

**2. Stock Detail View** (`/stock/:ticker`)
- Hero: price chart (1D / 1W / 1M / 3M / 1Y toggles) with volume bars overlaid
- Tabs: Overview | Technicals | Fundamentals | Insider | Institutional | Sentiment | AI Summary
- Each tab renders agent-specific sub-report as interactive visuals
- Timeline of past AI analyses for this ticker — see how the signal has shifted over time
- Quick-add to watchlist button

**3. Institutional Flow** (`/institutional-flow`)
- Standalone, market-wide live feed of new 13F and superinvestor moves — not scoped to any single ticker
- Each card: action badge (New Position / Add / Trim / Exit), fund → ticker, one-line headline, shares/value/% of portfolio, notability meter, timestamp
- Filter bar: action type, fund, ticker, minimum notability
- "Scan Now" button for a manual pull, consistent with the app's no-polling model
- Clicking the ticker navigates into that stock's full Stock Detail view; linked reciprocally from the Stock Detail Institutional tab

**4. Sector View** (`/sectors/:sector`)
- All tickers in sector mapped on a signal heatmap (green = bullish, red = bearish, size = market cap)
- Sorted list below with most recent signal and key metrics
- Sector-level macro context (e.g., Fed rate impact on Financials)

**5. Search**
- Global search in the nav — instant autocomplete by ticker and company name
- Results show last signal + conviction inline

**6. Watchlist**
- Pinned tickers, always visible in sidebar
- At-a-glance signal badges update after each run

#### Interactive Visuals (per Stock Detail)

| Tab | Visuals |
|---|---|
| Technicals | Price + volume chart, NYMO/NAMO oscillator chart, gap score meter, accumulation score gauge (0–5), momentum sparklines |
| Fundamentals | Revenue/earnings YoY bar charts, margin trend lines, key ratio cards (P/E, EV/EBITDA, FCF yield), earnings surprise history |
| Insider | Timeline of Form 4 filings plotted on price chart, cluster buying heatmap by month, buy/sell ratio donut |
| Institutional | 13F ownership % change over quarters, superinvestor overlap count, new positions vs. exits table |
| Sentiment | Earnings call tone score over quarters, keyword frequency bar chart (bullish vs. cautious terms), QoQ tone delta |
| AI Summary | Full synthesis report with collapsible per-agent breakdowns, conviction indicator, key flags/alerts |

#### Filters & Search

- Filter analysis feed by: sector, signal (bullish/bearish/neutral), conviction (high/med/low), date range
- Filter institutional flow feed by: action (new position/add/trim/exit), fund, ticker, minimum notability
- Stock search: instant lookup by ticker or company name
- Sector page: sort by signal strength, market cap, or last updated
- All filter state persisted in URL params (shareable, bookmarkable)

---

## Project Scaffold

```
stockai/
│
├── docker-compose.yml               # Orchestrates all services
├── .env                             # API keys, Mongo URI, Ollama URL
├── .env.example                     # Committed template (no secrets)
│
├── logs/                            # Root log directory — one subfolder per component, bind-mounted into containers
│   ├── agent-runner/                # agent-runner.log (.gitkeep until first run)
│   ├── backend/                     # backend.log
│   ├── frontend/                    # frontend.log (written by backend via POST /logs/frontend)
│   └── scripts/                     # scripts.log
│
├── agent-runner/                    # CrewAI pipeline — queue worker
│   ├── Dockerfile
│   ├── main.py                      # Entry point: polls work_queue every 30s, runs InstitutionalFlowWorker on its own daily timer
│   ├── logging_config.py            # get_logger(component) — file-based today, swappable sink later
│   ├── queue_worker.py              # Claims jobs, dispatches crew, marks done/failed
│   ├── crew.py                      # Assembles and kicks off the CrewAI crew per ticker
│   ├── institutional_flow_worker.py # Runs InstitutionalFlowScannerAgent on a daily schedule (not per-ticker)
│   │
│   ├── agents/                      # One file per CrewAI agent
│   │   ├── technical_analyst.py
│   │   ├── fundamental_analyst.py
│   │   ├── macro_analyst.py
│   │   ├── insider_analyst.py
│   │   ├── institutional_analyst.py
│   │   ├── sentiment_analyst.py
│   │   ├── recommender_agent.py
│   │   ├── portfolio_strategist.py
│   │   ├── earnings_scanner.py      # Scores/ranks upcoming earnings candidates
│   │   ├── earnings_conversation.py # Conversational handoff agent
│   │   └── institutional_flow_scanner.py # Market-wide 13F/superinvestor scan → scored feed events
│   │
│   ├── tools/                       # Python functions bound to agents
│   │   ├── price.py                 # get_price_history, get_technical_indicators
│   │   ├── financials.py            # get_financials, get_earnings_data
│   │   ├── macro.py                 # get_macro_data (FRED)
│   │   ├── insider.py               # get_insider_activity
│   │   ├── institutional.py         # get_institutional_holdings, get_recent_13f_changes (market-wide)
│   │   ├── superinvestor.py         # Playwright fetches Dataroma pages → raw text → Ollama extracts structured JSON (no hardcoded selectors); get_recent_superinvestor_moves (market-wide)
│   │   ├── sentiment.py             # get_earnings_sentiment (Finnhub transcripts)
│   │   ├── breadth.py               # get_market_breadth (NYMO/NAMO)
│   │   ├── earnings_calendar.py     # get_earnings_calendar, get_earnings_history
│   │   └── db.py                    # query_db, write_db, register_ticker, mark_ticker_removed (MongoDB helpers)
│   │
│   ├── skills/                      # Pluggable analytical engines (each maps to a spec doc)
│   │   ├── the_strat.py             # Bar classification, reversals, TFC, actionable signals → the-strat-spec.md
│   │   ├── accumulation.py          # Institutional accumulation scoring → accumulation_volume_rules.md
│   │   ├── gap_analysis.py          # Gap type, score, fill probability → gap_analysis_rules.md
│   │   ├── market_flow.py           # NYMO/NAMO buy-more/trim signals → market_flow_rules.md
│   │   └── position_management.py   # Stair-step stops, trailing logic → position_management_agent_spec.md
│   │
│   ├── chunker/                     # Pre-processing before agents run
│   │   ├── chunker.py               # Splits large payloads into chunks
│   │   └── summarizer.py            # Summarizes chunks via Ollama before feeding agents
│   │
│   └── requirements.txt
│
├── api/                             # FastAPI backend
│   ├── Dockerfile
│   ├── main.py                      # App entry point, mounts routers, global exception_handler(Exception)
│   ├── logging_config.py            # get_logger(component) — same shape as agent-runner's, duplicated not shared
│   │
│   ├── routers/
│   │   ├── analysis.py              # GET /analysis/feed, /analysis/{ticker}, /analysis/sector/{sector}
│   │   ├── stocks.py                # GET /stocks/search, /stocks/{ticker}/financials, /signals
│   │   ├── macro.py                 # GET /macro
│   │   ├── watchlist.py             # GET/POST /watchlist
│   │   ├── sectors.py               # GET /sectors
│   │   ├── queue.py                 # POST /queue/all (Run All — sweeps ticker_index), POST /queue/{ticker}, GET /queue
│   │   ├── earnings.py              # GET /earnings/calendar (also registers+enqueues), POST /earnings/scan, POST /earnings/analyze
│   │   ├── institutional_flow.py    # GET /institutional/flow, /institutional/flow/{ticker}, POST /institutional/scan
│   │   └── logs.py                  # POST /logs/frontend — writes client error reports via get_logger("frontend")
│   │
│   ├── models/                      # Pydantic schemas
│   │   ├── analysis.py
│   │   ├── stock.py
│   │   ├── queue.py
│   │   ├── watchlist.py
│   │   ├── institutional_flow.py
│   │   └── ticker.py                # TickerRecord, TickerListResponse — the system-wide ticker registry
│   │
│   ├── registry.py                  # register_ticker() — shared upsert into ticker_index, called by queue/watchlist/earnings routers
│   ├── db.py                        # MongoDB connection + collection accessors
│   └── requirements.txt
│
├── frontend/                        # React + Vite app
│   ├── Dockerfile
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── package.json
│   │
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                  # Router setup
│       │
│       ├── pages/
│       │   ├── Feed.tsx             # Analysis feed (default home)
│       │   ├── StockDetail.tsx      # /stock/:ticker
│       │   ├── Sectors.tsx          # /sectors/:sector
│       │   ├── Watchlist.tsx
│       │   ├── EarningsScan.tsx     # /earnings — conversational scanner UI
│       │   └── InstitutionalFlow.tsx # /institutional-flow — market-wide flow feed
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Navbar.tsx
│       │   │   └── Sidebar.tsx
│       │   ├── feed/
│       │   │   ├── AnalysisCard.tsx
│       │   │   └── FilterBar.tsx
│       │   ├── stock/
│       │   │   ├── PriceChart.tsx
│       │   │   ├── TechnicalsTab.tsx
│       │   │   ├── FundamentalsTab.tsx
│       │   │   ├── InsiderTab.tsx
│       │   │   ├── InstitutionalTab.tsx
│       │   │   ├── SentimentTab.tsx
│       │   │   └── AISummaryTab.tsx
│       │   ├── queue/
│       │   │   ├── PullAllButton.tsx
│       │   │   └── QueueStatus.tsx
│       │   ├── earnings/
│       │   │   ├── EarningsCalendarTable.tsx  # Ranked candidate table
│       │   │   ├── EarningsCandidateCard.tsx  # Per-ticker score breakdown
│       │   │   └── ScanControls.tsx           # Days-ahead, market cap floor
│       │   ├── institutional/
│       │   │   ├── InstitutionalFlowCard.tsx     # Per-event card
│       │   │   ├── InstitutionalFlowFilterBar.tsx # Filters + Scan Now
│       │   │   └── ActionBadge.tsx                # New Position/Add/Trim/Exit pill
│       │   └── shared/
│       │       ├── SignalBadge.tsx
│       │       ├── ConvictionMeter.tsx
│       │       ├── TickerStatusBadge.tsx  # "Removed from Market" badge, renders nothing when active
│       │       ├── SkeletonCard.tsx
│       │       └── ErrorBoundary.tsx      # Top-level catch; reports via errorLogger.ts on render errors
│       │
│       ├── hooks/
│       │   ├── useAnalysis.ts
│       │   ├── useQueue.ts
│       │   ├── useWatchlist.ts
│       │   └── useInstitutionalFlow.ts
│       │
│       └── lib/
│           ├── api.ts               # Axios/fetch wrapper pointing at FastAPI
│           ├── constants.ts
│           └── errorLogger.ts       # window.onerror / onunhandledrejection hooks -> POST /logs/frontend
│
└── scripts/                         # One-off utility scripts (not in Docker)
    ├── seed_watchlist.py            # Pre-populate watchlist in MongoDB
    └── backfill_financials.py       # One-time historical data pull
```

---

## Docker Services

```yaml
services:
  mongodb:       # Document store — analysis results, cached financials, work_queue
  fastapi:       # REST API — serves the React app, exposes queue endpoints
                 # volumes: ./logs:/logs
  react:         # Frontend — Vite dev server (or static build served via nginx)
  agent-runner:  # CrewAI pipeline — polls work_queue every 30s, writes to MongoDB
                 # volumes: ./logs:/logs
  ollama:        # Local LLM inference
```
Each container mounts the whole `logs/` tree but only ever writes inside its own `logs/<component>/` subfolder (see "Exception Handling & Logging"). `frontend` doesn't need its own mount — client errors are relayed through `POST /logs/frontend` and land in `./logs/frontend` via the `backend` container.

---

## Notes & Open Questions

- Multi-user auth, data isolation, billing — will need design work if/when rolling out to others. No action yet.

---

## Resolved Decisions

### Deployment Target: Personal Use First
Initially personal use only — single user, no auth required, no multi-tenancy. If the product proves valuable, a future phase will add user accounts, data isolation, and billing before any public rollout. Build nothing for that now.

### Model: Ollama
Start with **`mistral:7b`** (fast, familiar). Upgrade to **`llama3.1:8b`** when context limits bite — it has 128k context vs. Mistral's 32k, which matters when a single stock run includes financials + transcript + insider data + news. `qwen2.5:14b` is best-in-class quality if VRAM allows.

### Context Length Strategy: Chunk and Summarize
Each agent receives **pre-chunked, pre-summarized** input — not raw API dumps. A data-prep step runs before agent execution: large payloads (transcripts, full financial history, news feeds) are chunked, each chunk summarized, then the summaries are merged into a single structured context block per agent. Each agent only receives data relevant to its domain.

### UI Data Refresh: Manual Pull (No Polling)
The frontend **does not poll**. The user manually triggers data pulls via two UI buttons:
- **"Pull All"** (Run All) — adds every ticker in the system-wide registry to the work queue (see "Ticker Registry & Delisting Detection" below) — not just the watchlist
- **"Pull [Ticker]"** — adds a single stock to the work queue

The page refreshes manually (F5 / browser refresh) to see new results. WebSocket live updates are a future enhancement.

### Agent-Runner: Queue-Based Work Loop
Instead of a fixed cron schedule, `agent-runner` operates as a **persistent queue worker**:
- Polls MongoDB (`work_queue` collection) every **30 seconds** for pending jobs
- Each job document contains: `{ ticker, status: "pending"|"running"|"done"|"failed", source, created_at, updated_at }`
- When a job is found, the agent-runner claims it (sets `status: "running"`), runs the full CrewAI pipeline for that ticker, writes results to MongoDB, then marks the job `done` — or `failed` (with `delisted: true`) if the ticker no longer has any data, see below
- Processes one ticker at a time (sequential), or N parallel workers if queue depth warrants it later
- UI buttons and automatic discovery paths all write to `work_queue` via a FastAPI endpoint or (for the institutional flow worker) directly to MongoDB; agent-runner consumes from there uniformly, regardless of which path created the job

#### New FastAPI Endpoints (Queue)

| Endpoint | Description |
|---|---|
| `POST /queue/all` | Run All — enqueue every `active` ticker in `ticker_index` (the system-wide registry), not just the watchlist |
| `POST /queue/{ticker}` | Enqueue a single ticker manually; reactivates it if it was previously flagged `removed_from_market` |
| `GET /queue` | Current queue state (pending + running jobs) |
| `GET /stocks/{ticker}` | Basic registry record (name, sector, status) for a ticker |
| `GET /tickers?status=` | Admin/debug view of the full ticker registry |

### Ticker Registry & Delisting Detection
A ticker can enter the system two ways:
1. **Manual** — the user types a ticker and pulls it, or adds it to the watchlist (`POST /queue/{ticker}`, `POST /watchlist`).
2. **Discovery** — a ticker surfaces from an earnings calendar pull (`GET /earnings/calendar`) or an institutional flow scan (`institutional_flow_worker.md`). Every ticker either source returns is automatically registered and enqueued — no user selection required for it to land in the queue.

Both paths write through `register_ticker()` (see `backend/db.md`) into `ticker_index` — a single collection that is simultaneously the ticker search index (`GET /stocks/search`) and the full universe **Run All** sweeps. `POST /queue/all` no longer looks at the watchlist at all; it queries `ticker_index` for everything `status: "active"` and enqueues it, so "Run All" really does mean "everything the system has ever seen," not "everything I've pinned."

**Delisting detection**: before a full crew run starts, `crew.py` checks `price_tool.is_ticker_valid(ticker)` (yfinance existence check). If that fails *and* the financials fetch also comes back empty, the ticker is presumed no longer to trade — `queue_worker.py` marks it `status: "removed_from_market"` in both `ticker_index` and (if present) `watchlist`, rather than letting it fail silently on every future Run All. The record and any past analyses are kept, not deleted, and the UI shows a muted "Removed from Market" badge (`TickerStatusBadge.md`) instead of hiding the ticker. A manual pull on a flagged ticker re-checks it and reactivates it if it now resolves.

---

*Last updated: 2026-08-02*
