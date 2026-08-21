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
    out = insider.get_insider_activity("aapl", db=mongomock.MongoClient()["t"])

    # 024 — transactions come back newest-first now. Merging a stored set with a
    # fetched one destroys provider order, so an explicit sort is required; the
    # descending choice makes insider_analyst's `transactions[:15]` actually mean
    # "the 15 most recent" for a field it publishes as `recent_transactions`,
    # which arbitrary provider order never guaranteed.
    types = [t["transaction_type"] for t in out["transactions"]]
    assert types == ["option_exercise", "sale", "purchase"]

    by_type = {t["transaction_type"]: t for t in out["transactions"]}
    assert by_type["purchase"]["total_value"] == 500_000
    assert by_type["sale"]["shares"] == 2000  # abs of negative change
    assert by_type["option_exercise"]["is_open_market"] is False
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


# --- 021-stock-page-redesign: FMP-backed flow data ---------------------------

def test_insider_quarterly_stats_normalization(monkeypatch):
    raw = [
        {"symbol": "AAPL", "year": 2026, "quarter": 2, "acquiredTransactions": 7,
         "disposedTransactions": 40, "acquiredDisposedRatio": 0.175,
         "totalAcquired": 303199, "totalDisposed": 927380,
         "totalPurchases": 1, "totalSales": 12},
        {"symbol": "AAPL", "year": 2026, "quarter": 3, "acquiredTransactions": 0,
         "disposedTransactions": 1, "acquiredDisposedRatio": 0,
         "totalAcquired": 0, "totalDisposed": 1439,
         "totalPurchases": 0, "totalSales": 1},
    ]
    monkeypatch.setattr(insider, "fmp_get", lambda path, db=None: raw)

    stats = insider.get_insider_quarterly_stats("aapl")

    # newest quarter first regardless of the order FMP returned
    assert [(s["year"], s["quarter"]) for s in stats] == [(2026, 3), (2026, 2)]
    assert stats[1]["acquired_transactions"] == 7
    assert stats[1]["total_disposed"] == 927380
    assert stats[1]["acquired_disposed_ratio"] == pytest.approx(0.175)


def test_insider_quarterly_stats_caps_at_eight_quarters(monkeypatch):
    raw = [{"year": 2020 + (i // 4), "quarter": (i % 4) + 1} for i in range(20)]
    monkeypatch.setattr(insider, "fmp_get", lambda path, db=None: raw)
    assert len(insider.get_insider_quarterly_stats("AAPL")) == 8


def test_insider_quarterly_stats_fails_soft_on_budget(monkeypatch):
    from tools.fmp_client import FmpBudgetExceededError

    def boom(path, db=None):
        raise FmpBudgetExceededError("cap")

    monkeypatch.setattr(insider, "fmp_get", boom)
    assert insider.get_insider_quarterly_stats("AAPL") == []


def bo_filing(filer, filing_date, pct, shares="1000", type_="IA"):
    return {"nameOfReportingPerson": filer, "filingDate": filing_date,
            "percentOfClass": pct, "amountBeneficiallyOwned": shares,
            "typeOfReportingPerson": type_, "url": "https://sec.gov/x"}


def test_beneficial_ownership_fetch_normalizes_and_caches(db, monkeypatch):
    from tools.db import BENEFICIAL_OWNERSHIP_CACHE

    raw = [bo_filing("Capital Research", "2026-06-04", "11.1", "75279354")]
    monkeypatch.setattr(institutional, "fmp_get", lambda path, db=None: raw)

    out = institutional.get_beneficial_ownership("owl", db=db)

    assert out["stale"] is False
    f = out["filings"][0]
    assert f["filer"] == "Capital Research"
    assert f["shares"] == 75279354           # string → int
    assert f["pct_of_class"] == pytest.approx(11.1)   # string → float
    assert f["filer_type"] == "IA"
    assert db[BENEFICIAL_OWNERSHIP_CACHE].find_one({"ticker": "OWL"})["filings"] == raw


def test_beneficial_direction_accumulating_and_distributing():
    accumulating = [bo_filing("A", "2026-06-01", "12.0"), bo_filing("A", "2026-01-01", "9.0")]
    assert institutional.derive_beneficial_direction(
        institutional.normalize_beneficial_filings(accumulating)) == "accumulating"

    distributing = [bo_filing("A", "2026-06-01", "4.0"), bo_filing("A", "2026-01-01", "9.0")]
    assert institutional.derive_beneficial_direction(
        institutional.normalize_beneficial_filings(distributing)) == "distributing"


def test_beneficial_direction_is_none_without_a_repeat_filer():
    single = institutional.normalize_beneficial_filings([bo_filing("A", "2026-06-01", "12.0")])
    assert institutional.derive_beneficial_direction(single) is None


def test_beneficial_direction_mixed_on_a_tie():
    filings = institutional.normalize_beneficial_filings([
        bo_filing("A", "2026-06-01", "12.0"), bo_filing("A", "2026-01-01", "9.0"),
        bo_filing("B", "2026-06-01", "4.0"), bo_filing("B", "2026-01-01", "9.0"),
    ])
    assert institutional.derive_beneficial_direction(filings) == "mixed"


def test_beneficial_ownership_serves_cache_when_fetch_fails(db, monkeypatch):
    import requests as _requests
    from tools.db import BENEFICIAL_OWNERSHIP_CACHE

    db[BENEFICIAL_OWNERSHIP_CACHE].insert_one({
        "ticker": "OWL",
        "filings": [bo_filing("Cached Filer", "2026-05-01", "7.5")],
        "fetched_at": datetime.now(timezone.utc),
    })

    def boom(path, db=None):
        raise _requests.HTTPError("502")

    monkeypatch.setattr(institutional, "fmp_get", boom)

    out = institutional.get_beneficial_ownership("OWL", db=db)
    assert out["stale"] is True
    assert out["filings"][0]["filer"] == "Cached Filer"
