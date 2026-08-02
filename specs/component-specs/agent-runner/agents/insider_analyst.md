# agent-runner/agents/insider_analyst.py

## Purpose
Analyzes Form 4 insider transactions and the Finnhub MSPR (insider sentiment ratio) to surface cluster buying signals, unusual insider activity, and directional insider conviction.

## CrewAI Agent Definition

```python
Agent(
    role="Insider Activity Analyst",
    goal="Identify meaningful insider buying or selling signals for {ticker} and assess their significance",
    backstory="You specialize in SEC Form 4 filings. You know the difference between a routine option exercise and an open-market purchase that signals real conviction. You look for cluster buying — multiple insiders buying near the same time — as the highest-conviction signal.",
    tools=[get_insider_activity],
    llm=llm,
    allow_delegation=False
)
```

## Task Prompt
```
Analyze insider activity for {ticker}:
1. Recent transactions (last 90 days): distinguish open-market purchases vs. option exercises vs. sales.
2. Cluster signal: are multiple insiders buying within the same 30-day window?
3. Who is buying? CEO/CFO purchases carry more weight than director purchases.
4. MSPR (monthly insider sentiment ratio): is it trending positive or negative?
5. Net insider direction: net buyer or net seller over 90 days?
6. Any unusual size: purchases significantly larger than historical norms?

Return JSON: recent_transactions (array), cluster_signal (bool + details), key_buyers, mspr_trend, net_direction, signal_strength, overall_insider_signal, confidence.
```

## Data Sources
- Primary: FMP `v4/insider-trading` (cached in MongoDB)
- Finnhub `stock/insider-transactions` + `stock/insider-sentiment` for MSPR
- Backup: SEC EDGAR Form 4 search if FMP quota exhausted

## Cluster Signal Logic
- Cluster = 3+ distinct insiders making open-market purchases within a 30-day window
- Weight: CEO/CFO purchases = 2x weight of director purchases
- Flag if cluster + MSPR rising simultaneously

## Output Shape
```json
{
  "recent_transactions": [
    { "name": "John Smith", "title": "CEO", "type": "open_market_purchase", "shares": 5000, "value": 920000, "date": "2025-01-15" }
  ],
  "cluster_signal": { "detected": true, "insiders": ["CEO", "CFO", "Director"], "window_days": 22 },
  "key_buyers": ["John Smith (CEO) - $920k open market"],
  "mspr_trend": { "current": 42, "3m_ago": -12, "direction": "sharply_positive" },
  "net_direction": "net_buyer",
  "signal_strength": "strong",
  "overall_insider_signal": "bullish",
  "confidence": "high"
}
```
