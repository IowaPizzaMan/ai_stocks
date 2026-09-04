"""Exhaustive tests for skills/conviction.py — the deterministic conviction
rating rule engine. Spec: specs/037-stocks-conviction-and-activity;
contracts/conviction-rules.md.

This is the highest-value new test surface this feature adds (Constitution
Principle I): conviction.run() is a pure rule-engine skill with no LLM calls,
replacing what used to be a free-form model judgement.
"""
from datetime import datetime, timezone

from skills import conviction
from tools import strategy_signals

NOW = datetime(2026, 9, 4, tzinfo=timezone.utc)


# --- fixture builders --------------------------------------------------------

def _closes(values: list[float]) -> list[dict]:
    return [{"Date": i, "Close": c} for i, c in enumerate(values)]


def _flat(n: int, value: float = 100.0) -> list[dict]:
    return _closes([value] * n)


def _flat_then_drop(n: int, flat: float = 100.0, drop: float = 40.0) -> list[dict]:
    """All rolling-20 windows before the last are flat (sd=0 -> z=0); the very
    last window contains the crash, giving one strongly negative z at the
    end. Since >75% of the sample is 0, p25 == 0 and the crash's z is well
    below it -> reliably `in_bottom_quartile: True` without needing to hand-
    derive every value."""
    return _closes([flat] * (n - 1) + [drop])


def _flat_then_spike(n: int, flat: float = 100.0, spike: float = 220.0) -> list[dict]:
    """Mirror of _flat_then_drop: one strongly positive z at the end ->
    reliably `in_bottom_quartile: False`."""
    return _closes([flat] * (n - 1) + [spike])


# Sufficient/insufficient sample boundaries (Z_PERIOD=20 warmup + min_sample):
DAILY_SUFFICIENT_N = conviction.Z_PERIOD - 1 + conviction.MIN_DAILY_Z_SAMPLE       # 79
DAILY_INSUFFICIENT_N = DAILY_SUFFICIENT_N - 1                                     # 78
WEEKLY_SUFFICIENT_N = conviction.Z_PERIOD - 1 + conviction.MIN_WEEKLY_Z_SAMPLE     # 49
WEEKLY_INSUFFICIENT_N = WEEKLY_SUFFICIENT_N - 1                                   # 48


def _price_history(daily=None, weekly=None) -> dict:
    return {
        "daily": daily if daily is not None else _flat_then_drop(DAILY_SUFFICIENT_N),
        "weekly": weekly if weekly is not None else _flat_then_drop(WEEKLY_SUFFICIENT_N),
    }


def _the_strat_out(*, tfc_status="full_bullish", aligned=True, insufficient=False) -> dict:
    if insufficient:
        return {"tfc": None, "timeframes": {}}
    tfc = {"status": tfc_status}
    patterns = (
        [{"name": "revstrat_2bar_bullish", "direction": "long", "buy_trigger": 106.0}]
        if aligned else []
    )
    return {
        "tfc": tfc,
        "timeframes": {"weekly": {"patterns": patterns},
                        "monthly": {"patterns": []}, "quarterly": {"patterns": []},
                        "yearly": {"patterns": []}},
    }


def _accumulation_out(*, signal="ACCUMULATION", distribution_warning=False) -> dict:
    return {"signal": signal, "distribution_warning": distribution_warning,
            "rationale": "up/down volume ratio 3.0x over last 20 sessions"}


def _gap_out(*, direction="down", score=3, latest_gap=True, insufficient=False) -> dict:
    if insufficient or not latest_gap:
        return {"signal": "insufficient history" if insufficient else "no gaps in lookback window",
                "latest_gap": None}
    return {"signal": f"{direction}-gap score {score}",
            "latest_gap": {"direction": direction, "score": score, "bias": "bullish reversal",
                            "reversal_level": 95.0}}


def _financials(growth_yoy=0.08, qoq_pair=(110.0, 100.0)) -> dict:
    fin = {"growth": [{"growthRevenue": growth_yoy}] if growth_yoy is not None else []}
    if qoq_pair is not None:
        fin["income_quarterly"] = [{"date": "2026-06-30", "revenue": qoq_pair[0]},
                                    {"revenue": qoq_pair[1]}]
    else:
        fin["income_quarterly"] = []
    return fin


