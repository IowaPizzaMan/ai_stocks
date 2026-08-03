"""InstitutionalFlowScanner: market-wide 13F/superinvestor moves as feed events.
Spec: specs/component-specs/agent-runner/agents/institutional_flow_scanner.md

Per the Phase 3 decision, classification and notability scoring are
deterministic Python — the LLM only rewrites headlines for the top events,
and a headline is never worth failing a scan over (templated fallback).

Inputs come from the worker (institutional_flow_worker.py), not fetched here:
- dataroma_moves: tools/superinvestor.get_recent_superinvestor_moves() output
  ({fund, action, ticker, detail} dicts; action in buy/add/trim/sell/
  new_position/exit)
- filing_changes: tools/institutional.get_recent_13f_changes() output
  (yfinance top-holder rows with Holder/Shares/Value/pctChange/Date Reported
  plus the ticker)
"""
import re
from datetime import datetime, timezone

from llm import generate_json
from logging_config import get_logger

logger = get_logger(__name__)

TOP_HEADLINES = 15  # events that get an LLM-written headline per scan

# Ticker sanity filter — LLM extraction from Dataroma page text can produce junk
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

# Dataroma action vocabulary → the feed's four actions. "buy" is ambiguous on
# moves.php (covers both opens and additions) — mapped to "add" as the
# conservative read; "sell" likewise maps to "trim" unless flagged as an exit.
ACTION_MAP = {
    "new_position": "new_position",
    "buy": "add",
    "add": "add",
    "trim": "trim",
    "sell": "trim",
    "exit": "exit",
}

BASE_SCORE = {"new_position": 60, "exit": 55, "add": 45, "trim": 30}

# Fund-name substrings, lowercased. Passive/index vehicles are low notability;
# a short list of famously concentrated funds gets a 13F boost (every Dataroma
# move is a tracked superinvestor already, so the source bonus covers those).
PASSIVE_FUNDS = (
    "vanguard", "blackrock", "state street", "geode", "index", "ishares",
    "schwab", "northern trust", "fmr", "fidelity", "t. rowe",
)
HIGH_CONVICTION_FUNDS = (
    "berkshire", "pershing square", "scion", "appaloosa", "baupost",
    "third point", "greenlight", "icahn", "duquesne", "himalaya",
)

HEADLINES_SCHEMA = {
    "type": "object",
    "properties": {
        "headlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "headline": {"type": "string"},
                },
                "required": ["index", "headline"],
            },
        },
    },
    "required": ["headlines"],
}

