"""Claims jobs from work_queue, dispatches the crew, marks done/failed.

Spec: specs/component-specs/agent-runner/queue_worker.md — implement in Phase 3.
Includes delisting detection: on TickerDelistedError, mark the ticker
`removed_from_market` in ticker_index (and watchlist if present).
"""


def claim_and_run_next() -> bool:
    """Claim the oldest pending job and run it. Returns False when queue is empty."""
    raise NotImplementedError("queue_worker: Phase 3")
