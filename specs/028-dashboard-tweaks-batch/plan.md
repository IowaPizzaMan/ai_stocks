# Implementation Plan: Dashboard Tweaks Batch

**Branch**: `028-dashboard-tweaks-batch` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-dashboard-tweaks-batch/spec.md`

## Summary

Seven independent changes across the Stocks, Sectors, and stock-detail pages, plus one
new Congress page. Two are fixes to already-shipped surfaces (a broken ticker link; the
Portfolio Summary ignoring the feed filter), one is a removal (pull-cost diagnostics,
UI and storage), and four are additive (like/dislike tagging, a sector ETF comparison
chart, a most-actives panel, and a Congress disclosures page with a computed summary).

Technical approach: nothing here needs new infrastructure. The three new datasets
(sector ETF history, congressional disclosures, most-actives) are pulled by
`work_queue` admin jobs — two of which spec 017 already registered but never
implemented — into collections whose schemas 017 also already pinned, and are read back
by routers that only touch cache. Because 017's admin router was never built (R4),
each new surface gets its own small `POST /<area>/refresh` endpoint enqueueing its job,
mirroring the proven pattern in spec 027's digest panel rather than building an admin
API as a side effect. Sector history reuses `price_store` unchanged. The filter fix and
all summary math are pure functions with no LLM involvement.

The removal is net-negative surface area: one panel, one hook, one endpoint, one
writer, one collection, and two indexes all go away.

## Technical Context

**Language/Version**: Python 3.12 (backend, agent-runner), TypeScript / React 18 + Vite 5 (frontend)

**Primary Dependencies**: FastAPI, PyMongo (sync), TanStack Query v5, Recharts, React Router v6 — **no new dependencies in any service**

**Storage**: MongoDB 7.x — reuses existing `ticker_index` (+ `sentiment` field), `price_history`, `analyses`, `work_queue`, `portfolio_digest_cache` (+ `sector` on highlights); activates the already-declared `congress_trades` and `market_movers` constants; **drops** `pull_metrics`

**Testing**: pytest (routers, agent-runner tools, queue dispatch), Vitest + React Testing Library (components, hooks, pure helpers)

**Target Platform**: Self-hosted Docker Compose (single user, local-first)

**Project Type**: Web application (backend + frontend + agent-runner workers)

**Performance Goals**: Digest filtering is client-side array filtering over ≤25 highlights — instant, no network (SC-002). Sector chart serves ≤2,800 points at its widest window in one response. All provider work happens off the request path in queue jobs; no router blocks on FMP.

**Constraints**: No frontend polling beyond the sanctioned `useQueueStatus` busy-loop; all FMP access through `fmp_client.fmp_get`'s throttle + daily soft cap (14 calls per full refresh, R13); no LLM in any summary math (Principle III); `backend/db.py` and `agent-runner/tools/db.py` constants hand-synced (Principle VI)

**Scale/Scope**: 1 user; 11 fixed sector ETFs; digest highlights capped at 25; Congress summary over a rolling 90-day window

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First & Comprehensive Coverage | PASS | Every new deterministic surface is a pure function with an exhaustive case table: `filterHighlights` (4 dimensions × combinations), `rebaseToPercent`, `rank_most_bought`, `high_dollar` + bracket parsing (including unparseable/absent), and the congress row normalizer. Routers get contract tests; the three new job handlers get success/empty/provider-failure tests; frontend panels get RTL coverage for loading/empty/error/populated states. |
| II. Spec-Driven Development | PASS | Spec written and clarified (5 questions) before planning. All five answers are load-bearing here: Q1→R2, Q2→R6, Q3→R8, Q4→R11, Q5→R12. |
| III. Deterministic Core, LLM at the Edges | PASS | No LLM is added anywhere. The Congress summary is arithmetic (R8). Digest highlight filtering is a predicate (R2). `sector` is joined onto highlights deterministically *after* the model returns, so the model cannot invent it (R3). The existing digest agent is unchanged. |
| IV. Cache-Aware, Budget-Conscious Data Access | PASS | All 14 new provider calls route through `fmp_client.fmp_get` / `fetch_eod_history`, inheriting the throttle, daily soft cap, and `FmpBudgetExceededError` fail-soft path. Routers read cache only — no provider call in any GET. Each job isolates failures per sub-unit so one bad ETF cannot abort the other ten (R13). |
| V. Simplicity & Local-First Scope | PASS | No new service, queue, scheduler, or dependency. Refresh reuses `work_queue` via the pattern spec 027 already proved (R4). Sector history reuses `price_store` unchanged (R5). Like/dislike is one nullable field on an existing document rather than a new collection (R11). Movers implements only the category with a consumer (R9). The batch's net effect on collections is **zero new, one dropped**. |
| VI. Consistency Across Layers | PASS | `congress_trades` and `market_movers` use the schemas spec 017 already pinned rather than parallel shapes (R7, R9); the dead legacy `congressional_trades` name stays retired as 017 directed. New/removed constants are mirrored in both `db.py` files. The one deliberate deviation from 017 (Congress read path, R10) is recorded *in* 017's contract rather than left as silent drift. |

**Post-Phase-1 re-check (2026-08-22)**: All six still PASS. Phase 1 introduced no new
collection (the two "new" ones were already-declared constants), no new dependency, and
no LLM call. The one addition beyond the literal spec — a catch-all `*` route (R1) — is
five lines and *reduces* a failure class rather than adding capability, so it does not
warrant a Complexity Tracking entry. `sentiment` on `ticker_index` and `sector` on digest
highlights are additive nullable fields requiring no migration.

## Project Structure

### Documentation (this feature)

```text
specs/028-dashboard-tweaks-batch/
├── plan.md              # This file
├── research.md          # Phase 0 output (R1–R13)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── portfolio-digest-filtering.md   # US1/US2 — link fix, filter predicate, sector join
│   ├── stock-sentiment-api.md          # US3 — like/dislike + feed filter
│   ├── congress-api.md                 # US4 — list, summary, refresh, pull job
│   ├── sector-etf-series-api.md        # US5 — series endpoint, refresh, pull job
│   ├── market-movers-api.md            # US6 — most-actives read + refresh
│   └── pull-metrics-removal.md         # US7 — ordered removal inventory
├── checklists/
│   └── requirements.md  # Written by /speckit-specify
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/
├── db.py                              # + CONGRESS_TRADES/MARKET_MOVERS already present; − PULL_METRICS
├── main.py                            # + include_router(congress.router)
├── registry.py                        # unchanged
├── routers/
│   ├── analysis.py                    # + sentiment filter on GET /analysis/feed (two-step $in, R11)
│   ├── congress.py                    # NEW: GET /congress/trades, /congress/summary, POST /congress/refresh
│   ├── market.py                      # + GET /market/most-actives, POST /market/most-actives/refresh
│   ├── sectors.py                     # + GET /sectors/etf-series, POST /sectors/etf-series/refresh
│   └── stocks.py                      # + PUT/DELETE /stocks/{ticker}/sentiment; − GET /{ticker}/pull-metrics
└── tests/
    ├── test_congress.py               # NEW
    ├── test_sentiment.py              # NEW
    ├── test_sector_etf_series.py      # NEW
    └── test_market.py                 # + most-actives cases

