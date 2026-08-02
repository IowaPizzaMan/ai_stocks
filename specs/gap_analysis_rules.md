# Gap Analysis Rules — TechnicalAnalyst Agent
> Extracted from *Technical Analysis of Gaps* by Dahlquist & Bauer (2012).
> These rules are for use in the `TechnicalAnalyst` CrewAI agent and the `get_technical_indicators` tool.

---

## 1. Gap Detection

```python
# Gap up: today's low is above yesterday's high
is_gap_up = low[0] > high[-1]

# Gap down: today's high is below yesterday's low
is_gap_down = high[0] < low[-1]

# Gap size
gap_size_up   = (low[0] - high[-1]) / high[-1]
gap_size_down = (high[0] - low[-1]) / low[-1]  # will be negative
```

**Filter out:**
- Ex-dividend gaps (check ex-div date)
- Stocks with dollar volume < $5M on gap day
- Share volume < 100K on gap day
- Opening gaps that fill within the same session (track separately)

---

## 2. Gap Type Classification

| Type | Condition | Signal |
|---|---|---|
| **Breakaway** | Gap out of a consolidation/range (Day -1 price was ranging) | Continuation — strong directional signal |
| **Runaway/Measuring** | Gap occurs mid-trend (~43% of way to peak for up gaps; ~57% for down gaps) | Continuation — project target by mirroring distance from trend start to gap |
| **Exhaustion** | Gap after extended trend at extreme price | Reversal — do NOT trade in gap direction |
| **Common** | Small gap, illiquid or low-volume stock | Ignore |

**Measuring target for runaway gaps:**
```
target = gap_price + (gap_price - trend_start_price)
```

---

## 3. Baseline Return Patterns

- **Day 1 after any gap (up or down):** price tends to move lower
- **Down gaps:** reverse upward by Day 3 → **LONG signal at Day 3+ horizon**
- **Up gaps:** negative returns through Day 10, recover by Day 30 → **SHORT signal Days 1–10, LONG by Day 30**

---

## 4. Candle Color Rules

Evaluate the candle color (black = close < open; white = close > open) on Day -1 and Day 0.

| Pattern | Signal | Action |
|---|---|---|
| Black → Down Gap → Black (BDB) | Immediate reversal | **LONG Day 1** (strongest) |
| Black → Down Gap → White (BDW) | Down gap with intraday recovery | **LONG** — positive all holding periods |
| White → Down Gap → Black (WDB) | Gap down, continues falling | **Avoid long** — negative returns through Day 30 |
| White → Up Gap → White (WUW) | Most common (37% of all gaps) | **SHORT Days 1–10** |
| Black → Up Gap → White (BUW) | Up gap after down day | **LONG** — highest 1-day return of any up gap pattern |

**Key rule:** If Day -1 candle is **black** and a gap occurs Day 0 → price tends to reverse upward regardless of gap direction.

---

## 5. Volume Rules

Compare gap day volume to 10-day average volume. Classify as:
- Low: < 75% of avg
- Average: 75–125% of avg
- High: > 125% of avg
- Extreme: > 200% of avg

| Condition | Signal |
|---|---|
| **Low-volume down gap** | Reverses immediately on Day 1 → **LONG Day 1** |
| **High-volume down gap** | Continues down Days 1–3, reverses by Day 5 → **wait before going LONG** |
| **High-volume up gap** | Larger reversal magnitude → **better SHORT opportunity** |
| **Extreme volume + up gap** | All buyers in at once, nothing left to push higher → **strong SHORT** |

**Rule:** Gap size correlates with volume. Higher volume = bigger gap = more momentum but also faster reversal (especially for up gaps).

---

## 6. Moving Average Rules

Compute 10-day, 30-day, and 90-day SMAs.

| Condition | Signal |
|---|---|
| **Down gap above 30-day SMA** | Immediate reversal → **strongest LONG signal in the rulebook** |
| Down gap above 10-day SMA | Positive returns Day 1 through 30 → LONG |
| Down gap below all 3 SMAs | Largest negative Day 1 return → SHORT Day 1, then LONG Day 3+ |
| **Up gap below moving average** | Prolonged negative returns → **best SHORT opportunity** |
| Up gap > 175% of SMA (extreme price) | Very strong negative returns → **strong SHORT** |
| Up gap above 30-day or 90-day SMA | Positive returns by Day 5 → shorter SHORT window |

