# Phase 1 Data Model: The Strat Price-Action Rule Engine

This feature has no database schema — `the_strat.py` is a pure-function library, and
per [research.md](./research.md) (D1/D3) no new persistence is introduced. "Data
model" here means the shape of the Python dicts flowing through `the_strat.run()`'s
input and output, which is the contract other code (`crew.py`,
`agents/technical_analyst.py`, and this module's own tests) programs against.

## Entities

### Bar (per timeframe, per index `i`)

Existing shape, extended:

| Field | Type | Status | Notes |
|---|---|---|---|
| `type` | `"1" \| "2U" \| "2D" \| "3"` | existing (`bar_type()` return) | FR-001 |
| `outside_subtype` | `"bullish_engulfing" \| "bearish_engulfing" \| "regular" \| None` | **new** | only set when `type == "3"`; FR-003 |
| `closed` | `bool` | **new**, defaults `True` | `False` only for a bar the caller marks still-forming; see FR-002 note below |
| `candle_color` | `"green" \| "red"` | existing (`_color()`) | |

**FR-002 note**: `get_price_history()` returns only fully-closed historical bars, so
in practice every bar `the_strat.py` receives already has `closed=True`. The
`closed` field exists so a future caller *can* pass a still-forming bar (e.g. an
in-progress weekly/monthly bar built from partial data) without the module needing
to change; `detect_patterns`/`bar_type` must report `"Still Inside"` rather than a
finalized `"1"` when `closed=False`. No current call site sets `closed=False` —
this is forward compatibility, not new caller-facing behavior in this iteration.

### ActionableSignal (each entry in a timeframe's `patterns` list)

| Field | Type | Status | Notes |
|---|---|---|---|
| `name` | `str` | existing | e.g. `"hammer"`, `"revstrat_2bar_bullish"` |
| `direction` | `"long" \| "short" \| "either"` | existing | |
| `buy_trigger` / `sell_trigger` / `in_force_above` / `in_force_below` | `float` | existing | signal-type-specific, as today |
| `note` | `str` | existing | human-readable rationale |
| `universal_truth` | `bool` | **new** | FR-009 — `True` for Inside Bar Breakout, Rev Strat (any variant), Broadening Formation; `False` for Hammer, Shooting Star, Kicking Pattern |
| `momentum` | `bool \| None` | **new** | FR-006 (Hammer/Shooting Star only) / FR-010 (inside-bar breakout only); `None` where not applicable |
| `stop` | `float` | **new** | FR-033/FR-036–039 — computed per the applicable execution rule for this signal's type |
| `level_of_defense` | `"tight" \| "normal" \| "loose"` | **new** | FR-034 — derived from corroborating-evidence count (stacked signals, Full TFC alignment, BF alignment) and time-to-exhaustion |
| `in_force` | `bool` | **new** | FR-008 — `True` once trigger breached and neither the period closed nor `stop` violated |
| `soft` | `bool` | **new**, Rev Strat only | FR-018 — `True` when only one side breached but open/close remain within the inside bar's range |

### ReversalPattern (subset of ActionableSignal, reversal-specific names)

Extends the existing `212_reversal_*` / `22_reversal_*` / `revstrat_1bar_*` names
with two new pattern names:

| `name` | Trigger condition | FR |
|---|---|---|
| `failed_2_goes_3_bullish` / `_bearish` | A 2U (or 2D) bar fails to hold and the *same* bar's range also breaches the opposite side, without a preceding inside bar (distinguishes from `revstrat_1bar_*`, which requires `t1 == "1"`) | FR-014 |
| `312_reversal_bullish` / `_bearish` | `bar[i-2] == "3"` at a high/low, `bar[i-1] == "1"`, `bar[i]` is 2U (bullish) or 2D (bearish) back into the prior range | FR-014 |

### TimeFrameContinuityResult (`tfc` key in `run()`'s output)

Existing shape, extended:

| Field | Type | Status | Notes |
|---|---|---|---|
| `<timeframe>` | `"green" \| "red"` | existing | one key per tracked timeframe (weekly/monthly/quarterly/yearly) |
| `status` | `"full_bullish" \| "full_bearish" \| "conflict"` | existing | |
| `last_sale` | `float` | existing | |
| `control` | `list[str]` | **new** | FR-024 — timeframe(s) currently "in control"; shortest-two-agreement overrides longer timeframes when applicable |
| `natural_buyer_seller` | `bool` | **new** | FR-025 — `True` when this ticker's Full TFC direction is in complete conflict with the correlated instrument's (see D4); absent/`None` when no correlated ticker was supplied |

### BroadeningFormation (`broadening_formation` key, new top-level output field)

| Field | Type | Notes |
|---|---|---|
| `active` | `bool` | FR-026 — `True` whenever the latest bar is an Outside Bar (always true fractally per methodology, but reported for the evaluated timeframe) |
| `high` / `low` | `float` | current BF range extremes |
| `prior_levels` | `list[{high, low, as_of}]` | FR-029 — retained prior BF extremes as S/R reference |
| `reclaim_flag` | `bool` | FR-028 — set when a signal reverses price back into a previously broken range |
| `next_expansion_level` | `float \| None` | FR-027 — the Inside→Outside→Inside next-watch level, when applicable |

### PreTradeChecklistResult (`pre_trade_checklist` key, new top-level output field)

| Field | Type | Notes |
|---|---|---|
| `signal_stack` | `list[{timeframe, signal_name}]` | FR-032 |
| `direction_vs_control` | `"aligned" \| "against" \| "n/a"` | FR-032/FR-024, checklist Q3 |
| `entries` | `list[{signal_name, entry_trigger, stop, level_of_defense}]` | FR-033, checklist Q6 |
| `momentum_or_retracement` | `str` | checklist Q4 |
| `time_to_exhaustion` | `str` | checklist Q5 |
| `correlated_confirmation` | `{ticker, aligned: bool} \| None` | FR-025, checklist Q8; `None` when no correlated ticker supplied |
| `add_to_position_allowed` | `bool` | FR-035 — requires an existing-position input (see below); defaults `True`/n-a when no position supplied |

### VixEtnAdjustment (applies when the evaluated ticker is flagged as a VIX-ETN-class instrument)

| Field | Type | Notes |
|---|---|---|
| `instrument_class` | `"vix_etn" \| "equity"` | caller-supplied or ticker-list-based classification (e.g. VXX/UVXY/TVIX) |
| `entry_rule` | `str` | FR-040 — entries only from BF highs |
| `cover_recommended` | `bool` | FR-041/FR-042 |
| `cover_reason` | `str \| None` | one of: broader-market Full TFC bearish, backwardation detected, unrealized return negative |

## Inputs added to `run(ticker, data)`

| Key | Type | Required | Notes |
|---|---|---|---|
| `daily`/`weekly`/`monthly`/`quarterly`/`yearly` | existing (`get_price_history()` shape) | yes, unchanged | |
| `correlated` | `get_price_history()`-shaped dict \| None | no | D4 — enables `natural_buyer_seller` and checklist Q8 |
| `instrument_class` | `"vix_etn" \| "equity"` | no, default `"equity"` | drives VixEtnAdjustment |
| `backwardation` | `bool` | no, default `False` | FR-042 input, since this app has no options/futures term-structure feed of its own |
| `position` | `{entry_price, unrealized_return}` | no | FR-035/FR-042 "unrealized return negative" checks |

All new inputs are optional with safe defaults so existing call sites
(`crew.py:152`, `the_strat.run(ticker, price_history)`) keep working unchanged.
