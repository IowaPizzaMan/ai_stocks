"""Computed McClellan Oscillator (NYMO/NAMO proxies) from advance/decline counts.
Spec: specs/component-specs/agent-runner/tools/breadth.md

$NYMO/$NAMO are StockCharts-proprietary and not API-fetchable anywhere, so the
oscillator is computed locally over proxy universes (S&P 500 for NYSE,
NASDAQ-100 for NASDAQ). Closes are sourced from FMP per-symbol EOD history
through the shared throttle (specs/017-fmp-migration-admin, research D4) —
a batch-quote endpoint could cut this to one call per universe if entitled,
left as a future optimization since per-symbol works regardless of plan tier.
"""
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from pymongo.database import Database

from logging_config import get_logger
from tools.db import (
    BREADTH_CACHE,
    BREADTH_DIVERGENCES,
    BREADTH_META,
    BREADTH_UNIVERSE,
    MARKET_FLOW_EVENTS,
    get_db,
    track_fmp_call,
)

logger = get_logger(__name__)

UNIVERSE_MAX_AGE_DAYS = 7
ZONE_THRESHOLD = 60  # ±60 per market_flow_rules.md; calibrate vs StockCharts (proxy universes run narrower)
TREND_EPSILON = 5.0
SPY_TICKER = "SPY"
DIVERGENCE_WINDOW = 10   # sessions compared, split in half (prior swing vs recent swing)
FORWARD_WINDOWS = (5, 10)  # sessions of SPY follow-through recorded per resolved divergence
HISTORY_LIMIT = 20

# Wikipedia (and slickcharts) 403 the default urllib UA — always send a browser one
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

EXCHANGES = {"nyse": "sp500", "nasdaq": "nasdaq100"}


# --- Universe sourcing -------------------------------------------------------

def _fmp_constituents(name: str) -> list[str]:
    from tools.fmp_client import fmp_get

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
    """Wide Close-price frame (index: date, columns: tickers), one FMP EOD
    fetch per symbol. A ticker that fails is simply excluded — the oscillator
    tolerates a few missing names in a 500+ universe."""
    from tools.fmp_client import fetch_eod_history

    closes = {}
    for ticker in universe:
        try:
            closes[ticker] = fetch_eod_history(ticker)["Close"]
        except Exception as exc:
            logger.info("breadth: %s unavailable (%s), excluding from sweep", ticker, exc)
    wide = pd.DataFrame(closes)
    if period.endswith("d"):
        wide = wide.tail(int(period[:-1]))
    return wide


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


def _download_spy(period: str) -> pd.Series:
    from tools.fmp_client import fetch_eod_history

    series = fetch_eod_history(SPY_TICKER)["Close"]
    if period.endswith("d"):
        series = series.tail(int(period[:-1]))
    return series


def _spy_records(dates: list[str], db: Database) -> list[dict]:
    """SPY closes aligned to the breadth dates. Stored as `spy_close` on the
    nyse breadth_cache rows — the divergence read is SPY vs NYMO, so the two
    series share a row and one download backfills the window."""
    if not dates:
        return []

    cached = {
        r["date"]: r.get("spy_close")
        for r in db[BREADTH_CACHE].find(
            {"exchange": "nyse", "date": {"$in": dates}}, {"_id": 0, "date": 1, "spy_close": 1}
        )
    }
    if all(cached.get(d) is not None for d in dates):
        return [{"date": d, "close": cached[d]} for d in dates]

    closes = _download_spy(f"{len(dates) * 2}d")
    by_date = {d.date().isoformat(): round(float(v), 2) for d, v in closes.items() if pd.notna(v)}
    for date in dates:
        if date in by_date:
            db[BREADTH_CACHE].update_one(
                {"exchange": "nyse", "date": date}, {"$set": {"spy_close": by_date[date]}}
            )
    return [{"date": d, "close": by_date[d]} for d in dates if d in by_date]


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


def _no_divergence(description: str) -> dict:
    return {"type": "none", "description": description, "price_points": [], "osc_points": []}


def _anchor(entry: tuple[str, float, float], index: int) -> dict:
    return {"date": entry[0], "value": round(float(entry[index]), 2)}


def detect_divergence(nymo_records: list[dict], spy_records: list[dict]) -> dict:
    """SPY vs NYMO divergence over the last 10 sessions: price making a new
    extreme the oscillator refuses to confirm.

    `price_points` / `osc_points` carry the two swing anchors per series (the
    prior extreme and the one that failed to confirm it) so the UI draws the
    two opposite-sloping trend lines from real data instead of re-detecting
    swings client-side. Each series is anchored on its own swing dates, which
    need not coincide.
    """
    closes = {r["date"]: r["close"] for r in spy_records if r.get("close") is not None}
    paired = [
        (r["date"], closes[r["date"]], r["value"])
        for r in nymo_records
        if r.get("value") is not None and r["date"] in closes
    ]
    if len(paired) < DIVERGENCE_WINDOW:
        return _no_divergence("insufficient overlapping SPY/NYMO history")

    window = paired[-DIVERGENCE_WINDOW:]
    half = DIVERGENCE_WINDOW // 2
    prev, recent = window[:half], window[half:]

    spy_low_prev, spy_low_recent = min(prev, key=lambda p: p[1]), min(recent, key=lambda p: p[1])
    osc_low_prev, osc_low_recent = min(prev, key=lambda p: p[2]), min(recent, key=lambda p: p[2])
    if spy_low_recent[1] < spy_low_prev[1] and osc_low_recent[2] > osc_low_prev[2]:
        return {
            "type": "bullish",
            "description": "SPY made a lower low while NYMO held a higher low",
            "price_points": [_anchor(spy_low_prev, 1), _anchor(spy_low_recent, 1)],
            "osc_points": [_anchor(osc_low_prev, 2), _anchor(osc_low_recent, 2)],
        }

    spy_high_prev, spy_high_recent = max(prev, key=lambda p: p[1]), max(recent, key=lambda p: p[1])
    osc_high_prev, osc_high_recent = max(prev, key=lambda p: p[2]), max(recent, key=lambda p: p[2])
    if spy_high_recent[1] > spy_high_prev[1] and osc_high_recent[2] < osc_high_prev[2]:
        return {
            "type": "bearish",
            "description": "SPY made a higher high while NYMO set a lower high",
            "price_points": [_anchor(spy_high_prev, 1), _anchor(spy_high_recent, 1)],
            "osc_points": [_anchor(osc_high_prev, 2), _anchor(osc_high_recent, 2)],
        }
    return _no_divergence("no SPY/NYMO divergence in the last 10 sessions")


