"""Pluggable analytical engine. Rule system: specs/position_management_agent_spec.md — implement in Phase 2.

Pure functions only — no LLM calls inside skills.
"""


def run(ticker: str, data: dict) -> dict:
    """Standard skill interface: pre-fetched inputs in, structured dict out."""
    raise NotImplementedError("skills/position_management.py: see specs/position_management_agent_spec.md")
