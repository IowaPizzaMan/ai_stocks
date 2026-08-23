# Contract: Chat API

**Feature**: `031-semantic-layer-chat` | **Router**: `backend/routers/chat.py`

Follows the repo's existing conventions: `APIRouter(prefix="/chat", tags=["chat"])`, registered
bare via `app.include_router(chat.router)` in `backend/main.py`, `db=Depends(db_dependency)`.

---

## `POST /chat`

Ask a question. Stateless — the client replays conversation context each turn (FR-004).

### Request

```jsonc
{
  "question": "what stocks are at the bottom of their daily z-score range but moving up on the weekly, with improving financials and more free cash flow than debt?",
  "history": [                               // optional; last ~6 turns, server truncates beyond
    {"role": "user",      "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

| Field | Type | Rules |
|---|---|---|
| `question` | string | required, 1–2000 chars; 422 if empty or oversized |
| `history` | array | optional, default `[]`; server keeps only the most recent 6 turns |

### Response `200`

```jsonc
{
  "answer": "13 stocks are near the bottom of their 20-day range while rising on the week...",
  "criteria": [                              // FR-013 — plain language, always present
    {"label": "20-day z-score below average", "field": "zscore_20d", "op": "<", "value": 0},
    {"label": "rising over the past week",    "field": "weekly_change_pct", "op": ">", "value": 0},
    {"label": "financials improving",         "field": "financials_trend", "op": "=", "value": "improving"},
    {"label": "free cash flow exceeds debt",  "field": "fcf_exceeds_debt",  "op": "=", "value": true}
  ],
  "match_count": 13,
  "rows": [ {"ticker": "TPR", "range_pct_20d": 0.104, "weekly_change_pct": 0.92} ],
  "generated_query": {                       // FR-014 — returned always, UI hides behind a toggle
    "collection": "screener",
    "pipeline": [{"$match": {"zscore_20d": {"$lt": 0}}}, {"$limit": 50}]
  },
  "excluded_for_missing_data": 4,            // SC-008 — null-signal tickers, reported not hidden
  "signals_as_of": "2026-08-23T04:12:00Z",
  "degraded": false,
  "note": null
}
```

### Answerable-but-empty vs. cannot-answer

Both return `200` — consistent with the repo's read-only endpoints, which "always 200; an empty
result is a valid state, not an error" (`backend/routers/market.py:113-114`).

| Situation | Shape |
|---|---|
| Query ran, no matches | `match_count: 0`, `rows: []`, `answer` says so, `criteria` still populated |
| Out of scope (FR-007) | `answer` explains it cannot be answered, `criteria: []`, `generated_query: null`, `note: "out_of_scope"` |
| Signals stale / worker hasn't run | `degraded: true`, `note` names the reason, best-available rows still returned |

### Errors

| Code | When |
|---|---|
| `422` | `question` empty, >2000 chars, or `history` malformed |
| `503` | Ollama unreachable or timed out — `{"detail": "chat model unavailable"}` |
| `500` | Unexpected; caught by the global handler in `backend/main.py:44-49` |

**A rejected query is not a 500.** If the model emits a disallowed stage, the guard rejects it
and the endpoint returns `200` with `note: "query_rejected"` and an `answer` saying the question
couldn't be answered safely (FR-015). Failing loudly here would leak an internal safety event as
a server error.

---

## `GET /chat/schema`

Returns the semantic layer description the model is given. Exists for debugging and for the
UI's "what can I ask?" affordance.

```jsonc
{
  "collection": "screener",
  "fields": [
    {"name": "zscore_20d", "type": "number",
     "description": "Close vs 20-day mean in standard deviations; negative = below average"}
  ],
  "document_count": 556,
  "signals_as_of": "2026-08-23T04:12:00Z"
}
```

---

## Read-only guarantee (FR-012)

Enforced in `backend/semantic/query_guard.py`, between the model and the driver.

**Stage allowlist** — anything not listed is rejected:
`$match`, `$project`, `$addFields`, `$set`, `$group`, `$sort`, `$limit`, `$skip`, `$count`,
`$unwind`, `$lookup`, `$facet`, `$sample`, `$sortByCount`, `$replaceRoot`

**Always rejected**: `$out`, `$merge`, `$function`, `$accumulator`, `$where`, `$graphLookup`,
plus any unrecognized `$`-prefixed stage.

An allowlist is used deliberately: it fails safe when MongoDB adds stages, whereas a denylist
silently admits them.

**Also enforced**:
- Collection must be `screener` (or another explicitly readable collection); anything else rejected.
- `$limit` appended if absent — default 50, hard cap 200 (FR-016).
- `maxTimeMS` applied server-side (default 5000 ms).
- Executed through a client that performs reads only.

**Known limitation, stated plainly**: MongoDB auth is disabled in this deployment
(research.md R6), so this is enforcement in application code, not a database-level permission.
It cannot be bypassed by prompt content, but it is only as strong as the validator. Enabling
auth with a `read`-role user is the recorded follow-up.

---

## LLM invocation

Mirrors `agent-runner/llm.py`, with gaps fixed (research.md R10).

| Call | Settings |
|---|---|
| Query generation | `format=<JSON Schema>` (constrained decoding — guarantees parseable output), `temperature: 0`, `think: false` |
| Answer interpretation | `temperature: 0.2`, `think: false` |
| Both | explicit `timeout` (absent everywhere in the repo today), `keep_alive` long enough to keep the model resident |

Model pre-warmed at backend startup; without it the first question costs ~10s of load time and
misses SC-001 (research.md R2).
