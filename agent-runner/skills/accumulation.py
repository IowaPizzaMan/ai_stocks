"""Pluggable analytical engine. Rule system: specs/accumulation_volume_rules.md — implement in Phase 2.

Pure functions only — no LLM calls inside skills.
"""


def run(ticker: str, data: dict) -> dict:
    """Standard skill interface: pre-fetched inputs in, structured dict out."""
    raise NotImplementedError("skills/accumulation.py: see specs/accumulation_volume_rules.md")
