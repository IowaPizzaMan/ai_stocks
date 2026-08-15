# Phase 0 Research: The Strat Price-Action Rule Engine

## Current implementation coverage (FR → status)

Legend: ✅ implemented · 🟡 partial · ⬜ missing

| FR | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-001 | 4-way bar classification | ✅ | `bar_type()` |
| FR-002 | "Still Inside" unconfirmed until close | 🟡 | `run()` only ever receives closed historical bars from `get_price_history()`; there is no representation of a bar "still forming." Decision below. |
| FR-003 | Outside bar subtypes (Bullish/Bearish Engulfing, Regular) | ⬜ | `bar_type()` returns bare `"3"`, no subtype |
| FR-004/005 | Hammer / Shooting Star detection + in-force trigger | ✅ | `is_hammer`/`is_shooter`, trigger levels in `detect_patterns` |
| FR-006 | Momentum vs. Regular Hammer/Shooting Star | ⬜ | No trend-context check |
| FR-007 | Kicking patterns | ✅ | detected; in-force *tracking over time* not modeled (see FR-008) |
| FR-008 | Persist "in force" until period close or stop violation | ⬜ | `detect_patterns` is a single-snapshot read of the latest bar only |
| FR-009 | Universal-truth vs. conditional tagging | ⬜ | Not tagged in output |
| FR-010 | Momentum vs. retracement inside-bar breakout | ⬜ | `inside_bar_setup` has no such classification |
| FR-011 | Mother Bar identification + mid-range "avoid" flag | ⬜ | Not implemented |
| FR-012 | Multi-inside-bar chop flag | ⬜ | Not implemented |
| FR-013 | Inside-bar breakout entry trigger | ✅ | `buy_trigger`/`sell_trigger` on `inside_bar_setup` |
| FR-014 | All 4 canonical reversals | 🟡 | 2-1-2 ✅, 2-2 ✅, Failed-2-Goes-3 ⬜, 3-1-2 ⬜ |
| FR-015 | Rev Strat only after Inside Bar | ✅ | enforced via `t1 == "1"` checks |
| FR-016 | 2-bar vs. 1-bar Rev Strat distinction | ✅ | |
| FR-017 | 1-Bar Rev Strat flagged as BF risk | 🟡 | mentioned in free-text `note`, not a structured field |
| FR-018 | Soft Rev Strat | ⬜ | Not implemented |
| FR-019 | Cross-timeframe combinations | ⬜ | Each timeframe evaluated independently in `run()` |
| FR-020 | Hammer↔Shooting-Star counter reclassification | ⬜ | Not implemented |
| FR-021 | Measured-move projection | ⬜ | Not implemented |
| FR-022 | Per-timeframe color | ✅ | `_tfc()` |
| FR-023 | Full TFC / Conflict | ✅ | `_tfc()` |
| FR-024 | "In control" determination (shortest-two override) | ⬜ | `_tfc()` reports status only, no control field |
| FR-025 | Natural buyer/seller correlation flag | ⬜ | No correlated-instrument input |
| FR-026 | Fractal BF surfacing | ⬜ | Not implemented |
| FR-027 | Inside→Outside→Inside + next expansion level | ⬜ | Not implemented |
| FR-028 | Reclaiming-the-range / BF-failure flag | ⬜ | Not implemented |
| FR-029 | Retain BF highs/lows as S/R | ⬜ | Not implemented |
| FR-030/031 | App-specific TFC scope (excl. daily/intraday; incl. quarterly/yearly) + daily notable candle | ✅ | `_tfc()` excludes daily; `_daily_notable()` |
| FR-032 | Stacked signal count/types report | 🟡 | `run()` builds an `aligned` list inline for the signal string; not a structured checklist field |
| FR-033 | Entry trigger + stop per signal | 🟡 | Entry triggers present; **no stop/level-of-defense field anywhere** |
| FR-034 | Level of Defense conviction (looser/tighter) | ⬜ | Not implemented |
| FR-035 | Add-to-position guard | ⬜ | Not implemented (no position-state input) |
| FR-036–039 | Stop-placement rules (all signal types) | ⬜ | Entirely missing — largest single gap |
| FR-040–042 | VIX-ETN instrument-class rules | ⬜ | Entirely missing |

**Summary**: ~12 of 42 FRs fully covered, ~5 partial, ~25 missing. The missing set
clusters into five themes: (1) richer bar/pattern subtyping, (2) stop/level-of-defense
computation, (3) Broadening Formation tracking, (4) cross-signal/cross-timeframe
synthesis (checklist, combinations, measured move, "in control"), (5) VIX-ETN rules.

## Decisions

