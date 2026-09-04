# Implementation Plan: Stocks Page Organization, Conviction Rework & Activity Trail

**Branch**: `037-stocks-conviction-and-activity` | **Date**: 2026-09-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/037-stocks-conviction-and-activity/spec.md`

## Summary

Five deliverables across the deterministic core, the API, and the board UI:

1. **Conviction becomes a rule, not an LLM opinion.** A new pure skill `agent-runner/skills/conviction.py` derives `high | medium | low` from three stock-specific entry strategies (`the_strat`, `accumulation`, `gap_analysis`), the daily+weekly price z-score's position in its own trailing distribution, and quarterly revenue trend (YoY growth + no QoQ sequential decline). `crew.py` runs it after the existing skills and **overwrites** the `portfolio_strategist` LLM's `conviction` field; the LLM keeps `signal` and prose. This is a straight application of Constitution Principle III — the "everything is a 3" bug is exactly the failure mode that principle predicts.

2. **Board ordering.** The analyses document gains a numeric `conviction_rank` (3/2/1/0) written alongside `conviction`, so `GET /analysis/feed` can `.sort([("conviction_rank", -1), ("ticker", 1)])`. Because `analyses` is one document per ticker (unique index) this is a *total* order, so any signal-group subset of it is already conviction-desc-then-A→Z, and skip/limit paging over it makes "Load more" strictly append (FR-003). `groupBySignal` stops re-sorting by timestamp and preserves server order.

3. **Activity feed + change history from one event log.** A new append-only `stock_events` collection serves both: US3's global feed is the last 100 events, US5's per-stock trail is that ticker's events. Per clarification Q5 the feed logs *every* re-analysis, flagging the ones that moved signal/conviction — which makes the feed a superset of the change history and means one collection, one writer path, no duplication.

4. **Breadcrumbs (navigational).** Pure frontend: a route-derived `<Breadcrumbs>` in the layout. No API, no data.

5. **Revenue inputs.** *(Corrected during implementation — see research.md R4 Amendment: the plan originally called for widening `financials.py`'s `income_quarterly` limit 4→8, but `KNOWN_ISSUES.md` documents that this FMP plan 402s the entire call beyond ~4 quarterly periods, which would have broken the existing fetch instead of adding rows.)* Both figures are derivable today with **no endpoint change**: YoY reuses the already-cached annual `growth[0].growthRevenue` figure (the same value `tools/screener.py` already computes under a different field name); QoQ compares `income_quarterly[0]` vs `[1]`, needing only 2 of the 4 quarters already cached.

## Technical Context

**Language/Version**: Python 3.12 (backend + agent-runner), TypeScript 5 / React 18 (frontend)

**Primary Dependencies**: FastAPI + Uvicorn, Pydantic v2, PyMongo (sync), CrewAI, pandas + pandas-ta, Ollama; React 18 + Vite 5, Tailwind CSS v4, TanStack Query v5, React Router v6, Recharts

**Storage**: MongoDB 7.x. Touched collections: `analyses` (two new fields + one new index), `ticker_index` (read), `price_history` (read), `financials_cache` (read; endpoint limit change), and one new collection `stock_events`.

**Testing**: pytest (backend + agent-runner, separate venvs), Vitest + React Testing Library (frontend), `ruff` for both Python services

**Target Platform**: Self-hosted Docker Compose stack (`mongodb`, `backend`, `frontend`, `agent-runner`, `ollama`), single local user

**Project Type**: Web application — `backend/` (FastAPI) + `frontend/` (React SPA) + `agent-runner/` (worker & rule engine)

**Performance Goals**: Board first paint unchanged (feed stays one indexed query + one `ticker_index` lookup per page). Conviction computation is pure CPU over already-fetched `price_history` / `financials_cache` — target < 50 ms per ticker, no new network calls. Activity feed query served by a single indexed sort, capped at 100 documents.

**Constraints**: Zero new external API calls (Principle IV) — the revenue change is a wider `limit` on an FMP call already made and cached for 90 days. No polling (`refetchInterval: false`). Page must stay within its bounded viewport-relative layout; only the grid region scrolls.

**Scale/Scope**: Single user; a few hundred tracked tickers; `stock_events` grows by ~1 document per completed analysis, served capped at 100.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Verdict |
|-----------|------|---------|
| **I. Test-First & Comprehensive Coverage** | New rule-engine skill must have an exhaustive pytest suite; routers need contract tests; frontend logic needs Vitest coverage | **PASS (binding)** — `skills/conviction.py` is a pure function and becomes the highest-value new test surface: per-condition truth-table tests, boundary tests (25th-percentile inclusive), and missing-data tests. Plus `test_stock_events.py` (agent-runner writer), `backend/tests/test_events_router.py`, `test_analysis_feed_ordering.py`, and Vitest for `groupFeed`, `ActivityFeed`, `Breadcrumbs`, `ChangeHistory`. |
| **II. Spec-Driven Development** | Feature originates from a spec | **PASS** — `specs/037-stocks-conviction-and-activity/spec.md`, 7 clarifications resolved. |
| **III. Deterministic Core, LLM at the Edges** | Skills stay pure `run(ticker, data) -> dict`; agents must not override computed results | **PASS — and this is the point of the feature.** Conviction moves *out* of `portfolio_strategist`'s LLM schema and *into* a pure skill. `crew.py` overwrites the LLM's conviction with the computed one; the LLM's remaining role is `signal` + prose. The rationale is assembled from rule output, not model narration (FR-028). |
| **IV. Cache-Aware, Budget-Conscious Data Access** | No ad-hoc external calls; respect TTLs and the FMP budget guard | **PASS** — conviction reads only `price_history` and `financials_cache` through existing accessors, with zero new or widened FMP calls (research R4 Amendment: an earlier `limit=4→8` change was reverted during implementation after `KNOWN_ISSUES.md` surfaced that this FMP plan 402s the whole call beyond ~4 quarterly periods). |
| **V. Simplicity & Local-First Scope** | No new infrastructure ahead of need; triggering flows through `work_queue`; frontend never polls | **PASS** — one new collection, no new service, no scheduler. Events are written inline on the existing analysis-persist path. The activity feed fetches on navigation only. Deliberately **one** `stock_events` collection serves both US3 and US5 rather than two. |
| **VI. Consistency Across Layers** | `backend/` and `agent-runner/` must agree on collection/field names and enums; any collection admitted to `READABLE_COLLECTIONS` needs mirrored field-vocabulary tests in both services | **PASS with an explicit scope decision** — `STOCK_EVENTS` and the `conviction_rank` mapping are mirrored constants in `agent-runner/tools/db.py` and `backend/db.py` with a mirrored contract test on each side. **`stock_events` is deliberately NOT added to `query_guard.READABLE_COLLECTIONS`** this feature (see research R9), so the semantic-layer obligation is not triggered. Admitting it later requires the mirrored field-vocabulary pair first. |

**Result: PASS — no violations, Complexity Tracking table not required.**

Re-check after Phase 1 design: **still PASS.** The design added no new service, no new external call, no scheduler, and no semantic-layer surface. The one judgement call (two writers must emit `added` events — `backend/routers/queue.py` and `agent-runner/tools/db.py::register_ticker`) is exactly the cross-layer duplication Principle VI anticipates, and is covered by a mirrored constant plus a test on each side.

## Project Structure

### Documentation (this feature)

```text
specs/037-stocks-conviction-and-activity/
├── plan.md              # This file
├── spec.md              # Feature specification (7 clarifications resolved)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── conviction-rules.md    # The deterministic rating contract
│   ├── feed-ordering.md       # GET /analysis/feed ordering & paging contract
│   └── stock-events-api.md    # Activity feed + per-stock history endpoints
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
agent-runner/
├── skills/
│   └── conviction.py             # NEW — pure rating rules (US2)
├── tools/
│   ├── db.py                     # STOCK_EVENTS const, indexes, record_event(),
│   │                             #   register_ticker() emits "added"
│   └── revenue.py                # NEW — pure YoY/QoQ derivation from cached statements
│                                  #   (financials.py itself is unchanged — see research R4 Amendment)
├── crew.py                       # runs conviction skill; overwrites synthesis conviction
├── queue_worker.py               # emits "updated" event on analyses write
├── agents/
│   └── portfolio_strategist.py   # conviction removed from LLM schema
└── tests/
    ├── test_conviction.py        # NEW — exhaustive rule suite
    ├── test_revenue.py           # NEW
    └── test_stock_events.py      # NEW — writer + mirrored field contract

