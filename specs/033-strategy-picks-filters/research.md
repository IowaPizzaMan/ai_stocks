# Phase 0 Research: Combined Strategy Picks & Screener Filters in AI Chat

**Feature**: `033-strategy-picks-filters` | **Date**: 2026-08-23

This feature extends two already-implemented features rather than starting from scratch:
`032-weekly-strategy-picks` (`backend/semantic/strategy_picks.py`, `chat.py`'s dispatch) and
`031-semantic-layer-chat` (`backend/semantic/query_guard.py`, `schema.py`, and `chat.py`'s
query-generation call). All decisions below are about how to wire those two existing paths
together, not new infrastructure.

---

### R1 — Where does extra-condition extraction happen relative to intent detection?

**Decision**: One extended intent-detection call. `strategy_picks.INTENT_SCHEMA` gains
`"extra_conditions": {"type": ["array", "null"], "items": {"type": "string"}}` — the same
Ollama call that already extracts `{is_strategy_picks, direction, count, named_strategy}`
also pulls out every additional condition phrase in the question (e.g.
`["only stocks I've liked", "in the consumer staples sector"]`), verbatim or lightly
normalized, not translated into a query yet.

**Rationale**: FR-002 requires recognizing intent and every extra condition "within a single
strategy-picks question" — doing it in one call keeps the cost at exactly the "one intent call
+ one translation call" shape the spec's Assumptions section already prices in, and avoids a
second full-question classification pass. It also naturally supports User Story 2 (recognizing
strategy-picks phrasing without a keyword) since the same call already has to reason about the
whole question.

**Alternatives considered**: A separate "extract conditions" call after intent detection —
rejected, doubles cost for no accuracy benefit since both tasks read the same question text.
Regex/keyword extraction of conditions — rejected per FR-004, which requires the same
general LLM-based mechanism the free-form screener already uses, not a hardcoded phrase list.

---

### R2 — How is FR-001's keyword pre-filter removed without duplicating logic?

**Decision**: Delete `strategy_picks.looks_like_strategy_picks()` and its `_INTENT_HINT_KEYWORDS`
constant. `chat.answer_question()` calls `strategy_picks.detect()` unconditionally, on every
question, before falling through to the free-form flow when `is_strategy_picks` is false.

**Rationale**: This is exactly what FR-001 asks for — the pre-filter existed solely to avoid
paying for the intent call on non-strategy questions, and the spec's Assumptions section
explicitly accepts that cost now. `detect()`'s existing `LLMError` handling (treat as
`is_strategy_picks: False`) already covers the failure path; no new error handling needed.

**Alternatives considered**: Widening the keyword list — rejected, User Story 2's whole point is
that no fixed keyword list can cover natural phrasing ("give me 10 to buy and 10 to short").

---

### R3 — How does FR-004's "same mechanism the free-form screener already uses" avoid duplicating `chat.py`'s query-generation code?

**Decision**: Extract `chat.py`'s `QUERY_SCHEMA`, `_build_system_prompt()`, and
`_criteria_from_pipeline()` into a new shared module, `backend/semantic/screener_query.py`.
`chat.py` imports from it for the existing free-form flow (behavior-identical — pure code
motion); a new module `backend/semantic/condition_filter.py` imports the same three pieces to
translate a strategy-picks question's extra condition(s) into one pipeline against `screener`.

