# Phase 0 Research: Weekly Strategy Buy/Short Picks in AI Chat

**Feature**: `032-weekly-strategy-picks` | **Date**: 2026-08-23

All items below were resolved through direct code reading (agent-runner and backend, this
session) and the clarification conversation recorded in `spec.md`. No open
`NEEDS CLARIFICATION` markers remain.

---

## R1: Market Flow cannot independently rank a ticker universe

**Decision**: Market Flow is not one of the two per-strategy scanners. It is applied at read time
as a shared filter/caveat over The Strat's and Gap Analysis's candidate lists (FR-017–FR-019).

**Rationale**: `agent-runner/skills/market_flow.py::run(ticker, data)` takes `data["breadth"]` —
the output of `tools/breadth.py::get_market_breadth()`, a **market-wide** NYMO/NAMO reading
identical for every ticker on a given day — plus that ticker's own (optional) gap data. Its own
rule spec (`specs/market_flow_rules.md`, §6) states plainly: *"NYMO alone is not a stock
picker... always combine with per-stock signals."* Running it across the full universe would
produce the same `recommendation` for nearly every ticker (breadth dominates the verdict), so it
cannot rank a top-N list the way The Strat and Gap Analysis do.

**Alternatives considered**:
- Keep as a nominal 3rd list ranked by conviction + gap score — rejected: its buy list would
  substantially overlap Gap Analysis's own picks (both driven by the same gap score under the
  same breadth backdrop), reading as redundant rather than a distinct third opinion.
- Drop Market Flow from the feature entirely — rejected: its market-timing read is exactly the
  kind of context a trader wants attached to a pick ("don't buy into this signal, the market's
  overbought"), so folding it in as a caveat/filter preserves that value without fabricating a
  list it has no rule basis to produce.

---

## R2: Multi-timeframe price data requires no new precomputation

**Decision**: `skills/the_strat.py::run()` is fed directly from `tools/price.py::get_price_history()`
with no new data-fetching layer needed.

**Rationale**: `get_price_history()` (`tools/price.py:46-59`) resamples weekly/monthly/quarterly/
yearly locally via pandas from the single stored `price_history` document
(`price_store.get_series(ticker, refresh="none", ...)` — `refresh="none"` never contacts an
external provider). This already covers the **full** universe: `price_store._load` keys only on
`{"ticker": ticker}`, with no `is_tracked` filter, and `screener.refresh_all()` already proves the
same `price_history` collection spans the tracked-plus-breadth-only union. Constitution
Principle IV is satisfied with zero new external calls.

**Alternatives considered**: None needed — the existing function already does exactly what this
feature requires.

---

## R3: The Strat and Gap Analysis are not currently precomputed for the full universe

**Decision**: A new agent-runner background job (`strategy_signals_refresh`, registered in
`tools/admin_jobs.py::JOB_HANDLERS`, enqueued via `work_queue`) runs both skills across every
ticker with a `price_history` document, on the same cadence class as `screener_refresh`.

**Rationale**: The only existing caller of `skills/the_strat.run()` / `skills/gap_analysis.run()`
is `agent-runner/crew.py`'s `AnalysisCrew.run()`, invoked once per ticker only when that ticker's
`work_queue` analysis job runs — not a full-universe scan, and not on a schedule a chat request
could rely on. FR-002/003/009 require ranking *all* screened tickers and returning **fresh**
results, so the scan must happen for the whole universe on its own refresh cycle, mirroring
`screener.py`'s `refresh_all()`/`refresh_one()`/`run_..._refresh(db)` shape exactly (same file
family, same `work_queue`-registered-admin-job dispatch via `queue_worker.py::_run_admin_job`).

**Alternatives considered**:
- Compute live, per request, only for the tickers that end up qualifying — rejected: there's no
  way to know which tickers qualify without running the skill on (most of) the universe first;
  this is exactly the precomputation model 031 already validated for the screener flow.
- Trigger via a new standalone timer loop, like `breadth_worker` — rejected: the codebase's own
  test comments call that pattern out as "the one deliberate exception" to Constitution
  Principle V ("all analysis triggering flows through `work_queue`, never cron"); a second
  standalone timer would compound rather than justify that exception. `work_queue` registration
  is the idiomatic path `screener_refresh` already demonstrates.

---

## R4: Market Flow's filter reads already-cached data — no new agent-runner work

**Decision**: The Market Flow filter (FR-017) is computed **in the backend**, at read time, from
the already-cached `breadth_cache` / `breadth_meta` collections — not precomputed by agent-runner.

