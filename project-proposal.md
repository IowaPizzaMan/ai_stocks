# StockAI — Project Structure & Tech Stack Proposal

> Derived from `specs/SPEC.md`, `specs/architecture.mermaid`, `specs/DATA_SOURCES.md`, the five rule specs, and the 60+ component specs in `specs/component-specs/`. The specs prescribe most of the architecture; this document consolidates those decisions into a concrete, buildable stack, resolves ambiguities, and flags risks.

---

## 1. System Summary

A local-first, single-user stock research app with three moving parts around a shared MongoDB:

```
[React UI] → [FastAPI] → [MongoDB] ← [Agent Runner (CrewAI + Ollama)]
                                          ↑
                              [External data sources: yfinance, FMP,
                               Finnhub, FRED, SEC EDGAR, Dataroma]
```

- **Agent runner** is a persistent queue worker: it polls a `work_queue` collection every 30s, runs a CrewAI multi-agent pipeline per ticker via a local Ollama LLM, and writes results to MongoDB. A separate daily-timer worker handles the market-wide institutional flow scan.
- **FastAPI** is a thin read/write layer between MongoDB and the UI (plus queue-trigger endpoints and one streaming chat endpoint for the earnings scanner).
- **React UI** never polls; the user triggers pulls manually ("Pull All" / "Pull [Ticker]" / "Scan Now") and refreshes to see results.
- Everything runs in Docker Compose on a self-hosted GPU server (dev on the Windows machine, deploy to the server). No cloud hosting, no auth, no multi-tenancy (explicitly deferred in Resolved Decisions).

---

## 2. Tech Stack

### Backend & Agent Runner (Python)

| Concern | Choice | Rationale |
|---|---|---|
| Language | **Python 3.12** | CrewAI, yfinance, and all data libs are Python-native; one language for API + agents |
| API framework | **FastAPI + Uvicorn** | Spec-mandated; async-capable, Pydantic-integrated, automatic OpenAPI docs |
| Schemas | **Pydantic v2** | Required by current FastAPI/CrewAI; component-specs' models map 1:1 to Pydantic models |
| MongoDB driver | **PyMongo (sync)** in both services | `specs/data_fetcher.py` is already written against PyMongo. Single user = no async pressure; FastAPI runs sync endpoints in its thread pool. Skip Motor unless profiling says otherwise |
| Agent framework | **CrewAI** | Spec-mandated. Agents defined one-per-file with role/goal/tools per component-specs |
| LLM runtime | **Ollama** (Docker service) | Spec-mandated, all inference on-device. Start `mistral:7b`, upgrade path `llama3.1:8b` (128k context) per Resolved Decisions; `qwen2.5:14b` if VRAM allows |
| LLM client | **`ollama` Python client + CrewAI's LLM wrapper** (LiteLLM under the hood) | CrewAI talks to Ollama natively via `ollama/mistral:7b` model strings |
| Technical indicators | **pandas + pandas-ta** | Pure-Python install (TA-Lib needs a C library — avoid on Windows/Docker unless a specific indicator demands it) |
| Data sources | **yfinance, fredapi, finnhub-python, requests (FMP), quiverquant** | Matches `data_fetcher.py` dependency list |
| Scraping | **Playwright (Python)** | Spec-mandated for Dataroma: fetch page → raw text → Ollama extracts structured JSON (no brittle selectors) |
| Scheduling | **Plain loops in `main.py`** (30s queue poll; daily timer for institutional flow) | Spec explicitly rejects cron in favor of the queue-worker model; no APScheduler/Celery needed |
| Testing | **pytest** | Skills (`the_strat`, `accumulation`, `gap_analysis`, `market_flow`, `position_management`) are pure rule engines — spec says they're "tested independently", which is the highest-value test surface |
| Lint/format | **ruff** (lint + format) | One tool, fast, standard |

### Frontend (TypeScript)

