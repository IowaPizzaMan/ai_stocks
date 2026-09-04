# Contract: Strategy Picks (extends the Chat API)

**Feature**: `032-weekly-strategy-picks` | **Router**: `backend/routers/chat.py` (unchanged)

This is **additive** to `specs/031-semantic-layer-chat/contracts/chat-api.md` — same endpoint,
same request shape, same base response fields. A strategy-picks question is just a `POST /chat`
question that happens to get recognized as one; everything below documents only what's new.

---

## `POST /chat` (unchanged route, extended response)

### Request

Unchanged from 031 — `{ question: string, history: ChatTurn[] }`. No new request field. Examples
of questions that route to this feature's logic:

- `"Per my trading strategies, what 10 stocks should I buy for each strategy this coming week and at what prices?"`
- `"per my strategies what should I short this week"`
- `"give me the top 5 buys from my strategies"`

### Response `200` — strategy-picks case

All of 031's base fields are still present (`answer`, `criteria`, `match_count`, `rows`,
`generated_query`, `excluded_for_missing_data`, `signals_as_of`, `degraded`, `note`) so existing
consumers don't break (FR-011). For a strategy-picks question:

- `criteria: []`, `rows: []`, `generated_query: null` — this isn't a Mongo-pipeline question, so
  those fields carry their empty/neutral values rather than being repurposed.
- `match_count`: total candidates across all lists after the Market Flow filter.
- A new top-level field, **`strategy_picks`**, non-null only for this feature's questions:

The NYMO reading is a single market-wide value — the same for every ticker on a given day — so
there's no per-ticker signal to distinguish candidates by (research.md R1). The gate is therefore
uniform across a direction: either the reading overrides that whole direction this week, or it
doesn't touch it at all. A **normal week** (no override):

```jsonc
{
  "answer": "For your buy picks this week: The Strat likes AAPL above $187.50 (weekly 2-bar Rev Strat, full bullish TFC)... Gap Analysis likes MSFT above $412 (down-gap reversal, score 4/5)... This is informational analysis, not financial advice.",
  "criteria": [],
  "match_count": 2,
  "rows": [],
  "generated_query": null,
  "excluded_for_missing_data": 0,
  "signals_as_of": "2026-08-23T21:05:00Z",
  "degraded": false,
  "note": null,
  "strategy_picks": {
    "direction": "buy",                // "buy" | "short"
    "count_requested": 10,             // FR-016 — parsed from the question, default 10
    "week_of": "2026-08-24",           // next 5 trading days from ask-time (FR-009)
    "market_condition_note": null,
    "market_condition_unavailable": false,   // FR-018
    "lists": [
      {
        "strategy": "the_strat",
        "strategy_label": "The Strat",
        "candidates": [
          {"ticker": "AAPL", "entry_price": 187.50, "basis": "weekly 2-bar Rev Strat, full bullish TFC"}
        ],
        "note": null                    // e.g. "no candidates currently qualify" when candidates is []
      },
      {
        "strategy": "gap_analysis",
        "strategy_label": "Gap Analysis",
        "candidates": [
          {"ticker": "MSFT", "entry_price": 412.00, "basis": "down-gap reversal, score 4/5"}
        ],
        "note": null
      }
    ],
    "excluded_by_market_flow": []
  }
}
```

An **overbought week** (FR-017 overrides the whole buy direction — both strategies' candidates
move from `candidates` into `excluded_by_market_flow`, and each list's `note` explains why it's
empty):