agent-runner/
├── queue_worker.py                    # − _write_pull_metrics/_record_pull_metrics + 3 call sites
├── tools/
│   ├── db.py                          # − PULL_METRICS constant + its 2 index declarations
│   ├── admin_jobs.py                  # + congress_trades_pull, market_movers_pull, sector_etf_pull
│   ├── congress.py                    # NEW: fetch/normalize/upsert + rank_most_bought, high_dollar
│   ├── market_movers.py               # NEW: most-actives pull (category "actives", R9)
│   ├── sector_etfs.py                 # NEW: 11-ticker loop over price_store.get_series
│   ├── portfolio.py                   # + sector in _PROJECTION and post-LLM highlight join (R3)
│   └── price_store.py                 # unchanged — reused as-is (R5)
└── tests/
    ├── test_congress.py               # NEW: normalizer + both summary functions
    ├── test_market_movers.py          # NEW
    ├── test_sector_etfs.py            # NEW
    ├── test_portfolio_digest.py       # + sector join cases
    ├── test_admin_jobs.py             # + 3 new handler registrations
    └── test_queue_worker.py           # + dispatch tests; − pull-metrics tests

frontend/
├── src/
│   ├── App.tsx                        # + catch-all "*" NotFound route (R1)
│   ├── api/types.ts                   # + Sentiment, CongressTrade, CongressSummary, MostActive, SectorSeries; − Pull, PullStage
│   ├── lib/
│   │   ├── filterHighlights.ts        # NEW: pure digest-highlight predicate (R2)
│   │   └── rebaseToPercent.ts         # NEW: pure % rebasing (R6)
│   ├── hooks/
│   │   ├── useSentiment.ts            # NEW: set/clear mutations
│   │   ├── useCongress.ts             # NEW: trades + summary + refresh
│   │   ├── useSectorEtfSeries.ts      # NEW
│   │   ├── useMostActives.ts          # NEW
│   │   └── usePullMetrics.ts          # DELETED
│   ├── components/
│   │   ├── layout/Navbar.tsx          # + Congress nav entry
│   │   ├── feed/
│   │   │   ├── PortfolioDigestPanel.tsx   # link fix + filtered highlights + overview scope label
│   │   │   ├── FilterBar.tsx              # + liked/disliked filter buttons
│   │   │   └── MostActivesPanel.tsx       # NEW
│   │   ├── stock/
│   │   │   ├── SentimentButtons.tsx       # NEW: thumbs up/down, hidden when untracked
│   │   │   ├── PullCostPanel.tsx          # DELETED
│   │   │   └── PullCostPanel.test.tsx     # DELETED
│   │   ├── sectors/SectorEtfChart.tsx     # NEW: 11-line % chart + window selector
│   │   └── congress/
│   │       ├── CongressTable.tsx          # NEW
│   │       └── CongressSummary.tsx        # NEW
│   └── pages/
│       ├── Congress.tsx               # NEW
│       ├── Sectors.tsx                # + SectorEtfChart on the overview
│       ├── Stocks.tsx                 # + MostActivesPanel below the grid
│       └── StockDetail.tsx            # + SentimentButtons; − PullCostPanel + usePullMetrics
└── src/**/*.test.{ts,tsx}             # Vitest coverage per Principle I

