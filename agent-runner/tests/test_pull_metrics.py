"""Pull-cost recording across a crew run.
Spec: specs/024-delta-data-pulls (US1, FR-001..FR-005).

Reuses test_crew's fully-faked Crew (no network, no LLM) — this file is about
what gets *measured* during a pull, not what the pull computes.
"""
import mongomock
import pytest

import queue_worker
from tests.test_crew import make_crew
from tools import metrics
from tools.db import ANALYSES, PULL_METRICS, WORK_QUEUE

# every stage Crew._prefetch dispatches
EXPECTED_STAGES = {
    "price", "indicators", "financials", "earnings", "breadth", "insider",
    "insider_stats", "institutional", "beneficial", "sentiment", "news",
}


def test_run_records_one_stage_per_prefetch_job():
    crew = make_crew()
    crew.run("aapl")

    recorded = {s["name"] for s in crew.last_pull["stages"]}
    assert recorded == EXPECTED_STAGES


def test_stage_elapsed_never_exceeds_total_pull_time():
    """FR-004 — the breakdown must reconcile with wall clock, so unaccounted
    time is visible rather than hidden."""
    crew = make_crew()
    crew.run("aapl")

    pull = crew.last_pull
    accounted = sum(s["elapsed_ms"] for s in pull["stages"])
    assert accounted <= pull["total_ms"]
    assert pull["total_ms"] >= 0


def test_stages_are_ordered_most_expensive_first():
    """SC-006 — top three readable without re-sorting."""
    crew = make_crew()
    crew.run("aapl")

    elapsed = [s["elapsed_ms"] for s in crew.last_pull["stages"]]
    assert elapsed == sorted(elapsed, reverse=True)


def test_stage_with_no_provider_calls_reports_stored():
    """The faked fetchers make no HTTP calls, so a stage that declares nothing
    should infer 'stored' rather than claiming it fetched something (FR-002).

    `price` is the exception by design: it is the pull's one refreshing stage
    and reports whatever the store actually did.
    """
    crew = make_crew()
    crew.run("aapl")

    for stage in crew.last_pull["stages"]:
        assert stage["requests"] == 0
        assert stage["bytes"] == 0
        if stage["name"] == "price":
            continue
        assert stage["retrieval"] == metrics.STORED
        assert stage["outcome"] == metrics.STORED


def test_price_is_the_only_stage_that_refreshes():
    """FR-014 / SC-003 — the duplicate full-history download this feature exists
    to remove. `indicators` must read from the store, not fetch again."""
    crew = make_crew()
    crew.run("aapl")

    assert crew.refreshes == ["delta"]          # exactly one refresh per pull

    by_name = {s["name"]: s for s in crew.last_pull["stages"]}
    assert by_name["price"]["retrieval"] == metrics.INCREMENTAL
    assert by_name["indicators"]["retrieval"] == metrics.STORED
    assert by_name["indicators"]["requests"] == 0


def test_full_mode_refreshes_the_series_in_full():
    crew = make_crew()
    crew.run("aapl", mode="full")
    assert crew.refreshes == ["full"]


def test_degraded_stage_is_never_reported_as_fetched():
    """FR-002 — a fail-soft handler that served stale data must say so, even
    though it spent a request trying."""
    crew = make_crew()

    def degrading_news(t, db=None, rebuild=False):
        stage = metrics.current_stage()
        metrics.record_call(1234)          # the attempt that failed
        stage.mark(retrieval=metrics.INCREMENTAL, outcome=metrics.DEGRADED)
        return {"articles": [], "timeline": [], "trend": "mixed",
                "news_count": 0, "as_of": None, "stale": True}

    crew.get_stock_news = degrading_news
    crew.run("aapl")

    news = next(s for s in crew.last_pull["stages"] if s["name"] == "news")
    assert news["outcome"] == metrics.DEGRADED
    assert news["retrieval"] == metrics.INCREMENTAL
    assert news["requests"] == 1
    assert news["bytes"] == 1234


def test_mode_defaults_to_delta_and_is_recorded():
    crew = make_crew()
    crew.run("aapl")
    assert crew.last_pull["mode"] == "delta"


def test_parallel_prefetch_still_attributes_every_stage():
    """research D7 — the pool path is the one a contextvars implementation would
    silently drop, and it is the path earnings-scan pulls take."""
    crew = make_crew()
    crew.run("aapl", parallel_prefetch=True)

    recorded = {s["name"] for s in crew.last_pull["stages"]}
    assert recorded == EXPECTED_STAGES


def test_metrics_do_not_leak_between_runs():
    crew = make_crew()
    crew.run("aapl")
    first = len(crew.last_pull["stages"])
    crew.run("aapl")
    assert len(crew.last_pull["stages"]) == first


# --- persistence (queue_worker) ------------------------------------------------


@pytest.fixture
def db():
    return mongomock.MongoClient()["pull_metrics_test"]


@pytest.fixture(autouse=True)
def reset_startup():
    queue_worker._started = False
    yield
    queue_worker._started = False


class MetricsCrew:
    """Crew stub that reports a pull-cost record the way the real one does."""

    def __init__(self, last_pull=None, error=None):
        self.last_pull = last_pull if last_pull is not None else {
            "mode": "delta",
            "total_ms": 100,
            "stages": [{"name": "price", "elapsed_ms": 60, "requests": 1,
                        "bytes": 2048, "retrieval": "incremental", "outcome": "fetched"}],
        }
        self.error = error

    def run(self, ticker, parallel_prefetch=False, mode="delta"):
        if self.error:
            raise self.error
        return {"ticker": ticker, "signal": "bullish", "conviction": "high"}


def _enqueue(db, ticker="AAPL"):
    from datetime import datetime, timezone
    db[WORK_QUEUE].insert_one({
        "ticker": ticker, "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })


def test_completed_job_persists_one_pull_metrics_document(db):
    _enqueue(db)
    queue_worker.claim_and_run_next(db=db, crew=MetricsCrew())

    docs = list(db[PULL_METRICS].find({}))
    assert len(docs) == 1
    assert docs[0]["ticker"] == "AAPL"
    assert docs[0]["outcome"] == "done"
    assert docs[0]["stages"][0]["name"] == "price"
    assert docs[0]["total_ms"] == 100
    assert "started_at" in docs[0] and "completed_at" in docs[0]


def test_metrics_write_failure_does_not_fail_the_job(db, monkeypatch):
    """FR-005 — measurement must never cost us the analysis."""
    _enqueue(db)

    def explode(*args, **kwargs):
        raise RuntimeError("metrics collection is on fire")

    monkeypatch.setattr(queue_worker, "_write_pull_metrics", explode)
    handled = queue_worker.claim_and_run_next(db=db, crew=MetricsCrew())

    assert handled is True
    assert db[WORK_QUEUE].find_one({})["status"] == "done"
    assert db[ANALYSES].find_one({"ticker": "AAPL"})["signal"] == "bullish"


def test_crew_without_metrics_support_is_tolerated(db):
    """Legacy/fake crews that expose no last_pull must not break the worker."""
    class BareCrew:
        def run(self, ticker, parallel_prefetch=False, mode="delta"):
            return {"ticker": ticker, "signal": "neutral", "conviction": "low"}

    _enqueue(db)
    assert queue_worker.claim_and_run_next(db=db, crew=BareCrew()) is True
    assert db[WORK_QUEUE].find_one({})["status"] == "done"
    assert db[PULL_METRICS].count_documents({}) == 0
