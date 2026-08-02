# agent-runner/tools/earnings_calendar.py

## Purpose
Fetches the upcoming earnings calendar from FMP (broad sweep across all companies) and enriches each company with historical post-earnings move data from Finnhub. This is the data foundation for the EarningsScannerAgent.

## Functions

### `get_earnings_calendar(days_ahead: int = 7) -> list[dict]`
Pulls every company reporting in the next N days, then pre-screens for viability.

```python
import httpx
from datetime import date, timedelta

def get_earnings_calendar(days_ahead: int = 7) -> list[dict]:
    today = date.today().isoformat()
    end = (date.today() + timedelta(days=days_ahead)).isoformat()
    
    # FMP broad calendar — returns all companies in date range
    raw = fmp_get(f"v3/earning_calendar?from={today}&to={end}")
    
    # Pre-screen: drop micro-caps and tickers with no earnings history
    MIN_MARKET_CAP = 500_000_000  # $500M floor (configurable via env)
    
    screened = []
    for entry in raw:
        if entry.get("marketCap", 0) < MIN_MARKET_CAP:
            continue
        screened.append({
            "ticker": entry["symbol"],
            "company": entry.get("name", ""),
            "report_date": entry["date"],
            "report_time": entry.get("time", "unknown"),  # "bmo" / "amc" / "unknown"
            "eps_estimate": entry.get("epsEstimated"),
            "revenue_estimate": entry.get("revenueEstimated"),
            "market_cap": entry.get("marketCap"),
            "sector": entry.get("sector"),
        })
    
    return screened
```

### `get_earnings_history(ticker: str, num_quarters: int = 8) -> dict`
Fetches historical EPS data and reconstructs the post-earnings price move for each quarter. This is the core scoring input.

```python
def get_earnings_history(ticker: str, num_quarters: int = 8) -> dict:
    # Historical EPS: estimate vs actual, surprise %
    eps_history = finnhub_get(f"stock/earnings?symbol={ticker}")
    
    # For each earnings date, look up the next-day price move
    moves = []
    for quarter in eps_history[:num_quarters]:
        report_date = quarter.get("period")
        if not report_date:
            continue
        
        # Fetch price around earnings date: day before and day after
        from_ts = date_to_unix(report_date, offset_days=-1)
        to_ts   = date_to_unix(report_date, offset_days=+3)
        candles = finnhub_get(f"stock/candle?symbol={ticker}&resolution=D&from={from_ts}&to={to_ts}")
        
        if candles.get("s") != "ok" or len(candles.get("c", [])) < 2:
            continue
        
        # Price move = (close on day after report) / (close on day before report) - 1
        pre_close  = candles["c"][0]
        post_close = candles["c"][1]
        move_pct = round((post_close / pre_close - 1) * 100, 2)
        
        moves.append({
            "period": report_date,
            "eps_estimate": quarter.get("estimate"),
            "eps_actual": quarter.get("actual"),
            "surprise_pct": quarter.get("surprisePercent"),
            "beat": (quarter.get("actual") or 0) > (quarter.get("estimate") or 0),
            "move_pct": move_pct,
            "move_abs": abs(move_pct)
        })
    
    avg_abs_move = sum(m["move_abs"] for m in moves) / len(moves) if moves else 0
    beat_rate    = sum(1 for m in moves if m["beat"]) / len(moves) if moves else 0
    
    return {
        "ticker": ticker,
        "quarters": moves,
        "avg_abs_move_pct": round(avg_abs_move, 2),
        "beat_rate": round(beat_rate, 2),
        "num_quarters": len(moves)
    }
```

## Caching
- Calendar data: cache 4 hours (changes infrequently during the day). Key: `earnings_calendar_{date}_{days_ahead}`.
- Earnings history: cache 24 hours per ticker. Historical data doesn't change.

## Rate Limit Notes
- FMP: `v3/earning_calendar` counts as 1 call regardless of how many companies come back. Very efficient.
- Finnhub: `stock/earnings` + `stock/candle` = 2 calls per ticker for history. With 30 candidates, that's 60 Finnhub calls at 60/min — takes ~1 minute. Run with `ThreadPoolExecutor` to parallelize across tickers.

## Dependencies
- `httpx`
- `pymongo`
- `datetime`, `concurrent.futures`