### D1 — "In force" tracking stays stateless (recomputed per run, not persisted)

**Decision**: Represent "in force" by scanning forward from a signal's trigger bar
through the subsequent bars already present in the window `get_price_history()`
returns (up to 5y monthly / 2y weekly / configured daily period), rather than
persisting signal state in MongoDB across runs.

**Rationale**: Every sibling skill (`market_flow.py`, `gap_analysis.py`,
`accumulation.py`, `position_management.py`) is a pure function recomputed from a
fresh data pull each call — there is no precedent in this codebase for a skill
persisting its own state, and `agent-runner`'s only persistence layer (`tools/db.py`)
is used by `crew.py` for run *results*, not skill-internal state. The available
window is large enough to recompute in-force status without carrying state forward.

**Alternatives considered**: A new Mongo collection keyed by
`(ticker, timeframe, signal_id)` storing trigger bar and last-checked bar — rejected
as unjustified complexity (new collection, index, and write path) for something the
existing window already makes derivable, and it would break the pattern of every
other skill in this file's neighborhood.

### D2 — Bid/offer proxy for momentum & Rev-Strat stops (FR-037/FR-039)

**Decision**: Where the source methodology's stop rule references "1 cent below the
bid" or "1 cent above the offer," use the triggering bar's **Close** as the bid/offer
proxy (i.e., stop = close ∓ $0.01), and document this explicitly as an approximation
in the field/notes, not as a literal live-quote computation.

**Rationale**: This app has no bid/ask or intraday feed (Assumptions in spec.md;
FR-030). `position_management.py` already sets precedent for approximating an
intraday/quote-driven concept with an OHLC-only stand-in (its trailing stop uses
`prior_day_low - buffer` rather than any live quote). FR-036/FR-038 need no proxy —
they reference the triggering bar's own high/low, which is already in hand.

**Alternatives considered**: Next-bar's open as the proxy — rejected because the
next bar doesn't exist yet at signal-detection time (this would require deferring
the stop computation by one bar, complicating the output contract for no accuracy
gain given the spec's own note that "this app's actual order-placement behavior...
is out of scope").

### D3 — Broadening Formation levels computed on the fly, not persisted

**Decision**: Derive prior BF highs/lows (FR-029) by scanning back through the
already-fetched OHLC window for prior Outside Bar extremes, recomputed each call —
no new Mongo collection.

**Rationale**: Consistent with D1; the 5-year monthly / 2-year weekly window already
returned by `get_price_history()` is sufficient lookback for the timeframes this app
tracks. Revisit only if a specific ticker/timeframe combination needs a longer
lookback than the window provides (not indicated by any current FR).

### D4 — Correlated instrument input for FR-025 / checklist Q8

**Decision**: `the_strat.run()` accepts an optional correlated-ticker price history
(e.g., a broad index or sector ETF) passed in by the caller, reusing the existing
`_tfc()` calculation against it. No new sector-mapping table is introduced in this
feature — the caller (`crew.py`) supplies which correlated ticker to use (a
configured default, e.g. `SPY`, is acceptable for the initial implementation).

**Rationale**: Keeps `the_strat.py` a pure function with an explicit input rather
than reaching out to fetch its own correlated data or requiring a new
sector-lookup service. Auto-selecting a sector ETF per ticker is a larger feature
(would need a sector/industry mapping this codebase doesn't currently have wired to
`the_strat.py`) and is out of scope here; a caller-supplied ticker satisfies FR-025's
acceptance scenario without it.

**Alternatives considered**: Auto-deriving the correlated ticker from
`backend/models/stock.py`'s sector field — deferred; would require `agent-runner` to
query `backend`'s Mongo collections for sector metadata, a new coupling not
currently justified by this spec's acceptance criteria (a single configured/broad
correlated instrument is sufficient per FR-025's wording, "a correlated broader-market
instrument").

### D5 — Output contract grows additively only

**Decision**: All new information (outside-bar subtype, stop, level_of_defense,
universal_truth, in_force, control, broadening_formation, pre_trade_checklist, etc.)
is added as new keys to the existing dicts `the_strat.run()` returns. No existing
key (`ticker`, `timeframes`, `tfc`, `daily_notable_candle`, `signal`) is renamed or
removed.

**Rationale**: `crew.py:152` and `agents/technical_analyst.py` already consume this
dict by key; an additive-only contract means neither needs a breaking-change
migration, though `technical_analyst.py`'s prompt should be updated (tracked as a
task, not part of this plan's code surface) to narrate the new fields it now has
available.

## NEEDS CLARIFICATION resolved

All Technical Context fields above are resolved from the existing codebase — no
open NEEDS CLARIFICATION markers remain.
