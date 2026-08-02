"""Unit tests for the flow scanner agent + daily worker — mongomock, no network."""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

import institutional_flow_worker as worker
from agents import institutional_flow_scanner as scanner
from tools.db import INSTITUTIONAL_FLOW, INSTITUTIONAL_FLOW_META, TICKER_INDEX, WORK_QUEUE

NOW = datetime(2026, 8, 2, 23, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    return mongomock.MongoClient()["flow_test"]


def dataroma_move(**overrides):
    return {**{"fund": "Pershing Square", "action": "new_position",
               "ticker": "GOOGL", "detail": "8.4% of portfolio"}, **overrides}


def filing_row(**overrides):
    return {**{"ticker": "OXY", "Holder": "Berkshire Hathaway Inc",
               "Shares": 2_000_000, "Value": 130_000_000, "pctChange": 0.21,
               "Date Reported": "2026-06-30"}, **overrides}


# --- agent: classification -----------------------------------------------------

def test_dataroma_action_mapping(monkeypatch):
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {"headlines": []})
    moves = [dataroma_move(action=a, ticker=f"T{i}")
             for i, a in enumerate(["buy", "sell", "new_position", "exit", "add", "trim"])]
    events = scanner.run(moves, [], now=NOW)
    actions = {e["ticker"]: e["action"] for e in events}
    assert actions == {"T0": "add", "T1": "trim", "T2": "new_position",
                       "T3": "exit", "T4": "add", "T5": "trim"}


def test_junk_tickers_and_unknown_actions_dropped(monkeypatch):
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {"headlines": []})
    moves = [dataroma_move(ticker="not a ticker"),
             dataroma_move(action="hold"),
             dataroma_move(fund="")]
    assert scanner.run(moves, [], now=NOW) == []


def test_filing_action_from_pct_change(monkeypatch):
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {"headlines": []})
    rows = [filing_row(pctChange=0.3, ticker="ADD"),
            filing_row(pctChange=-0.12, ticker="TRIM"),
            filing_row(pctChange=-0.97, ticker="GONE"),
            filing_row(pctChange=0, ticker="FLAT"),
            filing_row(pctChange=0.5, ticker="NODATE", **{"Date Reported": "bogus"})]
    events = scanner.run([], rows, now=NOW)
    actions = {e["ticker"]: e["action"] for e in events}
    assert actions == {"ADD": "add", "TRIM": "trim", "GONE": "exit"}
    add = next(e for e in events if e["ticker"] == "ADD")
    assert add["filed_at"] == datetime(2026, 6, 30, tzinfo=timezone.utc)
    assert add["shares"] == 2_000_000
    assert add["value_usd"] == 130_000_000.0


# --- agent: notability ----------------------------------------------------------

def test_superinvestor_outranks_passive_flow(monkeypatch):
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {"headlines": []})
    events = scanner.run(
        [dataroma_move()],  # superinvestor new position
        [filing_row(Holder="Vanguard Group Inc", pctChange=0.02, ticker="AAPL")],
        now=NOW)
    assert events[0]["source"] == "dataroma"
    assert events[0]["notability_score"] > events[1]["notability_score"]
    assert events[1]["notability_score"] <= 40  # passive add is noise


def test_high_conviction_13f_gets_boost(monkeypatch):
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {"headlines": []})
    events = scanner.run(
        [], [filing_row(Holder="Berkshire Hathaway Inc", pctChange=0.21),
             filing_row(Holder="Some Fund LP", pctChange=0.21, ticker="MSFT")],
        now=NOW)
    berkshire = next(e for e in events if e["fund"].startswith("Berkshire"))
    other = next(e for e in events if e["fund"].startswith("Some"))
    assert berkshire["notability_score"] == other["notability_score"] + 15


def test_scores_clamped_and_sorted(monkeypatch):
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {"headlines": []})
    events = scanner.run(
        [dataroma_move(action="new_position")],
        [filing_row(Holder="Vanguard Index Trust", pctChange=-0.01, ticker="LOW")],
        now=NOW)
    scores = [e["notability_score"] for e in events]
    assert scores == sorted(scores, reverse=True)
    assert all(5 <= s <= 99 for s in scores)


# --- agent: headlines -----------------------------------------------------------

def test_llm_headlines_applied_to_top_events(monkeypatch):
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {
        "headlines": [{"index": 0, "headline": "Pershing Square opened a new GOOGL stake"}]})
    events = scanner.run([dataroma_move()], [], now=NOW)
    assert events[0]["headline"] == "Pershing Square opened a new GOOGL stake"


