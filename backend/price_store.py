"""Incrementally-maintained daily price series, one document per ticker.
Spec: specs/024-delta-data-pulls (US2); contracts/price-store.md.

⚠️  Hand-synced counterpart: agent-runner/tools/price_store.py. The two services
ship as separate images with separate dependency trees and deliberately share no
Python package (constitution Principle V), so this module is duplicated rather
than imported — the same precedent as db.py's constants, fmp.py, and
earnings_data.py. The pure functions below are covered by an identical case
table in both services' test suites, which is what actually enforces Principle
VI: divergence fails a test instead of silently corrupting stored data.

The backend's role is narrower than the agent-runner's: it serves chart reads.
It refreshes when a page asks for a ticker nothing has pulled yet, and otherwise
resamples locally from what the store already holds — which is what removes the
four-downloads-per-ticker behavior the old price_cache had (SC-004).

Unlike the old routers/price.py path, every provider call here goes through
fmp.fmp_get, so it counts against the daily budget (Principle IV; closes half of
a logged KNOWN_ISSUES.md entry).
"""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from pymongo.database import Database

from db import PRICE_HISTORY
from fmp import FmpBudgetExceededError, fmp_get
from logging_config import get_logger

logger = get_logger(__name__)

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

# Keep in sync with agent-runner/tools/price_store.py.
MAX_GAP_DAYS = 730
OVERLAP_DAYS = 1


# ──────────────────────────────────────────────────────────────────────────
# Pure functions — mirrored in agent-runner/tools/price_store.py
# ──────────────────────────────────────────────────────────────────────────

def merge_bars(stored: list[dict], fetched: list[dict]) -> list[dict]:
    """Merges newly fetched bars into a stored series, keyed on `date`.

    Fetched wins on a collision: a bar we are seeing again is a correction
    (dividend/split re-adjustment), not a duplicate to discard. Result is
    ascending with no duplicate dates; neither argument is mutated.
    """
    by_date: dict[str, dict] = {}
    for source in (stored or [], fetched or []):
        for row in source:
            key = row.get("date")
            if key:
                by_date[key] = row
    return [by_date[k] for k in sorted(by_date)]


def delta_start(coverage: dict | None, today: date, max_gap_days: int = MAX_GAP_DAYS) -> date | None:
    """The date to request from, or None meaning "fetch the whole history".

    The one-day back-off is deliberate: starting at last_date + 1 silently drops
    a trading day whenever the provider's day boundary and our stored date
    disagree, and the merge absorbs the overlap for the cost of one row.
    """
    last = (coverage or {}).get("last_date")
    if not last:
        return None
    try:
        last_date = date.fromisoformat(str(last)[:10])
    except ValueError:
        logger.warning("unparseable stored last_date %r — falling back to full fetch", last)
        return None
    if (today - last_date).days > max_gap_days:
        return None
    return last_date - timedelta(days=OVERLAP_DAYS)


def build_coverage(bars: list[dict], previous: dict | None, mode: str) -> dict:
    """Recomputes the coverage envelope from the merged series. A delta advances
    `extended_at` only — `established_at` stays the honest record of when this
    series was last built from scratch (FR-010, FR-025)."""
    now = datetime.now(timezone.utc)
    dates = [b["date"] for b in bars if b.get("date")]
    established = (previous or {}).get("established_at") if mode != "full" else None
    return {
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "bar_count": len(bars),
        "established_at": established or now,
        "extended_at": now,
        "source": "fmp",
    }


def bars_to_frame(bars: list[dict]) -> pd.DataFrame:
    if not bars:
        empty = pd.DataFrame(columns=OHLCV_COLUMNS)
        empty.index = pd.DatetimeIndex([], name="Date")
        return empty
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df.index.name = "Date"
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    return df[OHLCV_COLUMNS]


def frame_to_bars(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["Open"]), "high": float(row["High"]),
            "low": float(row["Low"]), "close": float(row["Close"]),
            "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
        }
        for idx, row in df.iterrows()
        if pd.notna(row["Open"]) and pd.notna(row["High"])
        and pd.notna(row["Low"]) and pd.notna(row["Close"])
    ]


# ──────────────────────────────────────────────────────────────────────────
# I/O
# ──────────────────────────────────────────────────────────────────────────

def _fetch(ticker: str, start: date | None, db: Database) -> pd.DataFrame:
    """Isolated provider call — the seam tests monkeypatch. Routed through
    fmp.fmp_get so it counts against the daily budget."""
    path = f"historical-price-eod/full?symbol={ticker}"
    if start is not None:
        path += f"&from={start.isoformat()}"
    raw = fmp_get(path, db)
    rows = raw.get("historical", raw) if isinstance(raw, dict) else raw
    if not rows:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df.index.name = "Date"
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    return df[OHLCV_COLUMNS]


def get_series(ticker: str, refresh: str, db: Database):
    """The stored daily series, optionally refreshed first.

    Returns `(DataFrame, meta)`. Never raises on a provider failure: stored bars
    are served with `outcome: "degraded"` (FR-012, Principle IV).
    """
    ticker = ticker.upper()
    doc = db[PRICE_HISTORY].find_one({"ticker": ticker}, {"_id": 0}) or {}
    stored_bars = doc.get("bars") or []
    coverage = doc.get("coverage") or {}

    if refresh == "none":
        return bars_to_frame(stored_bars), {
            "requests": 0, "retrieval": "stored", "outcome": "stored",
        }

    start = None if refresh == "full" else delta_start(coverage, date.today())
    retrieval = "incremental" if start is not None else "full"

    try:
        fetched = _fetch(ticker, start, db)
    except FmpBudgetExceededError:
        logger.warning("%s: FMP budget spent — serving stored price history", ticker)
        return bars_to_frame(stored_bars), {
            "requests": 1, "retrieval": retrieval, "outcome": "degraded",
        }
    except Exception as exc:
        logger.warning("%s: price fetch failed (%s) — serving stored history", ticker, exc)
        return bars_to_frame(stored_bars), {
            "requests": 1, "retrieval": retrieval, "outcome": "degraded",
        }

    fetched_bars = frame_to_bars(fetched)
    if refresh == "full":
        merged = fetched_bars or stored_bars
    else:
        merged = merge_bars(stored_bars, fetched_bars)

    # Built entirely in memory; a single atomic document swap follows (FR-030).
    db[PRICE_HISTORY].replace_one(
        {"ticker": ticker, },
        {"ticker": ticker, "bars": merged,
         "coverage": build_coverage(merged, coverage, refresh)},
        upsert=True,
    )
    return bars_to_frame(merged), {
        "requests": 1, "retrieval": retrieval, "outcome": "fetched",
    }