**Rule of thumb:** Down gap + price still above its SMA = overreaction, buy the dip. Down gap + price below all SMAs = momentum is real, wait before buying.

---

## 7. Market Context Rules

- Count how many stocks are gapping in the same direction across the market (breadth signal).
- **High gap day** = 500+ stocks gapping the same direction simultaneously.

| Market Condition | Signal |
|---|---|
| High down gap day → **Day 1** | SHORT the gap-down stocks |
| High down gap day → **Day 2+** | Reversal — go LONG |
| High up gap day → **Day 1** | Continuation — LONG |
| High up gap day → **Day 2+** | Reversal — SHORT |

**Prior market direction effect (down gaps only):**
- Market strongly down last 1–10 days → downward momentum may persist 1–5 more days → **delay long entry**
- Market up recently → reversal after down gap tends to be stronger and faster → **LONG sooner**

Note: Prior market direction has little impact on up gap signals — treat those consistently.

---

## 8. Gap Closing / Fill Rules

- Median time to close: **up gaps = 5 trading days, down gaps = 6 trading days**
- ~22% of gaps close Day 1
- ~53% of up gaps close by Day 5; ~55% of down gaps close by Day 6
- ~96% of all gaps close within 18 months

**Myth debunked:** A gap not closing within 3 days does NOT reliably predict trend continuation. Do not use this as a signal.

**Opening gap rule:** If an intraday opening gap is not filled within the first 30 minutes of trading, the trend in the gap direction is likely to continue that session.

**3-Window Rule:**
- 3 consecutive unclosed rising windows (up gaps) = overbought signal
- Rising windows become **support zones**; falling windows become **resistance zones**

---

## 9. Signal Strength Scoring

Score each gap 1–5 by layering confirming signals. Higher score = higher conviction.

**For down gaps (potential LONG):**
| Condition | Points |
|---|---|
| Large gap size (> 1%) | +1 |
| Day -1 candle is black | +1 |
| Gap occurs above 30-day SMA | +1 |
| Low volume on gap day | +1 |
| Market was up recently (or neutral) | +1 |

**For up gaps (potential SHORT Days 1–10):**
| Condition | Points |
|---|---|
| Large gap size (> 1%) | +1 |
| WUW candle pattern | +1 |
| Gap occurs below moving average | +1 |
| High or extreme volume on gap day | +1 |
| Exhaustion gap context (extended prior trend) | +1 |

Score ≥ 3 = act on signal. Score ≤ 2 = skip or paper trade only.

---

---

## 10. Power Earnings Gap (PEG) — Watchlist Strategy

> Source: Trader Stewie / Art of Trading — *What's a "Power Earnings Gap" and How to Trade Them?* (artoftrading.net)

A **Power Earnings Gap** is an earnings-driven breakaway gap with specific close and volume requirements. It is the primary watchlist-generation strategy: stocks that pass the PEG criteria are tracked for days-to-weeks entries *after* the gap day.

### 10.1 Qualification Criteria (all three required)

| Criterion | Requirement |
|---|---|
| **Earnings catalyst** | Stock gaps up on strong earnings report |
| **Strong close** | Candle closes at or near the session HIGH (not a reversal/red close) |
| **Huge volume** | Volume is significantly above average — institutions accumulating |

> **The close is the most important signal.** A gap up that reverses and closes red is a failed PEG — do NOT add to watchlist.

### 10.2 Short Interest Amplifier

Short interest supercharges PEG moves. Institutions gapping a heavily-shorted stock forces shorts to cover, creating a squeeze on top of organic buying.

| Short Interest | Expected Behavior |
|---|---|
| < 10% | Standard PEG move |
| **10–20%** | **Ideal PEG zone — notably bigger moves** |
| **20–30%** | **Aggressive squeeze likely** |
| **> 30%** | **Explosive / spectacular squeeze potential** |

Check short interest via Finviz or ShortSqueeze.com. Short interest ≥ 10% upgrades a PEG candidate's priority on the watchlist.

### 10.3 Contextual Filters

Apply these before adding to watchlist:
- **Overall market health** — avoid adding PEGs during broad market downtrends (check NYMO/NAMO via `market_flow_rules.md`)
- **Sector strength** — confirm the sector is not under distribution
- **Geopolitical / macro news** — nothing that structurally breaks the move

