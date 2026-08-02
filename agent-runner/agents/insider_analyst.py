"""InsiderAnalyst: Form 4 cluster signals and insider conviction.
Spec: specs/component-specs/agent-runner/agents/insider_analyst.md

Cluster detection and net direction are computed deterministically in
tools/insider.py; the LLM weighs who is buying and how unusual it is.
"""
import json

from llm import generate_json

SYSTEM = (
    "You specialize in SEC Form 4 filings. You know the difference between a routine "
    "option exercise and an open-market purchase that signals real conviction. You look "
    "for cluster buying — multiple insiders buying near the same time — as the "
    "highest-conviction signal. CEO/CFO purchases carry more weight than director buys."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "key_buyers": {"type": "array", "items": {"type": "string"}},
        "mspr_trend": {
            "type": "object",
            "properties": {"direction": {"type": "string",
                                         "enum": ["sharply_positive", "positive", "flat",
                                                  "negative", "sharply_negative"]},
                           "commentary": {"type": "string"}},
            "required": ["direction", "commentary"],
        },
        "unusual_size": {"type": "string"},
        "signal_strength": {"type": "string", "enum": ["strong", "moderate", "weak", "none"]},
        "overall_insider_signal": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "narrative": {"type": "string"},
    },
    "required": ["key_buyers", "mspr_trend", "unusual_size", "signal_strength",
                 "overall_insider_signal", "confidence", "narrative"],
}


def run(ticker: str, context: dict, client=None) -> dict:
    """context: {'insider': tools/insider.get_insider_activity() output}"""
    insider = context["insider"]
    transactions = insider.get("transactions", [])[:15]

    prompt = f"""Analyze insider activity for {ticker} (last 90 days).

## Normalized transactions (open-market purchases are the conviction signal)
{json.dumps(transactions, default=str)}

## Pre-computed signals
cluster_signal: {json.dumps(insider.get("cluster_signal"))}
net_direction: {insider.get("net_direction")}
open_market_buy_value: {insider.get("open_market_buy_value")}
open_market_sell_value: {insider.get("open_market_sell_value")}

## MSPR monthly insider sentiment ratio (positive = insiders net-buying)
{json.dumps(insider.get("mspr_monthly", []), default=str)}

1. key_buyers: notable open-market purchasers with role and size ("Jane Doe (CEO) — $920k
   open market"); empty list if none.
2. mspr_trend: direction over the available months with a one-line read.
3. unusual_size: any transaction dramatically larger than the others? ("none" if not)
4. signal_strength, overall_insider_signal, confidence — remember sales for tax/option
   reasons are weak evidence; open-market buys are strong evidence.
5. narrative: 2-3 sentences tying it together."""

    report = generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
    return {
        "recent_transactions": transactions,
        "cluster_signal": insider.get("cluster_signal"),
        "net_direction": insider.get("net_direction"),
        **report,
    }