SYSTEM = (
    "You watch 13F filings and superinvestor portfolio changes the moment they post. "
    "You write tight, feed-readable headlines that separate real conviction signals "
    "from passive index rebalancing."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_passive(fund: str) -> bool:
    f = fund.lower()
    return any(name in f for name in PASSIVE_FUNDS)


def _is_high_conviction(fund: str) -> bool:
    f = fund.lower()
    return any(name in f for name in HIGH_CONVICTION_FUNDS)


def _score(action: str, source: str, fund: str, pct_change: float | None) -> int:
    score = BASE_SCORE[action]
    if source == "dataroma":
        score += 25  # every Dataroma fund is a tracked superinvestor
    if _is_passive(fund):
        score -= 30
    elif source == "13F" and _is_high_conviction(fund):
        score += 15
    if pct_change is not None:  # QoQ position change, 1.0 = +100%
        score += min(20, round(abs(pct_change) * 40))
    return max(5, min(99, score))


def _fmt_value(value_usd: float) -> str:
    if value_usd >= 1e9:
        return f"${value_usd / 1e9:.1f}B"
    return f"${value_usd / 1e6:.0f}M"


def _template_headline(e: dict) -> str:
    fund, ticker = e["fund"], e["ticker"]
    pct = e.get("pct_change")
    pos = f" (position now {_fmt_value(e['value_usd'])})" if e.get("value_usd") else ""
    if e["action"] == "new_position":
        return f"{fund} opened a new position in {ticker}{pos}"
    if e["action"] == "exit":
        return f"{fund} exited its {ticker} position"
    if e["action"] == "add":
        qoq = f" by {abs(pct) * 100:.0f}% QoQ" if pct else ""
        return f"{fund} added to its {ticker} position{qoq}{pos}"
    qoq = f" by {abs(pct) * 100:.0f}% QoQ" if pct else ""
    return f"{fund} trimmed its {ticker} stake{qoq}{pos}"


def _dataroma_event(move: dict, now: datetime) -> dict | None:
    ticker = str(move.get("ticker", "")).upper().strip()
    action = ACTION_MAP.get(str(move.get("action", "")).lower())
    fund = str(move.get("fund", "")).strip()
    if not fund or not action or not TICKER_RE.match(ticker):
        return None
    return {
        "fund": fund,
        "ticker": ticker,
        "action": action,
        "shares": None,
        "value_usd": None,
        "pct_of_portfolio": None,
        "pct_change": None,
        "detail": move.get("detail") or None,
        "notability_score": _score(action, "dataroma", fund, None),
        "source": "dataroma",
        # moves.php text rarely carries a parseable date — scan time stands in
        "filed_at": now,
    }


def _filing_event(row: dict) -> dict | None:
    ticker = str(row.get("ticker", "")).upper().strip()
    fund = str(row.get("Holder", "")).strip()
    pct_change = row.get("pctChange")
    if not fund or pct_change in (None, 0) or not TICKER_RE.match(ticker):
        return None
    pct_change = float(pct_change)
    if pct_change > 0:
        action = "add"
    elif pct_change <= -0.95:
        action = "exit"
    else:
        action = "trim"

    reported = str(row.get("Date Reported") or "")
    try:
        filed_at = datetime.strptime(reported, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None  # no filing date, no stable identity for dedup

    shares = row.get("Shares")
    value = row.get("Value")
    return {
        "fund": fund,
        "ticker": ticker,
        "action": action,
        # yfinance rows carry the *current* position, not the traded delta
        "shares": int(shares) if shares else None,
        "value_usd": float(value) if value else None,
        "pct_of_portfolio": None,
        "pct_change": round(pct_change, 4),
        "detail": None,
        "notability_score": _score(action, "13F", fund, pct_change),
        "source": "13F",
        "filed_at": filed_at,
    }


def _polish_headlines(events: list[dict], client=None) -> None:
    """LLM headlines for the top events by notability; templates for the rest."""
    for e in events:
        e["headline"] = _template_headline(e)

    top = events[:TOP_HEADLINES]
    if not top:
        return
    lines = "\n".join(
        f"{i}: {e['fund']} | {e['action']} | {e['ticker']} | "
        f"QoQ change {e['pct_change']} | position value {e['value_usd']} | "
        f"detail: {e.get('detail') or '-'} | source {e['source']}"
        for i, e in enumerate(top)
    )
    prompt = f"""These are today's most notable institutional/superinvestor moves:

{lines}

Write one feed-readable headline per move (max ~90 chars), e.g.
"Pershing Square opened a new $220M position in GOOGL". State only what the
data shows — never invent share counts or dollar amounts that aren't given.
Return one entry per index, same indices as above."""

    try:
        result = generate_json(prompt, HEADLINES_SCHEMA, system=SYSTEM, client=client)
        for h in result["headlines"]:
            i = h.get("index")
            if isinstance(i, int) and 0 <= i < len(top) and h.get("headline"):
                top[i]["headline"] = h["headline"].strip()
    except Exception as exc:
        logger.warning("headline generation failed — keeping templated lines: %s", exc)


def run(dataroma_moves: list[dict], filing_changes: list[dict],
        client=None, now: datetime | None = None) -> list[dict]:
    """Turn raw tool output into feed-ready events, most notable first."""
    now = now or _utcnow()
    events: list[dict] = []
    for move in dataroma_moves or []:
        e = _dataroma_event(move, now)
        if e:
            events.append(e)
    for row in filing_changes or []:
        e = _filing_event(row)
        if e:
            events.append(e)

    events.sort(key=lambda e: e["notability_score"], reverse=True)
    _polish_headlines(events, client=client)
    logger.info("flow scan built %s events (%s dataroma, %s 13F)",
                len(events),
                sum(1 for e in events if e["source"] == "dataroma"),
                sum(1 for e in events if e["source"] == "13F"))
    return events
