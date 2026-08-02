# Market Flow Rules — RecommenderAgent
> Based on NYMO and NAMO (McClellan Oscillator) as taught by Trader Stewie / Art of Trading.
> These rules drive the `RecommenderAgent`'s buy-more / start-selling / hold signals.
> Source: https://www.artoftrading.net/post/how-to-use-nymo-and-namo

---

## What Are NYMO and NAMO?

- **NYMO** = McClellan Oscillator using the **NYSE** (New York Stock Exchange)
- **NAMO** = McClellan Oscillator using the **NASDAQ**
- Both measure **market breadth**: Net Advancing stocks minus Net Declining stocks, smoothed into an oscillator
- **Sourcing note:** the `$NYMO` / `$NAMO` symbols are StockCharts symbols and are **not available** via yfinance or any other API in this stack (verified 2026-08-02 — all of `$NYMO`, `^NYMO`, `$NAMO`, `^NYAD`, `^TRIN` return no data from Yahoo). We **compute the oscillator locally** from advance/decline counts — see Data Fetching below.

These are **market timing tools** — not used to pick stocks, but to decide *when* to act on stock positions (add, hold, or reduce/exit).

---

## Data Fetching

Computed locally by `agent-runner/tools/breadth.py` (see `component-specs/agent-runner/tools/breadth.md` for the full implementation). Summary:

1. Pull constituent lists for two proxy universes: **S&P 500** (NYMO proxy — NYSE-dominated) and **NASDAQ-100** (NAMO proxy).
2. One batched `yf.download(universe)` per day gets daily closes; count advancers and decliners.
3. Ratio-adjust and smooth (StockCharts ratio-adjusted methodology):

```python
rana = 1000 * (advancers - decliners) / (advancers + decliners)  # ratio-adjusted net advances
mcclellan = rana.ewm(span=19, adjust=False).mean() - rana.ewm(span=39, adjust=False).mean()
```

Use the most recent value as the current reading. Daily advance/decline counts and oscillator values are stored in MongoDB (`breadth_cache`) alongside SPY price for divergence tracking, so each daily run only computes the incremental day.

**Calibration caveat:** because these are proxy universes (500 + 100 large caps) rather than full-exchange breadth (~2,800 NYSE issues), absolute values will deviate somewhat from StockCharts' published $NYMO/$NAMO. The thresholds below are a starting point — validate the computed oscillator against StockCharts' charts for a few weeks and adjust zone boundaries if the computed range runs systematically narrower or wider.

---

## 1. Reading Thresholds

| NYMO / NAMO Level | Market Condition | Implication |
|---|---|---|
| > +60 | Overbought / Euphoric | Consider reducing / not adding |
| +20 to +60 | Bullish momentum | Trend is intact, holds are fine |
| 0 to +20 | Neutral / mild bullish | Normal conditions |
| 0 to -40 | Mild weakness | Monitor, no action required |
| -40 to -60 | Moderate oversold | Begin watching for reversal setups |
| **-60 or lower** | **Oversold / fear** | **Market is getting ugly — potential opportunity zone** |
| **-80 or lower** | **Extreme oversold** | **Rare (~1–2x/year) — strong bottom signal looming** |
| **-100 or lower** | **Panic / volatility extreme** | **Extremely rare — capitulation, major bounce likely** |

**Key rule:** The deeper the NYMO/NAMO reading, the higher the confidence that a bounce is approaching. These extremes are not reasons to sell — they are the *setup* for the strongest bounces of the year.

---

## 2. Core Signal Patterns

