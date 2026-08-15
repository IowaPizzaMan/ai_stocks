# Contract: `agent-runner/skills/the_strat.py::run(ticker, data) -> dict`

This is the interface contract for this feature — `the_strat.py` has no HTTP/CLI
surface of its own; it is imported directly by `crew.py` (see
`specs/component-specs/agent-runner/agents/technical_analyst.md` and
`crew.py:152`) exactly like every other `skills/*.py` module. This document
specifies the function signature both existing and new callers must honor.

## Signature

```python
def run(
    ticker: str,
    data: dict,
) -> dict:
    ...
```

## Input — `data`

```text
{
  "daily":     <get_price_history() shape: list[dict] | pd.DataFrame>,   # required
  "weekly":    <same>,                                                    # required
  "monthly":   <same>,                                                    # required
  "quarterly": <same>,                                                    # required
  "yearly":    <same>,                                                    # required

  "correlated":       <get_price_history() shape> | None,   # optional, default None
  "instrument_class":  "equity" | "vix_etn",                # optional, default "equity"
  "backwardation":      bool,                                # optional, default False
  "position":  {"entry_price": float, "unrealized_return": float} | None,  # optional
}
```

Backward compatibility: every existing call site passes only
`{daily, weekly, monthly, quarterly, yearly}` (the exact shape
`tools/price.py::get_price_history()` returns) — this remains valid; all new keys
are optional with the defaults shown.

Errors (unchanged): raises `KeyError` if any of the five required timeframe keys
is missing (existing behavior, see `test_missing_timeframe_raises`).

## Output — return value

```text
{
  "ticker": str,

  "timeframes": {
    "<daily|weekly|monthly|quarterly|yearly>": {
      "last_bar": "1" | "2U" | "2D" | "3",
      "sequence": list[str],              # last 5 bar types, unchanged
      "candle_color": "green" | "red",
      "patterns": list[ActionableSignal],  # see data-model.md — now carries the
                                            #   new fields (stop, level_of_defense,
                                            #   universal_truth, in_force, momentum,
                                            #   soft) in addition to the existing ones
      "outside_subtype": "bullish_engulfing" | "bearish_engulfing" | "regular" | None,
                                            # new; only meaningful when last_bar == "3"
    },
    ...
  },

  "tfc": {
    "weekly": "green" | "red",
    "monthly": "green" | "red",
    "quarterly": "green" | "red",
    "yearly": "green" | "red",
    "status": "full_bullish" | "full_bearish" | "conflict",
    "last_sale": float,
    "control": list[str],                  # new — FR-024
    "natural_buyer_seller": bool | None,    # new — FR-025; None if no `correlated` input given
  },

  "daily_notable_candle": {
    "bar_type": str, "candle_color": str, "reasons": list[str]
  } | None,                                 # unchanged

  "broadening_formation": {                 # new — see data-model.md
    "active": bool, "high": float, "low": float,
    "prior_levels": list[dict], "reclaim_flag": bool,
    "next_expansion_level": float | None,
  },

  "pre_trade_checklist": {                  # new — see data-model.md
    "signal_stack": list[dict], "direction_vs_control": str,
    "entries": list[dict], "momentum_or_retracement": str,
    "time_to_exhaustion": str, "correlated_confirmation": dict | None,
    "add_to_position_allowed": bool,
  },

  "vix_etn_adjustment": {                   # new — only populated when
    "instrument_class": str, "entry_rule": str,   #   instrument_class == "vix_etn";
    "cover_recommended": bool, "cover_reason": str | None,  # else this key is None
  } | None,

  "signal": str,                            # unchanged — human-readable summary line
}
```

**Additive-only guarantee** (see research.md D5): `ticker`, `timeframes.*.last_bar`,
`timeframes.*.sequence`, `timeframes.*.candle_color`, `timeframes.*.patterns`
(existing fields within each pattern dict), `tfc.<timeframe>`, `tfc.status`,
`tfc.last_sale`, `daily_notable_candle`, and `signal` keep their existing meaning
and type. Existing consumers (`crew.py`, `agents/technical_analyst.py`) do not
need to change to keep working; they should be updated (tracked in tasks.md) to
narrate the new fields.

## Consumers to update (tracked for /speckit-tasks, not this plan's code)

- `agent-runner/agents/technical_analyst.py` — prompt should reference
  `strat.tfc.control`, `strat.broadening_formation`, and
  `strat.pre_trade_checklist` once populated.
- `specs/component-specs/agent-runner/tools/price.md` — note the optional
  `correlated` ticker fetch if `crew.py` is updated to supply one.
- `specs/component-specs/agent-runner/agents/technical_analyst.md` — reflect the
  new `strat` fields available to the prompt.