def test_headline_falls_back_to_template_on_llm_failure(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(scanner, "generate_json", boom)
    events = scanner.run([dataroma_move()], [filing_row(pctChange=-0.12)], now=NOW)
    assert "opened a new position in GOOGL" in events[0]["headline"]
    trim = next(e for e in events if e["action"] == "trim")
    assert "trimmed its OXY stake by 12% QoQ" in trim["headline"]


# --- worker: scheduling ---------------------------------------------------------

def test_not_due_before_scan_hour(db):
    ran = []
    early = NOW.replace(hour=10)
    assert worker.run_daily_scan_if_due(early, db=db, scan=lambda **kw: ran.append(1)) is None
    assert ran == []


def test_due_after_scan_hour_once_per_day(db):
    calls = []

    def fake_scan(db=None, now=None):
        calls.append(now)
        worker._set_meta(db, "last_scan_at", now)
        return 0

    assert worker.run_daily_scan_if_due(NOW, db=db, scan=fake_scan) == 0
    # second tick same evening: already scanned today
    assert worker.run_daily_scan_if_due(NOW + timedelta(minutes=5), db=db, scan=fake_scan) is None
    # next evening: due again
    assert worker.run_daily_scan_if_due(NOW + timedelta(days=1), db=db, scan=fake_scan) == 0
    assert len(calls) == 2


def test_manual_request_runs_regardless_of_hour_and_is_consumed(db):
    db[INSTITUTIONAL_FLOW_META].insert_one({"key": "manual_scan_requested", "value": True})
    calls = []
    early = NOW.replace(hour=10)

    assert worker.run_daily_scan_if_due(
        early, db=db, scan=lambda **kw: calls.append(1) or 0) == 0
    assert db[INSTITUTIONAL_FLOW_META].find_one({"key": "manual_scan_requested"})["value"] is False
    # flag consumed — no re-run on the next tick
    assert worker.run_daily_scan_if_due(early, db=db, scan=lambda **kw: calls.append(1) or 0) is None
    assert calls == [1]


def test_failed_scan_leaves_last_scan_unchanged(db):
    def boom(**kw):
        raise RuntimeError("playwright exploded")

    assert worker.run_daily_scan_if_due(NOW, db=db, scan=boom) is None
    assert worker._get_meta(db, "last_scan_at") is None
    # still due on the next tick (scheduled path retries; window re-covered)
    ran = []

    def ok(db=None, now=None):
        ran.append(1)
        worker._set_meta(db, "last_scan_at", now)
        return 0

    assert worker.run_daily_scan_if_due(NOW + timedelta(minutes=1), db=db, scan=ok) == 0


# --- worker: run_scan pipeline ----------------------------------------------------

@pytest.fixture
def scan_fakes(monkeypatch):
    monkeypatch.setattr(worker.superinvestor_tool, "get_recent_superinvestor_moves",
                        lambda since, client=None: [dataroma_move()])
    monkeypatch.setattr(worker.institutional_tool, "get_recent_13f_changes",
                        lambda since, db=None: [filing_row()])
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {"headlines": []})


def test_run_scan_writes_events_and_enqueues(db, scan_fakes):
    written = worker.run_scan(db=db, now=NOW)

    assert written == 2
    docs = list(db[INSTITUTIONAL_FLOW].find({}))
    assert {d["ticker"] for d in docs} == {"GOOGL", "OXY"}
    def aware(dt):  # mongomock round-trips datetimes as naive UTC
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    assert all(aware(d["scanned_at"]) == NOW for d in docs)

    assert db[TICKER_INDEX].find_one({"ticker": "GOOGL"})["sources"] == ["institutional_flow"]
    assert db[WORK_QUEUE].count_documents({"status": "pending"}) == 2
    assert aware(worker._get_meta(db, "last_scan_at")) == NOW


def test_run_scan_dedups_repeat_events(db, scan_fakes):
    assert worker.run_scan(db=db, now=NOW) == 2
    # same moves re-scraped next day → nothing new
    assert worker.run_scan(db=db, now=NOW + timedelta(days=1)) == 0
    assert db[INSTITUTIONAL_FLOW].count_documents({}) == 2


def test_dataroma_dedup_survives_llm_rewording(db, scan_fakes, monkeypatch):
    """Re-extraction of the same page words fund/action differently — the
    fuzzy fund-name + action-insensitive match must still collapse it."""
    assert worker.run_scan(db=db, now=NOW) == 2
    monkeypatch.setattr(
        worker.superinvestor_tool, "get_recent_superinvestor_moves",
        lambda since, client=None: [dataroma_move(
            fund="Bill Ackman - Pershing Square Capital", action="buy")])
    monkeypatch.setattr(worker.institutional_tool, "get_recent_13f_changes",
                        lambda since, db=None: [])

    assert worker.run_scan(db=db, now=NOW + timedelta(days=1)) == 0
    assert db[INSTITUTIONAL_FLOW].count_documents({"source": "dataroma"}) == 1


def test_dataroma_dedup_within_one_batch(db, scan_fakes, monkeypatch):
    monkeypatch.setattr(
        worker.superinvestor_tool, "get_recent_superinvestor_moves",
        lambda since, client=None: [dataroma_move(),
                                    dataroma_move(fund="Pershing Square Capital", action="add")])
    monkeypatch.setattr(worker.institutional_tool, "get_recent_13f_changes",
                        lambda since, db=None: [])
    assert worker.run_scan(db=db, now=NOW) == 1


def test_dataroma_different_fund_or_ticker_not_deduped(db, scan_fakes, monkeypatch):
    assert worker.run_scan(db=db, now=NOW) == 2
    monkeypatch.setattr(
        worker.superinvestor_tool, "get_recent_superinvestor_moves",
        lambda since, client=None: [dataroma_move(fund="Baupost Group"),
                                    dataroma_move(ticker="MSFT")])
    monkeypatch.setattr(worker.institutional_tool, "get_recent_13f_changes",
                        lambda since, db=None: [])
    assert worker.run_scan(db=db, now=NOW + timedelta(days=1)) == 2


def test_run_scan_skips_delisted_and_already_queued(db, scan_fakes):
    db[TICKER_INDEX].insert_one({"ticker": "GOOGL", "status": "removed_from_market"})
    db[WORK_QUEUE].insert_one({"ticker": "OXY", "status": "pending",
                               "created_at": NOW, "updated_at": NOW})

    worker.run_scan(db=db, now=NOW)

    # delisted ticker: not resurrected, not enqueued
    assert db[TICKER_INDEX].find_one({"ticker": "GOOGL"})["status"] == "removed_from_market"
    assert db[WORK_QUEUE].count_documents({"ticker": "GOOGL"}) == 0
    # already-queued ticker: no duplicate job
    assert db[WORK_QUEUE].count_documents({"ticker": "OXY"}) == 1
