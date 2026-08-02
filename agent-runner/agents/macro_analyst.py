"""MacroAnalyst: contextualizes a ticker in the current macro regime.
Spec: specs/component-specs/agent-runner/agents/macro_analyst.md
"""
import json

from llm import generate_json

SYSTEM = (
    "You track Federal Reserve policy, inflation readings, GDP trends, and yield curve "
    "signals. You translate macro data into sector-specific impact — e.g., how rising "
    "rates hurt growth stocks but help banks."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "inflation_impact": {
            "type": "object",
            "properties": {"trend": {"type": "string", "enum": ["rising", "falling", "stable"]},
                           "impact_on_sector": {"type": "string"}},
            "required": ["trend", "impact_on_sector"],
        },
        "rate_impact": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["hiking", "holding", "cutting"]},
                           "impact_on_valuation": {"type": "string"}},
            "required": ["direction", "impact_on_valuation"],
        },
        "growth_backdrop": {
            "type": "object",
            "properties": {"recession_signal": {"type": "string", "enum": ["none", "mild", "elevated", "strong"]},
                           "commentary": {"type": "string"}},
            "required": ["recession_signal", "commentary"],
        },
        "consumer_backdrop": {"type": "string"},
        "sector_rotation_signal": {"type": "string"},
        "overall_macro_signal": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["inflation_impact", "rate_impact", "growth_backdrop", "consumer_backdrop",
                 "sector_rotation_signal", "overall_macro_signal", "confidence"],
}


def _latest(series: list[dict]) -> float | None:
    return next((o["value"] for o in series or [] if o.get("value") is not None), None)


def _compact(macro: dict, keep: int = 6) -> dict:
    """Newest `keep` non-null observations per series — plenty for trend reads."""
    out = {}
    for series_id, obs in (macro or {}).items():
        vals = [o for o in obs if o.get("value") is not None][:keep]
        out[series_id] = vals
    return out


def run(ticker: str, context: dict, client=None) -> dict:
    """context: {'macro': get_macro_data() output, 'yield_curve':
    get_yield_curve_status() output, 'sector': str | None}"""
    macro = _compact(context.get("macro") or {})
    yield_curve = context.get("yield_curve") or {}
    sector = context.get("sector") or "unknown"

    prompt = f"""Assess the macro environment for {ticker} (sector: {sector}).

## FRED series (newest first; CPIAUCSL/PCEPI are index levels, FEDFUNDS/UNRATE/DGS* are %)
{json.dumps(macro, default=str)}

## Yield curve status (computed)
{json.dumps(yield_curve, default=str)}

1. inflation_impact: is inflation rising/falling/stable and what does that mean for this sector?
2. rate_impact: Fed direction of travel and the valuation impact for this kind of business.
3. growth_backdrop: GDP trend + recession probability from the yield curve spreads.
4. consumer_backdrop: unemployment/sentiment read — mark "not directly relevant" if the
   business isn't consumer-facing.
5. sector_rotation_signal: is this macro regime favoring or rotating away from {sector}?
6. overall_macro_signal and confidence for {ticker} specifically."""

    report = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
    # attach the hard numbers the LLM reasoned from
    report["inflation_impact"]["cpi_latest"] = _latest(macro.get("CPIAUCSL"))
    report["rate_impact"]["fed_funds_rate"] = _latest(macro.get("FEDFUNDS"))
    report["growth_backdrop"]["yield_curve_spread"] = yield_curve.get("10y_2y_spread")
    report["growth_backdrop"]["curve_inverted"] = yield_curve.get("inverted")
    return report
