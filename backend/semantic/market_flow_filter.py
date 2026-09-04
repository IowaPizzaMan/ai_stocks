"""Market Flow breadth filter for strategy picks (FR-017/FR-018).
Spec: specs/032-weekly-strategy-picks; data-model.md; research.md R1/R4.

Market Flow's own rule spec (specs/market_flow_rules.md) states plainly that
NYMO/NAMO breadth "is not a stock picker" — it's a single market-wide value,
identical for every ticker on a given day, so it can't independently rank a
candidate list the way The Strat and Gap Analysis do. Here it's applied
instead as a read-time filter/caveat over their already-computed lists.

`classify_level` is a small pure port of
agent-runner/skills/market_flow.py::classify_level's thresholds (§1) — not
imported, per the hand-duplication precedent already established for
backend/llm.py and the two services' db.py collection constants (the two
services share no Python package, per constitution Principle V).

No new agent-runner work is needed: `breadth_cache` is already refreshed
daily by agent-runner's breadth_worker and already registered in this
service's db.py, so this module only ever reads it — once per request, via
get_market_condition(), rather than once per strategy.
"""
from pymongo.database import Database

from db import BREADTH_CACHE

# §1 reading thresholds (specs/market_flow_rules.md).
OVERBOUGHT_EXCLUDES_BUYS = ("overbought",)
OVERSOLD_EXCLUDES_SHORTS = ("oversold", "extreme_oversold", "panic")


def classify_level(value: float | None) -> str:
    """Mirrors skills/market_flow.py::classify_level verbatim."""
    if value is None:
        return "unknown"
    if value <= -100:
        return "panic"
    if value <= -80:
        return "extreme_oversold"
    if value <= -60:
        return "oversold"
    if value <= -40:
        return "moderate_oversold"
    if value < 0:
        return "mild_weakness"
    if value <= 20:
        return "neutral"
    if value <= 60:
        return "bullish_momentum"
    return "overbought"


def get_market_condition(db: Database) -> dict:
    """One read of the latest NYSE `breadth_cache` row (FR-018). Callers
    fetch this once per request and reuse it across both strategies' filter
    calls, rather than re-reading breadth per strategy."""
    doc = db[BREADTH_CACHE].find_one({"exchange": "nyse"}, sort=[("date", -1)])
    nymo = doc.get("mcclellan") if doc else None
    return {"nymo": nymo, "level": classify_level(nymo), "available": nymo is not None}


def describe_override(direction: str, condition: dict) -> str | None:
    """Whether the current market-wide reading overrides `direction` this
    week, independent of whether any strategy actually has candidates —
    callers use this for a single top-level note even when every list
    happens to be empty for its own (non-breadth) reasons."""
    if not condition["available"]:
        return None
    level, nymo = condition["level"], condition["nymo"]
    if direction == "buy" and level in OVERBOUGHT_EXCLUDES_BUYS:
        return f"market overbought (NYMO {nymo:+.0f}) — breadth doesn't support new buys this week"
    if direction == "short" and level in OVERSOLD_EXCLUDES_SHORTS:
        return f"market oversold (NYMO {nymo:+.0f}) — breadth doesn't support new shorts this week"
    return None


def apply_filter(candidates: list[dict], direction: str, condition: dict) -> dict:
    """FR-017. Pure given an already-fetched `condition`
    (get_market_condition()'s output) — no Mongo access here. `candidates`:
    a strategy's own ranked list (each item at least
    `{"ticker": ..., "entry_price": ...}`), `direction`: "buy" or "short".

    The reading is market-wide, so the gate is uniform across a direction's
    candidates — Market Flow has no per-ticker signal to distinguish them at
    this level (research.md R1): either the reading overrides that whole
    direction, or it doesn't touch it at all.

    Returns `{"kept": [...], "excluded": [{...candidate, "reason": str}...],
    "note": str | None}`."""
    if not candidates:
        # Nothing to attribute to breadth — FR-007's "strategy had no
        # candidates" is a different reason than this filter's.
        return {"kept": [], "excluded": [], "note": None}

    reason = describe_override(direction, condition)
    if reason is None:
        return {"kept": list(candidates), "excluded": [], "note": None}
    return {"kept": [], "excluded": [{**c, "reason": reason} for c in candidates], "note": reason}
