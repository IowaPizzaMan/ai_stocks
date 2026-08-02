"""Computed McClellan Oscillator (NYMO/NAMO proxies) from advance/decline counts.
Spec: specs/component-specs/agent-runner/tools/breadth.md

$NYMO/$NAMO are StockCharts-proprietary and not API-fetchable anywhere, so the
oscillator is computed locally over proxy universes (S&P 500 for NYSE,
NASDAQ-100 for NASDAQ) — one batched yf.download per universe per day.
"""
import io
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import yfinance as yf
from pymongo.database import Database

from tools.db import BREADTH_CACHE, BREADTH_UNIVERSE, get_db, track_fmp_call

logger = logging.getLogger(__name__)

UNIVERSE_MAX_AGE_DAYS = 7
ZONE_THRESHOLD = 60  # ±60 per market_flow_rules.md; calibrate vs StockCharts (proxy universes run narrower)
TREND_EPSILON = 5.0

# Wikipedia (and slickcharts) 403 the default urllib UA — always send a browser one
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

EXCHANGES = {"nyse": "sp500", "nasdaq": "nasdaq100"}


# --- Universe sourcing -------------------------------------------------------

def _fmp_constituents(name: str) -> list[str]:
    from tools.financials import fmp_get

    # 402s on the free tier (constituents are paid) — the scrape fallback below
    # is the de facto source; this stays for keys that do have access
    endpoint = {"sp500": "sp500-constituent", "nasdaq100": "nasdaq-constituent"}[name]
    rows = fmp_get(endpoint)
    return [r["symbol"] for r in rows]


def _read_html_table(url: str) -> list[pd.DataFrame]:
    r = requests.get(url, headers=BROWSER_UA, timeout=30)
    r.raise_for_status()
    return pd.read_html(io.StringIO(r.text))


def _wikipedia_sp500() -> list[str]:
    tables = _read_html_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    return tables[0]["Symbol"].tolist()


def _slickcharts_nasdaq100() -> list[str]:
    # The Nasdaq-100 Wikipedia constituents table doesn't parse via read_html
    tables = _read_html_table("https://www.slickcharts.com/nasdaq100")
    for t in tables:
        if "Symbol" in t.columns:
            return t["Symbol"].tolist()
    raise ValueError("no Symbol column found on slickcharts nasdaq100 page")


def _yahooize(tickers: list[str]) -> list[str]:
    """Class shares use '.' in most listings but '-' on Yahoo (BRK.B -> BRK-B)."""
    return [str(t).strip().upper().replace(".", "-") for t in tickers if t and str(t).strip()]


def get_universe(name: str, db: Database | None = None) -> list[str]:
    """Constituent list for 'sp500' or 'nasdaq100', cached 7 days in Mongo.
    FMP is primary; Wikipedia/slickcharts scrape is the free fallback."""
    if name not in ("sp500", "nasdaq100"):
        raise ValueError(f"unknown universe: {name}")
    db = db if db is not None else get_db()

    cutoff = datetime.now(timezone.utc) - timedelta(days=UNIVERSE_MAX_AGE_DAYS)
    cached = db[BREADTH_UNIVERSE].find_one({"name": name, "fetched_at": {"$gt": cutoff}})
    if cached:
        return cached["tickers"]

    tickers: list[str] = []
    try:
        track_fmp_call(db=db)
        tickers = _yahooize(_fmp_constituents(name))
    except Exception as exc:
        logger.warning("FMP constituents failed for %s (%s); using scrape fallback", name, exc)
    if not tickers:
        scraper = _wikipedia_sp500 if name == "sp500" else _slickcharts_nasdaq100
        tickers = _yahooize(scraper())

    db[BREADTH_UNIVERSE].replace_one(
        {"name": name},
        {"name": name, "tickers": tickers, "fetched_at": datetime.now(timezone.utc)},
        upsert=True,
    )
    return tickers


# --- Oscillator math ---------------------------------------------------------

def _download_closes(universe: list[str], period: str) -> pd.DataFrame:
    return yf.download(universe, period=period, interval="1d", auto_adjust=True, progress=False)["Close"]


def compute_mcclellan(closes: pd.DataFrame) -> pd.DataFrame:
    """Ratio-adjusted McClellan from a wide Close-price frame (index: date,
    columns: tickers). Pure function — testable without yfinance."""
    chg = closes.diff()
    adv = (chg > 0).sum(axis=1)
    dec = (chg < 0).sum(axis=1)
    rana = 1000 * (adv - dec) / (adv + dec)
    mo = rana.ewm(span=19, adjust=False).mean() - rana.ewm(span=39, adjust=False).mean()
    return pd.DataFrame({"advancers": adv, "decliners": dec, "rana": rana, "mcclellan": mo}).dropna()