def _data(**overrides) -> dict:
    base = {
        "the_strat": _the_strat_out(),
        "accumulation": _accumulation_out(),
        "gap_analysis": _gap_out(),
        "price_history": _price_history(),
        "financials": _financials(),
        "market_flow": {"recommendation": "HOLD"},
    }
    base.update(overrides)
    return base


# --- Rule 1: the_strat call ---------------------------------------------------

def test_the_strat_buy_on_full_bullish_with_aligned_pattern():
    call, why = conviction._the_strat_call(_the_strat_out(aligned=True))
    assert call == "buy"
    assert "full TFC bullish" in why


def test_the_strat_not_buy_on_full_bullish_with_no_aligned_pattern():
    call, _ = conviction._the_strat_call(_the_strat_out(aligned=False))
    assert call == "not-buy"


def test_the_strat_not_buy_on_full_bearish():
    call, _ = conviction._the_strat_call(_the_strat_out(tfc_status="full_bearish"))
    assert call == "not-buy"


def test_the_strat_not_buy_on_conflict():
    call, _ = conviction._the_strat_call(_the_strat_out(tfc_status="conflict"))
    assert call == "not-buy"


def test_the_strat_no_call_on_insufficient_history():
    call, why = conviction._the_strat_call(_the_strat_out(insufficient=True))
    assert call == "no-call"
    assert "insufficient" in why


def test_the_strat_excludes_non_trigger_patterns_from_alignment():
    out = {
        "tfc": {"status": "full_bullish"},
        "timeframes": {
            "weekly": {"patterns": [{"name": "inside_bar_setup", "direction": "either"}]},
            "monthly": {"patterns": [{"name": "kicking_bullish", "direction": "long"}]},
            "quarterly": {"patterns": []}, "yearly": {"patterns": []},
        },
    }
    call, _ = conviction._the_strat_call(out)
    assert call == "not-buy"  # neither pattern counts toward alignment


# --- Rule 1: accumulation call -------------------------------------------------

def test_accumulation_buy_on_confirmed_accumulation():
    call, _ = conviction._accumulation_call(_accumulation_out(), daily_bar_count=100)
    assert call == "buy"


def test_accumulation_not_buy_on_distribution_warning_even_if_signal_says_accumulation():
    call, _ = conviction._accumulation_call(
        _accumulation_out(signal="ACCUMULATION", distribution_warning=True), daily_bar_count=100)
    assert call == "not-buy"


def test_accumulation_not_buy_on_early_accumulation():
    call, _ = conviction._accumulation_call(_accumulation_out(signal="EARLY_ACCUMULATION"),
                                              daily_bar_count=100)
    assert call == "not-buy"


def test_accumulation_not_buy_on_neutral():
    call, _ = conviction._accumulation_call(_accumulation_out(signal="NEUTRAL"), daily_bar_count=100)
    assert call == "not-buy"


def test_accumulation_no_call_on_insufficient_daily_bars():
    call, why = conviction._accumulation_call(_accumulation_out(), daily_bar_count=10)
    assert call == "no-call"
    assert "insufficient" in why


# --- Rule 1: gap_analysis call -------------------------------------------------

def test_gap_analysis_buy_on_down_gap_at_or_above_threshold():
    call, _ = conviction._gap_analysis_call(_gap_out(direction="down", score=3))
    assert call == "buy"


def test_gap_analysis_not_buy_on_down_gap_below_threshold():
    call, _ = conviction._gap_analysis_call(_gap_out(direction="down", score=2))
    assert call == "not-buy"


def test_gap_analysis_not_buy_on_up_gap():
    call, _ = conviction._gap_analysis_call(_gap_out(direction="up", score=5))
    assert call == "not-buy"


def test_gap_analysis_no_call_on_insufficient_history():
    call, why = conviction._gap_analysis_call(_gap_out(insufficient=True))
    assert call == "no-call"
    assert "insufficient" in why


def test_gap_analysis_no_call_when_no_gap_in_window():
    call, _ = conviction._gap_analysis_call(_gap_out(latest_gap=False))
    assert call == "no-call"


# --- Rule 2: z-score bottom quartile ------------------------------------------

