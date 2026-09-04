# Phase 0 Research: Stocks Page Organization, Conviction Rework & Activity Trail

**Feature**: `037-stocks-conviction-and-activity` | **Date**: 2026-09-04

All Technical Context unknowns are resolved below. No `NEEDS CLARIFICATION` remains.

---

## R1 — Where the conviction rating is computed

**Decision**: A new pure rule-engine skill, `agent-runner/skills/conviction.py`, exposing
`run(ticker: str, data: dict) -> dict`. `crew.py` calls it after the existing skills and
**overwrites** `synthesis["conviction"]` with the computed value before the analyses
document is assembled. `conviction` is removed from `portfolio_strategist`'s JSON schema
and from its prompt.

**Rationale**: The bug the user reported ("most of the stuff is ending up a 3") is the exact
failure Constitution Principle III predicts. Today `agents/portfolio_strategist.py` asks a
7B–14B local model to emit `conviction: high|medium|low` as a free judgement, with a prompt
that nudges toward "very high conviction"; the model has no calibration pressure, so it
saturates. Moving the level into a pure function makes it deterministic, exhaustively
testable (Principle I), and auditable independent of model quality.

Keeping it a *skill* rather than a helper in `crew.py` matters: skills are the project's
declared "pure functions with no LLM calls, exhaustive pytest suite" surface, and this is
now the highest-value new member of that set.

**Alternatives considered**:
- *Post-process the LLM's answer in `crew.py`* — rejected: hides rule logic in orchestration
  code where it is awkward to unit-test, and blurs the skills boundary Principle III draws.
- *Keep the LLM's conviction, add a separate "buy gate" field* — rejected: the user's whole
  point is that the number on the meter must mean "buy"; two competing numbers is worse than
  one wrong one, and FR-012 requires board / filter / detail page to agree.
- *Tighten the prompt instead* — rejected: Principle III explicitly assumes small models are
  unreliable at rule-following under tool-calling pressure. A prompt tweak is untestable and
  would regress silently on a model swap.

---

## R2 — Mapping each entry strategy's output to {buy, not-buy, no-call}

**Decision** (satisfies FR-006a; full table in [contracts/conviction-rules.md](./contracts/conviction-rules.md)):

| Strategy | Source field | `buy` when | `no-call` when |
|----------|--------------|-----------|----------------|
| `the_strat` | `tfc.status`, `timeframes[tf].patterns` | `tfc.status == "full_bullish"` **and** ≥1 actionable long/either pattern on yearly/quarterly/monthly/weekly | `tfc is None` (insufficient history) |
| `accumulation` | `signal`, `distribution_warning` | `signal == "ACCUMULATION"` (score ≥ 3) and not `distribution_warning` | insufficient-history early return |
| `gap_analysis` | `latest_gap.direction`, `latest_gap.score` | `latest_gap.direction == "down"` **and** `latest_gap.score >= 3` (a down-gap is the long/reversal setup) | `signal == "insufficient history"` or `latest_gap is None` |

Everything else is `not-buy`. Per FR-006 both `not-buy` and `no-call` fail the gate; the
distinction exists only so FR-009/FR-010 can say *why* ("no call — not enough history"
reads differently from "bearish").

