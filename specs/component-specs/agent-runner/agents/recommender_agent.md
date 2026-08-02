# agent-runner/agents/recommender_agent.py

## Purpose
Determines *when* to act on a position — not what to buy, but whether to buy more, hold, trim, or start selling. Uses NYMO/NAMO market breadth readings and gap scores to time entries/exits against market conditions.

## CrewAI Agent Definition

```python
Agent(
    role="Market Timing & Flow Analyst",
    goal="Determine whether current market breadth conditions support adding to, holding, or reducing {ticker}",
    backstory="You specialize in market internals. You use the McClellan Oscillator (NYMO for NYSE, NAMO for NASDAQ) to gauge whether the overall market is oversold (good time to buy more) or overbought (time to be cautious or trim). You also use gap analysis scores stored in MongoDB to identify exhaustion signals.",
    tools=[get_market_breadth, run_market_flow_skill, query_db],
    llm=llm,
    allow_delegation=False
)
```

## Task Prompt
```
Assess market timing conditions for {ticker}:
1. Current NYMO reading: value, trend (rising/falling), is it oversold (<-60), neutral, or overbought (>60)?
2. Current NAMO reading: same assessment.
3. Divergence check: is SPY making a lower low while NYMO makes a higher low (bullish divergence / buy signal)?
4. Exhaustion check: is SPY making a higher high while NYMO makes a lower high (bearish divergence / trim signal)?
5. Gap score from MongoDB: any recent exhaustion gap (bearish) or breakaway gap (bullish) signals for this ticker?
6. Run market_flow skill: apply rules from market_flow_rules.md to produce a recommendation.

Return JSON: nymo_reading, namo_reading, breadth_signal, divergence_detected, gap_score_summary, recommendation (BUY_MORE/HOLD/TRIM/START_SELLING/AVOID_ADD/WATCH), conviction, rationale.
```

## Market Flow Rules (enforced by `skills/market_flow.py`)
See `market_flow_rules.md` for the full rule set. Key signals:
- NYMO < -60 + rising: BUY_MORE opportunity
- SPY double bottom + NYMO higher low: high-conviction BUY_MORE
- NYMO > 60 + exhaustion gap: START_SELLING signal
- NYMO > 80: avoid new adds regardless of ticker quality

## Output Shape
```json
{
  "nymo_reading": { "value": -72, "trend": "rising", "zone": "oversold" },
  "namo_reading": { "value": -68, "trend": "rising", "zone": "oversold" },
  "breadth_signal": "oversold_bounce_developing",
  "divergence_detected": { "type": "bullish", "description": "SPY double bottom + NYMO higher low" },
  "gap_score_summary": { "recent_gaps": ["continuation_gap score:3"], "exhaustion_present": false },
  "recommendation": "BUY_MORE",
  "conviction": "high",
  "rationale": "NYMO deeply oversold at -72 and rising with bullish divergence against SPY double bottom. No exhaustion gap signals. Strong setup for adding."
}
```

## Skills Used
- `skills/market_flow.py` — applies the full rule system
- Gap scores queried directly from MongoDB `analyses` collection (set by TechnicalAnalyst earlier in this run)