def test_percentile_linear_interpolation():
    assert conviction._percentile([1, 2, 3, 4], 25) == 1.75
    assert conviction._percentile([10, 20, 30, 40, 50], 25) == 20  # exact integer index


def test_quartile_status_boundary_is_inclusive():
    """Hand-constructed so the latest z-value exactly equals p25 (verified
    independently — see research notes) — proves FR-011's `<=` inclusivity,
    not just a comfortably-below case."""
    closes = [100.0] * 19 + [100.0, 105.0, 95.0, 110.0, 90.0]
    status = conviction._quartile_status(_closes(closes), history=5, min_sample=5)
    assert status["value"] == status["p25"]
    assert status["in_bottom_quartile"] is True


def test_quartile_status_false_when_latest_above_p25():
    closes = [100.0] * 19 + [100.0, 105.0, 95.0, 110.0, 102.0]
    status = conviction._quartile_status(_closes(closes), history=5, min_sample=5)
    assert status["value"] > status["p25"]
    assert status["in_bottom_quartile"] is False


def test_quartile_status_none_when_sample_too_small():
    closes = [100.0] * 19 + [100.0, 105.0, 95.0, 110.0]  # only 4 z-values, min_sample=5
    status = conviction._quartile_status(_closes(closes), history=5, min_sample=5)
    assert status["in_bottom_quartile"] is None
    assert status["value"] is None
    assert status["sample"] == 4


def test_quartile_status_uses_only_the_trailing_history_window():
    closes = [100.0] * 19 + [100, 105, 95, 110, 90, 100, 105, 95, 110, 102.0]
    status = conviction._quartile_status(_closes(closes), history=5, min_sample=5)
    assert status["sample"] == 5  # not 10


def test_daily_sufficient_boundary_crash_is_in_bottom_quartile():
    daily = _flat_then_drop(DAILY_SUFFICIENT_N)
    status = conviction._quartile_status(daily, conviction.DAILY_Z_HISTORY, conviction.MIN_DAILY_Z_SAMPLE)
    assert status["sample"] == conviction.MIN_DAILY_Z_SAMPLE
    assert status["in_bottom_quartile"] is True


def test_daily_one_bar_short_of_sufficient_is_no_call():
    daily = _flat_then_drop(DAILY_INSUFFICIENT_N)
    status = conviction._quartile_status(daily, conviction.DAILY_Z_HISTORY, conviction.MIN_DAILY_Z_SAMPLE)
    assert status["in_bottom_quartile"] is None


def test_weekly_sufficient_boundary_crash_is_in_bottom_quartile():
    weekly = _flat_then_drop(WEEKLY_SUFFICIENT_N)
    status = conviction._quartile_status(weekly, conviction.WEEKLY_Z_HISTORY, conviction.MIN_WEEKLY_Z_SAMPLE)
    assert status["in_bottom_quartile"] is True


def test_weekly_one_bar_short_of_sufficient_is_no_call():
    weekly = _flat_then_drop(WEEKLY_INSUFFICIENT_N)
    status = conviction._quartile_status(weekly, conviction.WEEKLY_Z_HISTORY, conviction.MIN_WEEKLY_Z_SAMPLE)
    assert status["in_bottom_quartile"] is None


# --- Rule 4: level truth table (via run()) ------------------------------------

def test_high_when_all_three_conditions_pass():
    out = conviction.run("AVB", _data(), now=NOW)
    assert out["level"] == "high"
    assert out["rank"] == 3
    assert out["blockers"] == []
    assert out["missing_inputs"] == []


def test_not_high_when_one_strategy_is_not_buy():
    out = conviction.run("AVB", _data(the_strat=_the_strat_out(aligned=False)), now=NOW)
    assert out["level"] != "high"
    assert any("strategies" in b for b in out["blockers"])


def test_not_high_when_daily_zscore_not_bottom_quartile_even_if_weekly_is():
    out = conviction.run("AVB", _data(price_history=_price_history(
        daily=_flat_then_spike(DAILY_SUFFICIENT_N))), now=NOW)
    assert out["level"] != "high"


def test_not_high_when_weekly_zscore_not_bottom_quartile_even_if_daily_is():
    out = conviction.run("AVB", _data(price_history=_price_history(
        weekly=_flat_then_spike(WEEKLY_SUFFICIENT_N))), now=NOW)
    assert out["level"] != "high"


