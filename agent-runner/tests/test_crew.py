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
    # rows=120 by default — ::63 and ::100 each still land >= 2 records, which
    # is all the_strat.run needs (it only classifies the last couple of bars)
    return {
        "daily": records, "weekly": records[::5], "monthly": records[::21],
        "quarterly": records[::63], "yearly": records[::100],
        "ticker": "AAPL",
    }


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
    # 021 additions
    crew.get_insider_quarterly_stats = lambda t, db=None: []
    crew.get_beneficial_ownership = lambda t, db=None: {
        "filings": [], "direction": None, "stale": False}
    crew.get_stock_news = lambda t, db=None: {
        "articles": [], "timeline": [], "trend": "mixed", "news_count": 0,
        "as_of": None, "stale": False}
    return crew


def test_run_produces_full_analyses_document():
    crew = make_crew()
    doc = crew.run("aapl")

    assert doc["ticker"] == "AAPL"
    assert doc["signal"] in ("bullish", "bearish", "neutral")
    assert doc["conviction"] in ("high", "medium", "low")
    assert "timestamp" in doc and "summary" in doc
    assert set(doc["sub_reports"]) == {"technical", "fundamental", "insider",
                                       "institutional", "sentiment", "recommendation",
                                       "news"}
    # deterministic pieces flow through
    assert doc["sub_reports"]["technical"]["strat_result"]["tfc"]["status"] in (
        "full_bullish", "full_bearish", "conflict")
    assert doc["sub_reports"]["recommendation"]["recommendation"] in (
        "BUY_MORE", "HOLD", "TRIM", "START_SELLING", "AVOID_ADD", "WATCH")
    assert doc["sub_reports"]["institutional"]["institutional_summary"]["ownership_pct"] == 60.0
    assert doc["sub_reports"]["insider"]["net_direction"] == "balanced"
    assert doc["sub_reports"]["sentiment"]["news_count"] == 0
    assert len(doc["position_management"]["stair_step_stops"]) > 0
    # feed flag fields ride top-level (5 increasing vs 5 decreasing → mixed;
    # the insider stub has no recent_summary → None)
    assert doc["recent_institutional_activity"] == "mixed"
    assert doc["recent_insider_summary"] is None
    # first-ever pull for this ticker → nothing to diff against (021 FR-025)
    assert doc["changes_since_last"] is None
    # seven LLM calls: tech, fund, insider, institutional, sentiment,
    # recommender, strategist — macro no longer runs per ticker, and the news
    # agent short-circuits without articles rather than calling the model
    assert len(crew.client.calls) == 7


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
    assert set(doc["sub_reports"]) == {"technical", "fundamental", "insider",
                                       "institutional", "sentiment", "recommendation",
                                       "news"}


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


# --- 021-stock-page-redesign: changes since last analysis ---------------------

def test_diff_since_last_is_none_on_first_pull():
    from crew import diff_since_last
    assert diff_since_last(None, "bullish", "high", []) is None


def test_diff_since_last_reports_signal_and_conviction_moves():
    from crew import diff_since_last

    previous = {"timestamp": "2026-08-01T00:00:00Z", "signal": "neutral",
                "conviction": "low", "flags": ["stale financials"]}
    diff = diff_since_last(previous, "bullish", "high", ["gap unfilled"])

    assert diff["previous_timestamp"] == "2026-08-01T00:00:00Z"
    assert diff["signal"] == {"from": "neutral", "to": "bullish", "changed": True}
    assert diff["conviction"] == {"from": "low", "to": "high", "changed": True}
    assert diff["flags_added"] == ["gap unfilled"]
    assert diff["flags_removed"] == ["stale financials"]


def test_diff_since_last_marks_unchanged_when_nothing_moved():
    from crew import diff_since_last

    previous = {"timestamp": "2026-08-01T00:00:00Z", "signal": "bullish",
                "conviction": "high", "flags": ["a"]}
    diff = diff_since_last(previous, "bullish", "high", ["a"])

    assert diff["signal"]["changed"] is False
    assert diff["conviction"]["changed"] is False
    assert diff["flags_added"] == [] and diff["flags_removed"] == []


def test_run_diffs_against_the_stored_previous_analysis():
    crew = make_crew()
    crew.db["analyses"].insert_one({
        "ticker": "AAPL", "timestamp": "2026-08-01T00:00:00Z",
        "signal": "bearish", "conviction": "low", "flags": ["old flag"],
    })

    doc = crew.run("aapl")

    changes = doc["changes_since_last"]
    assert changes is not None
    assert changes["signal"]["from"] == "bearish"
    assert changes["signal"]["to"] == doc["signal"]
    assert "old flag" in changes["flags_removed"]


def test_run_attaches_news_subreport_and_flow_fields():
    crew = make_crew()
    crew.get_stock_news = lambda t, db=None: {
        "articles": [{"date": "2026-08-15", "datetime": "2026-08-15 09:00:00",
                      "source": "Wire", "headline": "Record beat", "url": "u",
                      "text_excerpt": "strong demand", "bullish_count": 3,
                      "bearish_count": 0, "ai_summary": None}],
        "timeline": [{"date": "2026-08-15", "bullish": 3, "bearish": 0, "article_count": 1}],
        "trend": "bullish", "news_count": 1, "as_of": "2026-08-15", "stale": False,
    }
    crew.get_insider_quarterly_stats = lambda t, db=None: [
        {"year": 2026, "quarter": 2, "acquired_transactions": 7, "disposed_transactions": 40,
         "acquired_disposed_ratio": 0.175, "total_acquired": 303199, "total_disposed": 927380,
         "total_purchases": 1, "total_sales": 12}
    ]
    crew.get_beneficial_ownership = lambda t, db=None: {
        "filings": [{"filer": "Capital Research", "filing_date": "2026-06-04",
                     "shares": 75279354, "pct_of_class": 11.1, "filer_type": "IA", "url": "u"}],
        "direction": "accumulating", "stale": False,
    }

    doc = crew.run("aapl")
    subs = doc["sub_reports"]

    assert subs["news"]["trend"] == "bullish"
    assert subs["news"]["news_count"] == 1
    assert subs["insider"]["quarterly_stats"][0]["total_disposed"] == 927380
    assert subs["institutional"]["beneficial_direction"] == "accumulating"
    assert subs["institutional"]["beneficial_filings"][0]["filer"] == "Capital Research"
    # with articles present the news agent does call the model → eight calls
    assert len(crew.client.calls) == 8