**Rationale**: `breadth_worker.py` already refreshes NYMO/NAMO once per UTC day
(`settings.breadth_refresh_hour_utc`, gated by a `breadth_meta` `last_run_at` doc) and
`get_market_breadth()` itself caches per-exchange rows in `breadth_cache` keyed by
`computed_on: today`. Both collections are **already registered in `backend/db.py`**
(`BREADTH_CACHE`, `BREADTH_META`), so backend can read the latest NYSE row directly — no RPC to
agent-runner, no new agent-runner job, no new external call. `market_flow.py::classify_level()`
is a small, pure threshold ladder; backend gets its own copy
(`backend/semantic/market_flow_filter.py`) rather than importing agent-runner code, following the
same hand-duplication precedent already established for `llm.py` and the `db.py` collection
constants (031, Constitution Principle V — the two services share no Python package).

**Alternatives considered**: Precompute the filter value into `strategy_signals` alongside The
Strat/Gap Analysis fields — rejected: it's a single market-wide value, not a per-ticker one;
storing it once per ticker document would be pure duplication for no benefit, and reading
`breadth_cache` directly is one extra cheap Mongo read.

---

## R5: `strategy_signals` is a new collection, not new fields on `screener`

**Decision**: A dedicated `strategy_signals` collection (single writer: the new agent-runner
job), not additional fields on the existing `screener` documents.

**Rationale**: `screener.refresh_all()`/`refresh_one()` do a **full-document** `replace_one` per
ticker (`screener.py:228,258`). 031's own `data-model.md` explicitly flags this exact hazard for
`price_history`'s two writers: *"Do not add fields — both services `replace_one` the whole
document and would erase them."* A second job writing `the_strat`/`gap_analysis` fields onto
`screener` docs would have them silently wiped on the next `screener_refresh` cycle. `screener`
was also purpose-built flat specifically so a **free-form LLM-generated** query can reliably
target it (031 research.md R1) — this feature's fields are read only by deterministic Python
(FR-008), never by an LLM-authored pipeline, so there's no benefit to co-locating them and a real
risk in doing so.

**Alternatives considered**: Modify `screener.compute_signals()` itself to also call the two
skills and include their output in the same upserted document — rejected: couples an
already-shipped, already-tested feature (031) to this one's schedule and failure modes, and
still doesn't solve the "flat collection reserved for LLM queries vs. deterministic-only fields"
tension.

---

## R6: The response-timing clarification is satisfiable without new async infrastructure

**Decision**: No background-job-plus-polling architecture is needed to satisfy the spec's
Clarifications ("thinking indicator, then present in the same reply — no re-ask, no revisit,
no manual refresh").

**Rationale**: `frontend/src/pages/Chat.tsx` already renders `{chat.isPending && <p>thinking…</p>}`
around a single `useMutation` POST request (`frontend/src/hooks/useChat.ts`) — this is the exact
UX the clarification describes, already built, already satisfying Constitution Principle V's "no
polling" rule. Because R3–R5 move all the expensive per-ticker computation to a background
refresh job, the request-time cost of a strategy-picks question is two small Ollama calls plus
two cheap indexed Mongo reads — the same order of magnitude as 031's existing ~5–8s warm
response, not a long-running operation that would need its own status-check mechanism.

**Alternatives considered**: A `work_queue` job per chat request, with the frontend polling a
status endpoint — rejected outright once R3–R5 established that request-time work is cheap; it
would add exactly the async complexity the clarification's answer described (and Constitution
Principle V forbids) for no remaining reason.

---

## R7: Deriving direction and entry price per strategy

**Decision** (full derivation rules in [data-model.md](./data-model.md)):

- **The Strat**: direction comes from `the_strat.run()`'s existing `tfc.status`
  (`full_bullish`/`full_bearish`/`conflict`) combined with its already-computed per-timeframe
  `patterns` list; entry price is the matching pattern's own `buy_trigger`/`sell_trigger` field,
  preferring the weekly timeframe (the feature's "this coming week" framing) with a documented
  fallback order. No new pattern-detection logic — this is purely aggregating fields
  `detect_patterns()` already returns.
- **Gap Analysis**: direction comes from `latest_gap.direction` + `score >= 3` (the rule spec's
  own §9 actionability threshold) + `bias`; entry price is a **new** field added to
  `gap_analysis.run()`'s per-gap output — the pre-gap extreme (`prev_low`/`prev_high`, already
  computed locally inside the existing loop, just not currently returned), i.e. the "gap-fill
  level" the rule spec already describes in §8.

**Rationale**: Both strategies already compute everything needed except one missing field (gap
entry price), which is a small, additive change to an existing pure function — no redesign of
either skill's rule logic, keeping this feature a consumer of the existing rule engines rather
than a reimplementation of them (Constitution Principle III).

**Alternatives considered**: Compute entry price as a generic band off last close (spec's
rejected clarification option) — already decided against during `/speckit-specify`
(spec.md Clarifications), so not revisited here.