def test_not_high_when_revenue_not_growing_yoy():
    out = conviction.run("AVB", _data(financials=_financials(growth_yoy=-0.02)), now=NOW)
    assert out["level"] != "high"
    assert any("year over year" in b for b in out["blockers"])


def test_not_high_when_revenue_declines_qoq_even_with_positive_yoy():
    """The 'losing ground' case the user explicitly called out (clarification
    Q2) — a QoQ decline blocks high even when YoY growth is positive."""
    out = conviction.run("AVB", _data(financials=_financials(growth_yoy=0.08, qoq_pair=(90.0, 100.0))),
                          now=NOW)
    assert out["level"] != "high"
    assert any("quarter over quarter" in b for b in out["blockers"])


def test_insufficient_data_never_yields_high_and_is_recorded_as_missing():
    out = conviction.run("AVB", _data(the_strat=_the_strat_out(insufficient=True)), now=NOW)
    assert out["level"] != "high"
    assert "strategy:the_strat" in out["missing_inputs"]


def test_blockers_empty_iff_high():
    high = conviction.run("AVB", _data(), now=NOW)
    assert high["level"] == "high" and high["blockers"] == []

    low = conviction.run("AVB", _data(the_strat=_the_strat_out(aligned=False),
                                       accumulation=_accumulation_out(signal="NEUTRAL")), now=NOW)
    assert low["level"] != "high" and low["blockers"] != []


def test_flipping_any_single_high_condition_drops_the_rating():
    """SC-004: each of the three gating conditions, flipped alone, drops a
    high-rated stock."""
    baseline = conviction.run("AVB", _data(), now=NOW)
    assert baseline["level"] == "high"

    strategy_flip = conviction.run("AVB", _data(gap_analysis=_gap_out(direction="up")), now=NOW)
    zscore_flip = conviction.run("AVB", _data(
        price_history=_price_history(daily=_flat_then_spike(DAILY_SUFFICIENT_N))), now=NOW)
    revenue_flip = conviction.run("AVB", _data(financials=_financials(growth_yoy=-0.01)), now=NOW)

    for flipped in (strategy_flip, zscore_flip, revenue_flip):
        assert flipped["level"] != "high"
        assert flipped["rank"] < baseline["rank"]


def test_market_flow_changes_only_caveats_never_the_level():
    favorable = conviction.run("AVB", _data(market_flow={"recommendation": "BUY_MORE"}), now=NOW)
    unfavorable = conviction.run("AVB", _data(market_flow={"recommendation": "TRIM"}), now=NOW)
    assert favorable["level"] == unfavorable["level"] == "high"
    assert favorable["caveats"] == []
    assert unfavorable["caveats"] != []
    assert "timing headwind" in unfavorable["caveats"][0]


def test_medium_requires_majority_strategies_and_one_zscore_timeframe_and_no_qoq_decline():
    out = conviction.run("AVB", _data(
        the_strat=_the_strat_out(aligned=False),  # only 2 of 3 strategies now buy
        price_history=_price_history(weekly=_flat_then_spike(WEEKLY_SUFFICIENT_N)),  # only daily bottom-quartile
    ), now=NOW)
    assert out["level"] == "medium"
    assert out["rank"] == 2


def test_low_when_majority_strategies_fail():
    out = conviction.run("AVB", _data(
        the_strat=_the_strat_out(aligned=False),
        accumulation=_accumulation_out(signal="NEUTRAL"),
    ), now=NOW)
    assert out["level"] == "low"
    assert out["rank"] == 1


def test_computed_at_is_injectable_and_returned():
    out = conviction.run("AVB", _data(), now=NOW)
    assert out["computed_at"] == NOW
    assert out["ticker"] == "AVB"


# --- describe_transition() ----------------------------------------------------

def test_describe_transition_with_no_prior_detail_returns_summary():
    detail = conviction.run("AVB", _data(), now=NOW)
    reason = conviction.describe_transition(None, detail)
    assert "aligned" in reason


def test_describe_transition_names_the_flipped_condition():
    old = conviction.run("AVB", _data(financials=_financials(growth_yoy=-0.02)), now=NOW)
    new = conviction.run("AVB", _data(), now=NOW)
    reason = conviction.describe_transition(old, new)
    assert "revenue trend" in reason


