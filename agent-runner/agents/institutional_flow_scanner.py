"""Market-wide 13F/superinvestor scan, scored by notability.

Spec: specs/component-specs/agent-runner/agents/institutional_flow_scanner.md — implement per its build phase.
"""


def build_agent(tools: list | None = None):
    """Return the configured CrewAI Agent for InstitutionalFlowScanner."""
    raise NotImplementedError("institutional_flow_scanner: see spec")
