"""Agent-runner entry point. Spec: specs/component-specs/agent-runner/main.md

Three loops in one process:
- work_queue poll every `queue_poll_seconds` (per-ticker crew runs)
- earnings_scans poll (user-triggered calendar scans — checked first, a user
  is watching the progress spinner)
- institutional flow scan once daily (market-wide, independent of the queue)
- market breadth refresh once daily (NYMO/NAMO + SPY divergence tracking)
"""
import time
from datetime import datetime, timezone

from breadth_worker import run_daily_breadth_if_due
from earnings_scan_worker import claim_and_run_next_scan
from institutional_flow_worker import run_daily_scan_if_due
from logging_config import get_logger
from queue_worker import claim_and_run_next
from settings import settings

logger = get_logger(__name__)


def main() -> None:
    logger.info(
        "agent-runner starting (poll=%ss, model=%s, ollama=%s)",
        settings.queue_poll_seconds, settings.ollama_model, settings.ollama_url,
    )
    while True:
        try:
            now = datetime.now(timezone.utc)
            run_daily_scan_if_due(now=now)
            run_daily_breadth_if_due(now=now)
            scanned = claim_and_run_next_scan()
            worked = claim_and_run_next()
            if not (scanned or worked):
                time.sleep(settings.queue_poll_seconds)
        except NotImplementedError as exc:
            # Scaffold state: workers aren't implemented yet — idle instead of crash-looping
            logger.info("not implemented yet (%s); idling", exc)
            time.sleep(settings.queue_poll_seconds)
        except Exception:
            logger.exception("worker loop error; continuing")
            time.sleep(settings.queue_poll_seconds)


if __name__ == "__main__":
    main()
