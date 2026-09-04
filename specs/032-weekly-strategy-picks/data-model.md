# Phase 1 Data Model: Weekly Strategy Buy/Short Picks in AI Chat

**Feature**: `032-weekly-strategy-picks` | **Date**: 2026-08-23

---

## New collection: `strategy_signals`

One flat document per ticker, covering the same universe as `screener` (every ticker with a
`price_history` document — tracked plus breadth-only). Written solely by the new agent-runner job
`strategy_signals_refresh`; read solely by backend's `semantic/strategy_picks.py` (never by a
free-form LLM-generated query — see research.md R5). Registered as
`STRATEGY_SIGNALS = "strategy_signals"` in **both** `backend/db.py` and
`agent-runner/tools/db.py`, per the Constitution Principle VI hand-sync convention.

### Document shape

```jsonc
{
  "ticker": "AAPL",
  "signals_as_of": "2026-08-23T21:05:00Z",
  "insufficient_history": false,
  "the_strat": {
    "direction": "long",          // "long" | "short" | null
    "pattern": "revstrat_2bar_bullish",   // name from skills/the_strat.py::detect_patterns()
    "timeframe": "weekly",        // which timeframe's pattern supplied entry_price
    "entry_price": 187.50,        // that pattern's buy_trigger / sell_trigger
    "strength": 3                 // count of aligned timeframes, 0-4 (see derivation below)
  },
  "gap_analysis": {
    "direction": "long",          // "long" | "short" | null
    "score": 4,                   // skills/gap_analysis.py latest_gap.score, 0-5
    "entry_price": 182.10,        // NEW field: pre-gap reversal/fill level
    "bias": "LONG at day 3+"      // latest_gap.bias, carried through verbatim
  }
}
```

### Field derivation

**`the_strat` block** — built entirely from `skills/the_strat.py::run()`'s existing output, no
new pattern-detection logic:

1. Call `the_strat.run(ticker, get_price_history(ticker))` (same call shape `crew.py` already
   uses).
2. `direction`: `"long"` if `tfc["status"] == "full_bullish"`, `"short"` if `"full_bearish"`,
   `null` if `"conflict"` or the ticker has insufficient history for `the_strat.run()` to compute
   TFC at all (its own `"insufficient ... history"` short-circuit).
3. `strength`: count of `{yearly, quarterly, monthly, weekly}` timeframes that have at least one
   actionable pattern (`timeframes[tf]["patterns"]`, excluding `inside_bar_setup` — an
   equilibrium-only state, not a directional signal) whose `direction` matches `either` or the
   resolved `direction` above. Range 0–4; only timeframes actually aligned with the full-TFC call
   count, consistent with `the_strat.run()`'s own `signal` string construction.
4. `pattern` / `timeframe` / `entry_price`: the matching pattern from the **weekly** timeframe if
   one exists; else the nearest of `{monthly, quarterly, yearly}` in that order (weekly is
   preferred because "this coming week" is the feature's framing — a monthly-only aligned setup
   still qualifies for `direction`/`strength` but its trigger price is a different time horizon,
   which is why the source timeframe is recorded). `entry_price` is that pattern's `buy_trigger`
   (long) or `sell_trigger` (short) verbatim — never recomputed.
5. If no pattern exists on any of the four timeframes despite `direction` being set (rare —
   `tfc["status"]` can be aligned purely on candle color with no actionable trigger on any
   timeframe), `direction` is forced to `null`: FR-012 requires excluding a candidate the system
   cannot give a defensible price for, and TFC color alignment alone isn't a trigger level.

**`gap_analysis` block** — built from `skills/gap_analysis.py::run()`, plus one small additive
field on that function's existing per-gap output:

1. Call `gap_analysis.run(ticker, get_price_history(ticker)["daily"], market_trend=..., nymo=...)`
   (same call shape `crew.py` already uses; `market_trend` and `nymo` are optional context this
   job already has available from the same background pass — see Market Flow note below).
2. **New field on `gap_analysis.run()`'s gap dict**: `reversal_level` — the pre-gap extreme,
   `prev_low = df["Low"].iloc[i-1]` for a down gap, `prev_high = df["High"].iloc[i-1]` for an up
   gap. Both values are already computed locally inside the existing gap-detection loop
   (`gap_analysis.py:160`); this only adds them to the returned dict — no new computation, no
   change to `_score_gap`/`_bias`/`_gap_type` rule logic.