| Concern | Choice | Rationale |
|---|---|---|
| Framework | **React 18 + Vite 5 + TypeScript** | Spec-mandated (React + Vite); TS matches the `.tsx` scaffold |
| Styling | **Tailwind CSS v4** | Spec-mandated; dark-mode-first premium fintech design |
| Data fetching | **TanStack Query v5 (React Query)** | Spec-mandated; hooks (`useAnalysis`, `useQueue`, …) map directly to query/mutation hooks. Configure `refetchInterval: false` everywhere — the app's no-polling model |
| Charts | **Recharts** | Spec-mandated (price/volume, oscillators, gauges, heatmaps, sparklines) |
| Animation | **Framer Motion** | Spec-mandated |
| Routing | **React Router v6** | Standard for the spec'd routes (`/`, `/stock/:ticker`, `/sectors/:sector`, `/earnings`, `/institutional-flow`, `/watchlist`) |
| HTTP client | **Axios** via a single `lib/api.ts` wrapper | Spec names Axios; one place to set the FastAPI base URL |
| URL filter state | **React Router search params** | Spec requires all filter state in URL params (shareable/bookmarkable) |
| Testing | **Vitest + React Testing Library** | Native to Vite |

### Infrastructure

| Concern | Choice | Rationale |
|---|---|---|
| Orchestration | **Docker Compose** — 5 services: `mongodb`, `fastapi`, `react`, `agent-runner`, `ollama` | Spec-mandated service list |
| Database | **MongoDB Community 7.x** | Spec-mandated; collections per architecture diagram: `analyses`, `work_queue`, `watchlist`, `financials_cache` (90-day TTL), `transcripts_cache` (permanent), `macro_cache` (24h TTL), `institutional_cache`, `earnings_scans`/`earnings_cache`, `institutional_flow`(+`_meta`), `ticker_index` |
| TTLs | **MongoDB TTL indexes** on cache collections | Native expiry beats hand-rolled cleanup; permanent collections simply omit the index |
| Config | **`.env` + `.env.example`**, loaded via `pydantic-settings` | Spec-mandated; keys: FMP, Finnhub, FRED, Quiver, Mongo URI, Ollama URL |
| GPU | Ollama container with NVIDIA GPU passthrough on the target GPU server | Deployment target is a large GPU server; server-class VRAM makes `qwen2.5:14b` the sensible default model |
| Dev on frontend | Vite dev server in Docker for dev; `nginx`-served static build as the production-ish mode | Spec allows either |

---

## 3. Repository Structure

One repo, three deployable units plus shared config. This follows the SPEC.md scaffold with **one deliberate change**: the API service directory is named **`backend/`**, not `api/` — the component-specs tree (`specs/component-specs/backend/…`) and SPEC.md's own cross-references (e.g. "`backend/db.md`") already use `backend`, so the code should match the specs' naming.

```
ai-stock/
│
├── docker-compose.yml               # 5 services: mongodb, backend, frontend, agent-runner, ollama
├── .env / .env.example
├── project-proposal.md              # this document
├── specs/                           # (existing) source-of-truth specs
│
├── agent-runner/                    # CrewAI pipeline — queue worker
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                      # Entry: 30s work_queue poll + daily institutional-flow timer
│   ├── queue_worker.py              # Claim job → run crew → mark done/failed (+ delisting detection)
│   ├── crew.py                      # Assembles crew per ticker; parallel prefetch (ThreadPoolExecutor)
│   ├── institutional_flow_worker.py # Market-wide daily scan (own timer, not per-ticker)
│   ├── agents/                      # 11 agents, one file each (per component-specs/agent-runner/agents/)
│   ├── tools/                       # price, financials, macro, insider, institutional,
│   │                                #   superinvestor (Playwright), sentiment, breadth,
│   │                                #   earnings_calendar, db
│   ├── skills/                      # the_strat, accumulation, gap_analysis, market_flow,
│   │                                #   position_management — pure rule engines, one per rule spec
│   ├── chunker/                     # chunker.py + summarizer.py (pre-agent data prep via Ollama)
│   ├── data_fetcher.py              # Adapted from specs/data_fetcher.py — cache-aware fetch layer
│   └── tests/                       # pytest; skills get exhaustive rule-level tests
│
├── backend/                         # FastAPI service  ← named to match component-specs
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                      # App entry, mounts routers, CORS for the frontend
│   ├── db.py                        # Mongo connection + collection accessors + index bootstrap
│   ├── registry.py                  # register_ticker() shared upsert into ticker_index
│   ├── routers/                     # analysis, stocks, macro, watchlist, sectors, queue,
│   │                                #   earnings (incl. streaming chat), institutional_flow
│   ├── models/                      # Pydantic: analysis, stock, queue, watchlist,
│   │                                #   institutional_flow, ticker
│   └── tests/
│
├── frontend/                        # React + Vite + TS
│   ├── Dockerfile
│   ├── package.json / vite.config.ts / tailwind.config.ts / index.html
│   └── src/
│       ├── main.tsx / App.tsx       # Router setup
│       ├── pages/                   # Feed, StockDetail, Sectors, Watchlist,
│       │                            #   EarningsScan, InstitutionalFlow
│       ├── components/
│       │   ├── layout/              # Navbar, Sidebar
│       │   ├── feed/                # AnalysisCard, FilterBar
│       │   ├── stock/               # PriceChart + 6 tab components
│       │   ├── queue/               # PullAllButton, QueueStatus
│       │   ├── earnings/            # EarningsCalendarTable, EarningsCandidateCard, ScanControls
│       │   ├── institutional/       # InstitutionalFlowCard, FilterBar, ActionBadge
│       │   └── shared/              # SignalBadge, ConvictionMeter, TickerStatusBadge, SkeletonCard
│       ├── hooks/                   # useAnalysis, useQueue, useWatchlist, useInstitutionalFlow,
│       │                            #   useEarningsScan
│       └── lib/                     # api.ts (Axios), constants.ts
│
└── scripts/                         # One-off utilities, run outside Docker
    ├── seed_watchlist.py
    └── backfill_financials.py
```

