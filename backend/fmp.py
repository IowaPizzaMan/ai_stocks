"""Budget-guarded FMP access for the backend.
Spec: specs/022-market-news-feed (research.md D3)

Mirrors agent-runner/tools/fmp_client.py's accounting contract — same
`fmp_usage` collection, same UTC day bucket, same `fmp_daily_soft_cap` setting
name with 0 meaning disabled — so both services throttle against one number
(constitution Principle VI). The two services deliberately don't share a Python
package (Principle V), hence the small duplication rather than an import.

Callers MUST catch FmpBudgetExceededError and degrade to cached data; it should
never surface as a 5xx (Principle IV: fail soft, serve stale).

NOTE: routers/price.py and earnings_data.py still call FMP with bare
requests.get and do not increment this counter, so today's total under-reports
real spend. Tracked in KNOWN_ISSUES.md.
"""
from datetime import datetime, timezone

import requests
from pymongo import ReturnDocument
from pymongo.database import Database

from db import FMP_USAGE
from logging_config import get_logger
from settings import settings

logger = get_logger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable/"


class FmpBudgetExceededError(Exception):
    """The configured daily soft cap has been reached. Callers MUST catch this
    and serve stale cache rather than failing the request."""


def track_call(db: Database) -> int:
    """Increments today's counter and returns the new count (UTC day bucket)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = db[FMP_USAGE].find_one_and_update(
        {"date": today},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result["count"]


def fmp_get(path: str, db: Database) -> list | dict:
    """Budget-accounted FMP GET against the stable API.

    The cap is checked before the request goes out, so a blown budget never
    spends the very call it was meant to prevent.
    """
    count = track_call(db)
    cap = settings.fmp_daily_soft_cap
    if cap > 0 and count > cap:
        logger.warning(
            "FMP daily soft cap (%s) exceeded — %s calls today; degrading to cache", cap, count
        )
        raise FmpBudgetExceededError(f"daily soft cap {cap} exceeded ({count} calls today)")

    sep = "&" if "?" in path else "?"
    url = f"{FMP_BASE}{path}{sep}apikey={settings.fmp_api_key}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()