specs/017-fmp-migration-admin/
└── contracts/market-data-api.md       # + supersession note for congress-trades path (R10)
```

**Structure Decision**: The existing three-service layout is kept unchanged. This feature
adds one backend router, three agent-runner tool modules, one frontend page, and five
components — all inside the established directories. No shared package is introduced
(Principle V); the collection constants and document shapes stay hand-synced between
`backend/db.py` and `agent-runner/tools/db.py` per the convention every other collection
already follows (Principle VI).

## Implementation Sequencing

The seven stories are independent, but two orderings matter:

1. **US7 (removal) frontend-first.** Delete the panel, hook, and types before the
   endpoint and writer, so no intermediate commit references a removed endpoint (R12).
2. **US4/US5/US6 job-before-router-before-page.** Each new surface needs its pull job
   writing real data before its read endpoint is meaningful to test against, and the
   Congress field-name fixture (R7) must be captured from a live response first.

US1 is a one-line fix and can land immediately and independently. US2, US3 are
independent of all provider work.

## Provider shapes — resolved 2026-08-22

The batch's one open risk (unverified Congress/movers response shapes) was closed by
user-supplied live responses. Four findings changed the design:

1. **No per-trade id.** `senateId` is a *person* id (bioguide) repeated across that
   member's rows, so `trade_id` must be a composite hash — and must include
   `transaction_type` and `owner`, or a same-day Purchase/Sale, or the same trade held
   Joint vs Self, would collide and silently overwrite (R7).
2. **`transaction_type` is `"Purchase"`/`"Sale"`**, capitalised — not `buy`/`sell`. The buy
   predicate matches `"purchase"` case-insensitively and must not count `"Sale (Full)"` /
   `"Sale (Partial)"` as buys.
3. **`most-actives` returns no `volume`.** The read path can no longer order by it, so the
   job stamps the provider's array position as `rank` and the endpoint sorts on that.
   Without this the panel would render in arbitrary order while looking authoritative (R9).
   `changesPercentage` is already a percent, not a fraction.
4. **`person_id` removes a spec limitation.** The spec's Edge Cases accepted that a member
   filing under varying name spellings could not be reconciled; a stable bioguide id means
   the person filter no longer has that weakness.

The sample data also validates R8's window choice concretely: one row was disclosed
2026-08-20 for a trade made 2025-04-08 — a 16-month lag. A `transaction_date` window would
have hidden it entirely.

Residual risk is low: exact JSON key casing is still unconfirmed (the user supplied display
labels), so the normalizer keeps its candidate-key-set tolerance and the first task remains
capturing a fixture — now a verification step rather than a discovery step.

## Complexity Tracking

No constitution violations — table intentionally empty.
