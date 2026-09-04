"""Strategy picks: "per my trading strategies, what should I buy/short this
week and at what price". Spec: specs/032-weekly-strategy-picks;
contracts/strategy-picks-api.md; data-model.md.

Two Ollama calls, same shape as 031's answer_question() but with a narrower
first-call responsibility: detect() only extracts {direction, count,
named_strategy} from the question — it never sees ticker data and never
decides which stocks appear on a list. compute_picks() is 100% deterministic
Python (FR-008): ranked queries against the precomputed `strategy_signals`
collection, filtered by the Market Flow breadth reading. narrate() composes
prose from that already-final structured result.
"""
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

import llm
from db import STRATEGY_SIGNALS
from logging_config import get_logger
from semantic import condition_filter, market_flow_filter

logger = get_logger(__name__)

DEFAULT_COUNT = 10
MAX_REASONABLE_COUNT = 50  # FR-016 — an unreasonable request (e.g. "top 500") falls back to the default

STRATEGIES = ("the_strat", "gap_analysis")
STRATEGY_LABELS = {"the_strat": "The Strat", "gap_analysis": "Gap Analysis"}
_SORT_FIELD = {"the_strat": "the_strat.strength", "gap_analysis": "gap_analysis.score"}
# API-facing "buy"/"short" -> the stored field values ("long"/"short") on
# each strategy block in data-model.md.
_FIELD_DIRECTION = {"buy": "long", "short": "short"}

DISCLAIMER = "This is informational analysis only, not executed trades or licensed financial advice."

MAX_HISTORY_TURNS = 6  # mirrors chat.py's cap on replayed conversation context

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_strategy_picks": {"type": "boolean"},
        "direction": {"type": ["string", "null"], "enum": ["buy", "short", None]},
        "count": {"type": ["integer", "null"]},
        "named_strategy": {
            "type": ["string", "null"],
            "enum": ["the_strat", "gap_analysis", "market_flow", "unrecognized", None],
        },
        "unrecognized_strategy_text": {"type": ["string", "null"]},
        "extra_conditions": {"type": ["array", "null"], "items": {"type": "string"}},
    },
    "required": [
        "is_strategy_picks", "direction", "count", "named_strategy",
        "unrecognized_strategy_text", "extra_conditions",
    ],
}


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    trimmed = history[-MAX_HISTORY_TURNS:]
    lines = [f"{turn.get('role')}: {turn.get('content')}" for turn in trimmed]
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def _build_intent_system_prompt() -> str:
    return (
        "You classify a user's chat question about stock trading strategies. "
        "This system has exactly two rankable strategies: 'the_strat' (The "
        "Strat, a price-action pattern system) and 'gap_analysis' (Gap "
        "Analysis, a price-gap system). A third concept, 'market_flow' "
        "(NYMO/NAMO market breadth), exists but is NOT an independent "
        "strategy list — when the user asks for Market Flow's own picks, "
        "still set is_strategy_picks true and named_strategy to "
        "'market_flow' so the caller can explain that distinction.\n\n"
        "Set is_strategy_picks true whenever the user is asking what stocks "
        "to buy or short (or add to a portfolio) for the coming week, based "
        "on this system's own trading approach — with or without naming it "
        "explicitly (\"strategy\", \"The Strat\", \"Gap Analysis\", or "
        "\"Market Flow\" need NOT appear). Optionally the question narrows "
        "to one named strategy or asks for a specific count. Use the "
        "conversation history to resolve a follow-up that doesn't restate "
        "the direction or count.\n"
        "Example — is_strategy_picks true even with no strategy keyword: "
        "\"give me 10 stocks to buy and 10 to short\".\n"
        "Example — is_strategy_picks false (an ordinary data-screening "
        "question, not a request for this week's trade picks): \"what "
        "stocks have improving financials\".\n\n"
        "Also extract every additional filtering condition the question "
        "names beyond direction/count/named-strategy, as a list of short "
        "free-text phrases in extra_conditions — do not translate them into "
        "a query yourself, just capture what the user said. A per-ticker "
        "liked/disliked preference (e.g. \"only stocks I've liked\", "
        "\"stocks I've marked as liked\") is one recognized kind of extra "
        "condition; a sector, financial trend, or any other screening "
        "criterion named alongside the strategy-picks request is another. "
        "extra_conditions is null or [] when the question names no such "
        "condition.\n\n"
        'Reply with JSON: {"is_strategy_picks": bool, '
        '"direction": "buy"|"short"|null, "count": integer|null, '
        '"named_strategy": "the_strat"|"gap_analysis"|"market_flow"|'
        '"unrecognized"|null, "unrecognized_strategy_text": string|null, '
        '"extra_conditions": string[]|null}.\n'
        "direction is null only when the user asked for picks without "
        "saying buy or short anywhere in this turn or the recent history. "
        "count is null unless the user specified a number. named_strategy "
        "is 'unrecognized' (with unrecognized_strategy_text set to what "
        "they said) only when they named a specific strategy that isn't "
        "the_strat, gap_analysis, or market_flow."
    )


