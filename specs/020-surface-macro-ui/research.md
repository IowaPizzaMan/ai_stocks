# Research: Decouple Macro Analysis From Ticker Research

**Feature**: `specs/020-surface-macro-ui` | **Date**: 2026-08-15

No NEEDS CLARIFICATION markers remained in the Technical Context — the stack is fixed by the constitution and every touched surface already exists in the codebase. Research below records the design decisions where more than one implementation path was plausible.

## D1: How the independent macro refresh is scheduled

**Decision**: A new `agent-runner/macro_worker.py` with `run_macro_refresh_if_due(now, db=None, client=None)`, called every tick from `main.py`'s existing loop (same pattern as `breadth_worker.run_daily_breadth_if_due`). Gating is **staleness-driven, not meta-driven**: each invocation (throttled to at most one sweep per hour via a module-level in-process timestamp) enumerates active sectors from `ticker_index` and refreshes only sectors whose `macro_analysis_cache` doc is missing or older than 7 days (`CACHE_DAYS`, reused from `macro_analyst`).

**Rationale**:
- Reuses the loop that already exists (`main.py`) — no cron, no scheduler, per Constitution Principle V; matches how `breadth_worker` and `institutional_flow_worker` already integrate.
- The 7-day freshness contract already lives on the cache documents themselves (`computed_at` + the analyst's `CACHE_DAYS`); deriving "due" from the data avoids a second bookkeeping mechanism. `breadth_worker` needs its `breadth_meta` last-run key because its output is a daily append-only series; macro's cache doc *is* the state, so a separate meta key would be redundant.
- The hourly in-process throttle keeps the per-tick cost at zero for 59 of 60 minutes; the sweep itself is one indexed query over a ≤ ~11-doc collection. Single-process deployment (compose runs one agent-runner) makes an in-memory throttle safe.

**Alternatives considered**:
- *Meta-key daily gating like `breadth_worker`* (store `macro_last_run_at` in `breadth_meta`): works, but adds cross-purpose state in a collection named for breadth, and a failed partial sweep would either block retries for a day or need extra retry bookkeeping. Staleness-driven retries per sector are free.
- *Refresh on Macro-page request (backend-triggered)*: rejected — puts LLM latency (~minutes for 11 sectors on local Ollama) behind a page load and violates the "frontend fetches, never triggers analysis" grain of the app (all analysis flows through the agent-runner).
- *Ride the work_queue*: rejected — `work_queue` semantics are per-ticker; inventing a synthetic ticker for sector jobs contorts the queue contract (Principle VI).

## D2: What happens to `macro_analyst.run()`'s signature

**Decision**: Refactor to `run(sector: str, context: dict, client=None, db=None) -> dict`. Drop the `ticker` parameter and the ticker mentions in the prompt (the prompt already keyed almost entirely off sector; the ticker only appeared in two sentences). Keep the SCHEMA, the per-sector cache read/write, and `CACHE_DAYS = 7` exactly as they are. The worker is now the only caller.

**Rationale**: The clarified spec says macro is economy/sector-level, not ticker-level. The existing cache was already keyed by sector alone — the ticker in the prompt was cosmetic and occasionally misleading (an "AAPL" macro read served to AMD). Removing the parameter makes the contract honest and simplifies tests.

**Alternatives considered**: keeping `ticker: str | None = None` for backward compatibility — rejected; after crew.py stops calling it there is no other caller, and dead parameters invite drift.

## D3: What crew.py stops doing

**Decision**: Remove from `crew.py`: the `macro` and `yield_curve` prefetch jobs, the `macro_analyst` import and call, the `sector` lookup use for macro (the `record` lookup stays — sector still rides the final analysis doc top-level), and `"macro"` from `sub_reports`. `portfolio_strategist`'s SYSTEM prompt and instruction #2 lose their macro-weighting language ("macro alone is a mild concern…" etc.), per the spec's explicit tradeoff. `get_market_breadth` prefetch **stays** (gap_analysis, market_flow, and recommender still consume breadth).

**Rationale**: `get_macro_data` and `get_yield_curve_status` were prefetched solely for the macro analyst; fetching them per-ticker after decoupling would be waste. The strategist prompt change is required by FR-003 (verdict synthesized without macro as an input) — leaving the weighting language while the key is absent would instruct the LLM about an input that never arrives.

**Alternatives considered**: leaving the prompt untouched and relying on the missing key — rejected; the spec calls the removal intentional, and a prompt describing phantom inputs is exactly the kind of silent drift Principle II exists to prevent.

## D4: How the frontend gets macro reads

**Decision**: New `GET /market/macro` endpoint in the existing `backend/routers/market.py` (it already serves the other market-wide, ticker-less data: breadth and flow events). Response: `{"sectors": [ {sector, computed_at, ...read fields} ], "as_of": <newest computed_at>}` — all sector docs from `macro_analysis_cache`, newest first. `backend/db.py` gains `MACRO_ANALYSIS_CACHE = "macro_analysis_cache"` (Principle VI: both services name the shared collection identically).

**Rationale**: Read-only projection over what the agent-runner wrote is exactly the established pattern of `market.py` ("no computation here" per its docstring). One endpoint, one hook (`useMacroReads`), one page.

**Alternatives considered**: a new `/macro` router — rejected as unnecessary surface; the market router's charter ("market-wide, ticker-less") already covers it.

## D5: Feed → Stocks rename mechanics

**Decision**: Rename `frontend/src/pages/Feed.tsx` → `Stocks.tsx` (component `Stocks`, title `StockAI — Stocks`, nav label "Stocks", route stays `/`). Remove `MarketFlowCard`, `useMarketFlowEvents`, `useMarketBreadth`, and the pinned-events block from the page; `FilterBar`, tile board, infinite scroll, and empty states are untouched. `MarketFlowCard` and `BreadthDivergenceChart` components are **kept** and rendered by the new Macro page instead. `Feed.test.tsx` → `Stocks.test.tsx` with breadth-card assertions moved to `Macro.test.tsx`.

**Rationale**: FR-008/FR-009/FR-010. Renaming the file to match the page name keeps the codebase greppable; keeping the route at `/` satisfies "URL continues to work" with zero redirect machinery.

**Alternatives considered**: keeping the filename `Feed.tsx` with a `Stocks` component — rejected; filename/component mismatch is gratuitous confusion in a codebase where every other page file matches its component.

## D6: Historical `sub_reports.macro` in stored analyses

**Decision**: No migration, no purge. The `Analysis` TypeScript type keeps `macro?: MacroReport` as an optional field (documents written before this feature still contain it), but no component reads it. The feed projection and analysis endpoints are untouched.

**Rationale**: Spec assumption "No backfill required." Optional-and-unread is harmless; deleting the field from the type would misdescribe real stored documents.

## D7: Macro worker failure behavior

**Decision**: Per-sector try/except inside the sweep — one sector's LLM failure logs a warning and moves on; the stale doc stays served (fail-soft, matching Principle IV's "serve stale and log" posture). The hourly throttle timestamp advances even on partial failure, so a bad Ollama night costs at most one retry attempt per hour per stale sector, bounded by the sweep cadence.

**Rationale**: Matches the codebase's established degradation style (earnings theses, flow-scanner headlines, superinvestor fetch — all fail-soft with logging).
