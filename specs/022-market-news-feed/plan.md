# Implementation Plan: Market News Feed on the Stocks Page

**Branch**: `022-market-news-feed` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-market-news-feed/spec.md`

## Summary

Add a market-wide news panel below the stock grid on the Stocks page: the 20 most recent ticker-tagged stories, fetched when the page is opened, capped (no infinite scroll), never written into any ticker's analysis.

Technical approach: a new read-through endpoint `GET /market/news` on the existing `market` router serves articles from a new `market_news_cache` collection, refreshing from FMP `news/stock-latest` only when the cached copy is older than 60 minutes (timestamp comparison, deliberately not a TTL index — see research D4). The frontend adds a `useMarketNews` hook (TanStack Query, `staleTime` matching the TTL, no polling) and a `MarketNewsPanel` component rendered after the grid in `Stocks.tsx`.

The one piece of new infrastructure: **the backend currently has no FMP budget guard** — `routers/price.py` and `earnings_data.py` both call FMP with bare `requests.get` and never touch the `fmp_usage` counter that agent-runner's guard reads. Since this feature adds a user-triggered FMP path (the riskiest kind for quota), it introduces a small `backend/fmp.py` implementing the same day-bucket counter and soft-cap contract as `agent-runner/tools/fmp_client.py`, and routes the new endpoint through it. Retrofitting the two pre-existing call sites is recorded as a follow-up rather than bundled here.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / React 18 + Vite 5 (frontend)

**Primary Dependencies**: FastAPI, PyMongo (sync), requests, TanStack Query v5 — all already in use; **no new dependencies**

**Storage**: MongoDB — new `market_news_cache` collection (single document, code-evaluated 60-minute freshness so the stale-fallback copy survives); reuses the existing `fmp_usage` counter collection

**Testing**: pytest (backend router + budget guard), Vitest + React Testing Library (panel + page integration)

**Target Platform**: Self-hosted Docker Compose, single user

**Performance Goals**: Stocks page grid renders and stays interactive while news loads independently; cached news served without an external call

**Constraints**: At most one FMP call per hour for this feature (FR-011, SC-004); no polling (`refetchInterval: false`); news must never enter `analyses` documents (FR-008); a news failure must not degrade the grid (FR-012)

**Scale/Scope**: 1 user; 20 articles displayed; one cache document

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First & Comprehensive Coverage | PASS | New deterministic surfaces (cache hit/miss/TTL, article normalization, 20-cap, budget counter, fail-soft) get pytest coverage; panel rendering, cap, empty and error states get Vitest/RTL coverage. |
| II. Spec-Driven Development | PASS | Spec 022 written and clarified (3 questions) before planning; endpoint entitlements verified live and recorded in the spec's Data Sources. |
| III. Deterministic Core, LLM at the Edges | PASS | No LLM involvement at all — this is a plain headline list by explicit decision (spec Assumptions). |
| IV. Cache-Aware, Budget-Conscious Data Access | PASS (with a fix) | The feature is cache-first with a 60-minute TTL and fails soft to stale cache. It also closes a real gap by adding the backend's first budget guard; see research D3 and the follow-up note below. |
| V. Simplicity & Local-First Scope | PASS | One endpoint on an existing router, one collection, one hook, one component. No new service, worker, queue, or dependency. Deliberately no AI summarization or sentiment scoring. |
| VI. Consistency Across Layers | PASS | `backend/fmp.py` reuses agent-runner's exact `fmp_usage` day-bucket contract and setting names so both services agree on the day's spend; `MARKET_NEWS_CACHE` added to both services' collection-name lists per the existing "keep in sync" convention. |

**Post-Phase-1 re-check (2026-08-16)**: All six still PASS. The design added no infrastructure beyond the budget helper Principle IV requires, and kept the feature entirely out of the analysis-document path.

**Follow-up recorded, not bundled**: `routers/price.py` and `earnings_data.py` remain unguarded FMP callers, so the daily counter still under-reports total spend. Fixing them is a separate change (touches two working code paths this feature does not otherwise modify); logging it in `KNOWN_ISSUES.md` is a task in this feature so it is not lost.

## Project Structure

### Documentation (this feature)

```text
specs/022-market-news-feed/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── market-news-endpoint.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/
├── fmp.py                       # NEW: budget-guarded FMP GET (day counter + soft cap + fail-soft)
├── settings.py                  # + fmp_daily_soft_cap (mirrors agent-runner's name/default)
├── db.py                        # + MARKET_NEWS_CACHE, FMP_USAGE; unique index on `key`
├── routers/
│   └── market.py                # + GET /market/news (read-through cache)
└── tests/
    ├── test_market_news.py      # NEW: cache hit/miss/TTL, 20-cap, shaping, fail-soft
    └── test_fmp_guard.py        # NEW: counter increments, soft cap raises, disabled by default

frontend/
├── src/
│   ├── api/types.ts             # + MarketNewsArticle
│   ├── hooks/useMarketNews.ts   # NEW: TanStack Query, staleTime 60m, no polling
│   ├── components/feed/
│   │   ├── MarketNewsPanel.tsx      # NEW: 20-row list, loading/empty/error states
│   │   └── MarketNewsPanel.test.tsx # NEW
│   └── pages/
│       ├── Stocks.tsx           # render the panel below the grid
│       └── Stocks.test.tsx      # + panel placement, grid-survives-news-failure

KNOWN_ISSUES.md                  # + entry for the two unguarded FMP call sites
```

**Structure Decision**: Existing backend/frontend layout, no agent-runner involvement at all — this feature deliberately sits outside the analysis pipeline (FR-007/FR-008). The news endpoint joins the existing `/market` router rather than creating a new one, since it is market-wide read-only data exactly like `/market/breadth`.

## Complexity Tracking

No constitution violations. The one addition beyond the minimum — `backend/fmp.py` — exists to satisfy Principle IV rather than to work around it, and is ~40 lines mirroring an established pattern.
