"""EarningsScanner: scores and ranks upcoming earnings candidates.
Spec: specs/component-specs/agent-runner/agents/earnings_scanner.md

The composite score is fully deterministic Python (weights below, per spec);
the LLM only writes the one-line thesis for the top candidates — and a thesis
is never worth failing a scan over, so LLM errors degrade to a templated line.

Peak weeks pre-screen 900+ companies (live count 2026-08-02), so enrichment is
capped at MAX_CANDIDATES by market cap — every screened company still lands in
the scan doc's total_screened.
"""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf

from llm import generate_json
from logging_config import get_logger
from tools import earnings_calendar as calendar_tool
from tools import insider as insider_tool
from tools import price as price_tool

logger = get_logger(__name__)

MAX_CANDIDATES = 40   # enrichment cap: ~2 Finnhub + ~4 yfinance calls each
TOP_COUNT = 10        # candidates that get an LLM-written thesis
MOVE_CAP_PCT = 15.0   # avg abs move is normalized against this ceiling
FETCH_WORKERS = 6
FETCH_TIMEOUT_S = 300  # finnhub pacing serializes calls — generous per-future cap

SYSTEM = (
    "You analyze upcoming earnings events to find the highest-potential setups. You look "
    "for companies with a history of large post-earnings moves, analysts raising estimates "
    "into the print, and insider buying in the weeks before — signals that suggest "
    "conviction ahead of a catalyst."
)

THESES_SCHEMA = {
    "type": "object",
    "properties": {
        "theses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "one_line_thesis": {"type": "string"},
                },
                "required": ["ticker", "one_line_thesis"],
            },
        },
    },
    "required": ["theses"],
}


def _eps_revision_direction(ticker: str) -> str:
    """Have analysts raised or lowered current-quarter estimates recently?"""
    try:
        rev = yf.Ticker(ticker).get_eps_revisions()
        if rev is None or rev.empty:
            return "flat"
        row = rev.loc["0q"] if "0q" in rev.index else rev.iloc[0]
        up = sum(float(v) for k, v in row.items()
                 if "uplast" in k.lower() and not pd.isna(v))
        down = sum(float(v) for k, v in row.items()
                   if "downlast" in k.lower() and not pd.isna(v))
    except Exception as exc:
        logger.info("eps revisions unavailable for %s: %s", ticker, exc)
        return "flat"
    if up > down:
        return "up"
    if down > up:
        return "down"
    return "flat"


def _insider_signal(insider: dict) -> str:
    if insider.get("cluster_signal", {}).get("detected"):
        return "cluster"
    if any(t["transaction_type"] == "purchase" and t["is_open_market"]
           for t in insider.get("transactions", [])):
        return "single"
    return "none"


def _fetch_candidate_data(candidate: dict, db=None) -> dict:
    """Enrich one calendar entry with the four scoring inputs."""
    ticker = candidate["ticker"]
    history = calendar_tool.get_earnings_history(ticker, db=db)
    insider = insider_tool.get_insider_activity(ticker)
    accumulation = price_tool.get_accumulation_score(ticker)
    return {
        **candidate,
        "avg_abs_move_pct": history["avg_abs_move_pct"],
        "beat_rate": history["beat_rate"],
        "history_quarters": history["num_quarters"],
        "eps_revision": _eps_revision_direction(ticker),
        "insider_signal": _insider_signal(insider),
        "accumulation_score": accumulation["accumulation_score"],
    }


def score_candidate(enriched: dict) -> tuple[int, dict]:
    """Composite 0-100 score per the spec's weights."""
    move_pts = min(enriched["avg_abs_move_pct"], MOVE_CAP_PCT) / MOVE_CAP_PCT * 25
    beat_pts = enriched["beat_rate"] * 20
    revision_pts = {"up": 20, "flat": 10, "down": 0}[enriched["eps_revision"]]
    insider_pts = {"cluster": 20, "single": 10, "none": 0}[enriched["insider_signal"]]
    accumulation_pts = enriched["accumulation_score"] / 5 * 15
    breakdown = {
        "move_pts": round(move_pts, 1),
        "beat_pts": round(beat_pts, 1),
        "revision_pts": revision_pts,
        "insider_pts": insider_pts,
        "accumulation_pts": round(accumulation_pts, 1),
    }
    return round(sum(breakdown.values())), breakdown


