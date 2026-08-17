"""Incrementally-maintained daily price series, one document per ticker.
Spec: specs/024-delta-data-pulls (US2); contracts/price-store.md.

⚠️  Hand-synced counterpart: backend/price_store.py. The two services ship as
separate images with separate dependency trees and deliberately share no Python
package (constitution Principle V), so this module is duplicated rather than
imported — the same precedent as db.py's constants, backend/fmp.py, and
backend/earnings_data.py. The pure functions below are covered by an identical
case table in both services' test suites, which is what actually enforces
Principle VI: divergence fails a test instead of silently corrupting stored data.

Design notes worth keeping in view:

* One document per ticker holding the whole series. That single choice buys
  local resampling for every chart resolution (SC-004), natural in-pull
  deduplication (SC-003), and an atomic single-document swap on full refresh
  (FR-030) — a failed refresh cannot leave a half-written series because the
  write never starts.
* `refresh` is explicit. There is no TTL and no implicit freshness anywhere in
  this module; time-based expiry is exactly what this feature exists to remove.
* Nothing here detects splits or re-baselines on a schedule (FR-010). A
  corporate action leaves stored history stale until the operator triggers a
  full refresh — a deliberate, recorded trade (spec Assumptions).
"""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from pymongo.database import Database

from logging_config import get_logger
from tools.db import PRICE_HISTORY, get_db
from tools.fmp_client import FmpBudgetExceededError, fetch_eod_history

logger = get_logger(__name__)

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

# Past this, a delta window rivals the useful history length and a clean full
# fetch is simpler for the same one request (FR-011, research D11). Chosen to
# match the shortest resolution window the app serves (`daily: 2y`), so any
# wider gap means the stored series can't satisfy even the default chart.
MAX_GAP_DAYS = 730

# How far back to re-request beyond what we already hold. Never zero: starting
# at last_date + 1 silently drops a trading day whenever the provider's day
# boundary and our stored date disagree, and the merge absorbs the overlap for
# the cost of one row (research D5).
OVERLAP_DAYS = 1


# ──────────────────────────────────────────────────────────────────────────
# Pure functions — no Mongo, no HTTP. Mirrored in backend/price_store.py.
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

    None is returned for a missing/unusable baseline (FR-007) and for a gap so
    wide that incremental retrieval buys nothing (FR-011).
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
    """Recomputes the coverage envelope from the merged series.

    Bounds are always derived from `bars` rather than carried forward, so the
    envelope cannot drift out of step with what is actually stored. A delta
    advances `extended_at` only — `established_at` stays the honest record of
    when this series was last built from scratch (FR-010, FR-025).
    """
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
    """Stored bars → the OHLCV frame shape every downstream consumer already
    expects (FR-020), so resampling and indicator code needs no changes."""
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
    """Provider frame → storable rows."""
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

def _fetch(ticker: str, start: date | None, db: Database | None = None) -> pd.DataFrame:
    """Isolated provider call — the seam tests monkeypatch."""
    return fetch_eod_history(ticker, start=start, db=db)


def _load(db: Database, ticker: str) -> dict | None:
    return db[PRICE_HISTORY].find_one({"ticker": ticker}, {"_id": 0})


def get_series(ticker: str, refresh: str = "none", db: Database | None = None):
    """The stored daily series, optionally refreshed first.

    `refresh`:
      "none"  — read only; never contacts the provider. Every reader after the
                first in a pull uses this, which is what makes FR-014/SC-003
                structural rather than a coincidence.
      "delta" — request only what is missing, merge, persist.
      "full"  — rebuild from scratch and replace the stored series.

    Returns `(DataFrame, meta)` where meta carries {requests, bytes, retrieval,
    outcome} for the pull-cost recorder. Never raises on a provider failure:
    stored bars are served with `outcome: "degraded"` (FR-012, Principle IV).
    """
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    doc = _load(db, ticker) or {}
    stored_bars = doc.get("bars") or []
    coverage = doc.get("coverage") or {}

    if refresh == "none":
        return bars_to_frame(stored_bars), {
            "requests": 0, "retrieval": "stored", "outcome": "stored",
        }

    start = None if refresh == "full" else delta_start(coverage, date.today())
    retrieval = "incremental" if start is not None else "full"

    try:
        fetched = _fetch(ticker, start, db=db)
    except FmpBudgetExceededError:
        logger.warning("%s: FMP budget spent — serving stored price history", ticker)
        return bars_to_frame(stored_bars), {
            "requests": 1, "retrieval": retrieval, "outcome": "degraded",
        }
    except Exception as exc:
        # KeyboardInterrupt/SystemExit deliberately excluded: a worker restart
        # mid-refresh must propagate, and the stored series survives untouched
        # because nothing has been written yet (FR-030, SC-013).
        logger.warning("%s: price fetch failed (%s) — serving stored history", ticker, exc)
        return bars_to_frame(stored_bars), {
            "requests": 1, "retrieval": retrieval, "outcome": "degraded",
        }

    fetched_bars = frame_to_bars(fetched)
    if refresh == "full":
        # An empty answer is not evidence the ticker has no history — keep what
        # we hold rather than replacing a good series with nothing.
        merged = fetched_bars or stored_bars
    else:
        merged = merge_bars(stored_bars, fetched_bars)

    # Built entirely in memory; a single atomic document swap follows (FR-030).
    db[PRICE_HISTORY].replace_one(
        {"ticker": ticker},
        {"ticker": ticker, "bars": merged,
         "coverage": build_coverage(merged, coverage, refresh)},
        upsert=True,
    )
    return bars_to_frame(merged), {
        "requests": 1, "retrieval": retrieval, "outcome": "fetched",
    }