def detect(question: str, history: list[dict], *, client=None) -> dict:
    """One Ollama call classifying the question and extracting parameters.
    Never sees or returns ticker data — selection stays 100% deterministic
    Python (FR-008). May raise llm.LLMError; callers should treat that the
    same as is_strategy_picks=False rather than failing the whole request."""
    prompt = _format_history(history) + f"Question: {question}"
    return llm.generate_json(
        prompt=prompt,
        schema=INTENT_SCHEMA,
        system=_build_intent_system_prompt(),
        client=client,
        options={"temperature": 0},
    )


def _resolve_count(count) -> int:
    if isinstance(count, bool) or not isinstance(count, int):
        return DEFAULT_COUNT
    if count <= 0 or count > MAX_REASONABLE_COUNT:
        return DEFAULT_COUNT
    return count


def _candidate_from_the_strat(doc: dict) -> dict:
    ts = doc["the_strat"]
    basis = f"{ts['timeframe']} {ts['pattern'].replace('_', ' ')}, strength {ts['strength']}/4"
    return {"ticker": doc["ticker"], "entry_price": ts["entry_price"], "basis": basis}


def _candidate_from_gap_analysis(doc: dict) -> dict:
    ga = doc["gap_analysis"]
    basis = f"{ga['direction']} gap, score {ga['score']}/5 — {ga['bias']}"
    return {"ticker": doc["ticker"], "entry_price": ga["entry_price"], "basis": basis}


_BUILDERS = {"the_strat": _candidate_from_the_strat, "gap_analysis": _candidate_from_gap_analysis}


def _rank_strategy(
    strategy: str, field_direction: str, count: int, db: Database,
    ticker_filter: set[str] | None = None,
) -> list[dict]:
    predicate = {f"{strategy}.direction": field_direction}
    if ticker_filter is not None:
        predicate["ticker"] = {"$in": sorted(ticker_filter)}
    cursor = (
        db[STRATEGY_SIGNALS]
        .find(predicate)
        .sort([(_SORT_FIELD[strategy], DESCENDING), ("ticker", ASCENDING)])
        .limit(count)
    )
    builder = _BUILDERS[strategy]
    return [builder(doc) for doc in cursor]


