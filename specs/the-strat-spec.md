# The Strat — Complete Knowledge Spec
> Based on Rob Smith's Price Discovery System / T3 Live Quant Edge curriculum

---

## Core Philosophy

**Subjectivity is the enemy of the trader.** The Strat replaces subjective analysis (patterns, indicators, gut feel) with objective, quantifiable conditions — things that are either TRUE or FALSE.

From one bar to the next, **only 3 outcomes are possible**. It is impossible for price to do anything else:
1. The next bar stays within the previous bar's range → **Inside Bar (1)**
2. The next bar takes out one side of the previous range → **Directional Bar (2U or 2D)**
3. The next bar takes out both sides of the previous range → **Outside Bar (3)**

Price action is also always creating **Broadening Formations** — ranges expanding on both sides. Everything that trades will trade in a continuous series of Broadening Formations, period. This is a universal truth, not a rare event.

---

## The 4 Bar Types

| Type | Name | Definition |
|---|---|---|
| **1** | Inside Bar | High ≤ previous high AND Low ≥ previous low. Range is contained within the prior bar. |
| **2U** | Directional Up | Makes a higher high without making a lower low. |
| **2D** | Directional Down | Makes a lower low without making a higher high. |
| **3** | Outside Bar | Makes BOTH a higher high AND a lower low. Engulfs the prior bar. |

