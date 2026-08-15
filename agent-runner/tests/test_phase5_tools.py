"""Unit tests for Phase 5 tools (insider/institutional/sentiment/superinvestor) — offline."""
from datetime import datetime, timezone

import mongomock
import pytest

from tools import insider, institutional, sentiment, superinvestor
from tools.db import INSTITUTIONAL_CACHE


@pytest.fixture
def db():
    return mongomock.MongoClient()["p5_test"]


# --- insider -----------------------------------------------------------------

def fh_txn(name, code, change, price, date_):
    return {"name": name, "transactionCode": code, "change": change,
            "transactionPrice": price, "transactionDate": date_, "filingDate": date_}


def test_insider_normalization_and_net_direction(monkeypatch):
    def fake_get(path, **params):
        if path == "stock/insider-transactions":
            return {"data": [
                fh_txn("CEO Jane", "P", 5000, 100.0, "2026-07-01"),
                fh_txn("CFO Bob", "S", -2000, 100.0, "2026-07-05"),
                fh_txn("Dir Amy", "M", 1000, 0.0, "2026-07-06"),
            ]}
        return {"data": [{"year": 2026, "month": 7, "mspr": 25.0}]}

    monkeypatch.setattr(insider, "finnhub_get", fake_get)
    out = insider.get_insider_activity("aapl")

    types = [t["transaction_type"] for t in out["transactions"]]
    assert types == ["purchase", "sale", "option_exercise"]
    assert out["transactions"][0]["total_value"] == 500_000
    assert out["transactions"][1]["shares"] == 2000  # abs of negative change
    assert out["transactions"][2]["is_open_market"] is False
    assert out["net_direction"] == "net_buyer"
    assert out["mspr_monthly"][0]["mspr"] == 25.0


def test_cluster_detection_positive():
    txns = insider._normalize([
        fh_txn("A", "P", 100, 10, "2026-07-01"),
        fh_txn("B", "P", 100, 10, "2026-07-10"),
        fh_txn("C", "P", 100, 10, "2026-07-25"),
    ])
    cluster = insider.detect_cluster(txns)
    assert cluster["detected"] is True
    assert cluster["insiders"] == ["A", "B", "C"]
    assert cluster["window_days"] == 24


def test_cluster_needs_three_distinct_open_market_buyers():
    txns = insider._normalize([
        fh_txn("A", "P", 100, 10, "2026-07-01"),
        fh_txn("A", "P", 100, 10, "2026-07-02"),   # same person twice
        fh_txn("B", "M", 100, 0, "2026-07-03"),    # option exercise doesn't count
        fh_txn("C", "P", 100, 10, "2026-07-04"),
    ])
    assert insider.detect_cluster(txns)["detected"] is False


def test_cluster_window_excludes_spread_out_buys():
    txns = insider._normalize([
        fh_txn("A", "P", 100, 10, "2026-05-01"),
        fh_txn("B", "P", 100, 10, "2026-06-15"),
        fh_txn("C", "P", 100, 10, "2026-07-30"),
    ])
    assert insider.detect_cluster(txns)["detected"] is False


# --- institutional (read-only since specs/017-fmp-migration-admin) -----------

CACHED_HOLDERS = {
    "top_holders": [
        {"Date Reported": "2026-03-31", "Holder": "Blackrock Inc.", "pctChange": -0.01},
        {"Date Reported": "2026-03-31", "Holder": "Vanguard", "pctChange": 0.02},
    ],
    "fund_holders": [],
    "ownership_pct": 65.7,
    "institutions_count": 7659,
    "insiders_pct": 1.6,
    "top10_increasing": 1,
    "top10_decreasing": 1,
    "as_of": "2026-03-31",
}


def test_institutional_holdings_serves_cache_readonly_and_flags_stale(db):
    db[INSTITUTIONAL_CACHE].insert_one({"ticker": "AAPL", "data": CACHED_HOLDERS})

    out = institutional.get_institutional_holdings("aapl", db=db)
    assert out["ownership_pct"] == 65.7
    assert out["top_holders"][0]["Holder"] == "Blackrock Inc."
    assert out["stale"] is True  # never refreshed — 13F not entitled


def test_institutional_holdings_empty_when_never_cached(db):
    out = institutional.get_institutional_holdings("NEVER", db=db)
    assert out["top_holders"] == [] and out["ownership_pct"] is None
    assert out["stale"] is True


def test_recent_13f_changes_filters_by_date(db):
    db[INSTITUTIONAL_CACHE].insert_one({"ticker": "AAPL", "data": CACHED_HOLDERS})

    changes = institutional.get_recent_13f_changes(
        datetime(2026, 3, 1, tzinfo=timezone.utc), universe=["AAPL"], db=db)
    assert len(changes) == 2
    assert changes[0]["ticker"] == "AAPL"

    late = institutional.get_recent_13f_changes(
        datetime(2026, 6, 1, tzinfo=timezone.utc), universe=["AAPL"], db=db)
    assert late == []


# --- sentiment ---------------------------------------------------------------

def test_sentiment_news_and_surprises(monkeypatch):
    def fake_get(path, **params):
        if path == "company-news":
            return [{"datetime": 1785695580, "headline": f"headline {i}",
                     "summary": "s" * 500, "source": "src"} for i in range(40)]
        return [{"period": "2026-03-31", "actual": 1.91, "estimate": 1.93,
                 "surprisePercent": -0.9}] * 10

    monkeypatch.setattr(sentiment, "finnhub_get", fake_get)
    out = sentiment.get_earnings_sentiment("AAPL")

    assert len(out["news"]) == sentiment.MAX_HEADLINES
    assert len(out["news"][0]["summary"]) == sentiment.SUMMARY_CHARS
    assert len(out["earnings_surprises"]) == 8
    assert out["transcripts"] == []
    assert "premium" in out["transcripts_note"]


# --- superinvestor -----------------------------------------------------------

def test_superinvestor_degrades_without_playwright(db, monkeypatch):
    def boom(url):
        raise RuntimeError("playwright not installed")

    monkeypatch.setattr(superinvestor, "_fetch_page_text", boom)
    out = superinvestor.get_superinvestor_activity("AAPL", db=db)
    assert out["available"] is False
    assert out["moves"] == []


def test_superinvestor_extracts_and_filters(db, monkeypatch):
    monkeypatch.setattr(superinvestor, "_fetch_page_text", lambda url: "page text")
    monkeypatch.setattr(superinvestor, "generate_json", lambda *a, **k: {
        "moves": [
            {"fund": "Pershing Square", "action": "add", "ticker": "AAPL"},
            {"fund": "Berkshire", "action": "trim", "ticker": "KO"},
        ]
    })
    out = superinvestor.get_superinvestor_activity("AAPL", db=db)
    assert out["available"] is True
    assert out["moves"] == [{"fund": "Pershing Square", "action": "add", "ticker": "AAPL"}]
    assert db[superinvestor.DATAROMA_META].find_one({"key": "last_pull"})


def test_recent_moves_returns_all(monkeypatch):
    monkeypatch.setattr(superinvestor, "_fetch_page_text", lambda url: "text")
    monkeypatch.setattr(superinvestor, "generate_json", lambda *a, **k: {
        "moves": [{"fund": "X", "action": "buy", "ticker": "A"},
                  {"fund": "Y", "action": "sell", "ticker": "B"}]
    })
    moves = superinvestor.get_recent_superinvestor_moves(datetime(2026, 7, 1))
    assert len(moves) == 2