def compute_picks(
    direction: str, count: int, db: Database, *,
    ticker_filter: set[str] | None = None, condition_label: str | None = None,
) -> dict:
    """Deterministic — never touches the LLM (FR-008). `direction`:
    "buy" | "short". `ticker_filter`, when not None, narrows each strategy's
    Mongo predicate to that ticker set *before* sort/limit (FR-003) — an
    empty (but non-None) set legitimately yields zero candidates (FR-006).
    Returns the structured (pre-narration) result shape from
    contracts/strategy-picks-api.md."""
    field_direction = _FIELD_DIRECTION[direction]
    condition = market_flow_filter.get_market_condition(db)
    market_condition_note = market_flow_filter.describe_override(direction, condition)
    empty_note = (
        f"no candidates currently qualify under {condition_label} this week"
        if ticker_filter is not None else
        "no candidates currently qualify this week"
    )

    lists = []
    excluded_by_market_flow = []
    for strategy in STRATEGIES:
        try:
            raw = _rank_strategy(strategy, field_direction, count, db, ticker_filter)
        except Exception as exc:  # FR-015 — one strategy's failure must not sink the other
            logger.warning("strategy_picks: %s ranking failed: %s", strategy, exc)
            lists.append({
                "strategy": strategy, "strategy_label": STRATEGY_LABELS[strategy],
                "candidates": [], "note": "temporarily unavailable",
            })
            continue

        if not raw:
            lists.append({
                "strategy": strategy, "strategy_label": STRATEGY_LABELS[strategy],
                "candidates": [], "note": empty_note,
            })
            continue

        filtered = market_flow_filter.apply_filter(raw, direction, condition)
        for item in filtered["excluded"]:
            excluded_by_market_flow.append({**item, "strategy": strategy})
        lists.append({
            "strategy": strategy, "strategy_label": STRATEGY_LABELS[strategy],
            "candidates": filtered["kept"], "note": filtered["note"],
        })

    return {
        "direction": direction,
        "count_requested": count,
        "week_of": datetime.now(timezone.utc).date().isoformat(),
        "market_condition_note": market_condition_note,
        "market_condition_unavailable": not condition["available"],
        "lists": lists,
        "excluded_by_market_flow": excluded_by_market_flow,
    }


def _format_narration_prompt(question: str, picks: dict, criteria: list[dict] | None = None) -> str:
    lines = [f"User asked: {question}", f"Direction: {picks['direction']}",
              f"Week of: {picks['week_of']}"]
    condition_requested = picks.get("condition_requested")
    if condition_requested:
        if picks.get("condition_applied"):
            crit_text = "; ".join(c["label"] for c in (criteria or [])) or condition_requested
            lines.append(f"Extra condition applied: {crit_text}")
            if picks.get("condition_note"):
                lines.append(f"Interpretation note: {picks['condition_note']}")
        else:
            lines.append(
                "Extra condition could NOT be applied: "
                f"{picks.get('condition_note') or condition_requested}"
            )
    if picks["market_condition_unavailable"]:
        lines.append("Market-condition (breadth) data was unavailable — no filter was applied.")
    elif picks["market_condition_note"]:
        lines.append(f"Market condition note: {picks['market_condition_note']}")
    for entry in picks["lists"]:
        lines.append(f"\n{entry['strategy_label']} candidates:")
        if entry["candidates"]:
            for c in entry["candidates"]:
                lines.append(f"  - {c['ticker']} at {c['entry_price']} ({c['basis']})")
        else:
            lines.append(f"  (none — {entry['note']})")
    if picks["excluded_by_market_flow"]:
        lines.append("\nExcluded by market condition:")
        for item in picks["excluded_by_market_flow"]:
            lines.append(f"  - {item['ticker']} ({STRATEGY_LABELS[item['strategy']]}): {item['reason']}")
    return (
        "\n".join(lines)
        + "\n\nWrite a thorough, detailed natural-language answer using exactly the tickers, "
          "prices, and reasons above — do not add, remove, or reorder any candidate, and do "
          "not invent numbers not given here. Group by strategy, and for each candidate expand "
          "on its stated basis/reason rather than just listing it. If a strategy has no "
          "candidates, say so plainly using its stated reason. If anything was excluded by "
          "market condition, mention it and explain why. If an extra condition was applied, "
          "state plainly what it was. If an extra condition could not be applied, say so "
          "plainly and explain why, then still answer using the results computed without it. "
          "End with this exact disclaimer sentence: " + DISCLAIMER
    )


def _fallback_narration(picks: dict) -> str:
    """Used only if the narration call itself fails — the data is real, only
    the prose is templated (mirrors chat.py's _fallback_answer)."""
    parts = []
    for entry in picks["lists"]:
        if entry["candidates"]:
            names = ", ".join(f"{c['ticker']} at {c['entry_price']}" for c in entry["candidates"])
            parts.append(f"{entry['strategy_label']}: {names}")
        else:
            parts.append(f"{entry['strategy_label']}: {entry['note']}")
    body = "; ".join(parts) + ". " + DISCLAIMER

    condition_requested = picks.get("condition_requested")
    if not condition_requested:
        return body
    if picks.get("condition_applied"):
        return f"Using {condition_requested}: {body}"
    note = picks.get("condition_note") or f"couldn't apply \"{condition_requested}\""
    return f"Note: {note} {body}"


