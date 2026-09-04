"""Pure signal derivation + persistence for the `strategy_signals` collection.
Spec: specs/032-weekly-strategy-picks; data-model.md.

Mirrors tools/screener.py's shape (compute_signals -> refresh_all/refresh_one
-> run_..._refresh admin-job entry point), but is a separate collection and a
separate writer — see the STRATEGY_SIGNALS comment in tools/db.py for why it
must not be folded into `screener`'s documents.

compute_signals() is pure (no I/O): given the same `price_data` (a
tools/price.py::get_price_history() dict), it always derives the same
the_strat/gap_analysis blocks. It calls skills/the_strat.py and
skills/gap_analysis.py exactly as crew.py's AnalysisCrew.run() already does
(research.md R3) — no new pattern-detection or scoring logic, only
aggregation of fields those pure skills already compute.
"""
from datetime import datetime, timezone

from pymongo.database import Database

from logging_config import get_logger
from skills import gap_analysis, the_strat
from tools.db import PRICE_HISTORY, STRATEGY_SIGNALS, get_db
from tools.price import get_price_history

logger = get_logger(__name__)

# §9 of gap_analysis_rules.md: "Score >= 3 = act on signal. Score <= 2 = skip
# or paper trade only." — the rule system's own actionability threshold.
GAP_SCORE_THRESHOLD = 3

# Timeframes the_strat.run() checks for Full TFC alignment (daily is
# deliberately excluded from alignment itself — see skills/the_strat.py).
ALIGNMENT_TIMEFRAMES = ("yearly", "quarterly", "monthly", "weekly")
# "This coming week" is the feature's framing, so a weekly trigger is
# preferred; fall back to progressively longer horizons when no weekly
# pattern backs the aligned TFC call.
ENTRY_TIMEFRAME_PREFERENCE = ("weekly", "monthly", "quarterly", "yearly")

# inside_bar_setup is an equilibrium state, not a directional signal (its
# "direction" is "either"). Kicking patterns are directional but the_strat
# rule spec requires "additional intraday signals" to confirm them, which
# this app has no intraday feed to provide (skills/the_strat.py module
# docstring); they also carry no buy_trigger/sell_trigger field, so they
# cannot supply the specific entry price FR-004 requires. Neither counts
# toward alignment strength or supplies an entry price for this feature.
NON_TRIGGER_PATTERNS = {"inside_bar_setup", "kicking_bullish", "kicking_bearish"}

NULL_THE_STRAT = {"direction": None, "pattern": None, "timeframe": None,
                   "entry_price": None, "strength": 0}
NULL_GAP_ANALYSIS = {"direction": None, "score": None, "entry_price": None, "bias": None}


def _matching_pattern(patterns: list[dict], direction: str) -> dict | None:
    for p in patterns:
        if p["name"] in NON_TRIGGER_PATTERNS:
            continue
        if p.get("direction") == direction:
            return p
    return None


def _the_strat_block(strat_out: dict) -> dict:
    tfc = strat_out.get("tfc")
    if not tfc:
        return NULL_THE_STRAT

    if tfc.get("status") == "full_bullish":
        direction = "long"
    elif tfc.get("status") == "full_bearish":
        direction = "short"
    else:
        return NULL_THE_STRAT

    timeframes = strat_out.get("timeframes", {})
    strength = sum(
        1 for tf in ALIGNMENT_TIMEFRAMES
        if _matching_pattern(timeframes.get(tf, {}).get("patterns", []), direction) is not None
    )
    if strength == 0:
        # TFC aligned on candle color alone, no trigger level on any
        # timeframe — FR-012 requires excluding a candidate we can't give a
        # defensible price for, so this is treated the same as no signal.
        return NULL_THE_STRAT

    price_key = "buy_trigger" if direction == "long" else "sell_trigger"
    for tf in ENTRY_TIMEFRAME_PREFERENCE:
        pattern = _matching_pattern(timeframes.get(tf, {}).get("patterns", []), direction)
        if pattern is not None:
            return {
                "direction": direction,
                "pattern": pattern["name"],
                "timeframe": tf,
                "entry_price": round(float(pattern[price_key]), 2),
                "strength": strength,
            }
    return NULL_THE_STRAT  # unreachable given strength > 0; kept as a safe fallback


def _gap_analysis_block(gap_out: dict) -> dict:
    latest = gap_out.get("latest_gap")
    if not latest or latest.get("score", 0) < GAP_SCORE_THRESHOLD:
        return NULL_GAP_ANALYSIS

    direction = "long" if latest["direction"] == "down" else "short"
    return {
        "direction": direction,
        "score": latest["score"],
        "entry_price": latest["reversal_level"],
        "bias": latest.get("bias"),
    }


def compute_signals(ticker: str, price_data: dict, *, now: datetime | None = None) -> dict:
    """Pure: same (ticker, price_data) -> identical output. `price_data` is a
    tools/price.py::get_price_history() dict (daily/weekly/monthly/quarterly/
    yearly OHLCV records) — the same shape crew.py already feeds both skills."""
    now = now or datetime.now(timezone.utc)
    strat_out = the_strat.run(ticker, price_data)
    gap_out = gap_analysis.run(ticker, price_data)

    # data-model.md validation rule: insufficient history (from either skill)
    # forces both blocks to null rather than trusting a half-computed signal.
    insufficient_history = (
        strat_out.get("tfc") is None or gap_out.get("signal") == "insufficient history"
    )

    return {
        "ticker": ticker.upper(),
        "signals_as_of": now,
        "insufficient_history": insufficient_history,
        "the_strat": NULL_THE_STRAT if insufficient_history else _the_strat_block(strat_out),
        "gap_analysis": NULL_GAP_ANALYSIS if insufficient_history else _gap_analysis_block(gap_out),
    }


def refresh_all(db: Database | None = None) -> int:
    """Recomputes and upserts `strategy_signals` for every ticker that has a
    `price_history` document — the same universe screener.refresh_all() uses.
    Single writer, full-document replace keyed on ticker. Returns the number
    of documents written."""
    db = db if db is not None else get_db()

    count = 0
    for row in db[PRICE_HISTORY].find({}, {"ticker": 1}):
        ticker = row["ticker"]
        try:
            price_data = get_price_history(ticker, db=db)
        except Exception as exc:
            logger.warning("strategy_signals: %s price history unavailable (%s), skipping", ticker, exc)
            continue
        doc = compute_signals(ticker, price_data)
        db[STRATEGY_SIGNALS].replace_one({"ticker": doc["ticker"]}, doc, upsert=True)
        count += 1

    logger.info("strategy_signals refresh: wrote %s documents", count)
    return count


def refresh_one(ticker: str, db: Database | None = None) -> dict | None:
    """Recomputes `strategy_signals` for a single ticker. Returns the written
    document, or None if the ticker has no price history yet."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    if db[PRICE_HISTORY].find_one({"ticker": ticker}, {"ticker": 1}) is None:
        return None

    price_data = get_price_history(ticker, db=db)
    doc = compute_signals(ticker, price_data)
    db[STRATEGY_SIGNALS].replace_one({"ticker": ticker}, doc, upsert=True)
    return doc


def run_strategy_signals_refresh(db: Database) -> int:
    """Admin job entry point (tools/admin_jobs.py's JOB_HANDLERS shape:
    handler(db) -> record_count)."""
    return refresh_all(db)
