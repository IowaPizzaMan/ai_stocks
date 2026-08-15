"""Unit tests for the earnings scanner agent + scan worker — offline."""
import mongomock
import pytest

import earnings_scan_worker
from agents import earnings_scanner as scanner
from tools.db import EARNINGS_SCANS


@pytest.fixture
def db():
    return mongomock.MongoClient()["scanner_test"]


def enriched(**overrides):
    base = {
        "ticker": "TST", "company": "Test Co", "report_date": "2026-08-05",
        "report_time": "amc", "sector": "Technology", "market_cap": 1e9,
        "eps_estimate": 1.0, "revenue_estimate": 1e9,
        "avg_abs_move_pct": 7.5, "beat_rate": 0.75, "history_quarters": 8,
        "eps_revision": "flat", "insider_signal": "none", "accumulation_score": 0,
    }
    return {**base, **overrides}


# --- deterministic scoring -----------------------------------------------------

def test_score_max_candidate():
    score, breakdown = scanner.score_candidate(enriched(
        avg_abs_move_pct=20.0, beat_rate=1.0, eps_revision="up",
        insider_signal="cluster", accumulation_score=5))
    assert score == 100
    assert breakdown == {"move_pts": 25.0, "beat_pts": 20.0, "revision_pts": 20,
                         "insider_pts": 20, "accumulation_pts": 15.0}


def test_score_zero_candidate():
    score, breakdown = scanner.score_candidate(enriched(
        avg_abs_move_pct=0, beat_rate=0, eps_revision="down",
        insider_signal="none", accumulation_score=0))
    assert score == 0


def test_score_mid_candidate_move_capped_at_15pct():
    # 7.5% move → half of 25; 15%+ would max out
    score, breakdown = scanner.score_candidate(enriched())
    assert breakdown["move_pts"] == 12.5
    assert breakdown["beat_pts"] == 15.0
    assert breakdown["revision_pts"] == 10
    assert score == round(12.5 + 15.0 + 10 + 0 + 0)


# --- signal derivation -----------------------------------------------------------

def test_insider_signal_levels():
    assert scanner._insider_signal({"cluster_signal": {"detected": True}}) == "cluster"
    assert scanner._insider_signal({
        "cluster_signal": {"detected": False},
        "transactions": [{"transaction_type": "purchase", "is_open_market": True}],
    }) == "single"
    assert scanner._insider_signal({
        "cluster_signal": {"detected": False},
        "transactions": [{"transaction_type": "sale", "is_open_market": True},
                         {"transaction_type": "purchase", "is_open_market": False}],
    }) == "none"


def test_eps_revision_direction(monkeypatch):
    grades = [{"action": "upgrade"}, {"action": "upgrade"}, {"action": "maintain"},
              {"action": "downgrade"}]
    monkeypatch.setattr(scanner, "fmp_get", lambda path: grades)
    assert scanner._eps_revision_direction("TST") == "up"


def test_eps_revision_direction_degrades_to_flat(monkeypatch):
    def _raise(path):
        raise RuntimeError("nope")

    monkeypatch.setattr(scanner, "fmp_get", _raise)
    assert scanner._eps_revision_direction("TST") == "flat"


# --- run_scan --------------------------------------------------------------------

CALENDAR = [
    {"ticker": "BIG", "company": "Big", "report_date": "2026-08-04", "report_time": "bmo",
     "eps_estimate": 1.0, "revenue_estimate": 1e9, "market_cap": 50e9, "sector": "Tech"},
    {"ticker": "MID", "company": "Mid", "report_date": "2026-08-05", "report_time": "amc",
     "eps_estimate": 0.5, "revenue_estimate": 5e8, "market_cap": 5e9, "sector": "Energy"},
    {"ticker": "SML", "company": "Small", "report_date": "2026-08-06", "report_time": "amc",
     "eps_estimate": 0.1, "revenue_estimate": 1e8, "market_cap": 6e8, "sector": "Retail"},
]

