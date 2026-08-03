"""Unit tests for logging_config.py — the reusable, cloud-swappable logger.
Spec: specs/SPEC.md 'Exception Handling & Logging'."""
import logging

import pytest

import logging_config


@pytest.fixture(autouse=True)
def isolated_log_root(tmp_path, monkeypatch):
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


def test_default_component_is_backend():
    logger = logging_config.get_logger(__name__)
    assert logger.name == f"backend.{__name__}"