3. `direction`: `"long"` if `latest_gap.direction == "down"` and `latest_gap.score >= 3`;
   `"short"` if `latest_gap.direction == "up"` and `latest_gap.score >= 3`; `null` otherwise
   (no gap in the lookback window, or score below the rule spec's own §9 actionability
   threshold).
4. `entry_price`: `latest_gap.reversal_level` verbatim.
5. `score` / `bias`: carried through verbatim from `latest_gap`.

### Validation rules

- `ticker` unique; natural key for upsert (`replace_one(..., upsert=True)`, single writer — no
  cross-writer hazard, unlike the rejected "add fields to `screener`" alternative, research.md R5).
- `insufficient_history: true` (fewer than the minimum bars either skill needs) forces both
  `the_strat.direction` and `gap_analysis.direction` to `null` rather than a fabricated result.
- `entry_price` is never null when `direction` is non-null, and vice versa — a candidate with a
  direction but no defensible price is dropped entirely (FR-012), not stored half-populated.

### Indexes

```
{ticker: 1}                          unique
{"the_strat.direction": 1, "the_strat.strength": -1}
{"gap_analysis.direction": 1, "gap_analysis.score": -1}
```

Compound, unlike `screener`'s single-field indexes — this collection is queried by exactly one
deterministic code path (`semantic/strategy_picks.py`) with a fixed predicate/sort shape per
strategy, not by unpredictable LLM-generated pipelines (031 research.md R8's reasoning for
single-field indexes doesn't apply here).

### Lifecycle

Rebuilt per ticker on each `strategy_signals_refresh` run via `replace_one(..., upsert=True)`,
same cadence class as `screener_refresh`. No TTL — `signals_as_of` makes staleness visible, same
convention as `screener`. Removed when a ticker is removed, alongside `screener`'s existing
per-ticker cleanup.

---

## Market Flow filter (not persisted — computed at read time)

**Source**: latest `breadth_cache` row where `exchange: "nyse"`, sorted by `date` descending
(already-cached NYMO reading — research.md R4). No new collection.

**Classification** (`backend/semantic/market_flow_filter.py`, a small pure port of
`skills/market_flow.py::classify_level()` — same thresholds, duplicated per the established
hand-dup precedent, not imported):

| NYMO reading | Buy-list effect | Short-list effect |
|---|---|---|
| `> 60` (overbought) | Exclude candidate; caveat: "market is overbought, breadth doesn't support new buys this week" | No override — overbought breadth doesn't contradict a short candidate |
| `-40` to `60` (neutral/mild) | No override — surfaced as an informational caveat only if the strategy's own signal is already borderline (not required for FR-017's minimum bar) | No override |
| `< -60` (oversold) | No override — oversold breadth doesn't contradict a buy candidate | Exclude candidate; caveat: "market is oversold, breadth doesn't support new shorts this week" |

This mirrors `market_flow.py`'s own §1/§3 tables (`AVOID_ADD`/`TRIM` territory above +60,
`BUY_MORE` territory below -60) collapsed to the binary include/exclude behavior FR-017 requires,
rather than porting all six `RecommenderAgent` recommendation states — this feature needs a
buy/short gate, not a full position-management verdict.

**Missing data** (FR-018): if `breadth_cache` has no row for today or NYMO is `null`, the filter
step is skipped entirely — both strategies' lists are still returned, with a top-level note that
the market-condition filter couldn't be applied.

---

## Transient entities (not persisted)

### StrategyPicksIntent
`{ is_strategy_picks: bool, direction: "buy" | "short" | null, count: int | null,
named_strategy: string | null }` — the backend's first Ollama call output (constrained JSON
schema, `temperature: 0`, mirrors 031's query-generation call shape). Never stored; used once to
drive the deterministic query.

### StrategyCandidate
`{ ticker, entry_price, strategy: "the_strat" | "gap_analysis", strength_or_score,
market_flow_caveat: string | null, market_flow_excluded: bool }` — one per ranked result, built
by deterministic Python, handed to the narration call, then discarded.

### StrategyPicksResponse (additive to 031's `ChatResponse`)
See [contracts/strategy-picks-api.md](./contracts/strategy-picks-api.md) for the full shape.
