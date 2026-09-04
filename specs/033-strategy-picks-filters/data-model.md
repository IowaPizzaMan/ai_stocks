# Phase 1 Data Model: Combined Strategy Picks & Screener Filters in AI Chat

**Feature**: `033-strategy-picks-filters` | **Date**: 2026-08-23

This feature adds one field to an existing collection and reshapes several already-transient
(never-persisted) request/response entities from `032-weekly-strategy-picks`. No new MongoDB
collection.

---

## Modified collection: `screener`

One new field, appended to the existing flat per-ticker document (031 data-model.md):

```jsonc
{
  // ...existing fields unchanged...
  "liked_status": "liked"   // "liked" | "disliked" | null — user's per-ticker preference
}
```

**Derivation**: copied verbatim from `ticker_index.sentiment` (written by
`PUT /stocks/{ticker}/sentiment`, `backend/routers/stocks.py`) at `screener` refresh time.
`agent-runner/tools/screener.py::compute_signals()` gains a `liked_status: str | None` keyword
parameter, populated the same way `is_tracked` already is:

- `refresh_all()`: today reads `{row["ticker"] for row in db[TICKER_INDEX].find({}, {"ticker": 1})}`
  to build the tracked-ticker set. Extended to also project `sentiment`, building a
  `{ticker: sentiment}` map so `liked_status` can be looked up per ticker in the same loop
  (default `None` for a ticker with no `ticker_index` document, or no sentiment set).
- `refresh_one()`: today does `db[TICKER_INDEX].find_one({"ticker": ticker})` for `is_tracked`;
  extended to also read `.get("sentiment")` from that same document.

**Validation rules**:
- `liked_status` is `null` whenever the ticker has no `ticker_index` document, or has one with
  `sentiment: null` (the default/cleared state) — never fabricated as `"disliked"` by absence.
- Independent of `insufficient_history` / other price-derived nulls — a ticker with too little
  price history to compute signals can still have a `liked_status`.

**Indexes**: `db[SCREENER].create_index([("liked_status", ASCENDING)])` — same single-field
convention as `screener`'s other queryable fields (031 research.md R8: generated pipelines
combine predicates in unpredictable order, so single-field indexes serve more query shapes than
one compound index would).

**Schema description** (`backend/semantic/schema.py::SCREENER_SCHEMA["fields"]`, and its mirrored
field-name set in `backend/tests/test_screener_contract.py` / `agent-runner/tests/test_screener.py`):

```jsonc
{"name": "liked_status", "type": "string",
 "description": "The user's personal like/dislike marking for this ticker, set from the stock "
                 "page's like/dislike control. One of \"liked\", \"disliked\", or null if never marked."}
```

---

## New shared module: `backend/semantic/screener_query.py`

Pure code motion from `chat.py` (031) — no behavior change for the existing free-form flow
(FR-009). Houses the pieces both `chat.py` and the new `condition_filter.py` need:

- `QUERY_SCHEMA` (unchanged, moved verbatim)
- `build_system_prompt() -> str` (renamed from `chat._build_system_prompt`, unchanged body)
- `criteria_from_pipeline(pipeline: list[dict]) -> list[dict]` (renamed from
  `chat._criteria_from_pipeline`, unchanged body)
- `generate_pipeline(prompt_text: str, *, client=None) -> dict` — new thin wrapper: one
  `llm.generate_json(prompt=prompt_text, schema=QUERY_SCHEMA, system=build_system_prompt(), client=client, options={"temperature": 0})`
  call. `chat.answer_question()`'s existing call site (currently inlined) is refactored to call
  this wrapper with `_format_history(history) + f"Question: {question}"` as before — identical
  request/response shape, just deduplicated.

`chat.py` keeps its own `_format_history()` (031's conversation-replay concern, unrelated to
query generation) and imports the four names above from `screener_query`.

---

## New module: `backend/semantic/condition_filter.py`

Translates a strategy-picks question's extra condition(s) into a ticker set, using the exact
mechanism above (FR-004).

```python
def translate_conditions(conditions: list[str], db: Database, *, client=None) -> dict:
    """Returns a ConditionFilterResult (see below). `conditions` is the
    non-empty list from StrategyPicksIntent.extra_conditions — joined into
    one prompt so multiple conditions produce a single AND'd pipeline
    (FR-004), not one call per condition."""
```

Behavior:
1. Join `conditions` into one prompt line, e.g. `"Question: stocks that are: only stocks I've
   liked; in the consumer staples sector"` — phrased so the model treats every item as an AND'd
   clause, reusing `screener_query.build_system_prompt()`'s existing instruction to emit a single
   `$match`-bearing pipeline.
