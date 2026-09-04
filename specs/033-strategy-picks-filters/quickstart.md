# Quickstart: Combined Strategy Picks & Screener Filters in AI Chat

**Feature**: `033-strategy-picks-filters` | **Date**: 2026-08-23

Validates the acceptance scenarios in [spec.md](./spec.md) end-to-end against a running stack.
Prerequisites: `033-strategy-picks-filters` implemented (see [data-model.md](./data-model.md),
[contracts/strategy-picks-filters-api.md](./contracts/strategy-picks-filters-api.md)),
`agent-runner`'s `screener_refresh` and `strategy_signals_refresh` jobs have run at least once
since the change (so `screener` has `liked_status` populated and `strategy_signals` exists).

## Setup

```bash
docker compose up -d mongodb backend agent-runner ollama
# One-time, if not already tracked: pick a ticker you can mark liked, e.g. KO
curl -s -X PUT http://localhost:8000/stocks/KO/sentiment \
  -H "Content-Type: application/json" -d '{"sentiment": "liked"}'
# Force a refresh so screener.liked_status and strategy_signals reflect current data
curl -s -X POST http://localhost:8000/admin/jobs -H "Content-Type: application/json" \
  -d '{"job_type": "screener_refresh"}'
curl -s -X POST http://localhost:8000/admin/jobs -H "Content-Type: application/json" \
  -d '{"job_type": "strategy_signals_refresh"}'
```

## Scenario 1 — single extra condition narrows the candidate universe (AS1, AS2)

```bash
curl -s -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"question": "per my trading strategies, what should I buy this week using only stocks I'\''ve liked"}' | python -m json.tool
```

**Expected**: `strategy_picks.condition_requested` is non-null and mentions "liked";
`condition_applied: true`; every ticker in every list's `candidates` has `liked_status: "liked"`
in `screener` (spot-check via `GET /chat/schema` and a manual `screener` query, or by cross-
referencing `GET /tickers`). Repeat with a sector phrasing
(`"...in the consumer staples sector"`) and confirm every returned candidate belongs to that
sector.

## Scenario 2 — zero qualifying candidates under a combined condition (AS3)

Pick a condition unlikely to match any current candidate (e.g. a sector with no liked, currently-
signaling tickers). **Expected**: that strategy's `lists[].note` states plainly that nothing
qualifies under the combined criteria (not an empty list with no explanation, not the unfiltered
list).

## Scenario 3 — unanswerable condition (AS4, User Story 3)

```bash
curl -s -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"question": "what are the most popular stocks in consumer staples ready to buy per my strategy"}' | python -m json.tool
```

**Expected**: `strategy_picks.condition_applied: false`, `condition_note` explains the
limitation, and `strategy_picks.lists` still contain the plain (unfiltered) strategy-picks
answer — the request is not failed outright.

## Scenario 4 — two conditions combined with AND (AS5)

```bash
curl -s -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"question": "per my strategies, give me liked stocks in the consumer staples sector to buy this week"}' | python -m json.tool
```

**Expected**: `criteria` has two entries (liked_status, sector); every returned candidate
satisfies both.

## Scenario 5 — recognized without a trigger keyword (User Story 2, SC-002)

```bash
curl -s -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"question": "give me 10 stocks to buy and 10 to short"}' | python -m json.tool
```

**Expected**: `strategy_picks` is non-null (recognized as a strategy-picks question) despite no
mention of "strategy", "The Strat", "Gap Analysis", or "Market Flow".

## Scenario 6 — ordinary screener question unaffected (FR-009, SC-004)

```bash
curl -s -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"question": "what stocks have improving financials and free cash flow exceeding debt?"}' | python -m json.tool
```

**Expected**: `strategy_picks: null`; response shape identical to pre-033 behavior (only added
latency from the now-unconditional intent-detection call, per the spec's Assumptions).

## Automated coverage

```bash
# agent-runner
cd agent-runner && python -m pytest tests/test_screener.py tests/test_strategy_signals.py -q

# backend
cd backend && python -m pytest tests/test_screener_contract.py tests/test_db_constants.py \
  tests/test_chat_router.py tests/test_strategy_picks.py tests/test_condition_filter.py -q

# lint (constitution gate)
ruff check backend/
ruff check agent-runner/ scripts/
```

Expected: all pass, including the mirrored `liked_status` field-name assertions in
`test_screener_contract.py` / `agent-runner/tests/test_screener.py`, and the new
`test_condition_filter.py` covering the strip-display-stages behavior (research.md R4) and the
applied/zero-match/failed-translation response states (data-model.md's `StrategyPicksResponse`
table).
