# Contract: Strategy Picks Filters (extends the Strategy Picks & Chat APIs)

**Feature**: `033-strategy-picks-filters` | **Router**: `backend/routers/chat.py` (unchanged)

Additive to `specs/032-weekly-strategy-picks/contracts/strategy-picks-api.md`, which is itself
additive to `specs/031-semantic-layer-chat/contracts/chat-api.md`. Same endpoint (`POST /chat`),
same request shape. Everything below documents only what's new: three fields on the existing
`strategy_picks` response object, plus one behavior change (intent detection now runs on every
question, not only ones matching a keyword).

---

## `POST /chat` (unchanged route, extended response)

### Request

Unchanged — `{ question: string, history: ChatTurn[] }`. Examples of questions this feature adds
recognition/handling for:

- `"Per my trading strategies, what should I buy this week using only stocks I've liked?"`
- `"what should I buy this week in the consumer staples sector per my strategies"`
- `"per my strategies, give me liked stocks in the consumer staples sector to buy this week"`
- `"give me 10 stocks to buy and 10 to short"` (no strategy keyword — User Story 2)
- `"what are the most popular stocks in consumer staples ready to buy per my strategy"`
  (unanswerable condition — User Story 3)

### Response `200` — combined strategy-picks + condition case

All of 031/032's base fields are still present. New behavior: `criteria` is now populated (not
forced to `[]`) whenever an extra condition was successfully applied.

```jsonc
{
  "answer": "Using only your liked stocks in the consumer staples sector: The Strat likes KO above $61.20 (weekly 2-bar Rev Strat, full bullish TFC)... Gap Analysis has no qualifying candidates under those criteria this week. This is informational analysis only, not executed trades or licensed financial advice.",
  "criteria": [
    {"label": "liked_status = liked", "field": "liked_status", "op": "=", "value": "liked"},
    {"label": "sector = Consumer Staples", "field": "sector", "op": "=", "value": "Consumer Staples"}
  ],
  "match_count": 1,
  "rows": [],
  "generated_query": null,
  "excluded_for_missing_data": 0,
  "signals_as_of": "2026-08-23T21:05:00Z",
  "degraded": false,
  "note": null,
  "strategy_picks": {
    "direction": "buy",
    "count_requested": 10,
    "week_of": "2026-08-24",
    "market_condition_note": null,
    "market_condition_unavailable": false,
    "condition_requested": "liked stocks in the consumer staples sector",
    "condition_applied": true,
    "condition_note": null,
    "lists": [
      {
        "strategy": "the_strat",
        "strategy_label": "The Strat",
        "candidates": [
          {"ticker": "KO", "entry_price": 61.20, "basis": "weekly 2-bar Rev Strat, full bullish TFC"}
        ],
        "note": null
      },
      {
        "strategy": "gap_analysis",
        "strategy_label": "Gap Analysis",
        "candidates": [],
        "note": "no candidates currently qualify under liked stocks in the consumer staples sector this week"
      }
    ],
    "excluded_by_market_flow": []
  }
}
```

### Response `200` — condition couldn't be applied (FR-007)

```jsonc
{
  "answer": "I couldn't apply \"most popular in consumer staples\" — that doesn't correspond to any data I track. Here are your unfiltered strategy picks instead: ...",
  "criteria": [],
  "strategy_picks": {
    "direction": "buy",
    "condition_requested": "most popular in consumer staples",
    "condition_applied": false,
    "condition_note": "\"most popular in consumer staples\" doesn't correspond to any field this system tracks — answered without that condition.",
    "lists": [ /* full, unfiltered lists — same as a plain strategy-picks question */ ]
  }
}
```

