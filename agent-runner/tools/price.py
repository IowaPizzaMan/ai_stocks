"""Spec: specs/component-specs/agent-runner/tools/price.md — implement per its build phase."""


def get_price_history(ticker: str, period: str = '1y'):
    raise NotImplementedError("tools/price.py: see spec")

def get_technical_indicators(ticker: str):
    raise NotImplementedError("tools/price.py: see spec")

def is_ticker_valid(ticker: str):
    raise NotImplementedError("tools/price.py: see spec")