### 10.4 Entry Timing (Post-Gap)

Do NOT enter on the gap day. Enter *after* the stock sets up technically. Patterns to watch:

- Bull flag
- Pennant
- Wedge (ascending)
- Any consolidation that holds above the gap-day close

The PEG day proves institutional intent. Chart patterns after the gap are the entry trigger.

**Key principle:** No need to hold through earnings risk. The PEG stock has already proven itself — the big fish have spoken. Enter with confirmation, not on hope.

### 10.5 PEG Signal Score (for `TechnicalAnalyst` output)

| Condition | Points |
|---|---|
| Closes at or near session high (top 10% of day's range) | +2 |
| Volume ≥ 200% of 10-day average | +1 |
| Short interest ≥ 10% | +1 |
| Sector in uptrend | +1 |
| NYMO not overbought (< +40) | +1 |

Score ≥ 4 = high-priority watchlist add. Score 2–3 = watchlist with lower conviction. Score ≤ 1 = skip.

### 10.6 Duration Expectation

Successful PEG stocks tend to run for **multiple days to multiple weeks/months** after the gap. This is a swing trade setup, not a day trade.

---

### 10.7 PEG Red-to-Green (R2G) — Day Trade Entry

> Source: Trader Stewie / Art of Trading — *The "PEG R2G" Day Trading Strategy* (artoftrading.net, Jan 2019)

The **PEG R2G** is a momentum day trade played the session *after* a confirmed PEG. Where Section 10.4 targets multi-day swing entries via flag/pennant consolidation, R2G is a same-day scalp/day trade entry triggered by a small red open reversing to green.

**The logic:** A small red open the day after a big PEG move means buyers are *still in control* — they're not willing to sell much despite yesterday's huge gain. When the stock flips green, that's momentum confirmation, and the trade is to ride that momentum wave.

#### Setup Requirements (all required)

| Criterion | Requirement |
|---|---|
| **Day -1 PEG confirmed** | Stock made a clean PEG candle (gapped up on earnings, closed at/near highs, huge volume) |
| **Small red open** | Next morning opens *slightly* below prior close — giving back only a small amount of the PEG gain |
| **Not a big gap-down open** | A large gap-down negates the setup — it means sellers are in control |

> The size of the red open is the key read: 10–80 cents red on a $50–60 stock = buyers still interested. Multiple dollars red = avoid.

#### Trade Execution (4 Steps)

| Step | Action |
|---|---|
| **1. Watch the open** | Stock opens red / gaps down slightly after the PEG day |
| **2. Entry trigger** | Go long *as soon as* the stock crosses from red to green (above prior day's close). Use 5-min chart. |
| **3. Stop loss** | Just below the day's opening lows. A few cents below open low is sufficient. |
| **4. Target** | Look on higher time frames for old resistance levels and round numbers. First round number above = initial target. |

#### Chart Timeframe
Use the **5-minute chart** for entry and trade management. Daily chart for context and target identification.

#### Target Selection
- Old resistance levels visible on daily/weekly chart
- Round numbers (e.g., $60, $100, $50) — these act as natural profit-taking zones
- First round number above entry = conservative target; additional resistance levels = extended targets

#### Risk Profile
- **Best for:** Scalpers and day traders
- **Can apply to:** Swing traders if the stock and pattern are strong enough
- **Nature:** Pure momentum play — "buying high and selling higher"
- **Do not:** Overthink the entry. The R2G cross is the signal; act on it.

#### Key Distinction from Section 10.4
| | Section 10.4 (Swing Entry) | Section 10.7 (R2G Day Trade) |
|---|---|---|
| Timing | Days to weeks after the PEG | The very next session |
| Entry trigger | Bull flag / pennant / consolidation break | Red-to-green cross on 5-min chart |
| Hold period | Days to weeks | Intraday (hours) |
| Trader type | Swing traders | Day traders / scalpers |

---

*Source: Dahlquist, J. R. & Bauer, R. J. (2012). Technical Analysis of Gaps: Identifying Profitable Gaps for Trading. FT Press.*
*Source: Trader Stewie / Art of Trading — Power Earnings Gap strategy (artoftrading.net)*
