# Contract: Deterministic Conviction Rules

**Feature**: `037-stocks-conviction-and-activity` | **Implements**: FR-005 – FR-014, FR-006a, FR-006b

**Producer**: `agent-runner/skills/conviction.py` (pure)
**Consumers**: `agent-runner/crew.py` (writes `conviction`, `conviction_rank`, `conviction_detail`),
`agent-runner/queue_worker.py` (change reasons), `backend/routers/analysis.py` (sort),
`frontend` (meter, filter, rationale, change history)

---

## Interface

```python
def run(ticker: str, data: dict) -> dict
```

Pure: the same `(ticker, data)` always yields the same output. No I/O, no LLM call, no
clock read except an injectable `now`. This is a rule-engine skill under Constitution
Principle III and carries the exhaustive pytest suite Principle I requires.

### Input `data`

| Key | Source in `crew.py` | Used for |
|-----|---------------------|----------|
| `the_strat` | `the_strat.run(...)` output (`strat_out`) | strategy call |
| `accumulation` | `accumulation.run(...)` output | strategy call |
| `gap_analysis` | `gap_analysis.run(...)` output (`gap_out`) | strategy call |
| `price_history` | `tools/price.py::get_price_history()` | daily + weekly z-scores |
| `financials` | `tools/financials.py::get_financials()` | revenue trend (via `tools/revenue.py`) |
| `market_flow` | `market_flow.run(...)` output (`flow_out`) | **caveat only**, never the level |

### Output