def _breadth_records(exchange: str, universe: list[str], lookback_days: int, db: Database) -> list[dict]:
    """Per-day {date, value} mcclellan records, newest last. Served from
    breadth_cache when today's row is already stored; otherwise one batched
    download recomputes the window and upserts per-(exchange, date) docs."""
    today = datetime.now(timezone.utc).date().isoformat()
    if db[BREADTH_CACHE].find_one({"exchange": exchange, "computed_on": today}):
        rows = list(
            db[BREADTH_CACHE]
            .find({"exchange": exchange}, {"_id": 0})
            .sort("date", -1)
            .limit(lookback_days)
        )
        return [{"date": r["date"], "value": r["mcclellan"]} for r in reversed(rows)]

    # EMA39 needs runway: fetch ~3x the lookback window
    closes = _download_closes(universe, f"{lookback_days * 3}d")
    df = compute_mcclellan(closes)
    for date, row in df.tail(lookback_days).iterrows():
        doc = {
            "exchange": exchange,
            "date": date.date().isoformat(),
            "advancers": int(row["advancers"]),
            "decliners": int(row["decliners"]),
            "rana": round(float(row["rana"]), 2),
            "mcclellan": round(float(row["mcclellan"]), 1),
            "computed_on": today,
        }
        db[BREADTH_CACHE].replace_one({"exchange": exchange, "date": doc["date"]}, doc, upsert=True)

    return [
        {"date": d.date().isoformat(), "value": round(float(v), 1)}
        for d, v in df["mcclellan"].tail(lookback_days).items()
    ]


# --- Interpretation ----------------------------------------------------------

def classify_zone(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value < -ZONE_THRESHOLD:
        return "oversold"
    if value > ZONE_THRESHOLD:
        return "overbought"
    return "neutral"


def compute_trend(records: list[dict]) -> str:
    """Direction of the last few readings: rising/falling/flat."""
    if len(records) < 2:
        return "flat"
    delta = records[-1]["value"] - records[0]["value"]
    if delta > TREND_EPSILON:
        return "rising"
    if delta < -TREND_EPSILON:
        return "falling"
    return "flat"


def detect_divergence(nymo_records: list[dict], spy_close: pd.Series | None = None) -> dict:
    """SPY vs NYMO divergence over the last 10 sessions: price making a new
    extreme the oscillator refuses to confirm."""
    if len(nymo_records) < 10:
        return {"type": "none", "description": "insufficient history"}

    if spy_close is None:
        spy = yf.download("SPY", period="30d", interval="1d", auto_adjust=True, progress=False)
        spy_close = spy["Close"].squeeze()

    spy10 = spy_close.tail(10)
    nymo10 = [r["value"] for r in nymo_records[-10:]]
    if len(spy10) < 10:
        return {"type": "none", "description": "insufficient SPY history"}

    spy_prev, spy_recent = spy10.iloc[:5], spy10.iloc[5:]
    nymo_prev, nymo_recent = nymo10[:5], nymo10[5:]

    if spy_recent.min() < spy_prev.min() and min(nymo_recent) > min(nymo_prev):
        return {"type": "bullish", "description": "SPY made a lower low while NYMO held a higher low"}
    if spy_recent.max() > spy_prev.max() and max(nymo_recent) < max(nymo_prev):
        return {"type": "bearish", "description": "SPY made a higher high while NYMO set a lower high"}
    return {"type": "none", "description": "no SPY/NYMO divergence in the last 10 sessions"}


# --- Public entry point ------------------------------------------------------

def get_market_breadth(lookback_days: int = 90, db: Database | None = None) -> dict:
    db = db if db is not None else get_db()

    sections = {}
    for exchange, universe_name in EXCHANGES.items():
        universe = get_universe(universe_name, db=db)
        records = _breadth_records(exchange, universe, lookback_days, db)
        current = records[-1]["value"] if records else None
        sections[exchange] = {
            "history": records,
            "current": current,
            "zone": classify_zone(current),
            "trend": compute_trend(records[-5:]),
        }

    return {
        "nymo": sections["nyse"],
        "namo": sections["nasdaq"],
        "divergence": detect_divergence(sections["nyse"]["history"]),
        "method": "computed_ratio_adjusted",  # provenance flag for the UI/agents
    }
