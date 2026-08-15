"""Unit tests for the Phase 5 agents — LLM faked via schema-driven client."""
import json

import pytest

from agents import (
    insider_analyst,
    institutional_analyst,
    macro_analyst,
    recommender_agent,
    sentiment_analyst,
)


class SchemaFakeLLM:
    """Returns a minimal valid object for whichever schema each call passes."""

    def __init__(self):
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        payload = self._fill(kwargs["format"])
        return {"message": {"content": json.dumps(payload)}}

    def _fill(self, schema):
        payload = {}
        for key, spec in schema.get("properties", {}).items():
            t = spec.get("type")
            if t == "string":
                payload[key] = spec["enum"][0] if "enum" in spec else f"text-{key}"
            elif t == "array":
                payload[key] = []
            elif t == "object":
                payload[key] = self._fill(spec)
        return payload


@pytest.fixture
def client():
    return SchemaFakeLLM()


def macro_context():
    return {
        "macro": {
            "CPIAUCSL": [{"date": "2026-07-01", "value": 330.1}] * 8,
            "FEDFUNDS": [{"date": "2026-07-01", "value": 4.25}],
        },
        "yield_curve": {"10y_2y_spread": 0.4, "inverted": False, "inversion_severity": "none"},
    }


def test_macro_agent_attaches_hard_numbers(client):
    out = macro_analyst.run("Technology", macro_context(), client=client)
    assert out["rate_impact"]["fed_funds_rate"] == 4.25
    assert out["inflation_impact"]["cpi_latest"] == 330.1
    assert out["growth_backdrop"]["yield_curve_spread"] == 0.4
    assert out["overall_macro_signal"] in ("bullish", "bearish", "neutral")
    prompt = client.calls[0]["messages"][-1]["content"]
    assert "Technology" in prompt


def test_insider_agent_preserves_deterministic_fields(client):
    insider_data = {
        "transactions": [{"name": "CEO", "transaction_type": "purchase", "shares": 100,
                          "price_per_share": 10.0, "total_value": 1000.0,
                          "date": "2026-07-01", "filing_date": "2026-07-02",
                          "is_open_market": True}],
        "mspr_monthly": [{"year": 2026, "month": 7, "mspr": 30.0}],
        "cluster_signal": {"detected": True, "insiders": ["A", "B", "C"], "window_days": 12},
        "net_direction": "net_buyer",
        "open_market_buy_value": 1000.0,
        "open_market_sell_value": 0.0,
    }
    out = insider_analyst.run("AAPL", {"insider": insider_data}, client=client)
    assert out["cluster_signal"]["detected"] is True
    assert out["net_direction"] == "net_buyer"
    assert out["recent_transactions"][0]["name"] == "CEO"
    assert out["overall_insider_signal"] in ("bullish", "bearish", "neutral")


def test_institutional_agent_summary_and_unavailable_superinvestor(client):
    inst = {"ownership_pct": 65.7, "institutions_count": 7659, "insiders_pct": 1.6,
            "top10_increasing": 4, "top10_decreasing": 3, "as_of": "2026-03-31",
            "top_holders": [{"Holder": "Blackrock", "pctChange": -0.01}]}
    out = institutional_analyst.run("AAPL", {"institutional": inst, "superinvestor": None},
                                    client=client)
    assert out["institutional_summary"]["ownership_pct"] == 65.7
    assert out["superinvestor_available"] is False
    prompt = client.calls[0]["messages"][-1]["content"]
    assert "UNAVAILABLE" in prompt


def test_sentiment_agent_keyword_counts(client):
    news = [{"headline": "Record revenue and strong demand", "summary": "momentum builds"},
            {"headline": "Company faces headwinds", "summary": "cautious guidance"}]
    out = sentiment_analyst.run(
        "AAPL", {"sentiment": {"news": news, "earnings_surprises": [], "transcripts": []}},
        client=client)
    assert out["bullish_keywords"]["count"] >= 3  # record, strong, momentum...
    assert out["cautious_keywords"]["count"] >= 2  # headwind, cautious
    assert out["news_count"] == 2
    assert out["transcripts_available"] is False


def test_count_keywords_empty_news():
    counts = sentiment_analyst.count_keywords([])
    assert counts["bullish_keywords"]["count"] == 0
    assert counts["cautious_keywords"]["count"] == 0


def test_recommender_keeps_rule_verdict(client):
    flow = {"recommendation": "BUY_MORE", "conviction": "high",
            "rationale": "NYMO -72 oversold", "caveats": ["scale in"],
            "divergence_detected": True, "nymo_signal": "oversold",
            "nymo_current": -72, "namo_current": -68}
    breadth = {"nymo": {"current": -72, "zone": "oversold", "trend": "rising"},
               "namo": {"current": -68, "zone": "oversold", "trend": "rising"},
               "divergence": {"type": "bullish", "description": "d"}}
    gap = {"latest_gap": {"direction": "down", "gap_type": "runaway", "score": 4}}

    out = recommender_agent.run("AAPL", {"market_flow": flow, "breadth": breadth, "gap": gap},
                                client=client)
    assert out["recommendation"] == "BUY_MORE"       # rule verdict untouched
    assert out["conviction"] == "high"
    assert out["nymo_reading"] == {"value": -72, "trend": "rising", "zone": "oversold"}
    assert out["divergence_detected"] is True
    assert out["gap_score_summary"]["latest_gap"]["score"] == 4
    assert out["gap_score_summary"]["exhaustion_present"] is False
    assert "scale in" in out["caveats"]
    prompt = client.calls[0]["messages"][-1]["content"]
    assert "authoritative" in prompt


def test_recommender_handles_no_gap(client):
    flow = {"recommendation": "HOLD", "conviction": "low", "rationale": "r", "caveats": [],
            "divergence_detected": False, "nymo_signal": "neutral",
            "nymo_current": 5, "namo_current": 3}
    out = recommender_agent.run("AAPL", {"market_flow": flow, "breadth": {}, "gap": {}},
                                client=client)
    assert out["gap_score_summary"]["latest_gap"] is None
    assert out["recommendation"] == "HOLD"