# --- Divergence history + feed events ----------------------------------------

def _forward_change(spy_records: list[dict], from_date: str, sessions: int) -> float | None:
    """SPY % change over the N sessions after `from_date` — None until those
    sessions have actually printed."""
    dates = [r["date"] for r in spy_records]
    if from_date not in dates:
        return None
    start_i = dates.index(from_date)
    end_i = start_i + sessions
    if end_i >= len(spy_records):
        return None
    start, end = spy_records[start_i]["close"], spy_records[end_i]["close"]
    return round((end - start) / start * 100, 2) if start else None


def _fill_forward_returns(db: Database, spy_records: list[dict]) -> None:
    """Backfills spy_change_5d/10d on resolved divergences as the follow-through
    sessions print. Measured from the resolution date, which is where the
    chart's ▲/▼ marker sits."""
    for doc in db[BREADTH_DIVERGENCES].find({"resolved": {"$ne": None}}):
        updates = {}
        for sessions in FORWARD_WINDOWS:
            field = f"spy_change_{sessions}d"
            if doc.get(field) is None:
                change = _forward_change(spy_records, doc["resolved"], sessions)
                if change is not None:
                    updates[field] = change
        if updates:
            db[BREADTH_DIVERGENCES].update_one({"_id": doc["_id"]}, {"$set": updates})


def _emit_divergence_event(db: Database, divergence: dict, nymo_current: float | None,
                           today: str) -> dict:
    """Market-wide feed card — divergences aren't per-ticker, so they'd
    otherwise only surface inside whichever stock happened to be analyzed."""
    kind = divergence["type"]
    event = {
        "event_id": f"breadth-divergence-{kind}-{today}",
        "category": "market_flow",
        "kind": "breadth_divergence",
        "divergence_type": kind,
        "headline": f"{kind.capitalize()} SPY/NYMO divergence detected",
        "body": divergence.get("description", ""),
        "price_points": divergence.get("price_points", []),
        "osc_points": divergence.get("osc_points", []),
        "nymo_current": nymo_current,
        "detected_on": today,
        "created_at": datetime.now(timezone.utc),
    }
    db[MARKET_FLOW_EVENTS].replace_one({"event_id": event["event_id"]}, event, upsert=True)
    logger.info("emitted market_flow feed event: %s", event["headline"])
    return event


def update_divergence_tracking(db: Database, divergence: dict, spy_records: list[dict],
                               nymo_current: float | None = None,
                               today: str | None = None) -> dict | None:
    """Records divergence transitions in breadth_divergences and emits a feed
    event when a *new* divergence opens — never while the same one persists,
    or the daily run would re-fire it for as long as it lasts. Returns the
    emitted event, or None."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    current = divergence.get("type", "none")

    _fill_forward_returns(db, spy_records)
    db[BREADTH_META].replace_one(
        {"key": "last_divergence"},
        {"key": "last_divergence", "value": divergence, "computed_on": today},
        upsert=True,
    )

    active = db[BREADTH_DIVERGENCES].find_one({"resolved": None})
    if active and active["type"] == current:
        return None  # same divergence still in force
    if active:
        db[BREADTH_DIVERGENCES].update_one({"_id": active["_id"]}, {"$set": {"resolved": today}})
    if current == "none":
        return None

    db[BREADTH_DIVERGENCES].insert_one({
        "type": current,
        "detected_on": today,
        "resolved": None,
        "anchor_dates": [p["date"] for p in divergence.get("price_points", [])],
        "description": divergence.get("description"),
        "spy_change_5d": None,
        "spy_change_10d": None,
    })
    return _emit_divergence_event(db, divergence, nymo_current, today)


def get_divergence_history(db: Database, limit: int = HISTORY_LIMIT) -> list[dict]:
    """Resolved divergences, oldest first — backs the chart's ▲/▼ markers."""
    docs = (
        db[BREADTH_DIVERGENCES]
        .find({"resolved": {"$ne": None}}, {"_id": 0})
        .sort("resolved", -1)
        .limit(limit)
    )
    return list(reversed(list(docs)))


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

    nymo_history = sections["nyse"]["history"]
    try:
        spy = _spy_records([r["date"] for r in nymo_history], db)
    except Exception as exc:
        logger.warning("SPY history unavailable (%s) — divergence read skipped", exc)
        spy = []

    divergence = detect_divergence(nymo_history, spy)
    update_divergence_tracking(db, divergence, spy, nymo_current=sections["nyse"]["current"])

    return {
        "nymo": sections["nyse"],
        "namo": sections["nasdaq"],
        "spy": spy,
        "divergence": divergence,
        "divergence_history": get_divergence_history(db),
        "method": "computed_ratio_adjusted",  # provenance flag for the UI/agents
    }