**Not shared as a Python package**: `backend/` and `agent-runner/` both talk to MongoDB but ship as separate Docker images with separate `requirements.txt`. The only truly shared logic (ticker registration semantics, collection names) is small; duplicate the constants rather than adding a shared-package build step. Revisit if drift becomes a problem.

---

## 4. Docker Compose Sketch

```yaml
services:
  mongodb:
    image: mongo:7
    ports: ["27017:27017"]
    volumes: [mongo_data:/data/db]

  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes: [ollama_models:/root/.ollama]
    deploy:                       # target host is a GPU server — passthrough via nvidia-container-toolkit
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [mongodb]

  agent-runner:
    build: ./agent-runner        # includes Playwright + Chromium (use the MS Playwright base image)
    env_file: .env
    depends_on: [mongodb, ollama]

  frontend:
    build: ./frontend
    ports: ["5173:5173"]         # Vite dev; nginx static build for "prod" profile
    depends_on: [backend]
```

---

## 5. Key Design Decisions Restated (from the specs — build to these)

1. **Queue-based, not cron.** All analysis flows through `work_queue`; the runner claims jobs (`pending → running → done/failed`). UI buttons, earnings-calendar discovery, and the institutional flow worker all enqueue through the same mechanism.
2. **`ticker_index` is the universe.** Every ticker entering the system (manual or discovered) passes through `register_ticker()`. "Run All" sweeps `ticker_index` where `status: "active"` — not the watchlist. Delisting detection marks `removed_from_market` instead of deleting.
3. **Cache-first data layer.** Adapt `specs/data_fetcher.py`: first fetch stores full history; later fetches fill only the gap. This is what keeps FMP under 250 calls/day. Financials re-fetch only on new quarter; macro 24h TTL; transcripts permanent.
4. **Chunk-and-summarize before agents.** No raw API dumps into a 7B model. The chunker splits large payloads, Ollama summarizes each chunk, and each agent receives only its domain's merged summary.
5. **Skills are pure functions.** Each of the five rule specs becomes a deterministic `skill.run(ticker, data) -> dict` module with no LLM calls inside — the LLM interprets skill output, it doesn't compute it. This makes the core analytics unit-testable.
6. **No polling anywhere.** Frontend fetches on navigation and manual triggers only. WebSockets are explicitly a future enhancement.
7. **LLM extraction over brittle scraping.** Dataroma pages go Playwright → raw text → Ollama → structured JSON; no hardcoded CSS selectors.

---

## 6. Suggested Build Phases

