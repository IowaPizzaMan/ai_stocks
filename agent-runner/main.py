"""Agent-runner entry point. Spec: specs/component-specs/agent-runner/main.md

Two loops in one process:
- work_queue poll every `queue_poll_seconds` (per-ticker crew runs)
- institutional flow scan once daily (market-wide, independent of the queue)
"""
import logging
import time
from datetime import datetime, timezone

from institutional_flow_worker import run_daily_scan_if_due
from queue_worker import claim_and_run_next
from settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("agent-runner")


def main() -> None:
    logger.info(
        "agent-runner starting (poll=%ss, model=%s, ollama=%s)",
        settings.queue_poll_seconds, settings.ollama_model, settings.ollama_url,
    )
    while True:
        try:
            run_daily_scan_if_due(now=datetime.now(timezone.utc))
            worked = claim_and_run_next()
            if not worked:
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
