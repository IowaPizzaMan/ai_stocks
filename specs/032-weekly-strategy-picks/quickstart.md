# Quickstart: Weekly Strategy Buy/Short Picks in AI Chat

**Feature**: `032-weekly-strategy-picks` | **Depends on**: `031-semantic-layer-chat` running and
`screener`/`price_history` already populated for at least a handful of tickers.

## Prerequisites

- Docker Compose stack up: `docker compose up -d --build` (mongodb, backend, frontend,
  agent-runner, ollama), per `README.md`.
- `screener` collection non-empty (031 already running) — confirms `price_history` exists for the
  universe this feature scans.
- `breadth_cache` has at least one `exchange: "nyse"` row (the existing `breadth_worker` populates
  this daily; trigger it manually if the stack is fresh — see agent-runner's admin job docs).

## 1. Populate `strategy_signals`

Run the new background job once (mirrors how `screener_refresh` is triggered today):

```bash
# via the admin job endpoint/CLI this repo already uses for screener_refresh —
# see agent-runner/tools/admin_jobs.py JOB_HANDLERS for the exact trigger mechanism
# in use (work_queue insert with job_type="strategy_signals_refresh")
```

**Expected outcome**: `db.strategy_signals.countDocuments({})` equals (or is close to)
`db.screener.countDocuments({})` — same universe, one doc per ticker. Spot-check one tracked
ticker:

```js
db.strategy_signals.findOne({ ticker: "AAPL" })
// -> { ticker, signals_as_of, insufficient_history,
//      the_strat: { direction, pattern, timeframe, entry_price, strength },
//      gap_analysis: { direction, score, entry_price, bias } }
```

## 2. Ask a buy-picks question

Open the Chat page (`/chat` in the frontend) and ask:

> Per my trading strategies, what stocks should I buy this week and at what prices?

**Expected outcome**:
- The existing "thinking…" indicator appears, then the answer renders in the same reply (no
  extra step, no need to re-ask) — per the spec's Clarifications.
- The prose names specific tickers with specific prices, grouped by strategy (The Strat, Gap
  Analysis).
- If NYMO is currently overbought, at least one otherwise-qualifying candidate may be called out
  as excluded, with the reason stated in the answer text.
- A closing disclaimer sentence is present (FR-010).

Verify against the raw response shape in
[contracts/strategy-picks-api.md](./contracts/strategy-picks-api.md): `strategy_picks.lists` has
exactly two entries (`the_strat`, `gap_analysis`), each with ≤10 candidates.

## 3. Ask a short-picks question

> Per my trading strategies, what should I short this week and at what prices?

**Expected outcome**: same shape as step 2 with `strategy_picks.direction: "short"`. If a
strategy has no qualifying short candidates this week, its list entry has `candidates: []` and a
non-null `note` — confirm the prose says so explicitly rather than omitting that strategy.

## 4. Ask for a different count

> Give me the top 5 buys from my strategies.

**Expected outcome**: `strategy_picks.count_requested: 5`, each list has ≤5 candidates.

## 5. Ask about the excluded strategy by name

> What are my Market Flow picks this week?

**Expected outcome**: `strategy_picks: null`; the answer explains Market Flow is applied as a
filter across the other two strategies, not an independent list (FR-019) — confirms the
Clarifications-driven scope change is actually wired up, not just documented.

## 6. Confirm the existing screener chat still works unchanged (FR-011)

> What stocks are near the bottom of their 20-day range but rising this week?

**Expected outcome**: identical behavior to 031 today — `strategy_picks: null`, `rows`/`criteria`/
`generated_query` populated as before.

## Automated checks

```bash
# agent-runner: pure-function coverage for the new signal derivation
cd agent-runner && pytest tests/test_strategy_signals.py tests/test_gap_analysis.py -v

# backend: intent parsing, ranking/filtering, Market Flow threshold edges, router integration
cd backend && pytest tests/test_strategy_picks.py tests/test_market_flow_filter.py tests/test_chat_router.py tests/test_db_constants.py -v

# frontend: per-strategy list rendering
cd frontend && npx vitest run src/pages/Chat.test.tsx

# lint (Constitution: Development Workflow & Quality Gates)
ruff check agent-runner/ backend/
```