| Phase | Deliverable | Proves |
|---|---|---|
| **0. Skeleton** | Compose file with all 5 services up; health endpoints; Mongo indexes bootstrapped; Ollama pulls `mistral:7b` | Environment works end-to-end on this machine |
| **1. Data layer** | Port `data_fetcher.py` into `agent-runner/`; tools for price/financials/macro/insider with Mongo caching; `ticker_index` + `register_ticker()` | API budgets hold; cache math is right |
| **2. Skills** | All five skill modules with pytest suites against the rule specs | Core analytics correct before any LLM is involved |
| **3. Crew MVP** | `work_queue` + `queue_worker` + crew with 3 agents (Technical, Fundamental, PortfolioStrategist); results in `analyses` | The CrewAI ↔ Ollama loop produces usable synthesis on a 7B model — the riskiest bet in the project |
| **4. API + Feed UI** | `backend/` routers for analysis/queue/watchlist/stocks; Feed page + Stock Detail (Overview + AI Summary tabs); Pull buttons | Full vertical slice: click Pull → analysis appears |
| **5. Full agent roster** | Remaining agents (Macro, Insider, Institutional, Sentiment, Recommender), chunker/summarizer, all Stock Detail tabs | Complete per-ticker experience |
| **6. Earnings Scanner** | Calendar tools, scanner + conversation agents, streaming chat endpoint, EarningsScan page | Second run mode + conversational handoff |
| **7. Institutional Flow** | Daily worker, flow scanner agent, Dataroma Playwright pipeline, flow feed page | Market-wide discovery loop |

Phase 3 is deliberately early and small: if `mistral:7b` can't reliably drive CrewAI tool-calling and synthesis, the mitigation (better model, tighter prompts, or moving more logic into deterministic skills) should be found before building eight more agents on top.

---

## 7. Risks & Open Questions

1. ~~**`$NYMO` / `$NAMO` availability on Yahoo.**~~ **RESOLVED (2026-08-02).** Verified that Yahoo carries none of the breadth symbols (`$NYMO`, `^NYMO`, `$NAMO`, `^NYAD`, `^TRIN` all return zero rows via yfinance), and neither FMP, Finnhub, nor FRED provide them. Solution — verified working end-to-end: compute the ratio-adjusted McClellan Oscillator locally from advance/decline counts over proxy universes (S&P 500 for NYMO, NASDAQ-100 for NAMO) using one batched `yf.download` per day, cached in a new `breadth_cache` collection. Return shape of `get_market_breadth()` is unchanged, so no downstream spec was affected. Residual caveat: proxy-universe values won't exactly match StockCharts' published numbers, so the ±60 zone thresholds should be calibrated against StockCharts during Phase 2. Specs updated: `market_flow_rules.md`, `component-specs/agent-runner/tools/breadth.md`, `SPEC.md`, `DATA_SOURCES.md`, `architecture.mermaid`.
2. **Small-model tool-calling reliability.** CrewAI agents driving tools through a 7B model can be flaky (malformed tool calls, ignored instructions). The chunk-and-summarize design and deterministic skills reduce the LLM's job to interpretation — keep pushing logic out of prompts if this bites. Budget for stepping up to `llama3.1:8b` or `qwen2.5:14b`.
3. **FMP free-tier ceiling (250/day).** "Run All" over a growing `ticker_index` plus the earnings sweep can exceed it. The cache-aware fetcher is the mitigation; add a call-counter/budget guard in the FMP client that fails soft (serve stale cache, log) rather than burning the day's quota.
4. **Dataroma scraping fragility & etiquette.** Playwright + LLM extraction avoids selector rot but not layout paywalls/blocks. Keep scan frequency at once daily, cache aggressively, and treat this source as best-effort.
5. **Sequential crew runtime.** ~8 agents × local 7B inference per ticker could mean minutes per ticker; a 100-ticker "Run All" may take hours. Acceptable for an overnight batch, but surface per-job timing in `QueueStatus` early so expectations are grounded.
6. ~~**Ollama on Windows/Docker.**~~ **RESOLVED.** Deployment target is a large GPU server, not the dev machine — Ollama runs as a Docker service with NVIDIA GPU passthrough (`nvidia-container-toolkit` + `deploy.resources.reservations.devices` in compose). With server-class VRAM available, default to **`qwen2.5:14b`** (the spec's best-in-class quality option) rather than starting at `mistral:7b`, and consider bumping `num_ctx` — context length, not model size, is the binding constraint for stuffing financials + transcripts into a run. Local dev on the Windows machine can still point at the server's Ollama endpoint via `OLLAMA_URL` in `.env`.
7. **Quiver Quantitative** (congressional trades) has no free tier of consequence — the spec lists it, but confirm the subscription before wiring `get_congressional_trades()`; otherwise stub it and defer.

---

## 8. What I'd Explicitly *Not* Build Yet

Per the specs' Resolved Decisions: no auth, no multi-user, no billing, no WebSocket live updates, no options/IV scoring (deferred in the earnings scanner weights), no cloud deployment. The structure above leaves room for all of them without committing code to any.
