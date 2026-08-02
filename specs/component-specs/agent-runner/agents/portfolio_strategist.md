# agent-runner/agents/portfolio_strategist.py

## Purpose
The synthesis agent. Reads all sub-reports from every other agent and produces the final unified analysis: overall signal, conviction level, key trends, flags, and the plain-English summary. Also runs the position_management skill to output stop level recommendations.

## CrewAI Agent Definition

```python
Agent(
    role="Portfolio Strategist",
    goal="Synthesize all analyst sub-reports for {ticker} into a final investment thesis and actionable recommendation",
    backstory="You are the chief strategist who integrates technical, fundamental, macro, insider, institutional, and sentiment signals into a coherent view. You weight signals by reliability and recency, call out contradictions, and produce a clear final verdict.",
    tools=[run_position_management_skill, query_db],
    llm=llm,
    allow_delegation=False
)
```

## Task Prompt
```
You have received sub-reports from 7 specialist analysts for {ticker}. Synthesize them:

Sub-reports provided: {technical}, {fundamental}, {macro}, {insider}, {institutional}, {sentiment}, {recommendation}

1. Identify the dominant signal: do most analysts agree, or are there contradictions?
2. Weight signals: insider cluster buying + institutional accumulation + bullish technicals = very high conviction. Macro headwind alone = mild concern unless fundamentals deteriorating.
3. Call out any critical contradictions (e.g., strong technicals but insider selling — flag it).
4. Run position_management skill: generate current stair-step stop levels and trailing stop recommendation.
5. Produce final verdict: signal (bullish/bearish/neutral), conviction (high/medium/low), summary paragraph, key_trends list, flags list.

Return full synthesis JSON.
```

## Signal Weighting Logic
| Signal Type | Weight | Rationale |
|---|---|---|
| Insider cluster buying | Very High | Insiders have information advantage |
| Institutional accumulation | High | Smart money with deep research |
| Technical (multi-timeframe TFC aligned) | High | Price action confirms thesis |
| Fundamental health | High | Underlying business quality |
| Macro | Medium | Broad headwind/tailwind context |
| Earnings sentiment | Medium | Forward-looking but lagging |
| Market flow timing | High | Determines when, not what |

## Output Shape (written to MongoDB `analyses` collection)
```json
{
  "ticker": "AAPL",
  "timestamp": "2025-01-20T15:00:00Z",
  "signal": "bullish",
  "conviction": "high",
  "summary": "AAPL presents a high-conviction long setup...",
  "key_trends": [
    "Cluster insider buying by CEO and CFO in January",
    "Accumulation score 4/5 over 28 days",
    "NYMO oversold bounce developing — favorable timing"
  ],
  "flags": [],
  "position_management": {
    "stair_step_stops": [175.00, 168.00, 160.00],
    "trailing_stop_recommendation": "Use 8% trailing stop from recent high",
    "position_sizing": "full position appropriate given conviction"
  },
  "sub_reports": { ... }
}
```