The `conviction_detail` object defined in [data-model.md](../data-model.md#conviction_detail-new),
plus `level` and `rank` at the top for convenience.

---

## Rule 1 — Strategy calls (FR-006a)

Each of the three stock-specific entry strategies resolves to exactly one of
`buy` / `not-buy` / `no-call`. `market_flow` and `position_management` are **not** consulted
here (FR-006b).

### `the_strat`

| Condition | Call |
|-----------|------|
| `tfc is None` | `no-call` (insufficient history) |
| `tfc.status == "full_bullish"` **and** ≥1 pattern with `direction in ("long", "either")` on `yearly`/`quarterly`/`monthly`/`weekly` | `buy` |
| anything else (`full_bearish`, conflict, or bullish TFC with no aligned trigger) | `not-buy` |

Patterns named `inside_bar_setup`, `kicking_bullish`, `kicking_bearish` do **not** count
toward alignment — the same `NON_TRIGGER_PATTERNS` exclusion `tools/strategy_signals.py`
applies (spec 032: an equilibrium state is not directional, and kickers need intraday
confirmation this app cannot supply).

### `accumulation`

| Condition | Call |
|-----------|------|
| insufficient-history early return | `no-call` |
| `signal == "ACCUMULATION"` **and** `distribution_warning is False` | `buy` |
| `EARLY_ACCUMULATION`, `NEUTRAL`, `DISTRIBUTION_WARNING` | `not-buy` |

`EARLY_ACCUMULATION` is deliberately **not** a buy: it means the pattern is only 1–2
sessions old, and admitting it would re-loosen the gate this feature exists to tighten.

### `gap_analysis`

| Condition | Call |
|-----------|------|
| `signal == "insufficient history"` or `latest_gap is None` | `no-call` |
| `latest_gap.direction == "down"` **and** `latest_gap.score >= 3` | `buy` |
| anything else | `not-buy` |

A **down**-gap is the long setup (the reversal/reclaim entry); score ≥ 3 is §9 of
`specs/gap_analysis_rules.md`, the same `GAP_SCORE_THRESHOLD` pinned in
`tools/strategy_signals.py`.

**`strategies.pass` = all three are `buy`.** `no-call` and `not-buy` both fail (FR-006,
spec Edge Case "Partial strategy coverage").

---

## Rule 2 — Z-score bottom quartile (FR-006, FR-011)

For each of `daily` and `weekly`:

1. Build the 20-period rolling close z-score series over `price_history[tf]`
   (same definition as `frontend/src/lib/indicators/zscore.ts` and
   `tools/screener.py::_price_signals`; a zero-variance window yields `z = 0`, not a
   divide-by-zero).
2. `window` = the trailing z-values — last **252** for daily, last **104** for weekly.
3. `p25 = percentile(window, 25)`.
4. `in_bottom_quartile = value <= p25` — **inclusive** of the boundary (FR-011).

| Sample size | Result |
|-------------|--------|
| daily `< 60` or weekly `< 30` z-values | that timeframe → `in_bottom_quartile: null`, added to `missing_inputs`, `zscore.pass = false` |

**`zscore.pass` = daily AND weekly both in bottom quartile.** One timeframe alone is not
enough (US2 scenario 4).

---

## Rule 3 — Revenue trend (FR-006)

Delegated to `agent-runner/tools/revenue.py::derive_revenue_trend(financials)`. **No new or
widened FMP call** — both figures come from data `get_financials()` already caches today
(research R4 Amendment: an earlier version of this contract called for a `limit=8`
quarterly fetch to support a `q[0]` vs `q[4]` comparison; that was reverted after
`KNOWN_ISSUES.md` surfaced that this FMP plan 402s the whole call beyond ~4 quarterly
periods):

| Figure | Computation | Requires |
|--------|-------------|----------|
| `growth_yoy` | `financials["growth"][0]["growthRevenue"]` — FMP's own annual YoY revenue growth (most recent fiscal year vs. the one before); the same figure `tools/screener.py` already exposes as `revenue_growth_yoy` | a non-empty `growth` list |
| `change_qoq` | `(q[0].revenue - q[1].revenue) / abs(q[1].revenue)` on the **newest-first** `financials["income_quarterly"]` series | ≥ 2 quarters (well within the existing `limit=4`) |

- `yoy_growing = growth_yoy > 0`
- `qoq_declining = change_qoq < 0`
- **`revenue.pass` = `yoy_growing and not qoq_declining`**

A `null` figure (short series, missing `revenue` key, or a zero denominator) means
`revenue.pass = false` plus an entry in `missing_inputs` — never a silent skip
(spec Edge Cases: "Revenue data gaps").

QoQ decline blocks **high** even when YoY is positive (clarification Q2; spec Edge Case
"Conflicting revenue signals").

---

## Rule 4 — Level assignment (FR-006, FR-007, FR-008)

| Level | `rank` | Rule |
|-------|--------|------|
| `high` | 3 | `strategies.pass` **and** `zscore.pass` **and** `revenue.pass` |
| `medium` | 2 | ≥ 2 of 3 strategies are `buy`, **and** ≥ 1 z-score timeframe in bottom quartile, **and** `not qoq_declining` |
| `low` | 1 | everything else |

Invariants a test must assert:

- `missing_inputs` non-empty ⇒ level is never `high` (FR-009).
- Flipping any single Rule-1/2/3 input of a `high` stock drops it below `high` (SC-004).
- `blockers == []` **iff** level is `high`; otherwise `blockers` names ≥1 failing condition (SC-003).
- `market_flow` content never changes `level` — only `caveats` (FR-006b, research R10).
- `rank` always matches `level` via `{high: 3, medium: 2, low: 1}`.

---

## Rule 5 — Integration into the analyses document (FR-012, FR-014)

`crew.py` MUST, after running the skill:

```python
detail = conviction.run(ticker, {...})
synthesis["conviction"] = detail["level"]          # overwrite the LLM's value
synthesis["conviction_rank"] = detail["rank"]
synthesis["conviction_detail"] = detail
```

and `agents/portfolio_strategist.py` MUST drop `conviction` from its `SCHEMA`, its
`required` list, its returned dict, and the numbered prompt instructions — so no LLM-authored
conviction can survive anywhere.

`skills/market_flow.py`'s own `conviction` key (timing confidence: `low|medium|high|max`) is
a **different value** and is left untouched inside `sub_reports.recommendation`. A test
asserts the document's top-level `conviction` equals `conviction_detail.level` and is
independent of `sub_reports.recommendation.conviction` (research R10).

---

## Backward compatibility

Analyses documents written before this feature have `conviction` but no `conviction_rank`
or `conviction_detail`.

- The feed sort treats a missing `conviction_rank` as `0`, sorting such tickers after all
  rated ones within their signal group (data-model rank table; spec Edge Case "unknown
  conviction sorts last").
- The detail page renders a "rating not yet recomputed — re-run analysis" note instead of a
  rationale when `conviction_detail` is absent, rather than erroring
  (spec Edge Case "Reason unavailable for an old change").
- No migration is run; documents self-heal on their next analysis.
