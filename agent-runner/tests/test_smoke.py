"""Scaffold smoke test: every package imports and stubs raise NotImplementedError."""
import importlib

import pytest

MODULES = [
    "settings",
    "crew",
    "queue_worker",
    "institutional_flow_worker",
    "agents.technical_analyst",
    "tools.breadth",
    "skills.market_flow",
    "chunker.chunker",
]


@pytest.mark.parametrize("mod", MODULES)
def test_imports(mod):
    importlib.import_module(mod)


def test_skill_interface_is_stubbed():
    from skills import position_management

    with pytest.raises(NotImplementedError):
        position_management.run("SPY", {})
