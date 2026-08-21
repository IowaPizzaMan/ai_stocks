"""Shared Finnhub REST helper (free tier: 60 calls/min).

Calls are paced to stay under the per-minute cap — the earnings scan fires
dozens of insider lookups from a thread pool — and a 429 gets one
long-breath retry before failing.
"""
import threading
import time

import requests

from logging_config import get_logger
from settings import settings
from tools import metrics

logger = get_logger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1/"
MIN_CALL_INTERVAL = 1.05  # seconds — keeps sustained usage under 60/min
RETRY_AFTER_429 = 30.0

_lock = threading.Lock()
_last_call = 0.0


def _pace() -> None:
    global _last_call
    with _lock:
        wait = _last_call + MIN_CALL_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def finnhub_get(path: str, **params) -> dict | list:
    params["token"] = settings.finnhub_api_key
    for attempt in (0, 1):
        _pace()
        r = requests.get(f"{FINNHUB_BASE}{path}", params=params, timeout=20)
        # Attributed even on the 429 that gets retried — a throttled stage is
        # expensive in wall time and should say so in the breakdown (024).
        _record_metrics(r)
        if r.status_code == 429 and attempt == 0:
            time.sleep(RETRY_AFTER_429)
            continue
        r.raise_for_status()
        return r.json()


def _record_metrics(response) -> None:
    """Attributes this call to the active pull stage (024, FR-002). Never raises
    — measurement must not be able to fail a pull (FR-005)."""
    try:
        metrics.record_call(len(response.content or b""))
    except Exception:  # pragma: no cover - defensive; instrumentation is not load-bearing
        logger.debug("metrics attribution failed", exc_info=True)
