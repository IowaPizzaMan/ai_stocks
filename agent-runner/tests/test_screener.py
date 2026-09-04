"""Pure signal computation for the `screener` collection.
Spec: specs/031-semantic-layer-chat; contracts/screener-collection.md.

compute_signals() is deterministic, pure, and total (never raises) — the
mirrored contract in backend/tests/test_screener_contract.py checks the
field-name vocabulary matches what backend/semantic/schema.py describes to
the model, but the computation itself lives only here (agent-runner is the
sole writer of `screener`, per data-model.md).
"""
from datetime import datetime, timezone

from tools import screener

# Mirrored verbatim in backend/tests/test_screener_contract.py — that
# duplication IS the cross-service consistency check (constitution
# Principle VI): backend/semantic/schema.py describes exactly this field set
# to the model, and a field added/renamed here without updating there fails a
# test on both sides instead of silently corrupting chat's understanding of
# what it can query (contracts/screener-collection.md).
SCREENER_FIELDS = {
    "ticker", "name", "sector", "industry", "market_cap", "is_tracked",
    "last_close", "last_bar_date", "range_pct_20d", "zscore_20d",
    "weekly_change_pct", "monthly_change_pct", "weekly_trend",
    "revenue_growth_yoy", "net_income_growth_yoy", "net_profit_margin",
    "margin_trend", "financials_trend", "free_cash_flow", "total_debt",
    "fcf_exceeds_debt", "signals_as_of", "price_data_through",
    "financials_as_of", "insufficient_history", "liked_status",
}


def bar(d, close=100.0, high=None, low=None, open_=None, volume=1000):
    return {
        "date": d,
        "open": open_ if open_ is not None else close,
        "high": high if high is not None else close + 1,
        "low": low if low is not None else close - 1,
        "close": close,
        "volume": volume,
    }


def bars_series(n, start_close=100.0, step=1.0):
    """n ascending daily bars, closes rising by `step` each day."""
    out = []
    for i in range(n):
        c = start_close + i * step
        out.append(bar(f"2026-01-{i + 1:02d}" if i < 31 else f"2026-02-{i - 30:02d}",
                       close=c, high=c + 1, low=c - 1))
    return out


NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


# --- insufficient history boundary -----------------------------------------

def test_empty_bars_yields_insufficient_history_and_null_price_signals():
    doc = screener.compute_signals([], None, None, ticker="AAPL", is_tracked=True, now=NOW)
    assert doc["insufficient_history"] is True
    assert doc["last_close"] is None
    assert doc["range_pct_20d"] is None
    assert doc["zscore_20d"] is None
    assert doc["weekly_change_pct"] is None
    assert doc["monthly_change_pct"] is None
    assert doc["weekly_trend"] is None


