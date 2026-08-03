"""Reusable, cloud-swappable logging setup. Spec: specs/SPEC.md
'Exception Handling & Logging'.

get_logger() is the single choke point for where this service's logs go.
Today that's a rotating file under logs/<component>/ plus stderr. Moving to
a cloud logging backend later means changing the handlers registered in
_configure_component() -- call sites (`logger.info(...)`, `logger.exception(...)`)
never change.

Scripts outside this service (scripts/*.py) import this module too but pass
their own `component="scripts"` so their crashes land in logs/scripts/
instead of logs/agent-runner/.
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler

COMPONENT = "agent-runner"

# One level up from this file. In Docker, WORKDIR is /app (this file's dir),
# so logs land at /logs -- bind-mounted to ./logs on the host. Locally, this
# file lives in <repo>/agent-runner, so logs land at <repo>/logs.
_LOG_ROOT = os.environ.get(
    "LOG_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
)

_configured: set[str] = set()


def _configure_component(component: str) -> None:
    if component in _configured:
        return

    log_dir = os.path.join(_LOG_ROOT, component)
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, f"{component}.log"),
        when="midnight", backupCount=14, encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    component_logger = logging.getLogger(component)
    component_logger.setLevel(logging.INFO)
    component_logger.addHandler(file_handler)
    component_logger.addHandler(stream_handler)
    component_logger.propagate = False

    _configured.add(component)


def get_logger(name: str, component: str = COMPONENT) -> logging.Logger:
    """Logger writing to logs/<component>/<component>.log (rotated daily,
    14-day retention) plus stderr. Pass `name` as `__name__` from the calling
    module; `component` only needs overriding by callers outside this
    service (see scripts/*.py)."""
    _configure_component(component)
    if not name or name == "__main__":
        return logging.getLogger(component)
    return logging.getLogger(f"{component}.{name}")
