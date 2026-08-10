"""Unit tests for crew.py — all fetchers and the LLM faked; no network."""
import json

import mongomock
import numpy as np
import pandas as pd
import pytest

from crew import Crew, TickerDelistedError, _earnings_dates, _price_summary


def make_history(rows=120, seed=11):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.1, 1, rows))
    dates = pd.date_range("2026-02-02", periods=rows, freq="B")
    df = pd.DataFrame({
        "Date": dates,
        "Open": close - 0.3, "High": close + 1.5, "Low": close - 1.5,
        "Close": close, "Volume": rng.integers(1_000_000, 3_000_000, rows),
    })
    records = df.to_dict(orient="records")
    return {"daily": records, "weekly": records[::5], "monthly": records[::21], "ticker": "AAPL"}


class SchemaFakeLLM:
    """Returns a minimal valid object for whichever schema each call passes."""

    def __init__(self):
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        schema = kwargs["format"]
        payload = {}
        for key, spec in schema["properties"].items():
            if spec.get("type") == "string":
                payload[key] = spec["enum"][0] if "enum" in spec else f"text-{key}"
            elif spec.get("type") == "array":
                payload[key] = []
            elif spec.get("type") == "object":
                payload[key] = {k: [] for k in spec.get("properties", {})}
        return {"message": {"content": json.dumps(payload)}}


def make_crew(valid=True, financials=None):
    db = mongomock.MongoClient()["crew_test"]
    crew = Crew(db=db, client=SchemaFakeLLM())
    history = make_history()
    crew.is_ticker_valid = lambda t: valid
    crew.get_price_history = lambda t: history
    crew.get_technical_indicators = lambda t: [{"Date": "2026-08-01", "Close": 190.0, "RSI_14": 55.0}]
    crew.get_financials = lambda t, db=None: financials if financials is not None else {
        "income_annual": [{"date": "2025-09-30", "fiscalYear": "2025", "period": "FY",
                           "revenue": 1e9, "netIncome": 2e8, "grossProfit": 5e8,
                           "operatingIncome": 3e8}],
        "income_quarterly": [], "balance_annual": [], "cashflow_annual": [],
        "ratios": [], "key_metrics": [], "growth": [],
    }
    crew.get_earnings_data = lambda t: {"earnings_dates": [{"Earnings Date": "2026-07-30"}]}
    crew.get_market_breadth = lambda db=None: {
        "nymo": {"history": [{"date": "2026-08-01", "value": -15.0}], "current": -15.0,
                 "zone": "neutral", "trend": "flat"},
        "namo": {"history": [], "current": -10.0, "zone": "neutral", "trend": "flat"},
        "divergence": {"type": "none", "description": ""},
        "method": "computed_ratio_adjusted",
    }
    crew.get_macro_data = lambda db=None: {"FEDFUNDS": [{"date": "2026-07-01", "value": 4.25}]}
    crew.get_yield_curve_status = lambda db=None: {"10y_2y_spread": 0.4, "inverted": False,
                                                   "inversion_severity": "none"}
    crew.get_insider_activity = lambda t: {
        "transactions": [], "mspr_monthly": [],
        "cluster_signal": {"detected": False, "insiders": [], "window_days": None},
        "net_direction": "balanced", "open_market_buy_value": 0, "open_market_sell_value": 0,
    }
    crew.get_institutional_holdings = lambda t, db=None: {
        "top_holders": [], "fund_holders": [], "ownership_pct": 60.0,
        "institutions_count": 5000, "insiders_pct": 1.0,
        "top10_increasing": 5, "top10_decreasing": 5, "as_of": "2026-03-31",
    }
    crew.get_superinvestor_activity = lambda t, db=None, client=None: {
        "moves": [], "available": False, "note": "test"}
    crew.get_earnings_sentiment = lambda t: {"news": [], "earnings_surprises": [],
                                             "transcripts": [], "transcripts_note": "n/a"}
    return crew


def test_run_produces_full_analyses_document():
    crew = make_crew()
    doc = crew.run("aapl")

    assert doc["ticker"] == "AAPL"
    assert doc["signal"] in ("bullish", "bearish", "neutral")
    assert doc["conviction"] in ("high", "medium", "low")
    assert "timestamp" in doc and "summary" in doc
    assert set(doc["sub_reports"]) == {"technical", "fundamental", "macro", "insider",
                                       "institutional", "sentiment", "recommendation"}
    # deterministic pieces flow through
    assert doc["sub_reports"]["technical"]["strat_result"]["tfc"]["status"] in (
        "full_bullish", "full_bearish", "conflict")
    assert doc["sub_reports"]["recommendation"]["recommendation"] in (
        "BUY_MORE", "HOLD", "TRIM", "START_SELLING", "AVOID_ADD", "WATCH")
    assert doc["sub_reports"]["macro"]["rate_impact"]["fed_funds_rate"] == 4.25
    assert doc["sub_reports"]["institutional"]["institutional_summary"]["ownership_pct"] == 60.0
    assert doc["sub_reports"]["insider"]["net_direction"] == "balanced"
    assert doc["sub_reports"]["sentiment"]["news_count"] == 0
    assert len(doc["position_management"]["stair_step_stops"]) > 0
    # feed flag fields ride top-level (5 increasing vs 5 decreasing → mixed;
    # the insider stub has no recent_summary → None)
    assert doc["recent_institutional_activity"] == "mixed"
    assert doc["recent_insider_summary"] is None
    # eight LLM calls: tech, fund, macro, insider, institutional, sentiment,
    # recommender, strategist
    assert len(crew.client.calls) == 8


def test_invalid_ticker_with_no_financials_raises_delisted():
    crew = make_crew(valid=False, financials={"income_annual": [], "income_quarterly": []})
    with pytest.raises(TickerDelistedError):
        crew.run("GONE")


def test_invalid_ticker_with_financials_proceeds():
    crew = make_crew(valid=False)
    doc = crew.run("AAPL")
    assert doc["ticker"] == "AAPL"


def test_parallel_prefetch_produces_same_shape():
    doc = make_crew().run("AAPL", parallel_prefetch=True)
    assert set(doc["sub_reports"]) == {"technical", "fundamental", "macro", "insider",
                                       "institutional", "sentiment", "recommendation"}


def test_macro_analyst_cached_across_tickers_in_same_sector():
    db = mongomock.MongoClient()["crew_test"]
    db["ticker_index"].insert_many([
        {"ticker": "AAPL", "sector": "Technology"},
        {"ticker": "MSFT", "sector": "Technology"},
    ])
    crew = make_crew()
    crew.db = db

    crew.run("AAPL")
    first_call_count = len(crew.client.calls)
    crew.run("MSFT")
    second_run_calls = len(crew.client.calls) - first_call_count

    # same 8 agent/strategist calls minus the cached macro_analyst call
    assert second_run_calls == first_call_count - 1


def test_earnings_dates_extraction():
    earnings = {"earnings_dates": [
        {"Earnings Date": "2026-07-30"},
        {"Earnings Date": pd.Timestamp("2026-04-28 16:00:00")},
        {"other": 1},
    ]}
    dates = _earnings_dates(earnings)
    assert len(dates) == 2
    assert dates[0].isoformat() == "2026-07-30"


def test_price_summary():
    history = make_history()
    summary = _price_summary(history["daily"])
    assert summary["last_close"] > 0
    assert summary["low_60d"] <= summary["high_60d"]
    assert _price_summary([]) == {}