The same shape (`condition_applied: false`) is used when the translation call itself errors or
times out (FR-007's second clause) — `condition_note` then reads e.g. `"'most popular in
consumer staples' couldn't be evaluated right now — answered without that condition."` The
caller cannot distinguish "no matching field" from "model call failed" from the response alone,
by design (FR-007 treats them identically).

### Response `200` — ambiguous interpretation disclosed (FR-008)

```jsonc
{
  "strategy_picks": {
    "condition_requested": "large cap stocks",
    "condition_applied": true,
    "condition_note": "interpreted \"large cap\" as market cap over $10B"
  },
  "criteria": [{"label": "market_cap > 10000000000", "field": "market_cap", "op": ">", "value": 10000000000}]
}
```

### Response `200` — recognized without a keyword (User Story 2)

`"give me 10 stocks to buy and 10 to short"` — no strategy-related keyword present. Behavior:
identical `strategy_picks` shape as a keyworded question, `condition_requested: null` (no extra
condition named).

| Field | Type | Notes |
|---|---|---|
| `strategy_picks.condition_requested` | string \| null | Raw, combined extra-condition text from the question; null when none was named |
| `strategy_picks.condition_applied` | boolean | `false` only when `condition_requested` is set but couldn't be used (FR-007) |
| `strategy_picks.condition_note` | string \| null | Explains a not-applied condition (FR-007) or a disclosed interpretation (FR-008); null otherwise |
| `criteria` (base field, reused) | array | Populated with the applied condition's plain-language predicates when `condition_applied: true`; `[]` otherwise (unchanged 032 behavior when there's no condition) |

### Edge cases mapped to response shape

| Spec edge case | Response shape |
|---|---|
| Extra condition matches zero candidates for a strategy (FR-006, AS3) | `condition_applied: true`; that list's `candidates: []`, `note` names the condition |
| Condition doesn't correspond to any tracked field (FR-007, AS4) | `condition_applied: false`, `condition_note` explains; lists computed unfiltered |
| Condition-translation call errors/times out (FR-007) | Same as above — indistinguishable from an unrecognized condition |
| Two conditions named at once (AS5) | Single `condition_requested` combining both; a candidate must satisfy both `$match` clauses (AND) to appear |
| Ambiguous condition, reasonable interpretation exists (FR-008) | `condition_applied: true`, non-null `condition_note` states the interpretation, `criteria` shows the resolved predicate |
| Strategy-picks question with no keyword (US2, SC-002) | Recognized identically to a keyworded question |
| Ordinary screener question, no strategy-picks intent (FR-009) | `strategy_picks: null`; free-form flow response, byte-for-byte unchanged from 031/032 |

### Errors

Unchanged from 031/032 — `422` for a malformed request, `500` only for truly unexpected
failures. Every new failure mode above (unrecognized/failed condition, zero post-condition
candidates) is a `200`.

---

## Intent-detection call (internal, extends 032's contract)

`backend/semantic/strategy_picks.py::detect()` — same call, extended schema:

```jsonc
{
  "type": "object",
  "properties": {
    "is_strategy_picks": {"type": "boolean"},
    "direction": {"type": ["string", "null"], "enum": ["buy", "short", null]},
    "count": {"type": ["integer", "null"]},
    "named_strategy": {"type": ["string", "null"],
                        "enum": ["the_strat", "gap_analysis", "market_flow", "unrecognized", null]},
    "unrecognized_strategy_text": {"type": ["string", "null"]},
    "extra_conditions": {"type": ["array", "null"], "items": {"type": "string"}}
  },
  "required": ["is_strategy_picks", "direction", "count", "named_strategy",
               "unrecognized_strategy_text", "extra_conditions"]
}
```

**Behavior change from 032**: this call is no longer gated behind
`looks_like_strategy_picks()` — `chat.answer_question()` calls `detect()` on every question
(FR-001). A `is_strategy_picks: false` result falls through to the free-form flow exactly as
before; the only observable difference to that flow is added latency, not a shape or behavior
change (FR-009).

## Condition-translation call (internal, new)

`backend/semantic/condition_filter.py::translate_conditions()` — one `llm.generate_json()` call
reusing 031's own query-generation schema/prompt verbatim
(`backend/semantic/screener_query.py::QUERY_SCHEMA` / `build_system_prompt()`), invoked **only**
when `detect()` returned a non-empty `extra_conditions` list. Same `temperature: 0`,
constrained-decoding settings as every other query-generation call in this system. Produces a
pipeline against `screener` (not `strategy_signals`); execution strips display-oriented
`$sort`/`$limit`/`$project` stages before running (see research.md R4) so the resulting ticker
set is never truncated.
