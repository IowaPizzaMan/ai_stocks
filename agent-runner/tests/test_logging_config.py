"""Unit tests for logging_config.py — the reusable, cloud-swappable logger.
Spec: specs/SPEC.md 'Exception Handling & Logging'."""
import logging

import pytest

import logging_config


@pytest.fixture(autouse=True)
def isolated_log_root(tmp_path, monkeypatch):
    """Point at a scratch dir and forget prior configuration so each test
    gets a fresh file, then tear down the handlers we attached."""
    monkeypatch.setattr(logging_config, "_LOG_ROOT", str(tmp_path))
    logging_config._configured.clear()
    yield
    for component in list(logging_config._configured):
        component_logger = logging.getLogger(component)
        for handler in component_logger.handlers[:]:
            handler.close()
            component_logger.removeHandler(handler)
    logging_config._configured.clear()


def test_get_logger_writes_to_component_log_file(tmp_path):
    logger = logging_config.get_logger(__name__, component="widgets")
    logger.info("hello from test")

    log_file = tmp_path / "widgets" / "widgets.log"
    assert log_file.exists()
    assert "hello from test" in log_file.read_text(encoding="utf-8")


def test_get_logger_namespaces_module_names_under_component():
    logger = logging_config.get_logger("tools.institutional", component="widgets")
    assert logger.name == "widgets.tools.institutional"


def test_get_logger_collapses_dunder_main_to_bare_component_name():
    logger = logging_config.get_logger("__main__", component="widgets")
    assert logger.name == "widgets"


def test_default_component_is_agent_runner():
    logger = logging_config.get_logger(__name__)
    assert logger.name == f"agent-runner.{__name__}"


def test_reconfiguring_same_component_does_not_duplicate_handlers():
    from logging.handlers import TimedRotatingFileHandler

    logging_config.get_logger(__name__, component="widgets")
    logging_config.get_logger("other_module", component="widgets")

    # Count exact types, not isinstance: pytest's own log-capture handler is
    # a StreamHandler subclass and would otherwise be mistaken for ours.
    handlers = logging.getLogger("widgets").handlers
    assert sum(isinstance(h, TimedRotatingFileHandler) for h in handlers) == 1
    assert sum(type(h) is logging.StreamHandler for h in handlers) == 1
