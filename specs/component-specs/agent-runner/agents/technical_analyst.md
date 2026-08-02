# agent-runner/agents/technical_analyst.py

## Purpose
Analyzes price action, volume patterns, momentum, and gap behavior for a ticker. Runs three skills internally (The Strat, Accumulation, Gap Analysis) and synthesizes findings into a structured technical sub-report.

## CrewAI Agent Definition

```python
Agent(
    role="Technical Analyst",
    goal="Identify price patterns, momentum signals, and volume-based accumulation evidence for {ticker}",
    backstory="You are a seasoned technical analyst who specializes in price structure (The Strat), institutional accumulation patterns, and gap behavior. You look for setups where multiple technical signals align.",
    tools=[get_price_history, get_technical_indicators, get_accumulation_score, run_the_strat, run_gap_analysis],
    llm=llm,
    allow_delegation=False,
    verbose=False
)
```

## Task Prompt (passed in by crew.py)
```
Analyze {ticker} using the provided price and volume data.
1. Run the_strat skill: classify bar types, identify active patterns, assess TFC state across timeframes.
2. Run accumulation skill: score institutional accumulation (0-5), note up/down volume ratio.
3. Run gap_analysis skill: classify any recent gaps, score fill probability and follow-through signal.
4. Identify key support/resistance levels from price structure.
5. Note any momentum divergence or alignment across timeframes.

Don't just report the raw signal for each strategy — narrate the story behind it. Specifically:

**The Strat / TFC:**
- If there is an actionable signal on the daily chart, state whether it is reconfirmed or contradicted by the weekly, monthly, and yearly bars. Call out TFC conflict explicitly — e.g. "Daily/Weekly/Monthly are all green (bullish) but the Yearly bar is red — this is a short-term bounce inside a longer-term downtrend, not a Full TFC signal. Treat with a tighter stop until the Yearly turns." The reverse (short-term red within a green Yearly) should be flagged the same way.
- State where price currently sits within the active Broadening Formation. If price is near the BOTTOM of the BF, call that out as a potential reversal/support zone and note what would confirm a bounce (e.g. hammer, Rev Strat). If price is near the TOP of the BF, call that out as a potential exhaustion/resistance zone and note what would confirm a rejection (e.g. shooting star, failed 2 going 3). If price is mid-range, say so and note there's no edge from BF positioning right now.
- Note whether the current setup is a momentum trade (continuation, aligned with control TF) or a retracement trade (counter-trend), per the Momentum vs. Retracement rules.

**Accumulation / Volume:**
- Apply the same top/bottom framing to volume: is the accumulation happening while price is still near the bottom of its recent range (early-stage, more room to run) or after price has already pushed to the top of the range (later-stage, chase risk higher)? Call this out explicitly.
- If distribution volume is appearing after a prior accumulation phase, flag that rotation clearly — don't just report the ratio.
- Tie the accumulation narrative back to TFC where relevant (e.g. "accumulation score is 4 but the stock is at the top of its BF with the Yearly still red — institutional buying without confirmed longer-term trend support").

Return a structured JSON sub-report with keys: strat_result, accumulation_result, gap_result, key_levels, momentum_summary, tfc_narrative, bf_position_narrative, volume_narrative, overall_technical_signal (bullish/bearish/neutral), confidence.
```

## Skills Used
- `skills/the_strat.py` — bar classification, patterns, TFC
- `skills/accumulation.py` — institutional accumulation score
- `skills/gap_analysis.py` — gap type, score, fill probability

## Output Shape
```json
{
  "strat_result": { "bar_types": {...}, "patterns": [...], "tfc_state": {...}, "signals": [...] },
  "accumulation_result": { "score": 3, "up_down_ratio": 1.8, "max_spike": 2.4, "duration_days": 22, "peg_amplifier": false },
  "gap_result": { "gap_type": "breakaway", "score": 4, "fill_probability": "low", "follow_through": "bullish" },
  "key_levels": { "support": [182.50, 178.00], "resistance": [195.00, 200.00] },
  "momentum_summary": "RSI 58 trending up, MACD positive cross 3 days ago",
  "tfc_narrative": "Daily and Weekly are green with an actionable inside-bar breakout in force on the Daily, but the Yearly bar is still red. This is a short-term reconfirmation inside a longer-term downtrend, not Full TFC — treat as a retracement trade with a tighter stop until the Yearly flips.",
  "bf_position_narrative": "Price is sitting near the top of the active broadening formation, roughly 2% below the prior BF high. This is a potential exhaustion zone — watch for a shooting star or failed 2 to confirm rejection before adding size.",
  "volume_narrative": "Accumulation score 4 with a 2.8x up/down volume ratio, but the buying has occurred after price already pushed to the top of its 60-day range — this is later-stage accumulation with more chase risk than an entry near the bottom of the range would carry.",
  "overall_technical_signal": "bullish",
  "confidence": "high"
}
```

## Tools Bound
| Tool | Source |
|---|---|
| `get_price_history(ticker, period)` | `tools/price.py` |
| `get_technical_indicators(ticker)` | `tools/price.py` |
| `get_accumulation_score(ticker)` | `tools/price.py` → `skills/accumulation.py` |
| `run_the_strat(ticker, data)` | `skills/the_strat.py` |
| `run_gap_analysis(ticker, data)` | `skills/gap_analysis.py` |
