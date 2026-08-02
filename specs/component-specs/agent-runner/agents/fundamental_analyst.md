# agent-runner/agents/fundamental_analyst.py

## Purpose
Analyzes company financials, valuation ratios, earnings trends, and analyst estimates. Determines whether the business is financially healthy and fairly/under/overvalued.

## CrewAI Agent Definition

```python
Agent(
    role="Fundamental Analyst",
    goal="Assess the financial health, earnings trajectory, and valuation of {ticker}",
    backstory="You are a fundamental analyst trained in reading income statements, balance sheets, and cash flow statements. You evaluate whether a company is growing profitably and whether its current price reflects fair value.",
    tools=[get_financials, get_earnings_data],
    llm=llm,
    allow_delegation=False
)
```

## Task Prompt
```
Analyze the financial fundamentals of {ticker}:
1. Revenue trend: YoY growth rate, acceleration or deceleration.
2. Profitability: gross margin, operating margin, net margin — direction of change.
3. Balance sheet health: cash position, debt load, debt/equity ratio.
4. Cash flow: FCF generation, FCF yield vs. market cap.
5. Earnings: recent EPS beats/misses, forward estimate revisions (up or down).
6. Valuation: P/E, EV/EBITDA vs. sector peers and historical average.

Don't just report the latest value for each metric — pull the full historical series from the annual (4y) and quarterly (8q) data already present in `get_financials()`'s output (`income_annual`, `income_quarterly`, `balance_annual`, `cashflow_annual`, `ratios`, `key_metrics`) and `get_earnings_data()`'s output (`earnings_dates`, `eps_trend`). Each trend section below must include a `history` array of period-by-period points, not just a single current value plus a qualitative label — this is what lets the frontend chart the trend instead of just stating it.

Return structured JSON with keys: revenue_trend, margin_trend, balance_sheet_health, fcf_profile, earnings_track_record, valuation_assessment, overall_fundamental_signal, confidence.
```

## Data Sources
- Primary: FMP (cached in MongoDB — re-fetched quarterly)
- Backup: yfinance for earnings estimates and surprises

## Output Shape
```json
{
  "revenue_trend": {
    "yoy_growth_pct": 12.4,
    "direction": "accelerating",
    "history_annual": [
      { "period": "2022", "revenue_bn": 98.1, "net_income_bn": 21.3, "yoy_growth_pct": 8.1 },
      { "period": "2023", "revenue_bn": 108.4, "net_income_bn": 24.7, "yoy_growth_pct": 10.5 },
      { "period": "2024", "revenue_bn": 118.9, "net_income_bn": 27.9, "yoy_growth_pct": 9.7 },
      { "period": "2025", "revenue_bn": 133.6, "net_income_bn": 32.8, "yoy_growth_pct": 12.4 }
    ],
    "history_quarterly": [
      { "period": "Q1'25", "revenue_bn": 30.2, "yoy_growth_pct": 11.0 },
      { "period": "Q2'25", "revenue_bn": 32.5, "yoy_growth_pct": 11.8 },
      { "period": "Q3'25", "revenue_bn": 34.1, "yoy_growth_pct": 12.9 },
      { "period": "Q4'25", "revenue_bn": 36.8, "yoy_growth_pct": 13.6 }
    ]
  },
  "margin_trend": {
    "gross": 43.2, "operating": 28.1, "net": 24.5, "direction": "stable",
    "history_annual": [
      { "period": "2022", "gross": 41.8, "operating": 26.4, "net": 21.7 },
      { "period": "2023", "gross": 42.5, "operating": 27.2, "net": 22.8 },
      { "period": "2024", "gross": 43.0, "operating": 27.8, "net": 23.5 },
      { "period": "2025", "gross": 43.2, "operating": 28.1, "net": 24.5 }
    ]
  },
  "balance_sheet_health": {
    "cash_bn": 28.4, "debt_bn": 12.1, "debt_equity": 0.43, "assessment": "strong",
    "history_annual": [
      { "period": "2022", "cash_bn": 19.6, "debt_bn": 13.8, "debt_equity": 0.58 },
      { "period": "2023", "cash_bn": 22.9, "debt_bn": 13.2, "debt_equity": 0.52 },
      { "period": "2024", "cash_bn": 25.7, "debt_bn": 12.6, "debt_equity": 0.47 },
      { "period": "2025", "cash_bn": 28.4, "debt_bn": 12.1, "debt_equity": 0.43 }
    ]
  },
  "fcf_profile": {
    "fcf_bn": 22.1, "fcf_yield_pct": 3.8, "assessment": "healthy",
    "history_annual": [
      { "period": "2022", "fcf_bn": 15.4, "fcf_yield_pct": 3.1 },
      { "period": "2023", "fcf_bn": 18.2, "fcf_yield_pct": 3.4 },
      { "period": "2024", "fcf_bn": 20.3, "fcf_yield_pct": 3.6 },
      { "period": "2025", "fcf_bn": 22.1, "fcf_yield_pct": 3.8 }
    ]
  },
  "earnings_track_record": {
    "last_4_beats": 3, "last_miss_magnitude_pct": -2.1, "estimate_revisions": "up",
    "history_quarterly": [
      { "period": "Q1'25", "eps_estimate": 1.85, "eps_actual": 1.91, "surprise_pct": 3.2 },
      { "period": "Q2'25", "eps_estimate": 1.98, "eps_actual": 1.94, "surprise_pct": -2.1 },
      { "period": "Q3'25", "eps_estimate": 2.05, "eps_actual": 2.15, "surprise_pct": 4.9 },
      { "period": "Q4'25", "eps_estimate": 2.20, "eps_actual": 2.31, "surprise_pct": 5.0 }
    ]
  },
  "valuation_assessment": {
    "pe_ttm": 28.4, "ev_ebitda": 19.2, "vs_sector": "slight_premium", "vs_history": "fair",
    "history_annual": [
      { "period": "2022", "pe_ttm": 24.1, "ev_ebitda": 16.8 },
      { "period": "2023", "pe_ttm": 26.0, "ev_ebitda": 17.9 },
      { "period": "2024", "pe_ttm": 27.2, "ev_ebitda": 18.6 },
      { "period": "2025", "pe_ttm": 28.4, "ev_ebitda": 19.2 }
    ]
  },
  "overall_fundamental_signal": "bullish",
  "confidence": "high"
}
```
