# agent-runner/agents/macro_analyst.py

## Purpose
Contextualizes a **sector** within the current macroeconomic environment. Assesses whether the macro regime (rates, inflation, growth, yield curve) is a tailwind or headwind for that sector. Decoupled from per-ticker analysis (specs/020-surface-macro-ui): `run(sector, context, client=None, db=None)` takes no ticker at all. The only caller is `macro_worker.py`, once per active sector; `crew.py` never calls this agent.

## Task Prompt
```
Assess the macro environment for the {sector} sector:
1. Inflation regime: CPI/PCE trend — rising, falling, stable. Impact on this sector.
2. Rate environment: Fed funds rate, direction of travel, expected cuts/hikes. Impact on valuation and business model.
3. Growth: GDP trend, recession probability signals from yield curve (T10Y2Y, T10Y3M).
4. Consumer: unemployment, sentiment index — relevant if consumer-facing business.
5. Sector rotation: is the macro regime favoring or rotating away from this sector?

Return structured JSON: inflation_impact, rate_impact, growth_backdrop, consumer_backdrop (if applicable), sector_rotation_signal, overall_macro_signal, confidence.
```

## Data Source
- FRED API for all indicators (see DATA_SOURCES.md)
- Macro data is fetched once per worker sweep and shared across all sectors refreshed in that sweep

## Caching
Result is cached per sector in `macro_analysis_cache` for `CACHE_DAYS = 7`; `run()` returns the cached `result` unchanged when the sector's read is still fresh. `sector=None` falls back to the shared `"unknown"` bucket.

## Output Shape
```json
{
  "inflation_impact": { "cpi_yoy": 3.1, "trend": "falling", "impact_on_sector": "neutral" },
  "rate_impact": { "fed_funds_rate": 5.25, "direction": "holding", "impact_on_valuation": "slight_headwind" },
  "growth_backdrop": { "gdp_qoq_annualized": 2.1, "yield_curve_spread": 0.3, "recession_signal": "none" },
  "consumer_backdrop": null,
  "sector_rotation_signal": "technology_favored",
  "overall_macro_signal": "neutral",
  "confidence": "medium"
}
```