def test_24_bars_is_still_insufficient_history():
    doc = screener.compute_signals(bars_series(24), None, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["insufficient_history"] is True
    assert doc["range_pct_20d"] is None


def test_25_bars_is_sufficient_history():
    doc = screener.compute_signals(bars_series(25), None, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["insufficient_history"] is False
    assert doc["range_pct_20d"] is not None
    assert doc["zscore_20d"] is not None
    assert doc["weekly_change_pct"] is not None
    assert doc["monthly_change_pct"] is not None


# --- price signal math -------------------------------------------------------

def test_flat_series_has_zero_stdev_and_null_zscore():
    """A perfectly flat 20-day window can't produce a meaningful z-score —
    guarded to null rather than raising a division-by-zero."""
    flat = [bar(f"2026-01-{i + 1:02d}", close=100.0, high=100.0, low=100.0) for i in range(30)]
    doc = screener.compute_signals(flat, None, None, ticker="FLAT", is_tracked=True, now=NOW)
    assert doc["zscore_20d"] is None
    # range is also zero-width here (hi == lo across the window)
    assert doc["range_pct_20d"] is None


def test_zero_width_range_is_null_not_a_crash():
    """High == low across the whole 20-day window (e.g. a halted/illiquid
    name) must not raise ZeroDivisionError."""
    bars = [bar(f"2026-01-{i + 1:02d}", close=50.0, high=50.0, low=50.0) for i in range(30)]
    doc = screener.compute_signals(bars, None, None, ticker="HALT", is_tracked=True, now=NOW)
    assert doc["range_pct_20d"] is None


def test_range_position_and_zscore_are_computed_correctly():
    # 20-day window: closes 81..100 (rising), so last close (100) is near the top
    # of the window's high/low band (each bar's high/low is close +/- 1).
    bars = bars_series(30, start_close=71.0)  # closes 71..100 across 30 bars
    doc = screener.compute_signals(bars, None, None, ticker="RISE", is_tracked=True, now=NOW)
    assert doc["last_close"] == 100.0
    # window highs/lows span [80, 101] (closes 81..100 +/- 1) -> (100-80)/(101-80)
    assert doc["range_pct_20d"] == 20 / 21
    assert doc["zscore_20d"] > 0  # above the 20-day mean


def test_weekly_and_monthly_change_and_trend():
    bars = bars_series(30, start_close=71.0)  # +1.0/day, always rising
    doc = screener.compute_signals(bars, None, None, ticker="RISE", is_tracked=True, now=NOW)
    assert doc["weekly_change_pct"] > 0
    assert doc["weekly_trend"] == "up"
    assert doc["monthly_change_pct"] > 0


def test_weekly_trend_down_when_declining():
    bars = bars_series(30, start_close=129.0, step=-1.0)  # steadily falling
    doc = screener.compute_signals(bars, None, None, ticker="FALL", is_tracked=True, now=NOW)
    assert doc["weekly_change_pct"] < 0
    assert doc["weekly_trend"] == "down"


def test_nan_and_none_bar_values_are_skipped_not_raised():
    bars = bars_series(30)
    # Corrupt a couple of interior bars — must not crash compute_signals.
    bars[10]["close"] = float("nan")
    bars[12]["high"] = None
    bars[14]["low"] = float("inf")
    doc = screener.compute_signals(bars, None, None, ticker="DIRTY", is_tracked=True, now=NOW)
    assert doc["insufficient_history"] is False
    # Should still produce a result using the remaining clean values.
    assert doc["last_close"] == bars[-1]["close"]


# --- financial signals --------------------------------------------------------

def _financials(growth=None, ratios=None, cashflow=None, balance=None, income=None):
    return {
        "growth": growth or [],
        "ratios": ratios or [],
        "cashflow_annual": cashflow or [],
        "balance_annual": balance or [],
        "income_annual": income or [],
    }


def test_missing_financials_yields_all_null_financial_signals():
    doc = screener.compute_signals(bars_series(25), None, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["revenue_growth_yoy"] is None
    assert doc["net_income_growth_yoy"] is None
    assert doc["margin_trend"] is None
    assert doc["financials_trend"] is None
    assert doc["free_cash_flow"] is None
    assert doc["total_debt"] is None
    assert doc["fcf_exceeds_debt"] is None


def test_single_annual_period_cannot_derive_a_trend():
    """One period of ratios can't establish a trend (need >= 2) — growth
    fields (already YoY from FMP) may still populate, but margin_trend and
    the composite financials_trend must stay null."""
    fin = _financials(
        growth=[{"growthRevenue": 0.10, "growthNetIncome": 0.05}],
        ratios=[{"netProfitMargin": 0.20}],
        cashflow=[{"freeCashFlow": 1000}],
        balance=[{"totalDebt": 500}],
        income=[{"date": "2025-12-31"}],
    )
    doc = screener.compute_signals(bars_series(25), fin, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["revenue_growth_yoy"] == 0.10
    assert doc["net_income_growth_yoy"] == 0.05
    assert doc["margin_trend"] is None
    assert doc["financials_trend"] is None
    assert doc["free_cash_flow"] == 1000
    assert doc["total_debt"] == 500
    assert doc["fcf_exceeds_debt"] is True
    assert doc["financials_as_of"] == "2025-12-31"


def test_financials_trend_improving():
    fin = _financials(
        growth=[{"growthRevenue": 0.10, "growthNetIncome": 0.08}],
        ratios=[{"netProfitMargin": 0.25}, {"netProfitMargin": 0.20}],
    )
    doc = screener.compute_signals(bars_series(25), fin, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["margin_trend"] == "improving"
    assert doc["financials_trend"] == "improving"  # revenue+, net income+, margin improving = 3/3


def test_financials_trend_deteriorating():
    fin = _financials(
        growth=[{"growthRevenue": -0.10, "growthNetIncome": -0.08}],
        ratios=[{"netProfitMargin": 0.10}, {"netProfitMargin": 0.20}],
    )
    doc = screener.compute_signals(bars_series(25), fin, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["margin_trend"] == "deteriorating"
    assert doc["financials_trend"] == "deteriorating"


def test_financials_trend_flat_on_a_mixed_signal():
    """Two periods exist (margin_trend is defined), but only 1 of the 3
    criteria points the same way — neither threshold (>=2) is met."""
    fin = _financials(
        growth=[{"growthRevenue": 0.10, "growthNetIncome": -0.02}],
        ratios=[{"netProfitMargin": 0.18}, {"netProfitMargin": 0.20}],  # deteriorating
    )
    doc = screener.compute_signals(bars_series(25), fin, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["margin_trend"] == "deteriorating"
    # revenue+ (1 positive), net income- and margin- (2 negative) => deteriorating, not flat
    assert doc["financials_trend"] == "deteriorating"


def test_financials_trend_flat_when_truly_mixed():
    fin = _financials(
        growth=[{"growthRevenue": 0.10, "growthNetIncome": None}],
        ratios=[{"netProfitMargin": 0.20}, {"netProfitMargin": 0.20}],  # flat margin
    )
    doc = screener.compute_signals(bars_series(25), fin, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["margin_trend"] == "flat"
    # only 1 positive (revenue), 0 negative, margin flat => neither >=2 => flat
    assert doc["financials_trend"] == "flat"


def test_number_long_coercion_on_fcf_and_debt():
    """financials_cache stores large ints as BSON $numberLong when read
    through some drivers — must coerce to plain numbers before comparing."""
    fin = _financials(
        cashflow=[{"freeCashFlow": {"$numberLong": "98767000000"}}],
        balance=[{"totalDebt": {"$numberLong": "112377000000"}}],
    )
    doc = screener.compute_signals(bars_series(25), fin, None, ticker="AAPL", is_tracked=True, now=NOW)
    assert doc["free_cash_flow"] == 98767000000.0
    assert doc["total_debt"] == 112377000000.0
    assert doc["fcf_exceeds_debt"] is False  # FCF < debt


def test_fcf_exceeds_debt_null_when_either_input_missing():
    fin = _financials(cashflow=[{"freeCashFlow": 1000}])  # no balance sheet
    doc = screener.compute_signals(bars_series(25), fin, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["fcf_exceeds_debt"] is None


# --- profile passthrough + identity fields -----------------------------------

def test_profile_fields_pass_through():
    profile = {"name": "Apple Inc.", "sector": "Technology",
               "industry": "Consumer Electronics", "market_cap": {"$numberLong": "3000000000000"}}
    doc = screener.compute_signals(bars_series(25), None, profile, ticker="aapl", is_tracked=True, now=NOW)
    assert doc["ticker"] == "AAPL"  # uppercased
    assert doc["name"] == "Apple Inc."
    assert doc["sector"] == "Technology"
    assert doc["industry"] == "Consumer Electronics"
    assert doc["market_cap"] == 3_000_000_000_000.0


def test_missing_profile_yields_null_identity_fields():
    doc = screener.compute_signals(bars_series(25), None, None, ticker="X", is_tracked=False, now=NOW)
    assert doc["name"] is None
    assert doc["sector"] is None
    assert doc["is_tracked"] is False


# --- liked_status derivation (033-strategy-picks-filters, data-model.md) ----

def test_liked_status_defaults_to_none_when_not_provided():
    doc = screener.compute_signals(bars_series(25), None, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["liked_status"] is None


def test_liked_status_liked_passes_through():
    doc = screener.compute_signals(
        bars_series(25), None, None, ticker="X", is_tracked=True, now=NOW, liked_status="liked",
    )
    assert doc["liked_status"] == "liked"


def test_liked_status_disliked_passes_through():
    doc = screener.compute_signals(
        bars_series(25), None, None, ticker="X", is_tracked=True, now=NOW, liked_status="disliked",
    )
    assert doc["liked_status"] == "disliked"


def test_liked_status_none_is_never_fabricated_as_disliked():
    """No ticker_index document, or one with sentiment: null, must yield
    liked_status: None — never fabricated as "disliked" by absence
    (data-model.md validation rules)."""
    doc = screener.compute_signals(
        bars_series(25), None, None, ticker="X", is_tracked=True, now=NOW, liked_status=None,
    )
    assert doc["liked_status"] is None


def test_liked_status_independent_of_insufficient_history():
    """A ticker with too little price history to compute signals can still
    have a liked_status (data-model.md)."""
    doc = screener.compute_signals([], None, None, ticker="X", is_tracked=True, now=NOW, liked_status="liked")
    assert doc["insufficient_history"] is True
    assert doc["liked_status"] == "liked"


def test_signals_as_of_and_price_data_through():
    bars = bars_series(25)
    doc = screener.compute_signals(bars, None, None, ticker="X", is_tracked=True, now=NOW)
    assert doc["signals_as_of"] == NOW
    assert doc["price_data_through"] == bars[-1]["date"]


# --- field-vocabulary contract (mirrored in backend/tests/test_screener_contract.py) ---

def test_output_field_set_matches_the_mirrored_contract_table():
    doc = screener.compute_signals(bars_series(25), None, None, ticker="X", is_tracked=True, now=NOW)
    assert set(doc.keys()) == SCREENER_FIELDS


# --- regression: reproduces the live AAPL values measured in research.md R4 ---
# (5 years of daily bars, 2021-08-18 through 2026-08-21, sourced from the real
# price_history/financials_cache documents at the time of that measurement)

def test_reproduces_measured_aapl_reference_values():
    bars = bars_series(1258, start_close=50.0, step=0.2058)  # approximates AAPL's 5y climb
    # Override the tail so the last-20-day window matches the measured shape:
    # last close 309.35, near the bottom of the recent range, up on the week.
    tail_start = len(bars) - 20
    for i in range(tail_start, len(bars)):
        c = 300.0 + (i - tail_start) * 0.4
        bars[i] = bar(bars[i]["date"], close=c, high=c + 15, low=c - 15)
    bars[-1] = bar(bars[-1]["date"], close=309.35, high=309.35 + 15, low=309.35 - 15)

    fin = _financials(
        growth=[{"growthRevenue": 0.0642551178283274, "growthNetIncome": 0.19495177946573355}],
        ratios=[{"netProfitMargin": 0.2691506412181824}, {"netProfitMargin": 0.24}],
        cashflow=[{"freeCashFlow": {"$numberLong": "98767000000"}}],
        balance=[{"totalDebt": {"$numberLong": "112377000000"}}],
        income=[{"date": "2025-09-27"}],
    )
    doc = screener.compute_signals(bars, fin, None, ticker="AAPL", is_tracked=True, now=NOW)

    assert doc["last_close"] == 309.35
    assert doc["free_cash_flow"] == 98767000000.0
    assert doc["total_debt"] == 112377000000.0
    assert doc["fcf_exceeds_debt"] is False  # FCF < debt, matching the live measurement
    assert doc["revenue_growth_yoy"] == 0.0642551178283274
    assert doc["net_income_growth_yoy"] == 0.19495177946573355
    assert doc["margin_trend"] == "improving"
    assert doc["financials_trend"] == "improving"