def test_describe_transition_names_strategy_and_zscore_together():
    old = conviction.run("AVB", _data(the_strat=_the_strat_out(aligned=False),
                                       price_history=_price_history(
                                           daily=_flat_then_spike(DAILY_SUFFICIENT_N))), now=NOW)
    new = conviction.run("AVB", _data(), now=NOW)
    reason = conviction.describe_transition(old, new)
    assert "strategy alignment" in reason
    assert "z-score quartile position" in reason


def test_describe_transition_no_condition_change_still_returns_a_summary():
    detail = conviction.run("AVB", _data(), now=NOW)
    reason = conviction.describe_transition(detail, detail)
    assert reason  # non-empty, falls back to the plain summary


# --- Consistency mirror against tools/strategy_signals.py (research R2) ------

def test_the_strat_call_agrees_with_strategy_signals_direction():
    buy_case = _the_strat_out(aligned=True)
    assert conviction._the_strat_call(buy_case)[0] == "buy"
    assert strategy_signals._the_strat_block(buy_case)["direction"] == "long"

    not_buy_case = _the_strat_out(aligned=False)
    assert conviction._the_strat_call(not_buy_case)[0] == "not-buy"
    assert strategy_signals._the_strat_block(not_buy_case) == strategy_signals.NULL_THE_STRAT


# --- SC-002 sanity: high is the minority outcome ------------------------------

def test_high_is_the_minority_across_a_representative_input_matrix():
    """Not a hard gate (the exhaustive per-condition truth table above is the
    real proof) — but a concrete, deterministic stand-in for SC-002's "no more
    than ~25% of stocks rated high" over a full combinatorial sweep of the
    inputs: 2 the_strat states x 2 accumulation states x 2 gap states x 2
    daily-zscore states x 2 weekly-zscore states x 2 revenue states = 64
    combinations, of which exactly 1 satisfies every high-conviction
    condition simultaneously."""
    levels = []
    for strat_aligned in (True, False):
        for accum_signal in ("ACCUMULATION", "NEUTRAL"):
            for gap_score in (3, 2):
                for daily_in_q in (True, False):
                    for weekly_in_q in (True, False):
                        for revenue_favorable in (True, False):
                            data = _data(
                                the_strat=_the_strat_out(aligned=strat_aligned),
                                accumulation=_accumulation_out(signal=accum_signal),
                                gap_analysis=_gap_out(direction="down", score=gap_score),
                                price_history=_price_history(
                                    daily=_flat_then_drop(DAILY_SUFFICIENT_N) if daily_in_q
                                    else _flat_then_spike(DAILY_SUFFICIENT_N),
                                    weekly=_flat_then_drop(WEEKLY_SUFFICIENT_N) if weekly_in_q
                                    else _flat_then_spike(WEEKLY_SUFFICIENT_N),
                                ),
                                financials=_financials(growth_yoy=0.08 if revenue_favorable else -0.02),
                            )
                            levels.append(conviction.run("AVB", data, now=NOW)["level"])

    assert len(levels) == 64
    high_share = levels.count("high") / len(levels)
    assert high_share <= 0.25
    assert levels.count("high") == 1  # exactly the all-conditions-pass combination
    assert len(set(levels)) == 3  # high, medium, and low are all represented


def test_gap_analysis_call_agrees_with_strategy_signals_direction():
    buy_case = _gap_out(direction="down", score=3)
    assert conviction._gap_analysis_call(buy_case)[0] == "buy"
    assert strategy_signals._gap_analysis_block(buy_case)["direction"] == "long"

    # Below the actionable score threshold — both sides treat this as "no
    # signal" (an up-gap at/above threshold is a valid *short* candidate for
    # strategy_signals, so it isn't a null case there — just not a conviction
    # "buy", which only recognizes the down-gap/long setup).
    below_threshold_case = _gap_out(direction="down", score=2)
    assert conviction._gap_analysis_call(below_threshold_case)[0] == "not-buy"
    assert strategy_signals._gap_analysis_block(below_threshold_case) == strategy_signals.NULL_GAP_ANALYSIS