def narrate(question: str, picks: dict, *, client=None, criteria: list[dict] | None = None) -> str:
    try:
        return llm.generate_text(
            prompt=_format_narration_prompt(question, picks, criteria),
            client=client,
            options={"temperature": 0.2},
        )
    except llm.LLMError as exc:
        logger.warning("strategy_picks narration failed, using fallback: %s", exc)
        return _fallback_narration(picks)


_SUPPORTED_STRATEGIES_TEXT = "The Strat and Gap Analysis"


def answer_strategy_picks(
    question: str, history: list[dict], db: Database, *, client=None, intent: dict | None = None,
) -> dict:
    """Orchestrates detect() -> compute_picks() -> narrate() into the full
    chat response shape (contracts/strategy-picks-api.md), including 031's
    base fields so existing response consumers are unaffected (FR-011).
    `intent`: a pre-computed detect() result from a caller that already ran
    it to decide whether to dispatch here (chat.py) — avoids a second,
    identical Ollama call. When None, detect() is called here."""
    if intent is None:
        intent = detect(question, history, client=client)

    def _base(answer: str) -> dict:
        return {
            "answer": answer, "criteria": [], "match_count": 0, "rows": [],
            "generated_query": None, "excluded_for_missing_data": 0,
            "signals_as_of": None, "degraded": False, "note": None,
            "strategy_picks": None,
            # 035-chat-and-news-upgrade — additive field; strategy-picks
            # answers never cite news.
            "citations": [],
        }

    named = intent.get("named_strategy")
    if named == "market_flow":  # FR-019
        return _base(
            "Market Flow isn't one of your independent strategy picks lists — it's "
            "applied as a market-condition filter across " + _SUPPORTED_STRATEGIES_TEXT +
            "'s own picks, not a standalone list of its own."
        )
    if named == "unrecognized":  # FR-013
        raw = intent.get("unrecognized_strategy_text") or "that strategy"
        return _base(
            f"I don't recognize \"{raw}\" as one of your trading strategies. "
            f"I can give you picks from {_SUPPORTED_STRATEGIES_TEXT}."
        )

    direction = intent.get("direction") or "buy"
    count = _resolve_count(intent.get("count"))

    # 033-strategy-picks-filters — a strategy-picks question may also name
    # extra conditions (liked/disliked, sector, financial trend, etc.) that
    # narrow each strategy's candidate universe before ranking (FR-002-004).
    extra_conditions = intent.get("extra_conditions") or []
    condition_requested = "; ".join(extra_conditions) if extra_conditions else None
    condition_applied = False
    condition_note = None
    criteria: list[dict] = []
    ticker_filter: set[str] | None = None
    if extra_conditions:
        result = condition_filter.translate_conditions(extra_conditions, db, client=client)
        condition_applied = result["applied"]
        condition_note = result["note"]
        criteria = result["criteria"]
        if result["applied"]:
            ticker_filter = result["tickers"]

    picks = compute_picks(
        direction, count, db, ticker_filter=ticker_filter, condition_label=condition_requested,
    )
    picks["condition_requested"] = condition_requested
    picks["condition_applied"] = condition_applied
    picks["condition_note"] = condition_note

    if named in STRATEGIES:  # US3 follow-up narrowing, e.g. "just show me the Gap Analysis ones"
        picks["lists"] = [entry for entry in picks["lists"] if entry["strategy"] == named]
        picks["excluded_by_market_flow"] = [
            item for item in picks["excluded_by_market_flow"] if item["strategy"] == named
        ]

    answer = narrate(question, picks, client=client, criteria=criteria)

    match_count = sum(len(entry["candidates"]) for entry in picks["lists"])
    response = _base(answer)
    response["match_count"] = match_count
    response["strategy_picks"] = picks
    response["criteria"] = criteria
    return response