**Rationale**: Each mapping reuses a threshold the rule specs already set, rather than
inventing a new one:
- `gap_analysis` score ≥ 3 is §9 of `specs/gap_analysis_rules.md` ("Score >= 3 = act on
  signal. Score <= 2 = skip or paper trade only") — the same constant
  `tools/strategy_signals.py` already pins as `GAP_SCORE_THRESHOLD`.
- The `the_strat` rule ("full TFC + at least one aligned trigger") is exactly
  `tools/strategy_signals.py::_the_strat_block`'s existing `direction == "long"` +
  `strength >= 1` derivation, which spec 032 already argued for: TFC aligned on candle
  colour alone, with no trigger level anywhere, is not a defensible entry.
- `accumulation` requires the confirmed `ACCUMULATION` state (score ≥ 3), not
  `EARLY_ACCUMULATION`. "Early" means the pattern is only 1–2 sessions old; admitting it
  would re-loosen exactly the gate this feature exists to tighten.

**Consistency guard**: `conviction.py` implements these mappings directly against raw skill
output and does **not** import `tools/strategy_signals.py` — skills must not depend on
tools. A test in `agent-runner/tests/test_conviction.py` asserts that, for the same
`price_history`, `conviction`'s `the_strat`/`gap_analysis` calls agree with
`strategy_signals.compute_signals()`'s directional blocks. This is the Principle VI pattern
(consistency enforced by mirrored test, not by a shared import).

**Alternatives considered**: treating a `no-call` strategy as "skipped" rather than a
failure — rejected; the spec's Edge Cases pin it as not-a-buy, and skipping would let a
data-poor ticker qualify more easily than a well-covered one, which is backwards.

---

## R3 — Daily & weekly z-score, and the "bottom quartile" window

**Decision**: Compute a 20-period rolling close z-score series over
`price_history["daily"]` and `price_history["weekly"]` inside `conviction.py` (pure, from
data `crew.py` already fetched). A timeframe is *bottom-quartile* when its latest z-value
is `<= numpy.percentile(window, 25)` — inclusive, per FR-011 — where `window` is that
timeframe's own trailing z-series (daily: last 252 values; weekly: last 104). If fewer
than 60 daily or 30 weekly z-values exist, that timeframe is `no-call` and the stock cannot
be high (FR-009).

**Rationale**: 20 periods is already the project's canonical z-score window in two places —
`frontend/src/lib/indicators/zscore.ts` (`ZSCORE_WARMUP = 20`, spec 021 FR-007) and
`tools/screener.py::_price_signals` (`zscore_20d`). Reusing it keeps the number the user
sees on the Charts tab and the number gating conviction the *same* number, which matters
because FR-010's rationale will reference it.

The quartile is over the stock's **own** trailing history (spec Assumptions: not
cross-sectional), which makes "cheap for this stock" the test rather than "cheap versus
other stocks I happen to track" — the latter would drift as the watchlist changes.

Window lengths are bounded by what `tools/price.py::get_price_history()` already returns:
`daily` sliced to `1y` (~252 bars → ~232 z-values after the 20-bar warmup) and `weekly`
sliced to `2y` (~104 bars → ~84 z-values). The 252/104 caps are therefore "take what's
there", and the 60/30 minimums reject a newly-listed ticker whose quartiles would be noise.

**Alternatives considered**:
- *Read `screener.zscore_20d`* — rejected: it is a single daily scalar with no weekly
  counterpart and no distribution, so it cannot answer the quartile question, and reading a
  collection would make the skill impure.
- *Percentile over the raw close price instead of the z-series* — rejected: z-score is what
  the user asked for by name, and it already normalises for the trend.
- *Cross-sectional quartile across all tracked tickers* — rejected in the spec's
  Assumptions; also unstable as the universe changes.

---

## R4 — Revenue YoY and QoQ inputs

**Decision (revised during implementation — see Amendment below)**: Derive both figures in a
new pure module `agent-runner/tools/revenue.py` (`derive_revenue_trend(financials: dict) ->
dict`) entirely from data **already cached today, with no endpoint or limit change**:

- `growth_yoy` = `financials["growth"][0]["growthRevenue"]` — FMP's own annual
  year-over-year revenue growth figure (most recent fiscal year vs. the one before),
  fractional. Favourable when `> 0`.
- `change_qoq` = `financials["income_quarterly"][0].revenue` vs
  `financials["income_quarterly"][1].revenue` — sequential decline blocks **high**. Only
  needs 2 of the 4 already-cached quarters.
- Missing/short series → `None` for the affected figure, a revenue-condition failure per
  FR-009.

A separate pure module (rather than folding it into `conviction.py`) keeps the skill's input
a plain dict and lets the revenue derivation be unit-tested against fixture statements on
its own.

