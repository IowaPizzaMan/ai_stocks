"""TechnicalAnalyst: interprets pre-computed skill outputs + indicators.
Spec: specs/component-specs/agent-runner/agents/technical_analyst.md

The Strat / accumulation / gap math is done deterministically by the skills;
the LLM narrates TFC, range positioning, and the volume story, and calls the
overall signal. One structured-output call, no tool-calling.
"""
import json

from llm import generate_json

SYSTEM = (
    "You are a seasoned technical analyst specializing in price structure (The Strat), "
    "institutional accumulation patterns, and gap behavior. You look for setups where "
    "multiple technical signals align, and you narrate the story behind the numbers "
    "rather than restating them."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "key_levels": {
            "type": "object",
            "properties": {
                "support": {"type": "array", "items": {"type": "number"}},
                "resistance": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["support", "resistance"],
        },
        "momentum_summary": {"type": "string"},
        "tfc_narrative": {"type": "string"},
        "bf_position_narrative": {"type": "string"},
        "volume_narrative": {"type": "string"},
        "overall_technical_signal": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["key_levels", "momentum_summary", "tfc_narrative", "bf_position_narrative",
                 "volume_narrative", "overall_technical_signal", "confidence"],
}

INDICATOR_KEYS = ["Close", "RSI_14", "MACD", "MACD_HIST", "ATR_14", "EMA_21", "EMA_50", "EMA_200"]


def _compact_indicators(records: list[dict], keep: int = 10) -> list[dict]:
    """Last `keep` sessions, only the columns the narrative needs, rounded."""
    out = []
    for row in records[-keep:]:
        compact = {}
        date = row.get("Date") or row.get("date")
        if date is not None:
            compact["date"] = str(date)[:10]
        for key in INDICATOR_KEYS:
            value = row.get(key)
            if value is not None and value == value:  # skip NaN
                compact[key] = round(float(value), 2)
        out.append(compact)
    return out


def run(ticker: str, context: dict, client=None) -> dict:
    """context: {'strat': ..., 'accumulation': ..., 'gap': ..., 'indicators': [...],
    'price_summary': {...}} — all pre-computed by crew.py."""
    strat = context["strat"]
    accumulation = context["accumulation"]
    gap = context["gap"]

    prompt = f"""Analyze the technical picture for {ticker} from the pre-computed data below.

## The Strat skill output (bar types, patterns, Time Frame Continuity)
{json.dumps(strat, default=str)}

## Accumulation-volume skill output
{json.dumps(accumulation, default=str)}

## Gap-analysis skill output (latest gap + PEG status)
{json.dumps({k: gap[k] for k in ("latest_gap", "peg", "r2g_candidate", "signal") if k in gap}, default=str)}

## Recent price / momentum indicators (last sessions)
{json.dumps(_compact_indicators(context.get("indicators", [])), default=str)}

## Price summary
{json.dumps(context.get("price_summary", {}), default=str)}

Write the sub-report:
1. key_levels: pick 1-3 support and 1-3 resistance prices from the recent range and pattern trigger levels.
2. momentum_summary: RSI/MACD/EMA read in one or two sentences.
3. tfc_narrative: is any actionable daily signal reconfirmed or contradicted by weekly/monthly? Call out TFC conflict explicitly and what it means for stop placement.
4. bf_position_narrative: where does price sit in its recent range — near the bottom (potential support/reversal zone), near the top (potential exhaustion/resistance), or mid-range (no edge)? Name what would confirm.
5. volume_narrative: is accumulation early-stage (price still low in range) or later-stage (chase risk)? Flag distribution-after-accumulation rotation if present.
6. overall_technical_signal and confidence."""

    report = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
    return {
        "strat_result": strat,
        "accumulation_result": accumulation,
        "gap_result": {k: gap.get(k) for k in ("latest_gap", "peg", "r2g_candidate", "signal")},
        **report,
    }
