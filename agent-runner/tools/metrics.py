"""Per-stage provider-cost attribution for a pull.
Spec: specs/024-delta-data-pulls (US1, FR-001..FR-005); research D7.

Deliberately `threading.local`, NOT `contextvars`. `Crew._prefetch` runs its
stages either sequentially or inside a `ThreadPoolExecutor`, and
`ThreadPoolExecutor` does not propagate contextvars into pool workers — a
contextvar-based recorder would silently record nothing on the parallel path,
which is exactly the path earnings-scan pulls use. A thread-local set *inside*
each stage's callable is correct in both modes, because a pool worker runs one
stage at a time on its own thread.

Nothing here may ever fail a pull (FR-005): `record_call` is a no-op when no
stage is active, and the HTTP clients that call it swallow its errors.
"""
import time
from contextlib import contextmanager
from threading import Lock, local

from logging_config import get_logger

logger = get_logger(__name__)

_local = local()

# retrieval kinds (FR-002)
INCREMENTAL = "incremental"
FULL = "full"
STORED = "stored"

# stage outcomes (FR-002)
FETCHED = "fetched"
DEGRADED = "degraded"
SKIPPED = "skipped"
FAILED = "failed"


class StageRecord:
    """One dataset's retrieval within a pull. Mutated by the stage as it runs."""

    __slots__ = ("name", "elapsed_ms", "requests", "bytes", "retrieval", "outcome")

    def __init__(self, name: str):
        self.name = name
        self.elapsed_ms = 0
        self.requests = 0
        self.bytes = 0
        self.retrieval: str | None = None
        self.outcome: str | None = None

    def mark(self, retrieval: str | None = None, outcome: str | None = None) -> None:
        """Lets a stage declare what it actually did. Anything left unset is
        inferred on close from whether the stage spent any requests."""
        if retrieval is not None:
            self.retrieval = retrieval
        if outcome is not None:
            self.outcome = outcome

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "elapsed_ms": self.elapsed_ms,
            "requests": self.requests,
            "bytes": self.bytes,
            "retrieval": self.retrieval,
            "outcome": self.outcome,
        }


class PullRecorder:
    """Collects one pull's stage records. Thread-safe — stages may finish on
    different pool threads."""

    def __init__(self):
        self._stages: list[StageRecord] = []
        self._lock = Lock()

    def add(self, record: StageRecord) -> None:
        with self._lock:
            self._stages.append(record)

    def stages(self) -> list[dict]:
        """Finished stages as plain dicts, most expensive first (SC-006)."""
        with self._lock:
            return sorted(
                (s.to_dict() for s in self._stages),
                key=lambda s: s["elapsed_ms"],
                reverse=True,
            )

    def accounted_ms(self) -> int:
        with self._lock:
            return sum(s.elapsed_ms for s in self._stages)


def current_stage() -> StageRecord | None:
    """The stage active on this thread, or None outside any stage."""
    return getattr(_local, "stage", None)


def record_call(byte_count: int = 0) -> None:
    """Attributes one provider request to the active stage. A no-op when there
    is no active stage, so non-pull callers (routers, admin jobs, tests) need no
    special handling."""
    stage = current_stage()
    if stage is None:
        return
    stage.requests += 1
    stage.bytes += byte_count


@contextmanager
def stage_recorder(name: str, recorder: PullRecorder | None = None):
    """Times a pull stage and attributes every provider call made on this thread
    to it.

    Always finalizes and hands the record to `recorder`, including when the body
    raises — a stage that blew up is the most interesting one to see in the
    breakdown, so losing its record would defeat the point. The exception is
    re-raised unchanged; this wrapper never changes control flow (FR-005).
    """
    record = StageRecord(name)
    previous = current_stage()
    _local.stage = record
    started = time.monotonic()
    try:
        yield record
    except BaseException:
        record.mark(outcome=FAILED)
        raise
    finally:
        record.elapsed_ms = int((time.monotonic() - started) * 1000)
        # Infer whatever the stage did not declare: spending requests means it
        # went to the provider; spending none means it was served from storage.
        if record.outcome is None:
            record.outcome = FETCHED if record.requests else STORED
        if record.retrieval is None:
            record.retrieval = FULL if record.requests else STORED
        _local.stage = previous
        if recorder is not None:
            recorder.add(record)