**Note on the existing field**: `tools/screener.py` already computes this exact
`growthRevenue` value into its own `revenue_growth_yoy` field. `conviction.py`'s
`tools/revenue.py` reads the same underlying `financials["growth"]` payload independently
(not by reading the `screener` collection, which would make the skill impure) — the two
call sites deliberately compute the identical figure from the identical cached payload, they
just aren't allowed to share it via a collection read.

### Amendment (implementation-time correction, Constitution Principle II)

The original decision above (recorded during `/speckit-plan`) proposed widening
`ENDPOINTS["income_quarterly"]` from `limit=4` to `limit=8` so a true *quarterly*
year-over-year comparison (`q[0]` vs `q[4]`) would be possible. **This was wrong** and was
caught during `/speckit-implement` by re-reading `KNOWN_ISSUES.md`'s "Upstream / API-tier
constraints" section, which documents as a standing fact: *"quarterly statements 402 beyond
~4 periods → `limit=4`"*. On this FMP plan, requesting more than ~4 quarterly periods
doesn't return fewer rows — it 402s the **entire call**, which `_fetch_statement()` already
treats as `outcome: "unavailable"` and degrades to `[]`. Shipping the `limit=8` change would
have **silently broken today's working `income_quarterly` fetch** (4 quarters → zero),
regressing `agents/fundamental_analyst.py`'s existing consumption of that field — the
opposite of Principle IV's "fail soft" intent.

The corrected design needs no 5th quarter at all: FMP's `income-statement-growth` endpoint
(the `growth` key, already fetched at `limit=4`, **annual** by default) already computes a
year-over-year revenue growth figure per fiscal year — reusing it (as `tools/screener.py`
already does under a different field name) satisfies clarification Q2's "growing revenue
YoY" condition with a same-call, zero-new-request implementation. QoQ only ever needed 2 of
the 4 quarters already cached, so it was never at risk.

**No change to `agent-runner/tools/financials.py` is made by this feature.**

**Alternatives considered**:
- *Reuse `screener.revenue_growth_yoy` by reading the `screener` collection* — rejected:
  would make the skill impure (skills read only what `crew.py` hands them, per Principle
  III); reading the same upstream `financials["growth"]` payload independently costs nothing
  extra and keeps the skill pure.
- *Add `income-statement-growth?period=quarter`* — rejected: an unverified second FMP call
  per ticker against a 250/day budget, for a number a cheaper reuse already supplies, and
  quarterly `income-statement-growth` may hit the same >4-period 402 wall documented above.
- *TTM revenue comparison* — rejected in clarification Q2.
- *Widen `income_quarterly` to `limit=8` (original decision)* — rejected per the Amendment
  above: breaks on this FMP plan tier instead of adding rows.

---

## R5 — Board ordering and stable pagination

**Decision**: Write a numeric `conviction_rank` onto each `analyses` document alongside
`conviction` (`high→3, medium→2, low→1, missing/unknown→0`). Change
`GET /analysis/feed`'s sort from `.sort("timestamp", -1)` to
`.sort([("conviction_rank", -1), ("ticker", 1)])`, add the matching compound index, and
change `frontend/src/lib/groupFeed.ts` to **preserve incoming order** instead of re-sorting
each bucket by `timestamp` descending.

**Rationale**: Three facts make this work out simply.
1. `analyses` carries a **unique index on `ticker`** (`tools/db.py:131`, `backend/db.py:126`)
   — one document per ticker — so `(conviction_rank desc, ticker asc)` is a *total* order
   with no ties.
2. A subsequence of a totally-ordered list is itself ordered. The board groups by signal on
   the client, so each signal bucket is automatically conviction-desc-then-A→Z without the
   server needing to know about grouping at all.
3. `skip`/`limit` paging over a total order means page *n+1* sorts strictly after page *n*,
   so "Load more" only ever appends — satisfying FR-003's no-reflow requirement with no
   cursor machinery.

Sorting on the string `conviction` directly would order it alphabetically
(`high < low < medium`) — wrong — hence the numeric rank field. Storing the rank rather than
computing it with a Mongo `$switch` in an aggregation keeps the endpoint a plain indexed
`find()`, which is what today's fast path is.

