"""Spec: specs/component-specs/agent-runner/tools/db.md — implement per its build phase."""


def query_db(collection: str, filter: dict):
    raise NotImplementedError("tools/db.py: see spec")

def write_db(collection: str, data: dict):
    raise NotImplementedError("tools/db.py: see spec")

def register_ticker(ticker: str, source: str):
    raise NotImplementedError("tools/db.py: see spec")

def mark_ticker_removed(ticker: str):
    raise NotImplementedError("tools/db.py: see spec")
