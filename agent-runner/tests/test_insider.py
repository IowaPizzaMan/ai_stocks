"""Unit tests for tools/insider.py counts/summary and
tools/institutional.py's feed-flag direction — no network."""
import tools.insider as insider
from tools.insider import get_insider_activity, summarize_counts
from tools.institutional import recent_activity_direction


def fake_finnhub(transactions):
    def _get(path, **kwargs):
        if path == "stock/insider-transactions":
            return {"data": transactions}
        return {"data": []}  # insider-sentiment
    return _get


def txn(code, change, price=10.0, name="A Insider", date="2026-07-01"):
    return {"transactionCode": code, "change": change, "transactionPrice": price,
            "name": name, "transactionDate": date, "filingDate": date}


def test_open_market_counts_and_summary(monkeypatch):
    monkeypatch.setattr(insider, "finnhub_get", fake_finnhub([
        txn("P", 100), txn("P", 50, name="B Insider"), txn("S", -30),
        txn("M", 200),  # option exercise — not open market, must not count
    ]))
    result = get_insider_activity("AAPL")
    assert result["open_market_buy_count"] == 2
    assert result["open_market_sell_count"] == 1
    assert result["recent_summary"] == "2 buys, 1 sell"


def test_no_transactions_yields_no_summary(monkeypatch):
    monkeypatch.setattr(insider, "finnhub_get", fake_finnhub([]))
    result = get_insider_activity("AAPL")
    assert result["open_market_buy_count"] == 0
    assert result["recent_summary"] is None


def test_summarize_counts_pluralization():
    assert summarize_counts(1, 1) == "1 buy, 1 sell"
    assert summarize_counts(10, 2) == "10 buys, 2 sells"
    assert summarize_counts(0, 3) == "0 buys, 3 sells"
    assert summarize_counts(0, 0) is None


def test_recent_activity_direction():
    assert recent_activity_direction({"top10_increasing": 6, "top10_decreasing": 2}) == "buying"
    assert recent_activity_direction({"top10_increasing": 1, "top10_decreasing": 4}) == "selling"
    assert recent_activity_direction({"top10_increasing": 3, "top10_decreasing": 3}) == "mixed"
    assert recent_activity_direction({"top10_increasing": 0, "top10_decreasing": 0}) is None
    assert recent_activity_direction({}) is None
    assert recent_activity_direction({"top10_increasing": None, "top10_decreasing": None}) is None