```jsonc
{
  "strategy_picks": {
    "direction": "buy",
    "market_condition_note": "market overbought (NYMO +68) — breadth doesn't support new buys this week",
    "market_condition_unavailable": false,
    "lists": [
      {"strategy": "the_strat", "strategy_label": "The Strat", "candidates": [],
       "note": "market overbought (NYMO +68) — breadth doesn't support new buys this week"},
      {"strategy": "gap_analysis", "strategy_label": "Gap Analysis", "candidates": [],
       "note": "market overbought (NYMO +68) — breadth doesn't support new buys this week"}
    ],
    "excluded_by_market_flow": [
      {"ticker": "AAPL", "strategy": "the_strat", "reason": "market overbought (NYMO +68) — breadth doesn't support new buys this week"},
      {"ticker": "MSFT", "strategy": "gap_analysis", "reason": "market overbought (NYMO +68) — breadth doesn't support new buys this week"}
    ]
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `strategy_picks` | object \| null | `null` for every non-strategy-picks question (unchanged 031 behavior) |
| `strategy_picks.direction` | `"buy"` \| `"short"` | FR-002/003 |
| `strategy_picks.count_requested` | number | FR-016; 10 when not specified or not a valid positive integer |
| `strategy_picks.week_of` | string (date) | FR-009 |
| `strategy_picks.market_condition_note` | string \| null | FR-017 caveat surfaced even when nothing was excluded |
| `strategy_picks.market_condition_unavailable` | boolean | FR-018 |
| `strategy_picks.lists[]` | array, one entry per strategy (`the_strat`, `gap_analysis`) | Always both present, even when a list is empty (FR-007) |
| `strategy_picks.lists[].candidates[]` | array, ≤ `count_requested` | FR-006 — never padded |
| `strategy_picks.lists[].note` | string \| null | e.g. `"no candidates currently qualify this week"` |
| `strategy_picks.excluded_by_market_flow[]` | array | FR-017 — candidates that qualified on the strategy's own signal but were excluded by the breadth filter |

### Edge cases mapped to response shape

| Spec edge case | Response shape |
|---|---|
| Unrecognized named strategy (FR-013) | `strategy_picks: null`; `answer` explains and lists supported strategies (same shape as an out-of-scope 031 answer) |
| Zero qualifying candidates for a strategy (FR-007) | That entry in `lists[]` has `candidates: []` and a non-null `note` |
| One strategy's computation errors (FR-015) | `lists[]` contains only the successful strategy's entry plus a `note`-bearing entry for the failed one (`candidates: []`, `note: "temporarily unavailable"`) — never a 500 |
| Requested strategy Market Flow by name (FR-019) | `strategy_picks: null`; `answer` explains Market Flow is a filter applied across the other two, not its own list |
| Breadth data unavailable (FR-018) | `strategy_picks.market_condition_unavailable: true`, `excluded_by_market_flow: []`, both `lists[]` still fully populated |
| Invalid/unreasonable requested count (FR-016) | `count_requested: 10` (silently falls back — no error) |

### Errors

Unchanged from 031: `422` for a malformed request, `500` only for truly unexpected failures. All
of this feature's own failure modes (unrecognized strategy, zero candidates, one strategy
erroring, missing breadth data, bad count) are `200` responses per the table above, matching the
repo's established "always 200; an empty/degraded result is a valid state" convention
(031 contract, `backend/routers/market.py`).

---

## Intent-detection call (internal, not a public contract)

`backend/semantic/strategy_picks.py::detect()` — one `llm.generate_json()` call, schema:

```jsonc
{
  "type": "object",
  "properties": {
    "is_strategy_picks": {"type": "boolean"},
    "direction": {"type": ["string", "null"], "enum": ["buy", "short", null]},
    "count": {"type": ["integer", "null"]},
    "named_strategy": {"type": ["string", "null"],
                        "enum": ["the_strat", "gap_analysis", "market_flow", "unrecognized", null]},
    "unrecognized_strategy_text": {"type": ["string", "null"]}
  },
  "required": ["is_strategy_picks", "direction", "count", "named_strategy", "unrecognized_strategy_text"]
}
```

`named_strategy` is constrained to a fixed enum rather than an open string: `"the_strat"` /
`"gap_analysis"` route normally, `"market_flow"` triggers the FR-019 explanation, `"unrecognized"`
triggers the FR-013 explanation with the user's literal phrase carried separately in
`unrecognized_strategy_text` (so the "I don't recognize X" message can quote it back accurately
without needing an open-ended field on the main classification).

Same `temperature: 0`, constrained-decoding settings as 031's query-generation call. This call
**never** sees or returns ticker data — its only job is classifying the question and extracting
parameters, which is why Principle III is fully satisfied rather than merely mitigated
(research.md, plan.md Constitution Check).
