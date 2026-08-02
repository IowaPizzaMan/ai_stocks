"""RecommenderAgent: when to act — narrates the deterministic market_flow verdict.
Spec: specs/component-specs/agent-runner/agents/recommender_agent.md

The recommendation/conviction come verbatim from skills/market_flow.py (the
rule system is authoritative); the LLM contributes the breadth narrative and
a fuller rationale that ties in this ticker's gap picture.
"""
import json

from llm import generate_json

SYSTEM = (
    "You specialize in market internals. You use the McClellan Oscillator (NYMO/NAMO) to "
    "gauge whether the market is oversold (a time to add) or overbought (a time to trim), "
    "and gap signals for exhaustion checks. You explain timing verdicts crisply."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "breadth_signal": {"type": "string"},
        "rationale": {"type": "string"},
        "additional_caveats": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["breadth_signal", "rationale", "additional_caveats"],
}


def run(ticker: str, context: dict, client=None) -> dict:
    """context: {'market_flow': skills/market_flow.run() output,
    'breadth': get_market_breadth() output, 'gap': gap_analysis output}"""
    flow = context["market_flow"]
    breadth = context.get("breadth") or {}
    gap = context.get("gap") or {}

    nymo = breadth.get("nymo") or {}
    namo = breadth.get("namo") or {}
    latest_gap = gap.get("latest_gap")

    prompt = f"""Explain the market-timing picture for {ticker}.

## Rule-system verdict (authoritative — do not change it)
recommendation: {flow.get("recommendation")} | conviction: {flow.get("conviction")}
rule rationale: {flow.get("rationale")}
caveats: {json.dumps(flow.get("caveats", []))}

## Breadth readings
NYMO {nymo.get("current")} (zone {nymo.get("zone")}, trend {nymo.get("trend")});
NAMO {namo.get("current")} (zone {namo.get("zone")}, trend {namo.get("trend")});
divergence: {json.dumps(breadth.get("divergence"))}

## This ticker's latest gap
{json.dumps(latest_gap, default=str)}

1. breadth_signal: one short label for the current breadth regime
   (e.g. "oversold_bounce_developing", "overbought_extension", "no_edge").
2. rationale: 2-4 sentences expanding the rule rationale with the breadth trend and this
   ticker's gap context.
3. additional_caveats: anything the rule caveats missed; empty list if nothing."""

    report = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
    return {
        "nymo_reading": {"value": nymo.get("current"), "trend": nymo.get("trend"),
                         "zone": nymo.get("zone")},
        "namo_reading": {"value": namo.get("current"), "trend": namo.get("trend"),
                         "zone": namo.get("zone")},
        "breadth_signal": report["breadth_signal"],
        "divergence_detected": flow.get("divergence_detected", False),
        "gap_score_summary": {
            "latest_gap": ({"direction": latest_gap.get("direction"),
                            "type": latest_gap.get("gap_type"),
                            "score": latest_gap.get("score")} if latest_gap else None),
            "exhaustion_present": bool(latest_gap and latest_gap.get("gap_type") == "exhaustion"),
        },
        "recommendation": flow.get("recommendation"),
        "conviction": flow.get("conviction"),
        "rationale": report["rationale"],
        "caveats": (flow.get("caveats") or []) + report["additional_caveats"],
        "nymo_signal": flow.get("nymo_signal"),
        "nymo_current": flow.get("nymo_current"),
        "namo_current": flow.get("namo_current"),
    }
