"""Unit tests for tools/metrics.py — per-stage provider-cost attribution.
Spec: specs/024-delta-data-pulls (US1, FR-001..FR-005); research D7.

The parallel test is the point of this file. `Crew._prefetch` runs stages inside
a ThreadPoolExecutor, and a contextvars-based recorder would pass the sequential
test and silently record nothing there — so both execution modes are asserted
explicitly rather than assumed equivalent.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from tools import metrics


def test_records_requests_and_bytes_for_the_active_stage():
    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("price", recorder):
        metrics.record_call(1000)
        metrics.record_call(500)

    stage = recorder.stages()[0]
    assert stage["name"] == "price"
    assert stage["requests"] == 2
    assert stage["bytes"] == 1500


def test_record_call_outside_any_stage_is_a_noop():
    """Routers, admin jobs and tests call the same clients without a pull around
    them — attribution must not require a stage to exist (FR-005)."""
    metrics.record_call(999)  # must not raise
    assert metrics.current_stage() is None


def test_stages_attribute_separately_when_run_sequentially():
    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("price", recorder):
        metrics.record_call(100)
    with metrics.stage_recorder("news", recorder):
        metrics.record_call(20)
        metrics.record_call(30)

    by_name = {s["name"]: s for s in recorder.stages()}
    assert by_name["price"]["requests"] == 1
    assert by_name["price"]["bytes"] == 100
    assert by_name["news"]["requests"] == 2
    assert by_name["news"]["bytes"] == 50


def test_stages_attribute_separately_under_thread_pool():
    """The research D7 regression guard: ThreadPoolExecutor does NOT propagate
    contextvars, so an implementation built on them records nothing here while
    still passing the sequential test above."""
    recorder = metrics.PullRecorder()

    def job(name: str, calls: int, size: int):
        with metrics.stage_recorder(name, recorder):
            for _ in range(calls):
                metrics.record_call(size)

    jobs = [("price", 1, 400), ("news", 3, 10), ("insider", 2, 25), ("earnings", 1, 5)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(job, *args) for args in jobs]
        for f in futures:
            f.result(timeout=10)

    by_name = {s["name"]: s for s in recorder.stages()}
    assert len(by_name) == 4
    assert by_name["price"] == {**by_name["price"], "requests": 1, "bytes": 400}
    assert by_name["news"]["requests"] == 3
    assert by_name["news"]["bytes"] == 30
    assert by_name["insider"]["requests"] == 2
    assert by_name["insider"]["bytes"] == 50
    assert by_name["earnings"]["requests"] == 1


def test_a_stage_does_not_capture_another_threads_calls():
    """Cross-contamination check — a thread with no stage active must not have
    its calls charged to a stage running on a different thread."""
    recorder = metrics.PullRecorder()
    started = []

    def unstaged():
        metrics.record_call(10_000)
        started.append(True)

    with metrics.stage_recorder("price", recorder):
        metrics.record_call(100)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(unstaged).result(timeout=10)

    assert started == [True]
    assert recorder.stages()[0]["bytes"] == 100


def test_exception_inside_a_stage_is_recorded_then_reraised():
    """A stage that blew up is the most interesting row in the breakdown, so the
    record must survive — and the wrapper must not change control flow."""
    recorder = metrics.PullRecorder()

    with pytest.raises(ValueError, match="boom"):
        with metrics.stage_recorder("news", recorder):
            metrics.record_call(50)
            raise ValueError("boom")

    stage = recorder.stages()[0]
    assert stage["name"] == "news"
    assert stage["outcome"] == metrics.FAILED
    assert stage["requests"] == 1


def test_stage_clears_itself_on_exit_even_after_failure():
    recorder = metrics.PullRecorder()
    with pytest.raises(ValueError):
        with metrics.stage_recorder("news", recorder):
            raise ValueError("boom")
    assert metrics.current_stage() is None


def test_outcome_and_retrieval_are_inferred_when_not_declared():
    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("price", recorder):
        metrics.record_call(10)
    with metrics.stage_recorder("indicators", recorder):
        pass  # served from the store, no provider calls

    by_name = {s["name"]: s for s in recorder.stages()}
    assert by_name["price"]["outcome"] == metrics.FETCHED
    assert by_name["price"]["retrieval"] == metrics.FULL
    assert by_name["indicators"]["outcome"] == metrics.STORED
    assert by_name["indicators"]["retrieval"] == metrics.STORED


def test_declared_outcome_wins_over_inference():
    """A fail-soft handler that served stale cache must be able to say so, even
    though it spent a request trying (FR-002)."""
    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("news", recorder) as stage:
        metrics.record_call(10)
        stage.mark(retrieval=metrics.INCREMENTAL, outcome=metrics.DEGRADED)

    stage = recorder.stages()[0]
    assert stage["outcome"] == metrics.DEGRADED
    assert stage["retrieval"] == metrics.INCREMENTAL


def test_stages_are_returned_most_expensive_first():
    """SC-006 — the operator reads the top three without sorting them by hand.

    Records are built directly rather than by sleeping: sub-millisecond sleeps are
    not reliably ordered on Windows, and the behavior under test is the sort, not
    the clock.
    """
    recorder = metrics.PullRecorder()
    for name, elapsed in (("fast", 1), ("slow", 900), ("medium", 40)):
        record = metrics.StageRecord(name)
        record.elapsed_ms = elapsed
        recorder.add(record)

    assert [s["name"] for s in recorder.stages()] == ["slow", "medium", "fast"]


def test_accounted_ms_sums_the_stages():
    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("a", recorder):
        pass
    with metrics.stage_recorder("b", recorder):
        pass
    assert recorder.accounted_ms() == sum(s["elapsed_ms"] for s in recorder.stages())


def test_nested_stages_restore_the_outer_stage():
    """Defensive: a tool that wraps its own sub-step must not orphan the caller's
    stage when it exits."""
    recorder = metrics.PullRecorder()
    with metrics.stage_recorder("outer", recorder) as outer:
        with metrics.stage_recorder("inner", recorder):
            metrics.record_call(5)
        assert metrics.current_stage() is outer
        metrics.record_call(7)

    by_name = {s["name"]: s for s in recorder.stages()}
    assert by_name["inner"]["bytes"] == 5
    assert by_name["outer"]["bytes"] == 7
