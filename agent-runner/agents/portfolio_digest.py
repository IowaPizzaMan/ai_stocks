"""PortfolioDigest: synthesizes every tracked stock's own AI summary into one
cross-stock overview plus specific guidance on what to look at.
Spec: specs/027-stocks-news-tab-ai-summary

Unlike portfolio_strategist.py (which synthesizes one ticker's sub-reports
into that ticker's verdict), this agent reads across many tickers' already-
computed verdicts — it never reads raw sub-reports and never overrides any
stock's own stored signal/conviction (constitution Principle III).
"""
import json

from llm import generate_json

SYSTEM = (
    "You are a portfolio-level analyst reviewing a set of already-analyzed stocks. "
    "Each stock arrives with its own signal, conviction, summary, key trends, flags, "
    "and news stance — you do not re-derive any of that, you synthesize across it. "
    "You call out what stands out (strong conviction setups, contradictions, notable "
    "flags, sentiment shifts) and tell the reader specifically what to look at, "
    "referencing tickers by name rather than speaking in generalities."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {"type": "string"},
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "signal": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                    "conviction": {"type": "string", "enum": ["high", "medium", "low"]},
                    "note": {"type": "string"},
                },
                "required": ["ticker", "signal", "conviction", "note"],
            },
        },
    },
    "required": ["overview", "highlights"],
}


def run(stocks: list[dict], client=None) -> dict:
    """stocks: condensed entries from tools/portfolio.gather_and_rank —
    {ticker, signal, conviction, summary, key_trends, flags, news_stance}."""
    prompt = f"""Synthesize a cross-stock summary across the following {len(stocks)} \
analyzed stocks.

## Stocks
{json.dumps(stocks, default=str)}

1. overview: 2-4 sentences, plain English, describing the overall picture across this
   set — where conviction concentrates, where signals agree or conflict, and any
   theme worth noticing (e.g. several names flagging the same risk).
2. highlights: for each stock worth calling out specifically (not necessarily all of
   them — skip ones with nothing notable), a short note explaining why it deserves
   attention. Reference concrete details from that stock's summary/flags/news stance
   rather than restating its signal and conviction alone."""

    return generate_json(prompt, SCHEMA, system=SYSTEM, client=client)