ENRICHMENT = {
    # MID should outrank BIG despite smaller cap
    "BIG": {"avg_abs_move_pct": 3.0, "beat_rate": 0.5, "eps_revision": "flat",
            "insider_signal": "none", "accumulation_score": 0},
    "MID": {"avg_abs_move_pct": 12.0, "beat_rate": 1.0, "eps_revision": "up",
            "insider_signal": "cluster", "accumulation_score": 4},
}


@pytest.fixture
def scan_fakes(monkeypatch):
    monkeypatch.setattr(scanner.calendar_tool, "get_earnings_calendar",
                        lambda days_ahead, db=None: CALENDAR)
    monkeypatch.setattr(scanner, "MAX_CANDIDATES", 2)  # SML falls off the cap cut

    def fake_fetch(candidate, db=None):
        extra = ENRICHMENT[candidate["ticker"]]
        return {**candidate, "history_quarters": 8, **extra}

    monkeypatch.setattr(scanner, "_fetch_candidate_data", fake_fetch)


def test_run_scan_ranks_and_writes_llm_theses(scan_fakes, monkeypatch):
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {
        "theses": [{"ticker": "MID", "one_line_thesis": "MID: monster mover"},
                   {"ticker": "BIG", "one_line_thesis": "BIG: steady"}]})

    out = scanner.run_scan(days_ahead=7)

    assert out["total_screened"] == 3
    assert out["scored_count"] == 2
    assert [c["ticker"] for c in out["candidates"]] == ["MID", "BIG"]
    mid = out["candidates"][0]
    assert mid["score"] == 92  # move 20 + beat 20 + revision 20 + insider 20 + accum 12
    assert mid["one_line_thesis"] == "MID: monster mover"
    assert mid["score_breakdown"]["insider_pts"] == 20


def test_run_scan_survives_llm_failure_with_fallback_theses(scan_fakes, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(scanner, "generate_json", boom)
    out = scanner.run_scan(days_ahead=7)
    assert out["scored_count"] == 2
    assert "12.0% avg move" in out["candidates"][0]["one_line_thesis"]


def test_run_scan_drops_failed_candidates(scan_fakes, monkeypatch):
    def flaky_fetch(candidate, db=None):
        if candidate["ticker"] == "BIG":
            raise RuntimeError("api down")
        return {**candidate, "history_quarters": 8, **ENRICHMENT[candidate["ticker"]]}

    monkeypatch.setattr(scanner, "_fetch_candidate_data", flaky_fetch)
    monkeypatch.setattr(scanner, "generate_json", lambda *a, **kw: {"theses": []})

    out = scanner.run_scan(days_ahead=7)
    assert [c["ticker"] for c in out["candidates"]] == ["MID"]


# --- scan worker -------------------------------------------------------------------

def test_worker_no_pending_scan_returns_false(db):
    assert earnings_scan_worker.claim_and_run_next_scan(db=db) is False


def test_worker_completes_pending_scan(db):
    db[EARNINGS_SCANS].insert_one({"scan_id": "abc", "status": "pending", "days_ahead": 3})

    def fake_run(days_ahead, db=None):
        assert days_ahead == 3
        return {"candidates": [{"ticker": "MID"}], "total_screened": 5,
                "scored_count": 1, "top_count": 1}

    assert earnings_scan_worker.claim_and_run_next_scan(db=db, run_scan=fake_run) is True
    doc = db[EARNINGS_SCANS].find_one({"scan_id": "abc"})
    assert doc["status"] == "complete"
    assert doc["candidates"] == [{"ticker": "MID"}]
    assert doc["total_screened"] == 5
    assert doc["started_at"] and doc["completed_at"]


def test_worker_marks_failed_scan(db):
    db[EARNINGS_SCANS].insert_one({"scan_id": "bad", "status": "pending", "days_ahead": 7})

    def broken_run(days_ahead, db=None):
        raise RuntimeError("universe fetch died")

    assert earnings_scan_worker.claim_and_run_next_scan(db=db, run_scan=broken_run) is True
    doc = db[EARNINGS_SCANS].find_one({"scan_id": "bad"})
    assert doc["status"] == "failed"
    assert "universe fetch died" in doc["error"]
