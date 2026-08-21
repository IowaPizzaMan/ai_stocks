"""Unit tests for tools/insider.py counts/summary and
tools/institutional.py's feed-flag direction — no network."""
import mongomock
import pytest

import tools.insider as insider
from tools.insider import get_insider_activity, summarize_counts
from tools.institutional import recent_activity_direction


def fake_finnhub(transactions):
    def _get(path, **kwargs):
        if path == "stock/insider-transactions":
            return {"data": transactions}
        return {"data": []}  # insider-sentiment
    return _get


@pytest.fixture
def db():
    # 024 — insider transactions are stored between pulls, so these need a db.
    return mongomock.MongoClient()["insider_test"]


def txn(code, change, price=10.0, name="A Insider", date="2026-07-01"):
    return {"transactionCode": code, "change": change, "transactionPrice": price,
            "name": name, "transactionDate": date, "filingDate": date}


def test_open_market_counts_and_summary(monkeypatch, db):
    monkeypatch.setattr(insider, "finnhub_get", fake_finnhub([
        txn("P", 100), txn("P", 50, name="B Insider"), txn("S", -30),
        txn("M", 200),  # option exercise — not open market, must not count
    ]))
    result = get_insider_activity("AAPL", db=db)
    assert result["open_market_buy_count"] == 2
    assert result["open_market_sell_count"] == 1
    assert result["recent_summary"] == "2 buys, 1 sell"


def test_no_transactions_yields_no_summary(monkeypatch, db):
    monkeypatch.setattr(insider, "finnhub_get", fake_finnhub([]))
    result = get_insider_activity("AAPL", db=db)
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


# --- delta window (024 US4) ---------------------------------------------------

from datetime import date, timedelta  # noqa: E402


def _stored(db, ticker, transactions):
    db[insider.INSIDER_CACHE].insert_one(
        {"ticker": ticker, "transactions": transactions})


def test_delta_request_starts_from_the_newest_stored_event(monkeypatch, db):
    recent = (date.today() - timedelta(days=5)).isoformat()
    _stored(db, "AAPL", insider._normalize([txn("P", 100, date=recent)]))

    seen = {}

    def spy(path, **kwargs):
        seen.setdefault(path, kwargs)
        return {"data": []}

    monkeypatch.setattr(insider, "finnhub_get", spy)
    get_insider_activity("AAPL", db=db)

    expected = (date.today() - timedelta(days=6)).isoformat()  # newest minus 1d overlap
    assert seen["stock/insider-transactions"]["from"] == expected


def test_no_stored_events_uses_the_full_lookback(monkeypatch, db):
    seen = {}

    def spy(path, **kwargs):
        seen.setdefault(path, kwargs)
        return {"data": []}

    monkeypatch.setattr(insider, "finnhub_get", spy)
    get_insider_activity("COLD", db=db)

    expected = (date.today() - timedelta(days=insider.LOOKBACK_DAYS)).isoformat()
    assert seen["stock/insider-transactions"]["from"] == expected


def test_rebuild_ignores_the_stored_baseline(monkeypatch, db):
    recent = (date.today() - timedelta(days=5)).isoformat()
    _stored(db, "AAPL", insider._normalize([txn("P", 100, date=recent)]))

    seen = {}

    def spy(path, **kwargs):
        seen.setdefault(path, kwargs)
        return {"data": []}

    monkeypatch.setattr(insider, "finnhub_get", spy)
    get_insider_activity("AAPL", db=db, rebuild=True)

    expected = (date.today() - timedelta(days=insider.LOOKBACK_DAYS)).isoformat()
    assert seen["stock/insider-transactions"]["from"] == expected


def test_stored_and_fetched_transactions_are_merged(monkeypatch, db):
    old = (date.today() - timedelta(days=10)).isoformat()
    new = (date.today() - timedelta(days=1)).isoformat()
    _stored(db, "AAPL", insider._normalize([txn("P", 100, date=old)]))

    monkeypatch.setattr(insider, "finnhub_get",
                        fake_finnhub([txn("S", -50, date=new)]))
    out = get_insider_activity("AAPL", db=db)

    assert len(out["transactions"]) == 2
    assert out["transactions"][0]["date"] == new     # newest first


def test_the_overlap_day_is_not_duplicated(monkeypatch, db):
    """The deliberate one-day back-off must not double-count a filing."""
    day = (date.today() - timedelta(days=3)).isoformat()
    same = txn("P", 100, date=day)
    _stored(db, "AAPL", insider._normalize([same]))

    monkeypatch.setattr(insider, "finnhub_get", fake_finnhub([same]))
    out = get_insider_activity("AAPL", db=db)

    assert len(out["transactions"]) == 1


def test_an_amended_filing_replaces_its_predecessor(monkeypatch, db):
    """FR-019 — a corrected filing updates rather than duplicating."""
    day = (date.today() - timedelta(days=3)).isoformat()
    original = txn("P", 100, price=10.0, date=day)
    _stored(db, "AAPL", insider._normalize([original]))

    amended = txn("P", 100, price=12.5, date=day)
    monkeypatch.setattr(insider, "finnhub_get", fake_finnhub([amended]))
    out = get_insider_activity("AAPL", db=db)

    assert len(out["transactions"]) == 1
    assert out["transactions"][0]["price_per_share"] == 12.5


def test_events_older_than_the_lookback_are_trimmed(monkeypatch, db):
    ancient = (date.today() - timedelta(days=400)).isoformat()
    _stored(db, "AAPL", insider._normalize([txn("P", 100, date=ancient)]))

    monkeypatch.setattr(insider, "finnhub_get", fake_finnhub([]))
    out = get_insider_activity("AAPL", db=db)

    assert out["transactions"] == []


def test_provider_failure_serves_stored_transactions(monkeypatch, db):
    """US4 scenario 3 — a feed this plan doesn't cover degrades to what we hold
    and the rest of the pull proceeds."""
    day = (date.today() - timedelta(days=2)).isoformat()
    _stored(db, "AAPL", insider._normalize([txn("P", 100, date=day)]))

    def boom(path, **kwargs):
        raise RuntimeError("not entitled")

    monkeypatch.setattr(insider, "finnhub_get", boom)
    out = get_insider_activity("AAPL", db=db)

    assert len(out["transactions"]) == 1
    assert out["mspr_monthly"] == []


def test_stage_is_marked_incremental_when_a_baseline_exists(monkeypatch, db):
    """FR-002 — same instrumentation gap as news."""
    from tools import metrics
    recent = (date.today() - timedelta(days=5)).isoformat()
    _stored(db, "AAPL", insider._normalize([txn("P", 100, date=recent)]))
    monkeypatch.setattr(insider, "finnhub_get", fake_finnhub([]))

    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("insider", recorder):
        get_insider_activity("AAPL", db=db)

    assert recorder.stages()[0]["retrieval"] == metrics.INCREMENTAL


def test_stage_is_marked_degraded_when_the_provider_fails(monkeypatch, db):
    from tools import metrics
    day = (date.today() - timedelta(days=2)).isoformat()
    _stored(db, "AAPL", insider._normalize([txn("P", 100, date=day)]))

    def boom(path, **kwargs):
        raise RuntimeError("not entitled")

    monkeypatch.setattr(insider, "finnhub_get", boom)

    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("insider", recorder):
        get_insider_activity("AAPL", db=db)

    assert recorder.stages()[0]["outcome"] == metrics.DEGRADED
