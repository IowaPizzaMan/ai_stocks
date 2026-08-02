# agent-runner/agents/institutional_analyst.md

## Purpose
Tracks institutional ownership changes via 13F filings and superinvestor activity from Dataroma. Identifies whether smart money is accumulating, holding, or exiting a position.

## CrewAI Agent Definition

```python
Agent(
    role="Institutional Holdings Analyst",
    goal="Determine institutional and superinvestor conviction in {ticker} based on 13F changes and portfolio moves",
    backstory="You track what top hedge funds, mutual funds, and legendary investors are doing with their holdings. You know that new positions and increases from concentrated, high-conviction funds signal more than passive index fund inflows.",
    tools=[get_institutional_holdings, get_superinvestor_activity],
    llm=llm,
    allow_delegation=False
)
```

## Task Prompt
```
Analyze institutional and superinvestor activity for {ticker}:
1. 13F ownership: total institutional ownership %, QoQ change, # institutions increasing vs. decreasing.
2. New positions: any new entries from notable funds this quarter?
3. Exits: any full exits from major holders?
4. Superinvestor overlap: how many superinvestors tracked on Dataroma hold this ticker?
5. Recent superinvestor moves: adds, trims, or new positions in last quarter.
6. Concentration: are the buyers high-conviction concentrated funds (e.g., Pershing, Ackman) or passive index funds?

Return JSON: institutional_summary, notable_new_positions, notable_exits, superinvestor_count, superinvestor_moves, concentration_assessment, overall_institutional_signal, confidence.
```

## Data Sources
- FMP `v3/form-thirteen` for 13F holdings
- `tools/superinvestor.py` scrapes Dataroma via Playwright
- Fallback: SEC EDGAR 13F-HR filings

## Output Shape
```json
{
  "institutional_summary": { "ownership_pct": 72.4, "qoq_change_pct": 2.1, "increasing_count": 184, "decreasing_count": 97 },
  "notable_new_positions": [{ "fund": "Pershing Square", "shares": 1200000, "value_m": 220 }],
  "notable_exits": [],
  "superinvestor_count": 7,
  "superinvestor_moves": [{ "fund": "Berkshire Hathaway", "action": "add", "shares_added": 2000000 }],
  "concentration_assessment": "high_conviction_buyers_present",
  "overall_institutional_signal": "bullish",
  "confidence": "medium"
}
```
