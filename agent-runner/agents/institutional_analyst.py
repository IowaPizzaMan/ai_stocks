"""InstitutionalAnalyst: 13F ownership changes + superinvestor moves.
Spec: specs/component-specs/agent-runner/agents/institutional_analyst.md
"""
import json

from llm import generate_json

SYSTEM = (
    "You track what top hedge funds, mutual funds, and legendary investors are doing "
    "with their holdings. You know that new positions and increases from concentrated, "
    "high-conviction funds signal more than passive index fund inflows."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "notable_increases": {"type": "array", "items": {"type": "string"}},
        "notable_reductions": {"type": "array", "items": {"type": "string"}},
        "superinvestor_read": {"type": "string"},
        "concentration_assessment": {
            "type": "string",
            "enum": ["high_conviction_buyers_present", "mostly_passive_flows",
                     "mixed", "distribution_pattern", "insufficient_data"],
        },
        "overall_institutional_signal": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "narrative": {"type": "string"},
    },
    "required": ["notable_increases", "notable_reductions", "superinvestor_read",
                 "concentration_assessment", "overall_institutional_signal",
                 "confidence", "narrative"],
}


def run(ticker: str, context: dict, client=None) -> dict:
    """context: {'institutional': get_institutional_holdings() output,
    'superinvestor': get_superinvestor_activity() output (may be unavailable)}"""
    inst = context["institutional"]
    superinv = context.get("superinvestor") or {"moves": [], "available": False}

    prompt = f"""Analyze institutional and superinvestor activity for {ticker}.

## Ownership summary (13F-derived, quarterly)
institutional ownership: {inst.get("ownership_pct")}% across {inst.get("institutions_count")} institutions
(insiders hold {inst.get("insiders_pct")}%); of the top-10 holders, {inst.get("top10_increasing")}
increased and {inst.get("top10_decreasing")} decreased last quarter (as of {inst.get("as_of")}).

## Top-10 holders (pctChange is QoQ position change: 1.0 = +100%)
{json.dumps(inst.get("top_holders", []), default=str)}

## Superinvestor moves (Dataroma){"" if superinv.get("available") else " — UNAVAILABLE this run; do not invent any"}
{json.dumps(superinv.get("moves", []), default=str)}

1. notable_increases / notable_reductions: top-10 holders with meaningful QoQ change,
   as "Fund — +12% position" strings; empty lists if nothing meaningful.
2. superinvestor_read: what the moves say (or state that data was unavailable).
3. concentration_assessment: are buyers concentrated high-conviction funds or passive
   index flows? (Blackrock/Vanguard/State Street inflows are mostly passive.)
4. overall_institutional_signal, confidence, and a 2-3 sentence narrative."""

    report = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
    return {
        "institutional_summary": {
            "ownership_pct": inst.get("ownership_pct"),
            "institutions_count": inst.get("institutions_count"),
            "insiders_pct": inst.get("insiders_pct"),
            "top10_increasing": inst.get("top10_increasing"),
            "top10_decreasing": inst.get("top10_decreasing"),
            "as_of": inst.get("as_of"),
        },
        "superinvestor_available": superinv.get("available", False),
        "superinvestor_moves": superinv.get("moves", []),
        **report,
    }
