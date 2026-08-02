"""FRED macro indicators with a 24-hour Mongo cache.
Spec: specs/component-specs/agent-runner/tools/macro.md
"""
import logging
from datetime import datetime, timedelta, timezone

import requests
from pymongo.database import Database

from settings import settings
from tools.db import MACRO_CACHE, get_db

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred/"
CACHE_HOURS = 24

DEFAULT_INDICATORS = [
    "CPIAUCSL", "PCEPI", "FEDFUNDS", "UNRATE", "GDP", "GDPC1",
    "DGS10", "DGS2", "T10Y2Y", "T10Y3M", "VIXCLS", "UMCSENT",
]


def fred_get(series_id: str) -> list[dict]:
    """Last 12 observations for a series, newest first. FRED's '.' placeholder
    (weekends/holidays for daily series) maps to None."""
    url = (
        f"{FRED_BASE}series/observations?series_id={series_id}"
        f"&api_key={settings.fred_api_key}&file_type=json&sort_order=desc&limit=12"
    )
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return [
        {"date": o["date"], "value": float(o["value"]) if o["value"] != "." else None}
        for o in r.json()["observations"]
    ]


def get_macro_data(indicators: list[str] | None = None, db: Database | None = None) -> dict:
    """Requested FRED series, served from the shared 24h cache doc. Series the
    cache doesn't have yet are fetched and merged in, so non-default indicators
    still work on a warm cache."""
    db = db if db is not None else get_db()
    if indicators is None:
        indicators = DEFAULT_INDICATORS

    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_HOURS)
    cached = db[MACRO_CACHE].find_one({"fetched_at": {"$gt": cutoff}})
    data = dict(cached["data"]) if cached else {}

    missing = [s for s in indicators if s not in data]
    if missing:
        for series_id in missing:
            data[series_id] = fred_get(series_id)
        db[MACRO_CACHE].replace_one(
            {}, {"data": data, "fetched_at": datetime.now(timezone.utc)}, upsert=True
        )

    return {s: data[s] for s in indicators}


def _latest(series: list[dict]) -> float | None:
    """First non-null value in a newest-first series."""
    return next((o["value"] for o in series if o["value"] is not None), None)


def get_yield_curve_status(db: Database | None = None) -> dict:
    macro = get_macro_data(["T10Y2Y", "T10Y3M", "DGS10", "DGS2"], db=db)
    t10y2y = _latest(macro["T10Y2Y"])
    t10y3m = _latest(macro["T10Y3M"])
    return {
        "10y_2y_spread": t10y2y,
        "10y_3m_spread": t10y3m,
        "inverted": (t10y2y is not None and t10y2y < 0) or (t10y3m is not None and t10y3m < 0),
        "inversion_severity": (
            "unknown" if t10y2y is None
            else "deep" if t10y2y < -0.5
            else "mild" if t10y2y < 0
            else "none"
        ),
    }
