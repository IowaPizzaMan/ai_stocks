"""Spec: specs/component-specs/agent-runner/tools/institutional.md — implement per its build phase."""


def get_institutional_holdings(ticker: str):
    raise NotImplementedError("tools/institutional.py: see spec")

def get_recent_13f_changes(since, universe=None):
    raise NotImplementedError("tools/institutional.py: see spec")
