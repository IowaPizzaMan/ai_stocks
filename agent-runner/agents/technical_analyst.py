"""Price patterns, indicators, momentum, accumulation volume.

Spec: specs/component-specs/agent-runner/agents/technical_analyst.md — implement per its build phase.
"""


def build_agent(tools: list | None = None):
    """Return the configured CrewAI Agent for TechnicalAnalyst."""
    raise NotImplementedError("technical_analyst: see spec")
