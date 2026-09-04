"""One-time cleanup: drops the orphaned `portfolio_digest_cache` collection.
Spec: specs/031-semantic-layer-chat; research.md R7.

Found during that feature's data audit: 1 document, zero references anywhere
in backend/ or agent-runner/. `agent-runner/tools/portfolio.py` (the module
that used to write it) no longer exists — the collection was orphaned when
that feature was removed, and `logs/agent-runner/agent-runner.log.2026-08-22`
still shows `no handler registered for job_type=portfolio_digest`.

This does NOT run automatically in any test or CI step, and requires an
explicit --yes flag — dropping a collection is not reversible. Run outside
Docker, from the repo root:
    python scripts/drop_portfolio_digest_cache.py           # dry run
    python scripts/drop_portfolio_digest_cache.py --yes     # actually drops it
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from logging_config import get_logger  # noqa: E402
from db import get_db  # noqa: E402

logger = get_logger(__name__, component="scripts")

COLLECTION = "portfolio_digest_cache"


def run(db, confirmed: bool) -> None:
    count = db[COLLECTION].count_documents({})
    if count == 0 and COLLECTION not in db.list_collection_names():
        print(f"{COLLECTION!r} does not exist — nothing to do.")
        return

    print(f"{COLLECTION!r} currently holds {count} document(s).")
    if not confirmed:
        print("Dry run only — re-run with --yes to actually drop this collection.")
        return

    db.drop_collection(COLLECTION)
    logger.info("dropped orphaned collection %r (%s docs)", COLLECTION, count)
    print(f"Dropped {COLLECTION!r}.")


if __name__ == "__main__":
    try:
        run(get_db(), confirmed="--yes" in sys.argv)
    except Exception:
        logger.exception("drop_portfolio_digest_cache failed")
        raise
