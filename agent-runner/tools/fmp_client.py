"""Shared FMP HTTP client: throttle, budget guard, entitlement probe.
Spec: specs/component-specs/agent-runner/tools/fmp_client.md

Replaces the scattered fmp_get()/track_fmp_call() pattern that used to live
directly in tools/financials.py. Every FMP call in agent-runner should route
through here so the paid-tier throttle and fail-soft budget guard apply
uniformly (constitution Principle IV; see specs/017-fmp-migration-admin/
research.md D5).
"""
import time
from datetime import datetime, timezone
from collections import deque
from threading import Lock

import pandas as pd
import requests
from pymongo.database import Database

from logging_config import get_logger
from settings import settings
from tools import metrics
from tools.db import FMP_ENTITLEMENTS, get_db, track_fmp_call

logger = get_logger(__name__)

# The legacy /api/v3 endpoints 403 for accounts created after FMP's 2025
# migration — this key only works against the "stable" API.
FMP_BASE = "https://financialmodelingprep.com/stable/"

# In-process token bucket. agent-runner runs a single queue_worker loop, so
# no cross-process coordination is needed (constitution Principle V).
_call_times: deque = deque()
_lock = Lock()


class FmpBudgetExceededError(Exception):
    """Raised when the configured daily soft cap has been reached. Callers
    MUST catch this and serve stale cache — this client never crashes an
    analysis run on a budget breach (constitution Principle IV)."""


def _throttle() -> None:
    """Blocks just long enough to keep calls under `fmp_calls_per_minute`
    in any rolling 60s window."""
    limit = settings.fmp_calls_per_minute
    if limit <= 0:
        return
    with _lock:
        now = time.monotonic()
        while _call_times and now - _call_times[0] > 60:
            _call_times.popleft()
        if len(_call_times) >= limit:
            sleep_for = 60 - (now - _call_times[0])
            if sleep_for > 0:
                logger.info("fmp throttle: sleeping %.1fs to stay under %s calls/min", sleep_for, limit)
                time.sleep(sleep_for)
            now = time.monotonic()
            while _call_times and now - _call_times[0] > 60:
                _call_times.popleft()
        _call_times.append(now)


def _check_daily_soft_cap(db: Database | None = None) -> int:
    """Increments and returns today's call count. Raises FmpBudgetExceededError
    once the configured soft cap is passed (0 = disabled, e.g. free-tier
    downgrade sets this to 225 without any code change)."""
    count = track_fmp_call(db=db)
    cap = settings.fmp_daily_soft_cap
    if cap > 0 and count > cap:
        logger.warning("FMP daily soft cap (%s) exceeded — %s calls today; degrading to stale cache", cap, count)
        raise FmpBudgetExceededError(f"daily soft cap {cap} exceeded ({count} calls today)")
    return count


def fmp_get(path: str, db: Database | None = None) -> list | dict:
    """Throttled, budget-guarded FMP GET against the stable API.

    Raises FmpBudgetExceededError when the soft daily cap is exceeded —
    callers must catch this and fall back to stale cache. Raises
    requests.HTTPError on FMP failures (402/403 = not entitled on this plan,
    handled the same way by most callers)."""
    _check_daily_soft_cap(db=db)
    _throttle()
    sep = "&" if "?" in path else "?"
    url = f"{FMP_BASE}{path}{sep}apikey={settings.fmp_api_key}"
    r = requests.get(url, timeout=15)
    # Attribute the call before raise_for_status: a 402/403 still cost us the
    # round trip, and a stage that spent time on failures is worth seeing (024).
    _record_metrics(r)
    r.raise_for_status()
    return r.json()


def _record_metrics(response) -> None:
    """Attributes this call to the active pull stage (024, FR-002). Never raises
    — measurement must not be able to fail a pull (FR-005)."""
    try:
        metrics.record_call(len(response.content or b""))
    except Exception:  # pragma: no cover - defensive; instrumentation is not load-bearing
        logger.debug("metrics attribution failed", exc_info=True)


_OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def fetch_eod_history(ticker: str, db: Database | None = None, start=None) -> pd.DataFrame:
    """EOD history for a ticker from FMP (dividend/split adjusted), shaped like
    yfinance's history() output — Open/High/Low/Close/Volume columns, ascending
    DatetimeIndex — so downstream consumers (resampling, indicators) need no
    changes (research D2/D3).

    `start` bounds the request to bars on or after that date (024 US2). Note
    this saves transfer and parse time, NOT an API call: a bounded request costs
    the same single call as an unbounded one (research D1).
    """
    path = f"historical-price-eod/full?symbol={ticker}"
    if start is not None:
        path += f"&from={start.isoformat()}"
    raw = fmp_get(path, db=db)
    rows = raw.get("historical", raw) if isinstance(raw, dict) else raw
    if not rows:
        return pd.DataFrame(columns=_OHLCV_COLUMNS)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df.index.name = "Date"
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    return df[_OHLCV_COLUMNS]


# ──────────────────────────────────────────────────────────────────────────
# Entitlement probe (research D1) — verification tool for the endpoint
# families the user hasn't already confirmed directly against their account.
# See specs/017-fmp-migration-admin/fmp-gap-review.md for the user-verified
# decisions this probe cross-checks rather than decides from scratch.
# ──────────────────────────────────────────────────────────────────────────

PROBE_ENDPOINTS: dict[str, str] = {
    "eod_prices": "historical-price-eod/full?symbol=AAPL",
    "intraday_1h": "historical-chart/1hour?symbol=AAPL",
    "intraday_1m": "historical-chart/1min?symbol=AAPL",
    "batch_quote": "quote?symbol=AAPL,MSFT",
    "insider_trading": "insider-trading/latest?limit=1",
    "form_13f": "institutional-ownership/latest?limit=1",
    "senate_house": "senate-latest?limit=1",
    "sector_performance": "sector-performance-snapshot",
    "movers": "biggest-gainers",
    "economic_calendar": "economic-calendar",
    "earnings_calendar": "earnings?symbol=AAPL&limit=1",
    "analyst_grades": "grades?symbol=AAPL&limit=1",
    "fund_holdings": "etf/holdings?symbol=SPY",
    "transcripts": "earning-call-transcript?symbol=AAPL&year=2025&quarter=1",
    "company_info": "profile?symbol=AAPL",
    # 029-company-profile-tweaks — peers/employee-count are new families,
    # unprobed before now; add them so a future plan downgrade is visible in
    # fmp_entitlements instead of a mystery empty Overview section.
    "stock_peers": "stock-peers?symbol=AAPL",
    "employee_count": "historical-employee-count?symbol=AAPL",
}


def fmp_entitlement_probe(db: Database | None = None) -> list[dict]:
    """Tests each endpoint family against the live key and upserts one row
    per family into fmp_entitlements. Never raises — a family that errors
    is recorded as such rather than aborting the rest of the probe."""
    db = db if db is not None else get_db()
    results = []
    for family, path in PROBE_ENDPOINTS.items():
        result, status = "error", None
        try:
            fmp_get(path, db=db)
            result, status = "entitled", 200
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            result = "payment_required" if status in (401, 402, 403) else "error"
        except FmpBudgetExceededError:
            result = "error"
            logger.warning("entitlement probe for %s skipped — daily soft cap exceeded", family)
        except Exception as exc:
            logger.warning("entitlement probe failed for %s: %s", family, exc)

        doc = {
            "family": family,
            "probe_endpoint": path,
            "result": result,
            "http_status": status,
            "checked_at": datetime.now(timezone.utc),
        }
        db[FMP_ENTITLEMENTS].replace_one({"family": family}, doc, upsert=True)
        results.append(doc)

    logger.info("entitlement probe complete: %s", {r["family"]: r["result"] for r in results})
    return results
