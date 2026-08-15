"""FundamentalAnalyst: financial health, earnings trajectory, valuation.
Spec: specs/component-specs/agent-runner/agents/fundamental_analyst.md

History arrays are extracted deterministically from the cached FMP payloads so
the frontend can chart them verbatim; the LLM supplies direction/assessment
labels, the narrative, and the overall signal.
"""
import json

from llm import generate_json

SYSTEM = (
    "You are a fundamental analyst trained in reading income statements, balance sheets, "
    "and cash flow statements. You evaluate whether a company is growing profitably and "
    "whether its current price reflects fair value."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "revenue_direction": {"type": "string", "enum": ["accelerating", "stable", "decelerating", "declining"]},
        "margin_direction": {"type": "string", "enum": ["expanding", "stable", "compressing"]},
        "balance_sheet_assessment": {"type": "string", "enum": ["strong", "adequate", "stretched", "weak"]},
        "fcf_assessment": {"type": "string", "enum": ["healthy", "adequate", "weak", "negative"]},
        "estimate_revisions": {"type": "string", "enum": ["up", "flat", "down", "unknown"]},
        "valuation_view": {"type": "string", "enum": ["cheap", "fair", "slight_premium", "expensive", "unknown"]},
        "narrative": {"type": "string"},
        "overall_fundamental_signal": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["revenue_direction", "margin_direction", "balance_sheet_assessment",
                 "fcf_assessment", "estimate_revisions", "valuation_view", "narrative",
                 "overall_fundamental_signal", "confidence"],
}


def _get(row: dict, *keys, default=None):
    for key in keys:
        if row.get(key) is not None:
            return row[key]
    return default


def _bn(value) -> float | None:
    return round(value / 1e9, 2) if isinstance(value, (int, float)) else None


def _period(row: dict) -> str:
    year = _get(row, "fiscalYear", "calendarYear", default="")
    period = row.get("period", "FY")
    date = str(row.get("date", ""))[:10]
    return f"{period}'{year}" if period != "FY" else (str(year) or date)


def extract_histories(financials: dict) -> dict:
    """Period-by-period series (oldest→newest) from the raw FMP payloads."""
    income = list(reversed(financials.get("income_annual") or []))
    income_q = list(reversed(financials.get("income_quarterly") or []))
    balance = list(reversed(financials.get("balance_annual") or []))
    cashflow = list(reversed(financials.get("cashflow_annual") or []))

    revenue_annual = []
    prev_rev = None
    for row in income:
        rev = _get(row, "revenue")
        yoy = (round((rev - prev_rev) / prev_rev * 100, 1)
               if isinstance(rev, (int, float)) and isinstance(prev_rev, (int, float)) and prev_rev
               else None)
        revenue_annual.append({"period": _period(row), "revenue_bn": _bn(rev),
                               "net_income_bn": _bn(_get(row, "netIncome")),
                               "yoy_growth_pct": yoy})
        prev_rev = rev

    margins = []
    for row in income:
        rev = _get(row, "revenue")
        if not rev:
            continue
        margins.append({
            "period": _period(row),
            "gross": round(_get(row, "grossProfit", default=0) / rev * 100, 1),
            "operating": round(_get(row, "operatingIncome", default=0) / rev * 100, 1),
            "net": round(_get(row, "netIncome", default=0) / rev * 100, 1),
        })

    balance_hist = []
    for row in balance:
        equity = _get(row, "totalStockholdersEquity", "totalEquity")
        debt = _get(row, "totalDebt")
        balance_hist.append({
            "period": _period(row),
            "cash_bn": _bn(_get(row, "cashAndShortTermInvestments", "cashAndCashEquivalents")),
            "debt_bn": _bn(debt),
            "debt_equity": (round(debt / equity, 2)
                            if isinstance(debt, (int, float)) and isinstance(equity, (int, float)) and equity
                            else None),
        })

    fcf_hist = [{"period": _period(row), "fcf_bn": _bn(_get(row, "freeCashFlow"))}
                for row in cashflow]

    revenue_quarterly = []
    for row in income_q:
        revenue_quarterly.append({"period": _period(row), "revenue_bn": _bn(_get(row, "revenue")),
                                  "eps": _get(row, "eps", "epsDiluted")})

    return {
        "revenue_annual": revenue_annual,
        "revenue_quarterly": revenue_quarterly,
        "margins_annual": margins,
        "balance_annual": balance_hist,
        "fcf_annual": fcf_hist,
    }


def run(ticker: str, context: dict, client=None) -> dict:
    """context: {'financials': get_financials() output, 'earnings': get_earnings_data() output}"""
    histories = extract_histories(context.get("financials") or {})
    earnings = context.get("earnings") or {}

    prompt = f"""Assess the financial fundamentals of {ticker} from the extracted series below
(oldest to newest; *_bn values are USD billions).

## Revenue & net income (annual)
{json.dumps(histories["revenue_annual"])}

## Revenue & EPS (quarterly)
{json.dumps(histories["revenue_quarterly"])}

## Margins %, annual (gross / operating / net)
{json.dumps(histories["margins_annual"])}

## Balance sheet (cash, total debt, debt/equity)
{json.dumps(histories["balance_annual"])}

## Free cash flow (annual)
{json.dumps(histories["fcf_annual"])}

## Analyst estimates & revisions (FMP, may be partial)
{json.dumps({k: earnings.get(k) for k in ("eps_trend", "forward_estimates")}, default=str)[:2000]}

Evaluate: revenue trajectory (accelerating/decelerating?), margin direction, balance-sheet
health, FCF quality, estimate revisions, and a valuation view if the data allows (mark
"unknown" if not). Write a 3-5 sentence narrative that references specific numbers, then
give overall_fundamental_signal and confidence."""

    report = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
    return {
        "revenue_trend": {"direction": report["revenue_direction"],
                          "history_annual": histories["revenue_annual"],
                          "history_quarterly": histories["revenue_quarterly"]},
        "margin_trend": {"direction": report["margin_direction"],
                         "history_annual": histories["margins_annual"]},
        "balance_sheet_health": {"assessment": report["balance_sheet_assessment"],
                                 "history_annual": histories["balance_annual"]},
        "fcf_profile": {"assessment": report["fcf_assessment"],
                        "history_annual": histories["fcf_annual"]},
        "earnings_track_record": {"estimate_revisions": report["estimate_revisions"]},
        "valuation_assessment": {"view": report["valuation_view"]},
        "narrative": report["narrative"],
        "overall_fundamental_signal": report["overall_fundamental_signal"],
        "confidence": report["confidence"],
    }
