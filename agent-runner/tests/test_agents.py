"""Unit tests for the Phase 3 agents — LLM client faked; no network."""
import json

import pytest

from agents import fundamental_analyst, portfolio_strategist, technical_analyst


class FakeClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": json.dumps(self.payload)}}


TECH_LLM = {
    "key_levels": {"support": [180.0], "resistance": [195.0]},
    "momentum_summary": "RSI trending up.",
    "tfc_narrative": "Daily and weekly aligned green.",
    "bf_position_narrative": "Mid-range, no edge.",
    "volume_narrative": "Early-stage accumulation.",
    "overall_technical_signal": "bullish",
    "confidence": "medium",
}


def tech_context():
    return {
        "strat": {"tfc": {"status": "full_bullish"}, "signal": "full TFC bullish"},
        "accumulation": {"accumulation_score": 3, "signal": "ACCUMULATION"},
        "gap": {"latest_gap": None, "peg": None, "r2g_candidate": False, "signal": "no gaps",
                "gaps": []},
        "indicators": [{"Date": "2026-08-01", "Close": 190.0, "RSI_14": 61.2,
                        "MACD": 1.1, "MACD_HIST": 0.2, "ATR_14": 3.4,
                        "EMA_21": 188.0, "EMA_50": 184.0, "EMA_200": 170.0}],
        "price_summary": {"last_close": 190.0},
    }


def test_technical_agent_merges_skills_and_llm():
    client = FakeClient(TECH_LLM)
    out = technical_analyst.run("AAPL", tech_context(), client=client)

    assert out["overall_technical_signal"] == "bullish"
    assert out["strat_result"]["tfc"]["status"] == "full_bullish"
    assert out["accumulation_result"]["accumulation_score"] == 3
    assert out["gap_result"]["signal"] == "no gaps"
    assert out["key_levels"]["support"] == [180.0]

    prompt = client.calls[0]["messages"][-1]["content"]
    assert "AAPL" in prompt and "full_bullish" in prompt
    assert client.calls[0]["format"] == technical_analyst.SCHEMA


def test_technical_compact_indicators_drops_nan_and_rounds():
    rows = [{"Date": "2026-08-01", "Close": 190.123, "RSI_14": float("nan"), "MACD": 1.234}]
    compact = technical_analyst._compact_indicators(rows)
    assert compact == [{"date": "2026-08-01", "Close": 190.12, "MACD": 1.23}]


FUND_LLM = {
    "revenue_direction": "accelerating",
    "margin_direction": "expanding",
    "balance_sheet_assessment": "strong",
    "fcf_assessment": "healthy",
    "estimate_revisions": "up",
    "valuation_view": "fair",
    "narrative": "Revenue accelerated to 12% growth.",
    "overall_fundamental_signal": "bullish",
    "confidence": "high",
}


def fmp_financials():
    def income(year, revenue, net, gross, op):
        return {"date": f"{year}-09-30", "fiscalYear": str(year), "period": "FY",
                "revenue": revenue, "netIncome": net, "grossProfit": gross,
                "operatingIncome": op}
    return {
        "income_annual": [income(2025, 120e9, 30e9, 55e9, 38e9),
                          income(2024, 100e9, 24e9, 45e9, 30e9)],
        "income_quarterly": [{"date": "2025-09-30", "fiscalYear": "2025", "period": "Q4",
                              "revenue": 33e9, "eps": 2.1}],
        "balance_annual": [{"date": "2025-09-30", "fiscalYear": "2025", "period": "FY",
                            "cashAndShortTermInvestments": 28e9, "totalDebt": 12e9,
                            "totalStockholdersEquity": 60e9}],
        "cashflow_annual": [{"date": "2025-09-30", "fiscalYear": "2025", "period": "FY",
                             "freeCashFlow": 22e9}],
        "ratios": [], "key_metrics": [], "growth": [],
    }


def test_fundamental_histories_extracted_deterministically():
    hist = fundamental_analyst.extract_histories(fmp_financials())
    # oldest → newest with YoY computed on the second year
    assert hist["revenue_annual"][0]["revenue_bn"] == 100.0
    assert hist["revenue_annual"][1]["yoy_growth_pct"] == 20.0
    assert hist["margins_annual"][1] == {"period": "2025", "gross": 45.8, "operating": 31.7, "net": 25.0}
    assert hist["balance_annual"][0]["debt_equity"] == 0.2
    assert hist["fcf_annual"][0]["fcf_bn"] == 22.0
    assert hist["revenue_quarterly"][0]["period"] == "Q4'2025"


def test_fundamental_agent_merges():
    client = FakeClient(FUND_LLM)
    out = fundamental_analyst.run("AAPL", {"financials": fmp_financials(), "earnings": {}},
                                  client=client)
    assert out["overall_fundamental_signal"] == "bullish"
    assert out["revenue_trend"]["direction"] == "accelerating"
    assert out["revenue_trend"]["history_annual"][1]["yoy_growth_pct"] == 20.0
    assert out["balance_sheet_health"]["assessment"] == "strong"


def test_fundamental_handles_empty_payload():
    hist = fundamental_analyst.extract_histories({})
    assert hist["revenue_annual"] == []
    client = FakeClient(FUND_LLM)
    out = fundamental_analyst.run("AAPL", {"financials": {}, "earnings": {}}, client=client)
    assert out["revenue_trend"]["history_annual"] == []


STRAT_LLM = {
    "signal": "bullish",
    "conviction": "high",
    "summary": "High-conviction long setup.",
    "key_trends": ["Accumulation 4/5", "TFC aligned"],
    "flags": [],
    "position_sizing": "full position",
    "trailing_stop_recommendation": "trail below prior day low",
}


def test_strategist_builds_stop_ladder_and_verdict():
    client = FakeClient(STRAT_LLM)
    subs = {"technical": {"overall_technical_signal": "bullish",
                          "history_annual": ["should be trimmed"]},
            "fundamental": {"overall_fundamental_signal": "bullish"},
            "recommendation": {"recommendation": "BUY_MORE"}}
    out = portfolio_strategist.run("AAPL", subs, recent_lows=[186.0, 187.5, 189.2], client=client)

    assert out["signal"] == "bullish"
    assert out["position_management"]["stair_step_stops"] == [189.05, 187.35, 185.85]
    assert out["position_management"]["position_sizing"] == "full position"

    prompt = client.calls[0]["messages"][-1]["content"]
    assert "BUY_MORE" in prompt
    assert "should be trimmed" not in prompt  # history arrays stripped


def test_stair_step_stops_dedupes_and_sorts():
    assert portfolio_strategist.stair_step_stops([10.0, 10.0, 12.0]) == [11.85, 9.85]
    assert portfolio_strategist.stair_step_stops([]) == []
