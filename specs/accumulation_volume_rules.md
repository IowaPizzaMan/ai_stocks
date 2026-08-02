# Accumulation Volume Rules — InstitutionalAnalyst / TechnicalAnalyst
> Based on "The Power of Accumulation Volume" by Trader Stewie / Art of Trading.
> These rules define how to detect institutional accumulation (smart money buying) via volume patterns.
> Applies to both the `InstitutionalAnalyst` agent and `TechnicalAnalyst` agent.

---

## What Is Accumulation Volume?

**Accumulation Volume** = Institutional Accumulation. It is the footprint left when large institutional investors (hedge funds, mutual funds, pension funds, etc.) are actively buying a stock.

Because institutions invest millions to billions — not thousands — their buying pressure shows up clearly in **volume spikes on up days**. They cannot hide it. This is also called "smart money" activity.

The counterpart is **Distribution Volume** — the same phenomenon on the sell side (institutions exiting). This ruleset focuses on accumulation only.

---

## The Core Signal

What to look for:
1. **Volume on up days is at least 2–3x average daily volume** (ideally 4–5x on initial gap days)
2. **Volume on down days is low / quiet** — red days should have noticeably lighter volume than green days
3. **The pattern persists over a sustained period** — days, weeks, or months of this asymmetry
4. **Price is trending up** as the volume ramps — not just a single spike

The asymmetry between heavy up-volume and light down-volume is the defining characteristic. A single volume spike doesn't count — it must be a sustained pattern.

---

## Detection Rules

### Rule 1 — Up/Down Volume Ratio
For each trading day, compute:
- `up_volume`: volume on days where `close > open` (green days)
- `down_volume`: volume on days where `close < open` (red days)

Over a rolling window (e.g., 20 trading days):
```python
avg_up_volume = mean(up_days_volume)
avg_down_volume = mean(down_days_volume)
up_down_ratio = avg_up_volume / avg_down_volume
```

| Ratio | Signal |
|---|---|
| < 1.5 | No accumulation signal |
| 1.5 – 2.0 | Mild accumulation — monitor |
| 2.0 – 3.0 | Moderate accumulation — noteworthy |
| > 3.0 | **Strong accumulation — institutional interest confirmed** |

### Rule 2 — Volume vs. Average Daily Volume (ADV)
On any individual up day:
```python
adv = mean(volume, last_50_days)
volume_ratio = today_volume / adv
```

| Volume Ratio | Signal |
|---|---|
| < 1.5x ADV | Normal |
| 1.5x – 2x ADV | Elevated — worth noting |
| 2x – 3x ADV | **Accumulation signal** |
| > 3x ADV (especially on gap-up) | **Strong institutional footprint** — flag immediately |

### Rule 3 — Sustained Pattern (Trend Test)
Accumulation must persist over time, not be a one-day event. Use a rolling 20-day window and check:
- At least **60% of up days** have volume ≥ 1.5x ADV
- No more than **2–3 high-volume down days** in that window
- The pattern has been present for **≥ 3 weeks** for a confirmed signal

If the pattern just started (< 1 week), flag as `EARLY_ACCUMULATION` and monitor.

### Rule 4 — Power Earnings Gap Amplifier
Accumulation volume following a **Power Earnings Gap (PEG)** is especially significant.

> "The idea behind Power Earnings Gaps and institutional buying go hand in hand." — Trader Stewie

When a stock has a PEG score ≥ 3 (see `gap_analysis_rules.md`) AND accumulation volume starts appearing in the weeks following the gap, treat the conviction level as elevated. Institutions are "circling the wagons."

Back-to-back PEGs with sustained accumulation volume between them = **highest-conviction institutional interest**.

---

## Scoring Model

Compute an `accumulation_score` (0–5) for each ticker:

| Points | Condition |
|---|---|
| +1 | Up/down volume ratio > 1.5 over last 20 days |
| +1 | Up/down volume ratio > 2.5 over last 20 days |
| +1 | At least one up day with volume > 3x ADV in last 20 days |
| +1 | Pattern has been sustained for ≥ 3 weeks |
| +1 | Follows a PEG event (gap_score ≥ 3 in last 60 days) |

| Score | Interpretation |
|---|---|
| 0–1 | No meaningful accumulation |
| 2 | Mild — worth watching |
| 3 | Moderate accumulation — add to watchlist |
| 4 | Strong accumulation — institutional interest confirmed |
| 5 | **Maximum conviction** — sustained institutional accumulation post-PEG |

---

## Integration with Other Agents

### With InstitutionalAnalyst
Cross-reference volume-based accumulation with 13F filings and superinvestor data:
- If accumulation volume score ≥ 3 AND new institutional positions appear in latest 13F → **strong convergence signal**
- Volume accumulation can lead 13F filings by 1–2 quarters (institutions file quarterly; their buying shows up in volume first)

### With TechnicalAnalyst
The `TechnicalAnalyst` computes the accumulation score and passes it to the synthesis layer. Key tool:
```python
get_accumulation_score(ticker, lookback_days=60) -> dict
# Returns: score (0-5), up_down_ratio, max_volume_spike, pattern_duration_days, peg_amplifier
```

### With RecommenderAgent
| Accumulation Score | NYMO Signal | Combined Action |
|---|---|---|
| ≥ 4 | NYMO neutral or oversold | **Strong add — institutional support + market timing aligned** |
| ≥ 4 | NYMO > +60 (overbought) | Hold off — wait for market to cool, then add |
| ≥ 3 | NYMO ≤ -60 | **Buy signal elevated** — accumulation plus oversold market = rare opportunity |
| 5 (post-PEG) | Any | Add to watchlist immediately; prioritize entry timing |
| ≤ 2 | Any | No accumulation edge; rely on other signals |

### With gap_analysis_rules.md
- A PEG followed by accumulation volume (score ≥ 3) over the following weeks is the **"Killer Knock Out Punch"** setup
- Track accumulation score on all PEG watchlist tickers weekly

---

## Distribution Volume (Sell-Side Warning)

The inverse of accumulation. Warning signs to flag:
- High volume on **down days**, light volume on up days
- Up/down volume ratio falls **below 0.7** (sellers dominate)
- Appears after an extended uptrend or overbought NYMO reading

When distribution volume appears after a period of accumulation, it signals institutions are **rotating out**. Flag as `DISTRIBUTION_WARNING` and alert the user.

---

## Output Format

The `TechnicalAnalyst` should include in its per-ticker output:

```json
{
  "ticker": "AAPL",
  "accumulation_score": 4,
  "up_down_volume_ratio": 2.8,
  "max_volume_spike_vs_adv": 3.6,
  "pattern_duration_days": 28,
  "peg_amplifier": true,
  "signal": "ACCUMULATION",
  "distribution_warning": false,
  "rationale": "Strong up/down volume asymmetry (2.8x) sustained over 28 days following a Power Earnings Gap. Volume spiked to 3.6x ADV on the gap day. Institutional footprint confirmed."
}
```

Signal values: `ACCUMULATION`, `EARLY_ACCUMULATION`, `NEUTRAL`, `DISTRIBUTION_WARNING`

---

## Key Principle

> "Volume literally SPEAKS." — Trader Stewie

Volume asymmetry is one of the most reliable tells for institutional activity. Institutions can't hide their buying. When smart money consistently accumulates a stock over weeks or months — especially after a PEG — the odds of a sustained multi-month run increase dramatically.

---

*Source: Trader Stewie / Art of Trading — "The Power of Accumulation Volume" (Feb 2020)*
*Last updated: 2026-08-01*