### A. Extreme Oversold Single Reading
- NYMO or NAMO drops to **-80 or lower**
- **Signal: BUY / ADD** (scale in, don't go all-in — wait for confirmation)
- This happens only 1–2 times per year; historically produces some of the strongest multi-week recoveries

### B. Double Bottom + Higher Low (Strongest Signal)
This is the highest-conviction signal in the rulebook.

```
Step 1: NYMO drops to extreme low (e.g., -60)  → market panics, SPY hits low #1
Step 2: Bounce occurs (NYMO recovers toward 0)
Step 3: SPY retests low #1 (double bottom on price chart)
Step 4: NYMO only reaches -30 this time (higher low on NYMO)
         → DIVERGENCE: price made same low, breadth improved
```

**Signal: STRONG BUY / AGGRESSIVE ADD** — "look out above"

Detection pseudocode:
```python
def detect_nymo_divergence(nymo_series, spy_series, lookback=20):
    """
    Returns True if SPY made a double bottom while NYMO made a higher low
    within the last `lookback` days.
    """
    # Find first trough (NYMO < -50, SPY local low)
    # Find second trough (SPY retests prior low, NYMO trough is higher)
    # Return signal + levels
```

### C. NYMO Recovery from Oversold
- NYMO was ≤ -60, now crossing back above -40
- **Signal: CONFIRM BUY** — bounce is underway, fine to add if not already positioned

### D. NYMO at Overbought After Extended Run
- NYMO > +60, market has been trending up for weeks
- **Signal: TRIM / REDUCE** — not a hard sell, but a signal to start lightening up
- Combine with gap exhaustion signals (see `gap_analysis_rules.md` Section 2) for confirmation

---

## 3. Buy-More vs. Start-Selling Logic

The `RecommenderAgent` uses NYMO/NAMO to answer two questions:

**"Should I buy more of my existing positions?"**

| Condition | Answer |
|---|---|
| NYMO > +40 (already overbought) | No — don't chase |
| NYMO 0 to +40, trend intact | Yes — normal adds are fine |
| NYMO -40 to -60 (getting oversold) | Cautiously yes — scale in small |
| NYMO ≤ -60 | Yes — oversold zone, strong bounce candidates |
| NYMO ≤ -80 + higher low divergence | Strong yes — max conviction add |

**"Should I start selling / reducing?"**

| Condition | Answer |
|---|---|
| NYMO > +60, extended trend | Consider trimming 25–50% |
| Exhaustion gap (see gap rules) + NYMO overbought | Reduce meaningfully |
| NYMO crossing from positive to negative (trend shift) | Watch closely, reduce risk |
| Fundamental thesis broken (handled by other agents) | Sell regardless of NYMO |

---

## 4. NAMO vs. NYMO

- Use **NYMO** as the primary signal (broader, more stable)
- Use **NAMO** to assess **NASDAQ-specific** conditions — particularly relevant for tech/growth holdings
- If NYMO is mild but NAMO is extreme, tech names specifically may be at extremes while the broader market is OK
- When both NYMO and NAMO are at extremes simultaneously → highest confidence

---

## 5. Combining with Gap Analysis

Cross-reference with `gap_analysis_rules.md` for timing precision:

| NYMO Signal | Gap Signal | Combined Action |
|---|---|---|
| NYMO ≤ -60 (oversold) | Down gap with score ≥ 3 (strong LONG setup) | **Strong buy signal — act** |
| NYMO ≤ -80 + higher low divergence | Any down gap | **Maximum conviction add** |
| NYMO > +60 (overbought) | Up gap with exhaustion pattern | **Reduce / exit position** |
| NYMO > +60 | WUW candle pattern (gap_rules Section 4) | **Short-term short or trim** |
| NYMO neutral | Gap signal alone | **Follow gap signal at normal size** |
| NYMO not overbought (< +40) | PEG score ≥ 4 (see gap_rules Section 10) | **Add to watchlist, watch for chart pattern entry** |
| NYMO > +60 (overbought) | PEG candidate just gapped | **Hold off on entry — wait for NYMO to cool** |

---

## 6. Contextual Rules

- **NYMO alone is not a stock picker** — it tells you whether the *market environment* favors action. Always combine with per-stock signals from `TechnicalAnalyst`, `FundamentalAnalyst`, etc.
- Prior market direction matters for *down gaps* (see `gap_analysis_rules.md` Section 7): if NYMO just hit -80 AND the market has been down hard for 1–10 days, a gap down on Day 1 is still a potential SHORT — but by Day 2+ the reversal is likely. NYMO context speeds up the reversal call.
- NYMO at mild levels (-20 to +20) = market isn't giving a strong timing signal → defer to individual stock signals

---

## 7. Output Format for RecommenderAgent

For each position / watchlist ticker, the agent should produce:

```json
{
  "ticker": "AAPL",
  "nymo_current": -72,
  "namo_current": -68,
  "nymo_signal": "oversold",
  "divergence_detected": false,
  "gap_score": 4,
  "gap_type": "down_gap_above_30sma",
  "recommendation": "BUY_MORE",
  "conviction": "high",
  "rationale": "NYMO at -72 (oversold zone, rare). Stock gapped down above 30-day SMA with BDB candle pattern (gap score 4/5). Market breadth signals imminent bounce. Strong add opportunity.",
  "caveats": ["Wait for Day 1 close to confirm reversal", "Monitor if NYMO drops further to -80+ for max conviction"]
}
```

Recommendation values: `BUY_MORE`, `HOLD`, `TRIM`, `START_SELLING`, `AVOID_ADD`, `WATCH`

---

*Source: Trader Stewie / Art of Trading — NYMO & NAMO guide (artoftrading.net)*
*Last updated: 2026-08-01*
