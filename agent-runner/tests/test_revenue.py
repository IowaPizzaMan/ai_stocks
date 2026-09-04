"""Exhaustive tests for tools/revenue.py::derive_revenue_trend().
Spec: specs/037-stocks-conviction-and-activity; contracts/conviction-rules.md Rule 3.
"""
from tools.revenue import derive_revenue_trend


def _financials(growth=None, quarterly=None):
    return {"growth": growth or [], "income_quarterly": quarterly or []}


def test_growth_present_positive_is_growing():
    fin = _financials(growth=[{"growthRevenue": 0.081}])
    out = derive_revenue_trend(fin)
    assert out["growth_yoy"] == 0.081
    assert out["yoy_growing"] is True
    assert "growth_yoy" not in out["missing"]


def test_growth_present_negative_is_not_growing():
    fin = _financials(growth=[{"growthRevenue": -0.05}])
    out = derive_revenue_trend(fin)
    assert out["growth_yoy"] == -0.05
    assert out["yoy_growing"] is False
    assert "growth_yoy" not in out["missing"]


def test_growth_missing_key_marks_missing():
    fin = _financials(growth=[])
    out = derive_revenue_trend(fin)
    assert out["growth_yoy"] is None
    assert out["yoy_growing"] is False
    assert "growth_yoy" in out["missing"]


def test_qoq_growth_two_quarters():
    fin = _financials(quarterly=[{"date": "2026-06-30", "revenue": 110}, {"revenue": 100}])
    out = derive_revenue_trend(fin)
    assert out["change_qoq"] == 0.1
    assert out["qoq_declining"] is False
    assert out["latest_period"] == "2026-06-30"
    assert "change_qoq" not in out["missing"]


def test_qoq_decline_two_quarters():
    fin = _financials(quarterly=[{"revenue": 90}, {"revenue": 100}])
    out = derive_revenue_trend(fin)
    assert out["change_qoq"] == -0.1
    assert out["qoq_declining"] is True


def test_qoq_exactly_one_quarter_is_none():
    fin = _financials(quarterly=[{"revenue": 100}])
    out = derive_revenue_trend(fin)
    assert out["change_qoq"] is None
    assert out["qoq_declining"] is False
    assert "change_qoq" in out["missing"]
    # latest_period is still derivable from the single quarter present
    assert out["latest_period"] is None or "date" not in fin["income_quarterly"][0]


def test_empty_quarterly_series():
    fin = _financials(quarterly=[])
    out = derive_revenue_trend(fin)
    assert out["change_qoq"] is None
    assert out["latest_period"] is None
    assert "change_qoq" in out["missing"]


def test_zero_denominator_guard():
    fin = _financials(quarterly=[{"revenue": 50}, {"revenue": 0}])
    out = derive_revenue_trend(fin)
    assert out["change_qoq"] is None
    assert "change_qoq" in out["missing"]


def test_no_financials_at_all():
    out = derive_revenue_trend(None)
    assert out["growth_yoy"] is None
    assert out["change_qoq"] is None
    assert out["yoy_growing"] is False
    assert out["qoq_declining"] is False
    assert set(out["missing"]) == {"growth_yoy", "change_qoq"}


def test_nan_and_infinity_are_treated_as_absent():
    fin = _financials(growth=[{"growthRevenue": float("nan")}],
                       quarterly=[{"revenue": float("inf")}, {"revenue": 100}])
    out = derive_revenue_trend(fin)
    assert out["growth_yoy"] is None
    assert out["change_qoq"] is None


def test_mongo_numberlong_wrapper_is_coerced():
    fin = _financials(quarterly=[{"revenue": {"$numberLong": "110"}}, {"revenue": {"$numberLong": "100"}}])
    out = derive_revenue_trend(fin)
    assert out["change_qoq"] == 0.1