**Rationale**: `strategy_picks.py` cannot import from `chat.py` (which already imports
`strategy_picks` — a cycle), so the shared pieces need a home neither module owns exclusively.
This is the literal reading of FR-004 ("not a hardcoded list... the same general
question-to-query mechanism") — one function, two call sites, not a second implementation with
matching behavior.

**Alternatives considered**: Duplicating the schema/prompt into `strategy_picks.py` (the
established hand-dup precedent for cross-*service* boundaries like `llm.py` and `db.py`
constants) — rejected: that precedent exists because `backend/` and `agent-runner/` are separate
Docker images with separate dependency trees (constitution Principle VI); `chat.py` and
`strategy_picks.py` are the same service, same import graph, so a shared module is the correct
fix, not a justified duplication.

---

### R4 — How is the condition's ticker set computed without the free-form flow's display-oriented `$limit` truncating it?

**Decision**: The condition-translation call still goes through
`query_guard.validate_pipeline()` for stage-allowlist safety, but `condition_filter.py` then
strips any `$sort`/`$limit`/`$project` stages the model emitted, keeps only the `$match`
stage(s), and appends its own `{"$project": {"_id": 0, "ticker": 1}}` with no limit before
executing against `screener`.

**Rationale**: `query_guard`'s `DEFAULT_LIMIT` (50) / `HARD_LIMIT_CAP` (200) exist to bound rows
*shown to the user* in the free-form flow (031 FR-016) — reusing them here would silently drop
qualifying tickers past position 50/200 and violate FR-003 ("a filtered-out stock never displaces
a candidate that does meet every condition"). The condition query's only job is set membership,
not a display page, so it needs the complete match set. This is safe at this collection's scale
(031 research.md R8: `screener` is cache-resident, ~17 MB at 15x projected scale) — a full,
unlimited `$match` + ticker-only projection is cheap.

**Alternatives considered**: Raising `HARD_LIMIT_CAP` globally — rejected, that would also loosen
the free-form flow's own display cap (FR-009 requires zero behavior change there). A second,
higher constant reused by `query_guard` — rejected as unnecessary indirection when stripping the
display-oriented stages entirely is simpler and removes the truncation risk altogether rather
than just raising the ceiling.

---

### R5 — How is a user's "liked"/"disliked" preference exposed to this mechanism (FR-005)?

**Decision**: Add one new field to the `screener` collection: `liked_status` — `"liked"` |
`"disliked"` | `null`, copied from `ticker_index.sentiment` (already written by
`PUT /stocks/{ticker}/sentiment`, `backend/routers/stocks.py:168`). `agent-runner/tools/screener.py`'s
`compute_signals()` gains a `liked_status: str | None` parameter (same shape as its existing
`is_tracked: bool` parameter); `refresh_all()`/`refresh_one()` read it from the same
`ticker_index` lookup they already do for the tracked-ticker set. `semantic/schema.py`'s
`SCREENER_SCHEMA["fields"]` gets a matching entry so the query-generation model can target it
(e.g. `{"$match": {"liked_status": "liked"}}`), and the mirrored field-name test in
`backend/tests/test_screener_contract.py` / `agent-runner/tests/test_screener.py` is updated in
lockstep, per the constitution Principle VI convention this pair already enforces.

**Rationale**: `screener` is the only collection the query-generation mechanism can target
(FR-004's "same mechanism"), and it's already the flat, per-ticker, LLM-queryable shape this
needs (031 research.md R1) — adding one field is far simpler than teaching the mechanism to
join two collections. `ticker_index` is per-ticker already, so the join at write time
(agent-runner, once per refresh cycle) is trivial and mirrors how `is_tracked` is already
derived from the same collection.

**Alternatives considered**: Reading `ticker_index` directly from the condition-query mechanism
(a second readable collection) — rejected: `query_guard.READABLE_COLLECTIONS` and the whole
query-generation system prompt are built around a single target collection; adding a second
would require the model to reason about a join, which 031 R1 already found unreliable for a
small local model. Naming the field `sentiment` (matching `ticker_index`'s own field name) was
considered but rejected as ambiguous next to this app's other market/news-sentiment concepts —
`liked_status` is unambiguous in the schema description handed to the model.

---

### R6 — How does the condition filter combine with `strategy_signals` ranking (FR-003)?

**Decision**: `strategy_picks._rank_strategy()` gains an optional `ticker_filter: set[str] | None`
parameter. When present, it's added to the Mongo `find()` predicate as
`{"ticker": {"$in": sorted(ticker_filter)}}` alongside the existing `{strategy}.direction`
predicate, *before* the existing `.sort(...).limit(count)`. This is the same function, same
query shape as today — one extra predicate term.

**Rationale**: FR-003 requires the extra condition to narrow the candidate universe "before
ranking and selecting the top candidates" — doing it as an additional `find()` predicate (rather
than filtering the already-limited Python list afterward) is the only way to guarantee a
filtered-out stock never occupies one of the `count` slots that a qualifying stock should get.
Market Flow's filter (`market_flow_filter.apply_filter`) already runs *after* ranking/limiting,
unchanged — per the spec's clarification, the two filters are independent inclusion checks over
the same candidates and don't need to run in a particular relative order; leaving Market Flow
exactly where it is satisfies that without touching working code.

**Alternatives considered**: Filtering `strategy_signals` results in Python after the query —
rejected for the reason above (truncation risk identical to R4's). Pre-computing a materialized
`liked`/sector-filtered view of `strategy_signals` — rejected as unneeded complexity; conditions
are free-form and per-question, not a fixed set worth precomputing (constitution Principle V).

---

### R7 — How does the response shape distinguish "zero qualifying candidates" (FR-006) from "condition couldn't be applied" (FR-007)?

**Decision**: Two independent signals on the additive `strategy_picks` object, both `null`/`false`
when the question had no extra condition:
- `condition_requested` (string | null) — the combined extra-condition text, always populated
  when the question named one, regardless of outcome.
- `condition_applied` (bool) — `true` only if translation succeeded and the resulting ticker
  filter was actually used in the `strategy_signals` queries.
- `condition_note` (string | null) — populated in exactly two cases: translation failed (FR-007,
  explains what couldn't be applied) or the interpretation was ambiguous (FR-008, states which
  reading was used). `null` when the condition applied cleanly and unambiguously.

Per-list `note` text (already present per 032) is extended to name the condition when a
strategy's zero-candidate result is *caused* by it, e.g. `"no candidates currently qualify under
'liked stocks in the consumer staples sector' this week"` rather than the generic
032-era `"no candidates currently qualify this week"`.

**Rationale**: FR-006 (a real zero-match result) and FR-007 (translation failure, condition
silently dropped) are different failure surfaces the spec explicitly requires the response to
distinguish, and both must still let the rest of the answer stand. `condition_applied: false` +
non-null `condition_note` unambiguously signals "this condition was not used, here's why" — the
strategy lists are then computed exactly as if the condition had never been asked (FR-007's
"still answer whatever part of the question doesn't depend on it"). This mirrors the existing
`market_condition_note` / `market_condition_unavailable` pair (032 contracts) rather than
inventing a new shape.

**Alternatives considered**: A single free-text `condition_note` with no `condition_applied`
boolean — rejected, a consumer would have to string-match to tell "applied with a caveat" from
"not applied" apart, which the boolean makes explicit and testable.

---

### R8 — Does FR-008 (disclosing an ambiguous interpretation) need new machinery?

**Decision**: No new machinery. The condition-translation call's resulting pipeline is rendered
through the same `criteria_from_pipeline()` (moved per R3) already used by the free-form flow's
`criteria` field (031 FR-013) — and for a strategy-picks question, the top-level `criteria` field
(currently forced to `[]` per the 032 contract) is populated with this rendering whenever a
condition was successfully applied. The narration prompt is handed this same criteria text so
the model states the concrete interpretation used (e.g. "market cap over $10B") as part of the
prose answer, exactly like 031 already does for the free-form flow.

**Rationale**: Reusing the existing `criteria` field and rendering function means FR-008 is
satisfied by composition, not new UI or response surface — consistent with the spec's
Assumptions ("no new user-facing controls").

**Alternatives considered**: A dedicated `interpretation` field distinct from `criteria` —
rejected as redundant; `criteria_from_pipeline()`'s label format (e.g. `"market_cap > 10000000000"`)
already is a plain-language interpretation statement.