`groupBySignal`'s current `sort(...)` by `timestamp` must go, or it would undo the server
order on every render. Its docstring already promises it is "pure and stateless — called
with the full flattened item list on every render"; dropping the sort strengthens that.

**Alternatives considered**:
- *Sort client-side over loaded items only* — rejected by clarification Q6: "Load more" would
  insert earlier-sorting tiles above already-visible ones and reflow the board.
- *Fetch the whole universe and sort in the browser* — rejected: drops incremental loading,
  and spec 027 deliberately made loading explicit and bounded.
- *Aggregation pipeline with a computed rank* — rejected: heavier than a `find()` on an
  indexed field, for a value that is already known at write time.

---

## R6 — One event collection for both the activity feed and the change history

**Decision**: One new append-only collection, `stock_events`, serving both US3 and US5.
Event types `added` and `updated`; an `updated` event carries `changed: bool` plus, when
changed, the `signal`/`conviction` transitions and a reason string.

- **US3 activity feed** = last 100 events across all tickers, newest first, paged.
- **US5 per-stock trail** = that ticker's events, newest first, capped at 20.

Written at two points, mirroring where the underlying facts are already produced:
- `added` — `agent-runner/tools/db.py::register_ticker()` and `backend/routers/queue.py`'s
  registration branch (the two existing registration paths).
- `updated` — `agent-runner/queue_worker.py`, at the single existing
  `write_db(ANALYSES, result, upsert_key="ticker")` call site, using the previous document
  read just before the write.

**Rationale**: Clarification Q5 settled that the activity feed logs *every* re-analysis with
changed ones flagged — which makes the feed a strict superset of the change history. Two
collections would mean two writers producing overlapping records that could disagree; one
collection with a `changed` flag makes the per-stock view a filter over the same rows.
Principle V ("do not add infrastructure ahead of a demonstrated need") points the same way.

The change-reason for a conviction transition comes from the new `conviction_detail` block
(which condition flipped), not from LLM narration — FR-028 requires this, and R1 makes it
available for free.

**Precedent**: `market_flow_events` is already an append-only event collection with a
`created_at` descending index, so this is an established pattern in the codebase, not a new
one.

**Alternatives considered**:
- *Separate `activity_events` + `verdict_changes`* — rejected as duplicated writers for
  overlapping data.
- *Derive the feed on the fly from `ticker_index.first_seen_at` + `analyses.timestamp`* —
  rejected: `analyses` is upserted per ticker (unique index), so it keeps only the *latest*
  timestamp. Update history is unrecoverable without an event log. This is precisely why
  clarification Q7 could only back-fill `added`.
- *Reuse `crew.py`'s existing `changes_since_last`* — it computes the right diff but is
  stored on the (overwritten) analyses document, so it holds one diff, not a history. It is
  reused as the *shape* for the transition payload rather than as storage.

---

## R7 — Back-fill of `added` events (FR-021a)

**Decision**: A one-shot script, `backend/scripts/backfill_stock_events.py`, that inserts one
`added` event per existing `ticker_index` document dated from its `first_seen_at`, skipping
any ticker that already has an `added` event (idempotent). No `updated` back-fill.

**Rationale**: `ticker_index` already records `first_seen_at` on insert
(`tools/db.py:286`, `$setOnInsert`), so `added` history is fully reconstructible and the
feed is useful on day one. `updated` history is not reconstructible (see R6), which is
exactly what clarification Q7 chose. Idempotency lets the script be re-run safely, which
matters in a local-first setup with no migration framework.

Placed in `backend/` because it is an operator action against the database, and the backend
already owns `ticker_index` lifecycle endpoints.

**Alternatives considered**: seeding one `updated` event per ticker from
`analyses.timestamp` (spec clarification option C) — rejected by the user; it would also
imply a `changed` state that was never actually observed.

---

## R8 — Navigational breadcrumbs

**Decision**: Frontend-only. A pure `frontend/src/lib/breadcrumbs.ts`
(`trailFor(pathname, hash, context) -> Crumb[]`) plus a presentational
`components/layout/Breadcrumbs.tsx` mounted once in `App.tsx`'s layout, above `<Routes>`.

