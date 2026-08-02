"""Pluggable analytical engine. Rule system: specs/market_flow_rules.md — implement in Phase 2.

Pure functions only — no LLM calls inside skills.
"""


def run(ticker: str, data: dict) -> dict:
    """Standard skill interface: pre-fetched inputs in, structured dict out."""
    raise NotImplementedError("skills/market_flow.py: see specs/market_flow_rules.md")
