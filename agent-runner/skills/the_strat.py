"""Pluggable analytical engine. Rule system: specs/the-strat-spec.md — implement in Phase 2.

Pure functions only — no LLM calls inside skills.
"""


def run(ticker: str, data: dict) -> dict:
    """Standard skill interface: pre-fetched inputs in, structured dict out."""
    raise NotImplementedError("skills/the_strat.py: see specs/the-strat-spec.md")