Trail derivation from the existing routes in `App.tsx`:

| Route | Trail |
|-------|-------|
| `/` | `Stocks` |
| `/stock/:ticker` | `Stocks / <TICKER>` |
| `/stock/:ticker#news` | `Stocks / <TICKER> / News` |
| `/sectors/:sector?` | `Sectors` / `Sectors / <Sector>` |
| `/news`, `/macro`, `/watchlist`, `/earnings`, `/institutional-flow`, `/congress`, `/chat` | that page's name only |

**Rationale**: FR-026 requires the trail to be derived from the *current location*, not from
navigation history, so a deep link renders a full trail. React Router v6 already exposes
`useLocation()`; a pure function over `pathname` + `hash` satisfies this and is trivially
unit-testable, which FR-025's "no dangling separator" edge case needs.

The stock detail page keeps tab state in the URL **hash** (`StockDetail.tsx:55`,
`TABS.some(t => t.id === hash)`), so the third crumb reads the hash — no routing change and
no new route segments. Mounting once in the layout rather than per-page guarantees the
consistency FR-023 asks for.

**Alternatives considered**:
- *A breadcrumb context populated by each page* — rejected: pages could forget to set it, and
  it reintroduces the history dependence FR-026 forbids.
- *Converting stock tabs from hash to route segments* — rejected as scope creep; it would
  break existing bookmarks for no gain here.

---

## R9 — Semantic layer scope (Constitution Principle VI)

**Decision**: `stock_events` is **not** added to `backend/semantic/query_guard.py`'s
`READABLE_COLLECTIONS` and gets no `backend/semantic/schema.py` entry in this feature.

**Rationale**: Principle VI states that admitting a collection to `READABLE_COLLECTIONS`
obliges a mirrored field-vocabulary contract test in *both* services plus a fully described
schema, and that admitting one without that pair is incomplete. Nothing in this spec asks
the chat AI to answer questions about the activity feed, so taking on that obligation now
would be scope the user did not request. The collection stays server-internal, served only
by its own endpoints.

If chat access is wanted later it is a small, well-defined follow-up: schema entry +
`test_stock_events_contract.py` (backend) and `test_stock_events.py` (agent-runner) extended
to the mirrored-vocabulary form that `screener` already demonstrates.

**Note on `analyses`**: the two new fields (`conviction_rank`, `conviction_detail`) are added
to a collection that is likewise not in `READABLE_COLLECTIONS`, so the same reasoning applies
and no schema change is needed.

---

## R10 — Surfacing the `market_flow` timing caveat (FR-006b)

**Decision**: `market_flow`'s existing per-run output is passed to `conviction.run()` as
context only. When its `recommendation` is not a buy-side verdict, the conviction rationale
appends a caveat line (e.g. "market breadth is overbought — timing headwind"), and the level
is unchanged.

**Rationale**: Clarification Q4 removed `market_flow` and `position_management` from the
gate because both are market-wide/position-scoped rather than per-ticker entry calls, and
gating on breadth would make **high** unreachable outside oversold windows. The caveat keeps
the information visible where the user acts on it.

**Naming hazard to avoid**: `skills/market_flow.py` **already returns its own
`conviction` key** (`"low" | "medium" | "high" | "max"`) describing *timing* confidence, and
`agents/recommender_agent.py` passes it through. That is a different value from the board's
rating. The new field is named `conviction_detail` on the analyses document, and
`market_flow`'s key is left untouched — but any code touching both must not conflate them,
and a test asserts the analyses document's `conviction` comes from the skill, not from
`sub_reports.recommendation.conviction`.

---

## Resolved Outstanding item from `/speckit-clarify`

The clarify pass left one Outstanding item: *"quarterly-revenue series availability for
QoQ — defer to `/speckit-plan` research."* **Resolved in R4** (and corrected during
`/speckit-implement`, see R4's Amendment): QoQ only ever needed 2 of the already-cached 4
quarters; YoY is satisfied by reusing the already-cached annual `growth` figure. Both are
derivable from data `get_financials()` fetches today, with **no endpoint or limit change**.
