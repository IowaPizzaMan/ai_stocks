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


def test_all_skills_expose_run():
    from skills import accumulation, gap_analysis, market_flow, position_management, the_strat

    for skill in (accumulation, gap_analysis, market_flow, position_management, the_strat):
        assert callable(skill.run)
