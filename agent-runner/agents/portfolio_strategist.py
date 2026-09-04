"""PortfolioStrategist: synthesizes all sub-reports into the final verdict.
Spec: specs/component-specs/agent-runner/agents/portfolio_strategist.md

Stair-step stop levels come deterministically from recent session lows
(position_management's method); the LLM weighs the sub-reports, calls out
contradictions, and produces the final signal/summary/flags.

037-stocks-conviction-and-activity: `conviction` is NO LONGER part of this
agent's job. It used to be a free-form LLM judgement here, which is exactly
the failure mode Constitution Principle III warns about — a small local
model with no calibration pressure saturated at "high" for nearly every
ticker (the "everything is a 3" bug). The rating is now computed
deterministically by skills/conviction.py and OVERWRITES whatever this
function returns (crew.py never reads this agent's conviction — there isn't
one). Do not re-add a `conviction` field to SCHEMA/the prompt/the return dict.
"""
import json

from llm import generate_json

STOP_BUFFER = 0.15

SYSTEM = (
    "You are the chief strategist who integrates technical, fundamental, and market-timing "
    "signals into a coherent view. You weight signals by reliability and recency "
    "(institutional accumulation and multi-timeframe technical alignment are high weight), "
    "call out contradictions explicitly, and produce a clear final verdict."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "signal": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "summary": {"type": "string"},
        "key_trends": {"type": "array", "items": {"type": "string"}},
        "flags": {"type": "array", "items": {"type": "string"}},
        "position_sizing": {"type": "string"},
        "trailing_stop_recommendation": {"type": "string"},
    },
    "required": ["signal", "summary", "key_trends", "flags",
                 "position_sizing", "trailing_stop_recommendation"],
}


def stair_step_stops(recent_lows: list[float], buffer: float = STOP_BUFFER) -> list[float]:
    """Stop ladder from the last few session lows (newest first), each minus a
    small buffer — the levels a stair-step trail would walk through."""
    lows = [round(low - buffer, 2) for low in recent_lows[-3:]]
    return sorted(set(lows), reverse=True)


def run(ticker: str, sub_reports: dict, recent_lows: list[float] | None = None,
        client=None) -> dict:
    """sub_reports: {'technical': ..., 'fundamental': ..., 'recommendation': ...}
    recent_lows: last few daily session lows (oldest→newest) for the stop ladder."""
    stops = stair_step_stops(recent_lows or [])

    # Trim bulky raw arrays out of what the synthesizer reads — it needs the
    # assessments, not the chartable series or transaction dumps.
    bulky = {"strat_result", "gaps", "recent_transactions", "top_holders",
             "fund_holders", "superinvestor_moves", "mspr_monthly"}
    compact = {}
    for name, report in sub_reports.items():
        if isinstance(report, dict):
            compact[name] = {k: v for k, v in report.items()
                             if not str(k).startswith("history") and k not in bulky}
        else:
            compact[name] = report

    prompt = f"""Synthesize the analyst sub-reports for {ticker} into a final verdict.

## Sub-reports
{json.dumps(compact, default=str)}

## Current stair-step stop ladder (from recent session lows)
{json.dumps(stops)}

1. Identify the dominant signal — do the analysts agree, or contradict? Conviction is
   computed separately by a deterministic rule engine, not by you — do not attempt to
   rate it.
2. flags: list any critical contradictions (e.g., strong technicals but distribution
   volume) — empty list if none.
3. key_trends: 2-4 short bullets of the most decision-relevant findings.
4. summary: one paragraph, plain English, referencing the strongest evidence.
5. position_sizing: e.g. "full position", "half size until TFC confirms", "no position".
6. trailing_stop_recommendation: how to trail given volatility and structure."""

    verdict = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
    return {
        "signal": verdict["signal"],
        "summary": verdict["summary"],
        "key_trends": verdict["key_trends"],
        "flags": verdict["flags"],
        "position_management": {
            "stair_step_stops": stops,
            "trailing_stop_recommendation": verdict["trailing_stop_recommendation"],
            "position_sizing": verdict["position_sizing"],
        },
    }