backend/
├── db.py                         # STOCK_EVENTS const + indexes (mirrors agent-runner)
├── routers/
│   ├── analysis.py               # feed sort -> (conviction_rank desc, ticker asc)
│   ├── events.py                 # NEW — GET /events, GET /events/{ticker}
│   └── queue.py                  # ticker registration emits "added"
├── main.py                       # register events router
├── scripts/ or tools/
│   └── backfill_stock_events.py  # NEW — one-time "added" back-fill (FR-021a)
└── tests/
    ├── test_events_router.py     # NEW
    ├── test_analysis_feed_ordering.py  # NEW
    └── test_stock_events_contract.py   # NEW — mirrors agent-runner's field test

frontend/src/
├── components/
│   ├── feed/
│   │   └── ActivityFeed.tsx      # NEW — last-100 paged activity area (US3)
│   ├── layout/
│   │   └── Breadcrumbs.tsx       # NEW — route-derived trail (US4)
│   └── stock/
│       └── ChangeHistory.tsx     # NEW — per-stock verdict trail (US5)
├── hooks/
│   └── useStockEvents.ts         # NEW
├── lib/
│   ├── groupFeed.ts              # stop re-sorting by timestamp; preserve server order
│   └── breadcrumbs.ts            # NEW — pure path -> trail derivation
├── pages/
│   ├── Stocks.tsx                # mount ActivityFeed
│   └── StockDetail.tsx           # mount ChangeHistory
├── api/types.ts                  # StockEvent, ConvictionDetail, conviction_rank
└── App.tsx                       # mount Breadcrumbs in layout
```

**Structure Decision**: The existing three-directory web layout (`backend/`, `frontend/`, `agent-runner/`) is used unchanged. Work splits cleanly along the deterministic-core boundary: all rating logic lands in `agent-runner/skills/` as pure functions, all serving logic in `backend/routers/`, all presentation in `frontend/src/`. No shared package is introduced (Principle V); the two duplicated constants (`STOCK_EVENTS`, the conviction rank map) are kept honest by mirrored contract tests (Principle VI).

## Complexity Tracking

> Not required — Constitution Check passed with no violations.
