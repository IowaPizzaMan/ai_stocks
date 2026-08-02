# Position Management Agent — Spec

## Overview

This agent manages open swing trade positions using the **Stair-Step Stop Loss Method**. Its core job is to trail stops upward each day as winning trades progress, maximizing gains on "home run" trades while containing losses on positions that fail.

The agent is reactive and daily — it runs once per trading day (after market close or pre-market) and outputs updated stop levels for each active position.

---

## Core Strategy: Stair-Step Stop Loss

**Rule:** Once a swing trade is active and moving in the intended direction, move the stop loss to just below the **previous session's daily low** at the end of each trading day. Continue walking the stop up each day until the position is stopped out.

**Exit trigger:** The position is exited when price closes below (or intraday breaks below) the prior day's low.

**Goal:** Let winners run as long as price holds its daily structure. Capture multi-week or multi-month moves on breakout momentum stocks without capping upside with a fixed target.

---

## Inputs

The agent requires the following data per active position:

| Field | Description |
|---|---|
| `ticker` | Stock symbol |
| `entry_price` | Price at which the position was entered |
| `entry_date` | Date of entry |
| `current_stop` | The stop loss level currently in effect |
| `shares` | Number of shares held |
| `breakout_level` | The key price level that triggered the entry (e.g., $37.00 for NTNX) |
| `daily_OHLC` | Daily open, high, low, close for the current and prior session |
| `market_condition` | Agent-assessed or user-flagged: `favorable` / `neutral` / `unfavorable` |

---

## Daily Workflow

### Step 1 — Fetch Prior Day's Low
For each open position, retrieve the prior trading session's daily low.

### Step 2 — Calculate New Stop
```
new_stop = prior_day_low - buffer
```
`buffer` is a small cushion below the low to avoid stop-hunting noise. Default: **$0.10–$0.25** (configurable per position or globally). For higher-priced stocks, buffer can be set as a percentage (e.g., 0.3%).

### Step 3 — Apply Stop Only If Higher
The stop is a **trailing stop that only moves up**, never down.

```
if new_stop > current_stop:
    current_stop = new_stop
    action = "UPDATE"
else:
    action = "HOLD"  # keep existing stop, do not lower it
```

### Step 4 — Check Market Conditions
If `market_condition == "unfavorable"`, flag the position for manual review. The agent may recommend tightening stops or exiting early rather than continuing to trail. It does **not** auto-exit unless explicitly configured to do so.

### Step 5 — Check Exit Trigger
```
if current_price <= current_stop:
    action = "EXIT"
    reason = "Price broke below prior day's low"
```

### Step 6 — Output Action Report
Emit a structured report per position with the action (`UPDATE`, `HOLD`, `EXIT`), new stop level, and unrealized P&L.

---

## Output Schema (per position)

```json
{
  "ticker": "NTNX",
  "action": "UPDATE",
  "prior_day_low": 48.20,
  "new_stop": 47.95,
  "previous_stop": 44.50,
  "stop_moved_by": 3.45,
  "entry_price": 37.00,
  "unrealized_pnl_pct": 32.1,
  "days_held": 18,
  "market_condition": "favorable",
  "notes": "Stop walked up $3.45. Position continues to trend."
}
```

---

## Position State Machine

```
ENTRY → ACTIVE (trailing) → EXITED
               ↓
         [manual review if market unfavorable]
```

State transitions:
- `ACTIVE` → `EXITED`: stop triggered (price ≤ current_stop)
- `ACTIVE` → `REVIEW`: market condition turns unfavorable
- `REVIEW` → `ACTIVE`: market condition improves
- `REVIEW` → `EXITED`: user confirms exit or stop hits

---

## Configuration Parameters

| Parameter | Default | Description |
|---|---|---|
| `stop_buffer_fixed` | $0.15 | Fixed dollar cushion below prior day's low |
| `stop_buffer_pct` | null | Alternative: % buffer (overrides fixed if set) |
| `use_close_vs_intraday` | `intraday` | Trigger exit on intraday break or only on close |
| `min_profit_to_trail` | 5% | Don't trail until position is at least X% profitable |
| `max_days_held` | null | Optional: auto-flag positions held beyond N days |
| `market_condition_source` | `manual` | `manual` or `auto` (agent assesses via market breadth) |

---

## Market Condition Assessment (if `auto`)

The agent evaluates market conditions using a set of signals to determine if swing trading is "favorable":

- Major index trend: SPY / QQQ above or below 20-day MA
- VIX level: above 25 = unfavorable
- Advance/decline line: contracting = unfavorable
- Number of stocks making new 52-week highs vs. lows

If 2+ signals are negative, `market_condition` is set to `unfavorable` and trailing stops are paused or tightened.

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Gap down open below stop | Exit flagged immediately at open; notify user |
| Stock halted | Hold position, flag for manual review |
| Earnings upcoming | Warn user; optionally tighten stop or recommend exit before event |
| Stop never moves (stock consolidates flat) | Emit `HOLD` with note; flag if no upward movement in N days |
| Position goes negative from entry | Flag; revert to initial stop loss if still above entry |

---

## Notifications / Alerts

The agent should emit alerts when:
- A stop is updated (new level + how much it moved)
- A stop is triggered (exit signal with P&L summary)
- Market condition changes to unfavorable
- An earnings date is within 3 trading days of the position

---

## Integration Points

- **Data source:** Daily OHLC feed (e.g., Polygon.io, yfinance, Alpaca)
- **Broker API (optional):** Submit stop orders automatically via broker API (Alpaca, IBKR, TD Ameritrade)
- **Portfolio tracker:** Write updated stop levels back to a positions ledger (CSV, Google Sheet, or database)
- **Notification:** Push alerts via email, SMS, or Slack

---

## What This Agent Does NOT Do

- It does not select trades or entries — that is handled upstream by a scanner/signal agent
- It does not size positions — that is handled at entry time
- It does not use fixed profit targets — upside is open-ended by design
- It does not short positions (long-only by default; short support can be added as an extension)
