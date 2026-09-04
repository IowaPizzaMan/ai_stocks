"""Pure revenue-trend derivation for skills/conviction.py.
Spec: specs/037-stocks-conviction-and-activity; data-model.md; contracts/conviction-rules.md
Rule 3.

No new or widened FMP call. Both figures come from data get_financials() already caches
today (research.md R4 Amendment — an earlier version of this feature widened
tools/financials.py's income_quarterly limit from 4 to 8 to support a true q[0]-vs-q[4]
comparison; that was reverted after KNOWN_ISSUES.md surfaced that this FMP plan 402s the
*entire* income-statement call beyond ~4 quarterly periods, which would have silently
broken the existing 4-quarter fetch instead of adding rows):

- growth_yoy reads financials["growth"][0]["growthRevenue"] — FMP's own annual
  year-over-year revenue growth (most recent fiscal year vs. the one before), the same
  figure tools/screener.py already exposes as `revenue_growth_yoy`.
- change_qoq compares financials["income_quarterly"][0] against [1] (newest-first, per
  FMP) — needs only 2 of the already-cached 4 quarters.
"""


def _num(value):
    """Coerce a Mongo numeric wrapper ($numberLong et al.) or plain value to a finite
    float, or None. Mirrors tools/screener.py's `_num` — duplicated rather than imported
    since skills/tools must not depend on each other's internals across features."""
    if value is None:
        return None
    if isinstance(value, dict) and "$numberLong" in value:
        value = value["$numberLong"]
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")):  # NaN / +-Infinity
        return None
    return value


def derive_revenue_trend(financials: dict | None) -> dict:
    """Pure: same `financials` payload -> identical output. `financials` is a
    tools/financials.py::get_financials() dict (income_annual/income_quarterly/growth/
    ratios/cashflow_annual/balance_annual), the same shape crew.py already fetches.

    Returns {growth_yoy, change_qoq, yoy_growing, qoq_declining, latest_period, missing}.
    `missing` lists which of "growth_yoy"/"change_qoq" could not be computed — absence is
    always represented as None, never a fabricated value (screener.py's SC-008 discipline)."""
    result = {
        "growth_yoy": None,
        "change_qoq": None,
        "yoy_growing": False,
        "qoq_declining": False,
        "latest_period": None,
        "missing": [],
    }
    if not financials:
        result["missing"] = ["growth_yoy", "change_qoq"]
        return result

    growth = financials.get("growth") or []
    quarterly = financials.get("income_quarterly") or []

    growth_yoy = _num(growth[0].get("growthRevenue")) if growth else None
    result["growth_yoy"] = growth_yoy
    result["yoy_growing"] = growth_yoy is not None and growth_yoy > 0
    if growth_yoy is None:
        result["missing"].append("growth_yoy")

    if quarterly:
        result["latest_period"] = quarterly[0].get("date")

    change_qoq = None
    if len(quarterly) >= 2:
        latest_rev = _num(quarterly[0].get("revenue"))
        prior_rev = _num(quarterly[1].get("revenue"))
        if latest_rev is not None and prior_rev is not None and prior_rev != 0:
            change_qoq = (latest_rev - prior_rev) / abs(prior_rev)
    result["change_qoq"] = change_qoq
    result["qoq_declining"] = change_qoq is not None and change_qoq < 0
    if change_qoq is None:
        result["missing"].append("change_qoq")

    return result
