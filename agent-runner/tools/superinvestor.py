"""Dataroma superinvestor activity via Playwright + LLM extraction.
Spec: specs/component-specs/agent-runner/tools/superinvestor.md

Best-effort source: if Playwright isn't installed (local dev venv) or the
scrape/extraction fails, returns an empty result with `available: False` so
the InstitutionalAnalyst degrades instead of the crew failing. No hardcoded
CSS selectors — page text goes to Ollama for structured extraction.
"""
import random
import time
from datetime import date, datetime, timedelta, timezone

from pymongo.database import Database

from llm import generate_json
from logging_config import get_logger
from tools.db import DATAROMA_META, SUPERINVESTOR_MOVES_CACHE, get_db

logger = get_logger(__name__)

CACHE_DAYS = 7

MOVES_SCHEMA = {
    "type": "object",
    "properties": {
        "moves": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fund": {"type": "string"},
                    "action": {"type": "string", "enum": ["buy", "add", "trim", "sell", "new_position", "exit"]},
                    "ticker": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["fund", "action", "ticker"],
            },
        },
    },
    "required": ["moves"],
}


def _fetch_page_text(url: str) -> str:
    from playwright.sync_api import sync_playwright  # lazy — optional dependency locally

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=45_000)
            text = page.inner_text("body")
        finally:
            browser.close()
    time.sleep(2 + random.random())  # politeness between scrapes
    return text


def _extract_moves(page_text: str, ticker: str | None, client=None) -> list[dict]:
    scope = f"about {ticker}" if ticker else "for every fund move on the page"
    prompt = (
        f"Extract superinvestor portfolio moves {scope} from this Dataroma page text. "
        "Each move has a fund name, an action (buy/add/trim/sell/new_position/exit), a "
        "ticker symbol, and optional detail (share counts, % of portfolio).\n\n"
        f"Page text:\n{page_text[:8000]}"
    )
    result = generate_json(prompt, MOVES_SCHEMA, client=client)
    moves = result.get("moves", [])
    if ticker:
        moves = [m for m in moves if m.get("ticker", "").upper() == ticker.upper()]
    return moves


def _filter_ticker(moves: list[dict], ticker: str) -> list[dict]:
    return [m for m in moves if m.get("ticker", "").upper() == ticker.upper()]


def get_superinvestor_activity(ticker: str, db: Database | None = None, client=None) -> dict:
    """Per-ticker view onto a shared, CACHE_DAYS-old-at-most scrape+extraction
    of the whole Dataroma moves page — the page content and its LLM extraction
    don't depend on which ticker asked, so the scrape only actually runs once
    per week; every ticker in between just filters the cached move list."""
    db = db if db is not None else get_db()
    ticker = ticker.upper()

    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_DAYS)
    cached = db[SUPERINVESTOR_MOVES_CACHE].find_one({"fetched_at": {"$gt": cutoff}})
    if cached:
        return {"moves": _filter_ticker(cached["moves"], ticker), "available": True, "note": None}

    last_pull = db[DATAROMA_META].find_one({"key": "last_pull"})
    last_date = last_pull["date"] if last_pull else "2020-01-01"

    try:
        moves_text = _fetch_page_text(f"https://dataroma.com/m/moves.php?date={last_date}")
        all_moves = _extract_moves(moves_text, ticker=None, client=client)
    except Exception as exc:
        logger.info("superinvestor data unavailable for %s: %s", ticker, exc)
        return {"moves": [], "available": False,
                "note": f"Dataroma scrape unavailable ({type(exc).__name__})"}

    db[DATAROMA_META].replace_one(
        {"key": "last_pull"}, {"key": "last_pull", "date": date.today().isoformat()}, upsert=True
    )
    db[SUPERINVESTOR_MOVES_CACHE].replace_one(
        {}, {"moves": all_moves, "fetched_at": datetime.now(timezone.utc)}, upsert=True
    )
    return {"moves": _filter_ticker(all_moves, ticker), "available": True, "note": None}


def get_recent_superinvestor_moves(since: datetime, client=None) -> list[dict]:
    """Market-wide variant for the Phase 7 flow scanner — extracts every move
    on the page rather than one ticker's."""
    since_str = since.date().isoformat() if isinstance(since, datetime) else str(since)
    try:
        moves_text = _fetch_page_text(f"https://dataroma.com/m/moves.php?date={since_str}")
        return _extract_moves(moves_text, ticker=None, client=client)
    except Exception as exc:
        logger.info("superinvestor moves unavailable: %s", exc)
        return []