2. Call `screener_query.generate_pipeline(prompt_text, client=client)`. An `llm.LLMError` here is
   caught and mapped to `applied: False` (FR-007's "technically fails" case).
3. If `in_scope` is `false`: `applied: False` (FR-007's "no matching field" case).
4. Else `query_guard.validate_pipeline(pipeline, collection="screener")`. A `QueryRejected` here
   is also mapped to `applied: False` (treated the same as an unrecognized condition — it isn't
   expressible/safe against the data this system exposes).
5. Else strip any `$sort`/`$limit`/`$project` stages from the validated pipeline (031
   research.md R4 in this spec — display-oriented stages must not truncate a membership set),
   keep the `$match` stage(s), append `{"$project": {"_id": 0, "ticker": 1}}`, and execute against
   `db[SCREENER]` with no limit. `tickers = {row["ticker"] for row in cursor}` — may legitimately
   be an empty set (FR-006's zero-match case, not a failure).
6. `criteria = screener_query.criteria_from_pipeline(validated_pipeline)` for FR-008.

### ConditionFilterResult (transient, not persisted)

```jsonc
{
  "applied": true,
  "tickers": ["AAPL", "KO", "PG"],       // null when applied=false
  "criteria": [{"label": "liked_status = liked", "field": "liked_status", "op": "=", "value": "liked"},
               {"label": "sector = Consumer Staples", "field": "sector", "op": "=", "value": "Consumer Staples"}],
  "note": null                            // set only when applied=false, or when the interpretation
                                           // needs disclosing per FR-008
}
```

---

## Modified transient entity: `StrategyPicksIntent` (032, extended)

```jsonc
{
  "is_strategy_picks": true,
  "direction": "buy",
  "count": null,
  "named_strategy": null,
  "unrecognized_strategy_text": null,
  "extra_conditions": ["only stocks I've liked", "in the consumer staples sector"]  // NEW, [] | null when none
}
```

`INTENT_SCHEMA` (`backend/semantic/strategy_picks.py`) gains:

```jsonc
"extra_conditions": {"type": ["array", "null"], "items": {"type": "string"}}
```

added to `required`. `detect()`'s system prompt (`_build_intent_system_prompt()`) is extended to:
1. Instruct the model to list every additional filtering condition the question names beyond
   direction/count/named-strategy — as free-text phrases, not pre-translated — explicitly calling
   out liked/disliked preference as one recognized kind of condition (FR-005).
2. Broaden the `is_strategy_picks` recognition guidance with phrasing-agnostic criteria (asking
   what to buy/short "this week" per an approach/strategy, with or without the words "strategy",
   "The Strat", "Gap Analysis", or "Market Flow" appearing) — User Story 2's concrete failing
   example ("give me 10 stocks to buy and 10 to short") is used as an explicit positive example
   in the prompt, and an ordinary screener-shaped question (e.g. "what stocks have improving
   financials") as an explicit negative example, so FR-009's non-regression holds.

---

## Modified: `strategy_picks.compute_picks()` / `_rank_strategy()`

`_rank_strategy(strategy, field_direction, count, db, ticker_filter=None)` — when
`ticker_filter` is not `None`, the Mongo predicate becomes
`{f"{strategy}.direction": field_direction, "ticker": {"$in": sorted(ticker_filter)}}` before the
existing `.sort(...).limit(count)`. An empty (but non-`None`) `ticker_filter` legitimately
produces zero rows — FR-006.

`compute_picks(direction, count, db, *, ticker_filter=None, condition_label=None)` threads
`ticker_filter` into every `_rank_strategy()` call. When a strategy's result is empty *and*
`ticker_filter is not None`, that list's `note` names the condition:
`f"no candidates currently qualify under {condition_label} this week"` instead of 032's generic
`"no candidates currently qualify this week"`.

---

## Modified transient entity: `StrategyPicksResponse` (032, additive fields)

```jsonc
{
  // ...all 032 fields unchanged...
  "condition_requested": "liked stocks in the consumer staples sector",  // NEW, null if no extra condition
  "condition_applied": true,                                             // NEW, false only when condition_requested is set but couldn't be used
  "condition_note": null                                                 // NEW — see states below
}
```

| `condition_requested` | `condition_applied` | `condition_note` | Meaning |
|---|---|---|---|
| `null` | `false` | `null` | No extra condition in the question — 032 behavior, unchanged |
| set | `true` | `null` | Condition applied cleanly; interpretation (if any) is in the reused `criteria` field |
| set | `true` | non-null | Condition applied, but the interpretation was ambiguous — states which reading was used (FR-008) |
| set | `false` | non-null | Condition could not be translated/executed — explains what couldn't be applied (FR-007); strategy lists computed as if it were never asked |

Top-level `criteria` (already part of the base `ChatResponse`, forced to `[]` for every
032-era strategy-picks answer) is now populated with `ConditionFilterResult.criteria` whenever
`condition_applied` is `true` — reusing the existing field rather than adding a parallel one.

---

## Validation rules (new/changed)

- A strategy-picks question with `extra_conditions` present but every strategy's result already
  empty for a *different* reason (e.g. Market Flow override) still reports that list's `note` as
  the Market Flow reason, not the condition reason — the two filters' notes are not conflated;
  whichever filter actually produced the empty result names itself (Market Flow's own `note` in
  `apply_filter()` already takes priority since it only overwrites a non-empty `raw` result).
- `condition_applied: false` never removes or alters `direction`/`count`/`named_strategy`
  handling — the rest of the question is answered exactly as it would be with no extra condition,
  per FR-007.
- `liked_status` on `screener` and `extra_conditions` on the intent schema are both optional/
  nullable everywhere — an old cached `screener` document without the new field is treated as
  `liked_status: null` (Mongo's normal missing-field-as-null read semantics), not a migration
  requirement.