def _fallback_thesis(c: dict) -> str:
    return (f"{c['ticker']}: {c['avg_abs_move_pct']}% avg move, "
            f"{round(c['beat_rate'] * 100)}% beat rate, revisions {c['eps_revision']}, "
            f"insider {c['insider_signal']}, accumulation {c['accumulation_score']}/5")


def _add_theses(ranked: list[dict], client=None) -> None:
    """LLM one-liners for the top candidates; templated lines for the rest."""
    for c in ranked:
        c["one_line_thesis"] = _fallback_thesis(c)

    top = ranked[:TOP_COUNT]
    if not top:
        return
    lines = "\n".join(
        f"- {c['ticker']} ({c['company']}, {c['sector']}): reports {c['report_date']} "
        f"{c['report_time']}, score {c['score']}, avg abs move {c['avg_abs_move_pct']}%, "
        f"beat rate {c['beat_rate']}, EPS revisions {c['eps_revision']}, "
        f"insider {c['insider_signal']}, accumulation {c['accumulation_score']}/5"
        for c in top
    )
    prompt = f"""These are the top-ranked earnings setups for the coming days:

{lines}

Write one punchy thesis line per ticker (max ~140 chars) citing its standout
numbers, e.g. "NVDA: 9.2% avg move, analysts raising into the print, CEO bought $1M".
Return one entry per ticker, same tickers as above."""

    try:
        result = generate_json(prompt, THESES_SCHEMA, system=SYSTEM, client=client)
        theses = {t["ticker"].upper(): t["one_line_thesis"] for t in result["theses"]}
        for c in top:
            if theses.get(c["ticker"]):
                c["one_line_thesis"] = theses[c["ticker"]]
    except Exception as exc:
        logger.warning("thesis generation failed — keeping templated lines: %s", exc)


def run_scan(days_ahead: int = 7, db=None, client=None) -> dict:
    """Full sweep: calendar → cap-ranked enrichment → deterministic scoring → theses."""
    calendar = calendar_tool.get_earnings_calendar(days_ahead=days_ahead, db=db)
    pool_candidates = sorted(calendar, key=lambda c: c.get("market_cap") or 0,
                             reverse=True)[:MAX_CANDIDATES]
    logger.info("earnings scan: %s screened, enriching top %s by market cap",
                len(calendar), len(pool_candidates))

    enriched = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {c["ticker"]: pool.submit(_fetch_candidate_data, c, db)
                   for c in pool_candidates}
        for ticker, future in futures.items():
            try:
                enriched.append(future.result(timeout=FETCH_TIMEOUT_S))
            except Exception as exc:
                logger.warning("failed to enrich %s: %s", ticker, exc)

    ranked = []
    for e in enriched:
        score, breakdown = score_candidate(e)
        ranked.append({
            "ticker": e["ticker"],
            "company": e["company"],
            "report_date": e["report_date"],
            "report_time": e["report_time"],
            "sector": e["sector"],
            "market_cap": e["market_cap"],
            "score": score,
            "score_breakdown": breakdown,
            "avg_abs_move_pct": e["avg_abs_move_pct"],
            "beat_rate": e["beat_rate"],
            "history_quarters": e["history_quarters"],
            "eps_revision": e["eps_revision"],
            "insider_signal": e["insider_signal"],
            "accumulation_score": e["accumulation_score"],
        })
    ranked.sort(key=lambda c: c["score"], reverse=True)
    _add_theses(ranked, client=client)

    return {
        "candidates": ranked,
        "total_screened": len(calendar),
        "scored_count": len(ranked),
        "top_count": min(TOP_COUNT, len(ranked)),
    }