**Key rules:**
- A bar is "Still Inside" while it's forming — it must **close** to be classified. Don't trade it as an inside bar until the close is confirmed.
- You cannot have a Type 3 (outside bar) without first going Type 2. The range breaks one side before reversing to break the other.
- An Outside Bar IS a Broadening Formation on a fractal basis (zoom down one TF and you'll see the fractal triangle).

---

## The 3 Outside Bar Subtypes

| Type | Definition |
|---|---|
| **Bullish Engulfing Outside Bar** | GAPS BELOW the previous bar's low, then CLOSES ABOVE the previous bar's high. |
| **Bearish Engulfing Outside Bar** | GAPS ABOVE the previous bar's high, then CLOSES BELOW the previous bar's low. |
| **Regular Outside Bar** | Breaches both the high and low of the previous bar, but the OPEN and/or CLOSE are contained within the previous bar's range. Often misidentified as an engulfing bar — **they are not the same.** |

---

## The 4 Reversals

There are **only 4 ways price can reverse**. It is impossible for price to reverse any other way. This applies to all reversals — from minor pullbacks in a trend to major tops and bottoms.

| # | Pattern | Description |
|---|---|---|
| **1** | **2-1-2 Reversal** | 2 in one direction → Inside bar (1) → 2 in the opposite direction |
| **2** | **2-2 Reversal** | 2 in one direction → 2 immediately in the opposite direction |
| **3** | **Failed 2 Goes 3** | 2 in one direction fails and becomes an Outside Bar (3) |
| **4** | **3-1-2 Reversal** | Outside bar (3) at a high or low → Inside bar (1) → 2 back into the previous range |

These apply on **all timeframes** equally — yearly, monthly, weekly, daily, intraday. A "pullback" in a trend is simply a mini reversal that ultimately resolves back in the trend direction, and it must be one of these 4 setups.

---

## Actionable Signals

Actionable signals are **the "WHY" we can expect price to move.** They identify:
- Equilibriums that MUST at least attempt to break
- Participants caught on the wrong side of price

### Universal Truths vs. Non-Universal Signals

| Type | Universal Truth? | Reason |
|---|---|---|
| Inside Bar Breakout | ✅ Yes | Equilibrium is undeniable — bar failed to break previous high or low |
| Rev Strat | ✅ Yes | Equilibrium reversal — a breakout was attempted and is failing |
| Broadening Formation | ✅ Yes | Range expansion on both sides cannot be disputed |
| Hammer / Shooting Star | ❌ No | Cannot quantify exactly why the wick formed |
| Kicking Pattern | ❌ No (conditional) | Gap context matters; needs additional signals |

### Signal State: "In Force"
A signal is **"In Force"** from the moment the trigger level is breached, and remains in force as long as:
- The triggering bar's time period is still open, AND
- Price has not violated the signal's level of defense

---

## Candlestick Formations (Detailed)

### Regular Hammer
- **Context:** Forms after a previous lower trend — signals reversal off lows
- **Structure:** Open AND close in the **top 33%** of the bar's range; long lower wick
- **Trigger:** Goes In Force when price moves **above the HIGH** of the hammer
- **Why it works:** Lower wick = exhaustion of sellers + ill-timed new short positions; those shorts have stops above the high
- **Stop:** 1 cent below the bar that **triggers** the hammer (not below the hammer's low — too much risk)
- **Not a universal truth** — we cannot quantify exactly why the wick formed

### Momentum Hammer
- **Context:** Forms near the HIGHS of a strong uptrend (continuation, not reversal)
- **Structure:** Same as regular hammer — wick represents profit-taking pullback + ill-timed shorts
- **Trigger:** In Force above the HIGH of the hammer; **should trigger immediately**
- **Stop:** 1 cent below the bid after taking the offer (tight stop — momentum trade)

### Shooting Star
- **Context:** Forms after a previous uptrend — signals reversal off highs
- **Structure:** Open AND close in the **lower 33%** of the bar's range; long upper wick
- **Trigger:** Goes In Force when price moves **below the LOW** of the shooting star
- **Why it works:** Upper wick = exhaustion of buyers + ill-timed new long positions
- **Stop:** 1 cent above the bar that **triggers** the shooting star
- **Not a universal truth**

### Momentum Shooting Star
- **Context:** Forms on the LOWS of a previous strong downtrend (continuation)
- **Trigger:** In Force below the LOW; **should trigger immediately**
- **Stop:** 1 cent above the offer after hitting the bid

### Bullish Kicking Pattern
- **Structure:** Red bar followed by a green bar that **GAPS ABOVE** the red bar's entire range
- **In Force:** As long as price remains **above the opening price of the second (green) candle**
- **Why it works:** The gap immediately puts all shorts from the red bar into a loss; new longs are entering as price rises
- **Execution:** Needs additional intraday actionable signals. Take any intraday signal as long as price is **above the opening price of the day**

### Bearish Kicking Pattern
- **Structure:** Green bar followed by a red bar that **GAPS BELOW** the green bar's entire range
- **In Force:** As long as price remains **below the opening price of the second (red) candle**
- **Why it works:** The gap immediately puts all longs from the green bar into a loss; new shorts are entering
- **Execution:** Same — needs additional intraday signals. Price must be **below the opening price of the day**

---

## Inside Bars (Detailed)

### Definition
Any bar whose range is **equal to or less than** the previous bar's range. The bar must **CLOSE** inside to be counted — a bar still forming is "Still Inside" and considered consolidating on that timeframe.

### Momentum vs. Retracement Classification
- **Momentum:** Previous bar is GREEN + inside bar is in the **upper 50%** of that bar's range → break upward is momentum (breaking into new recent highs)
- **Retracement:** Previous bar is RED + inside bar breaks upward → counter-trend retracement trade
- These conditions are always subject to the higher timeframe context (TFC)

### Mother Bar
The bar immediately prior to the inside bar. Important rules:
- If the inside bar forms in the **middle of the Mother Bar's range** → **AVOID** — the inside bar likely isn't strong enough to breach the Mother Bar. A new broadening formation series is expected to begin within the Mother Bar.
- If the actionable signal is **close to taking out the Mother Bar's extreme**, the trade can be taken with the expectation that the signal will push price through the Mother Bar's range.
- **Multiple consecutive inside bars** ("multi-inside bar") = expect choppiness. During this condition, expect Rev Strats.

### Execution
- **Bullish breakout:** BUY when price goes **above the Inside Bar's high**. Stop: 1 cent below the **LOW of the bar that breaks** the inside bar.
- **Bearish breakout:** SELL when price goes **below the Inside Bar's low**. Stop: 1 cent above the **HIGH of the bar that breaks** the inside bar.

---

## The Rev Strat (Reversal Strategy)

A Rev Strat is a reversal **of the Inside Bar setup** — an equilibrium breakout was attempted and is **failing**. This IS a universal truth because an equilibrium break has been reversed, which cannot be disputed.

**Critical rule:** A Rev Strat ONLY occurs following an inside bar.

### 2-Bar Bullish Rev Strat
- **Pattern:** Inside bar → Hammer forms after the inside bar → price confirms above the hammer
- **Why:** Equilibrium reversal confirmed + ill-timed shorts have stops above the hammer, inside bar high, and mother bar high
- **Execution:** BUY 1 cent above the hammer. Stop: 1 cent below the bid after taking the offer
- **Should trigger immediately** — treat like a momentum signal

### 2-Bar Bearish Rev Strat
- **Pattern:** Inside bar → Shooting Star forms after the inside bar → price confirms below the shooting star
- **Execution:** SELL 1 cent below the shooting star. Stop: 1 cent above the offer

### 1-Bar Bullish Rev Strat
- **Pattern:** Inside bar breaks DOWN first, then reverses to take out the HIGH of the inside bar — all in one bar
- **Why:** Equilibrium was reversed; shorts who bought the breakdown are now trapped
- **Execution:** BUY 1 cent above the inside bar being reversed. Stop: 1 cent below the bid
- ⚠️ Immediately at risk for Broadening Formation (the bar IS an outside bar = fractal triangle). Prefer taking combinations that trigger a Rev Strat rather than the Rev Strat trigger itself.

### 1-Bar Bearish Rev Strat
- **Pattern:** Inside bar breaks UP first, then reverses to take out the LOW of the inside bar — all in one bar
- **Execution:** SELL 1 cent below the inside bar being reversed. Stop: 1 cent above the offer

### 1-Bar Rev Strat Becomes 2-Bar Rev Strat
- When a 1-Bar Rev Strat closes as a hammer or shooting star, the new trigger is above/below that candle, not the original inside bar
- This is still a countering of the known equilibrium

### Soft Rev Strat
- One side of the inside bar is breached, BUT the **open and close remain within the inside bar's range** (less violent rejection)
- Less powerful than a full Rev Strat — **prefer to combine with an additional actionable signal**

---

## Combinations

Combining signals from multiple timeframes or multiple signal types dramatically increases probability.

### Cross-Timeframe Combinations
- Shorter TF participation group triggers longer TF group (e.g., 30-min triggers daily, daily triggers weekly)
- Or: a longer-term signal already In Force is reconfirmed by a shorter-term actionable signal

### Simultaneous Break
When the broader averages, key sector ETFs, and most stocks all trigger actionable signals in the same direction. Often catalyzed by the Flip.

### Hammer Counters Shooting Star
- Hammer immediately follows a Shooting Star → treat as Momentum Hammer
- The Shooting Star = exhaustion of shorts + influx of aggressive longs; Hammer = confirms reversal
- Countering signals trigger in the direction of Participation Group control

### Shooting Star Counters Hammer
- Shooting Star immediately follows a Hammer → treat as Momentum Shooting Star

---

## The Measured Move

Occurs when an actionable signal triggers after a **quick advance or decline** — representing a brief hesitation before the strong trend continues.

**Gauging magnitude:** The expected continuation move ≈ the size of the previous move. Project it forward from the signal trigger point.

---

## Time Frame Continuity (TFC)

### The 4 Major Participation Groups

Each timeframe represents a distinct group of market participants:

| Group | Definition | Chart |
|---|---|---|
| **Monthly** | Anyone who put on, added to, or reduced a position during the calendar month | One bar per month |
| **Weekly** | Anyone who traded during the week | One bar per week |
| **Daily** | Anyone who traded during the day | One bar per day |
| **60-minute** | Anyone who traded during the 60-min period at the bottom of each hour | One bar per hour |

**Intraday groups:** 30-minute, 15-minute, 5-minute (and 3-min, 1-min during extreme volatility)

Always analyze **at least 4 charts** for any instrument.

### Full Time Frame Continuity

**Bullish Full TFC:** Last sale is **above** the opening of the Monthly, Weekly, Daily, AND 60-minute.
**Bearish Full TFC:** Last sale is **below** the opening of all four.

This is a Universal Truth — all known participants are aggressive in the same direction. The level of aggression is at its highest and cannot be disputed.

### The 4 C's of Continuity

| C | Question to Ask |
|---|---|
| **Control** | Which participation group(s) are in Control of the direction of price? |
| **Confirm** | Are all participation groups confirming each other? |
| **Conflict** | Are participation groups in conflict with each other? (One or two candles a different color) |
| **Change** | Are participation group(s) changing the continuity of the other groups? |

**Control hierarchy rules:**
- Monthly group = largest = institutional group
- Daily = who is in control today
- 60-minute = who is in control RIGHT NOW (most immediate)
- When the **60-minute AND Daily** are both confirming → they **override** the Weekly and Monthly for control
- The Flip determines which direction takes control on each new 60-min bar
- Weekly reconfirms or negates the Monthly; is in turn reconfirmed by Daily and 60-min throughout the week

### Continuity in Conflict
When one or two candles are a different color than the others — price is "In Conflict." Be cautious. The conflicting group creates uncertainty and often choppy action.

### Intraday TFC
Uses 60-min, 30-min, 15-min, 5-min timeframes. **The greater the volatility, the more important intraday TFC becomes** — during high volatility, there is as much movement and volume in shorter TFs as normally seen in higher TFs.

---

## The Flip

**Definition:** The moment the new 60-minute bar opens at the bottom of each hour.

**Why the bottom of the hour matters:**
- The U.S. market opens at the bottom of the hour (9:30)
- European markets CLOSE at the bottom of the hour — creating a liquidity event
- Weekly oil/natural gas inventory numbers and futures pit closes occur at the bottom of the hour
- **The Flip is the ONLY time during the trading day when a major TF signal can form AND trigger on the same day** (unlike monthly, weekly, and daily signals which must close first)

**The Flip's role in TFC:**
- As the most immediate TF, whichever direction the new 60-min bar goes from the Flip = the group currently in Control
- Determines whether TFs are Confirming or in Conflict
- When combined with an actionable signal triggering at the Flip, creates the potential for Change

**Importance:** On each Flip, evaluate how many new 60-min actionable signals have formed. Like billiards — evaluate not just the current shot but what conditions are created for the next move.

---

## Uncoupling

**Definition:** The first time during any month where the opening prices of the 4 major TFs occur at different times — when the participation groups "uncouple" from each other.

**Why it matters:** As the groups uncouple, we gain more quantitative evidence to gauge probability — each group's direction becomes independently verifiable.

**Timing rules:**
- On any Monday: Daily and Weekly open at the same price. The 60-min uncouples from Daily during the **second hour of Tuesday**.
- If the last day of the month falls Fri–Sun: uncoupling doesn't occur until the **second hour of the following Tuesday**.
- If the month ends any other day: uncoupling occurs during the **second hour of the following day**.
- Every day: uncoupling from the 60-min can't occur until the **second hour of trading**.

---

## Event Continuity

Events during the trading day create new continuity levels:

- **Known events:** Weekly oil inventory numbers, Fed minute announcements, etc.
- **Unknown events:** Unscheduled news that occurs during the day

The price at the moment the news event occurs becomes a new continuity level for the rest of the trading day. It changes the perception of all participation groups and their level of aggression.

---

## Broadening Formations (Detailed)

**Definition:** Any series of candles where both the highs AND lows of a previous range are breached. **Every instrument that trades will always trade in a continuous series of broadening formations.** This is not rare — it is one of the few things that CAN happen.

### Key Rules
- An Outside Bar IS a Broadening Formation (zoom down one TF → you see the fractal triangle inside it)
- A 1-Bar Rev Strat IS a Broadening Formation on a fractal basis (it's also an outside bar)
- All 1-Bar Rev Strats are Broadening Formations — be aware of this risk immediately upon entry

### Fractal Triangles
When you have an outside bar on a higher TF (e.g., daily), the lower TF (e.g., 60-min) MUST show a broadening formation pattern inside it. Use this lower TF "fractal triangle" to gauge the potential magnitude of the move.

### Inside / Outside / Inside Bar Pattern
- Contraction (inside bar) → Expansion (outside bar) → Contraction (inside bar)
- The third bar's inside bar equilibrium is actionable
- If the second inside bar goes In Force, look for the **LOW of the outside bar** to be breached as the BF continues to expand (or the HIGH, in bearish case)

### Hammer or Shooting Star Following an Outside Bar
- **Hammer after Outside Bar → In Force:** Look for the **HIGH of the Outside Bar** to be breached as the BF expands
- **Shooting Star after Outside Bar → In Force:** Look for the **LOW of the Outside Bar** to be breached
- Use the fractal triangle on the lower TF to gauge magnitude

### Reclaiming the Range
Any actionable signal that **reverses back into a previous range** = possible failure of price discovery. Creates the potential for the BF to test the other side of the range.
- Hammer reclaiming range high → potential BF to test previous high
- Shooting star reclaiming range high → BF forming to the downside

### Broadening Formations as Support/Resistance
Previous BF highs and lows become support and resistance levels. As time passes, if price doesn't reclaim the previous range, the losing positions continue to unwind causing price to drift further away. Look for a new BF to form, then line up the former BF level for added support/resistance.

### TFC Within Broadening Formations
Bullish Full TFC can occur even at the BOTTOM of a broadening formation (when price is dropping to a new low), depending on WHEN during the time period it happens.

### Drawing Broadening Formations
- Draw AFTER a change in TFC, backwards from most recent highs and lows
- Physical lines = visual representations only, subject to change with any TFC change or any new high/low
- Look for **LARGE outside bars** on higher TFs to identify major reclaim levels
- The lines represent potential "reclaim" levels — far more important to look for TFC Change + actionable signal that reclaims a previous range than to focus on the lines

---

## Importance of Time

- Signals are only In Force while the triggering bar's time period is still open
- **Want signals to trigger as early as possible** — gives more time to get reconfirming signals and add to position
- A Monthly signal In Force → you have the rest of that month to look for shorter-term signals to reconfirm it
- As a signal approaches exhaustion, the Level of Defense rises

### Turnaround Tuesday
- Market rallies Monday; takes out previous Friday's highs
- Stocks that formed inside days on Monday = too weak to rally with the market
- If the market pulls back Tuesday → all those weak stocks' inside day signals trigger the reversal breakdown simultaneously
- This is a combination negation reversal

### Identifying Natural Buyers/Sellers
Find stocks that are in **complete conflict** with their sector ETF or broader average:
- SPY in Full TFC up + individual stock in Full TFC down → **natural sellers** (institutions) HAVE to be in that stock
- The inside 60-min up signal in that stock has every reason to Rev Strat (and no reason to work)
- Also look for stocks with **long green or red bars midway through a time frame** (2nd week on monthly, Wednesday on weekly, midday on daily) — these have strong momentum but no current actionable signal, alert you to watch for shorter-TF setups

### Sideways 30
Price that stays between the highs and lows of the 15-minute and 45-minute periods (not just top/bottom of the hour) = "Sideways Inside 30." This tracks additional 30-minute participation groups that most traders ignore.

---

## Trade Execution Rules (Stop Placement)

| Signal | Entry | Stop |
|---|---|---|
| Regular Hammer | BUY above HIGH of hammer | 1 cent below the bar that **triggers** the hammer |
| Regular Shooting Star | SELL below LOW of shooting star | 1 cent above the bar that **triggers** the shooting star |
| Momentum Hammer | BUY above HIGH; triggers immediately | 1 cent below the bid after taking the offer |
| Momentum Shooting Star | SELL below LOW; triggers immediately | 1 cent above the offer after hitting the bid |
| Bullish Inside Bar Breakout | BUY above inside bar's HIGH | 1 cent below the LOW of the bar that breaks the inside bar |
| Bearish Inside Bar Breakout | SELL below inside bar's LOW | 1 cent above the HIGH of the bar that breaks the inside bar |
| Bullish 2-Bar Rev Strat | BUY 1 cent above the hammer | 1 cent below the bid immediately |
| Bearish 2-Bar Rev Strat | SELL 1 cent below the shooting star | 1 cent above the offer immediately |
| Bullish 1-Bar Rev Strat | BUY 1 cent above the inside bar being reversed | 1 cent below the bid immediately |
| Bearish 1-Bar Rev Strat | SELL 1 cent below the inside bar being reversed | 1 cent above the offer immediately |
| Bullish/Bearish Kicking | Need additional intraday signals above/below opening price of day | Per the intraday signal taken |

**Never move a stop AWAY from the direction of price.**

---

## Risk Management

### Level of Defense
- More evidence (stacked signals, Full TFC, BF alignment) = **looser stop** (high conviction)
- Less evidence / approaching exhaustion = **tighter stop**
- The checklist determines how wide or tight the Level of Defense should be

### Adding to a Position
Only add when:
1. The full position is NOT stopped out, AND
2. Another setup triggers where the stop on the ADD would still render a profit if both legs are stopped

### Trailing / Managing Exits (3 Options)
When approaching exhaustion:
1. Move stop up aggressively on the full position (maximizes time value, misses further runs)
2. Aggressive stop on a portion; move remainder to cost + commissions
3. Move full position to cost + commissions, then use PSAR on shortest TF to trail (most profit, most risk)

**PSAR usage:** Use on weekly for long-term investments, daily for swing trades, shortest available TF for day trades.

### By Trade Type
- **Long-term investments:** Monthly signals + shorter-TF combinations for entry; PSAR on weekly to trail
- **Medium-term swing:** Monthly or weekly entry; daily PSAR to trail; can hold through BF until pattern completes
- **Day trades:** Stop per signal execution rules; use PSAR on shortest TF as signal approaches exhaustion

---

## VIX ETNs (Secret Weapons): VXX, UVXY, TVIX

VIX ETNs must continually "roll" expiring options into new ones. This roll GUARANTEES long-term decay — they MUST decline over time. However, they can spike **significantly** during fear/volatility events.

### Key Concepts
- **Contango:** Normal state. Front-month options cheaper than back-month → ETNs decay steadily
- **Backwardation:** Fear state. Front-month options MORE expensive than back-month (e.g., Brexit, major elections, full TFC down in broader averages) → ETNs can spike violently
- Monitor at **VixCentral.com** or **CBOE.com**

### Trading Rules for VIX ETNs
- **Entry:** ONLY from entries that come DOWN off the HIGHS of Broadening Formations (not off bottoms)
- **Do NOT look to cover** just because price reaches the bottom of a BF — these products make continuously lower BFs due to decay, unlike stocks which tend to reclaim previous BF ranges
- **Cover when:** (1) Full TFC to downside in broader averages (fear spike risk), (2) Backwardation condition, or (3) any entry goes negative
- **BF expansion upside:** Cover to protect from spike, then re-enter when the triangle is reclaimed to the downside

---

## The Actionable Signal List (ASL)

Daily watchlist organized by which Strat signal each stock is currently showing, across 3 major timeframes:

**Columns:** Inside Day (ID), Inside Week (IW), Inside Month (IM), then all daily signals, then all weekly signals, then all monthly signals

**Signals tracked per timeframe:** Hammer, Shooter, Hammer Up (inside bar breaks up hammer-style), Shoot Down (inside bar breaks down shooter-style), Rev Strat Hammer, Rev Strat Shooter, Prev Inside Up, Prev Inside Down, Hammer Counter Shooter, Shooter Counter Hammer, Outside Bar, Outside Bar Up, Outside Bar Down

Symbols sourced from TC2000 scans.

---

## Trade Checklist (8 Questions — Pre-Trade)

Before entering any trade:

1. **How many actionable signals do we have, and what are they?**
   - Don't enter on a single inside 15-min alone. Stack from Monthly → Weekly → Daily → intraday.

2. **What actionable signals will be created if this trade works? What if it fails?**
   - Think forward — which conditions does success or failure create?

3. **Is the trade in the direction of the Participation Group in control (based on TFC)?**

4. **Is this a momentum or retracement trade? Where is it in the broadening formation?**

5. **How much time until exhaustion of the actionable signal(s) and TFC?**

6. **Where is my stop? (Level of Defense)**

7. **How will I manage risk — adding, reducing, or exiting?**

8. **Does this trade line up with the conditions of correlated broader averages or ETFs?**

---

## Winning vs. Losing Trade Profile

**Winning trades:**
- Scenario 2 or 3 in your favor
- Time frame continuity in your favor

**Losing trades:**
- Chopped up trading a scenario 1 (inside bar with no clear direction)
- Scenario 2 or 3 going against you
- Time frame continuity going against you

---

## Pattern Identification Reference (for scanning historical price data)

When identifying patterns algorithmically from OHLC data:

### Bar Classification
- **Inside (1):** `high[i] <= high[i-1] AND low[i] >= low[i-1]`
- **2U:** `high[i] > high[i-1] AND low[i] >= low[i-1]`
- **2D:** `low[i] < low[i-1] AND high[i] <= high[i-1]`
- **3 (Outside):** `high[i] > high[i-1] AND low[i] < low[i-1]`

### Hammer Detection
- Bar is 2D (made a lower low)
- `close >= open + 0.67 * (high - low)` — close in top 33%
- OR: `close >= low + 0.67 * (high - low)` — close near the top of range
- Signal triggers: price crosses above `high[i]`

### Shooting Star Detection
- Bar is 2U (made a higher high)
- `close <= low + 0.33 * (high - low)` — close in bottom 33%
- Signal triggers: price crosses below `low[i]`

### Inside Bar Breakout
- Current bar classified as 1 (inside)
- Bullish trigger: price crosses above `high[i]`
- Bearish trigger: price crosses below `low[i]`
- Avoid if inside bar formed in middle of Mother Bar range and Mother Bar range is large

### Rev Strat (2-Bar)
- `bar[i-1]` = Inside (1)
- `bar[i]` = Hammer → Bullish 2-Bar Rev Strat
- `bar[i]` = Shooting Star → Bearish 2-Bar Rev Strat

### Rev Strat (1-Bar)
- `bar[i-1]` = Inside (1)
- `bar[i]` = Outside (3) — broke both sides
- If `close[i]` is in upper portion → Bullish 1-Bar Rev Strat (broke down then reversed up)
- If `close[i]` is in lower portion → Bearish 1-Bar Rev Strat (broke up then reversed down)

### 2-1-2 Reversal (Rev Strat Hammer)
- `bar[i-2]` = 2D, `bar[i-1]` = 1, `bar[i]` = 2U → Bullish 2-1-2
- `bar[i-2]` = 2U, `bar[i-1]` = 1, `bar[i]` = 2D → Bearish 2-1-2

### 2-2 Reversal
- `bar[i-1]` = 2U (or 2D), `bar[i]` = 2D (or 2U) — immediate directional flip

### Kicking Pattern
- **Bullish:** `bar[i-1]` is red (close < open), `bar[i]` opens **above** `high[i-1]` (gap up)
- **Bearish:** `bar[i-1]` is green (close > open), `bar[i]` opens **below** `low[i-1]` (gap down)

### Broadening Formation
- Series of bars where successive bars make both higher highs and lower lows
- Formally: any Outside Bar proves a BF exists at that level
- On a lower TF: visualized as a "fractal triangle"

### TFC State
- For each bar, compare `close` to `open` of that timeframe's bar
- Green = close > open; Red = close < open
- Full TFC: all 4 major TFs (monthly, weekly, daily, 60-min) are same color
- Conflict: 1 or 2 TFs differ from the others

**Implementation note (this app):** `skills/the_strat.py` has no intraday feed,
so 60-minute is out of scope. Full TFC alignment is computed over **weekly,
monthly, quarterly, and yearly** — Daily is deliberately excluded from the
alignment check itself (per product decision: it's the noisiest of the
groups and shouldn't be able to single-handedly flip "all participation
groups agree" to a conflict). Quarterly and yearly aren't part of Rob Smith's
canonical 4 major groups above — they're added deliberately so Full TFC
reflects the longer-horizon participation groups relevant to this app's
position/swing trades.

Daily isn't dropped entirely, though: it's still classified and checked for a
**notable candle** — hammer, shooting star, outside bar, kicking pattern, or
reversal (any actionable pattern besides a plain inside-bar equilibrium
setup) — and called out separately (`daily_notable_candle` in `the_strat.run`'s
output) even though it no longer moves the alignment needle. See
`component-specs/agent-runner/tools/price.md` and
`component-specs/agent-runner/agents/technical_analyst.md`.
