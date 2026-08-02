"""Assembles and kicks off the CrewAI crew per ticker.

Spec: specs/component-specs/agent-runner/crew.md — implement in Phase 3.
Includes the parallel data prefetch (ThreadPoolExecutor) used by earnings handoffs.
"""


class TickerDelistedError(Exception):
    """Raised when a ticker fails the yfinance existence check AND has no financials."""


def run_crew(ticker: str, parallel_prefetch: bool = False) -> dict:
    """Run the full multi-agent pipeline for one ticker; returns the synthesis document."""
    raise NotImplementedError("crew: Phase 3")
