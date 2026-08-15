# agent-runner/tools/financials.py

> **Sourcing updated 2026-08-15** (specs/017-fmp-migration-admin): `get_financials()`'s FMP fetch now routes through the shared `tools/fmp_client.py` (throttle + budget guard), and the old free-tier `WARN_AT`/`SKIP_NON_ESSENTIAL_AT` counters were removed in favor of that shared guard. `get_earnings_data()` previously fetched via yfinance (estimates/trend/revisions/recs); it's now FMP (`earnings`, `analyst-estimates`, `grades`). `eps_trend`/`eps_revisions` have no FMP equivalent on this plan and are a **documented drop** — kept as empty values for shape compatibility with `agents/fundamental_analyst.py`. See `contracts/fmp-migration-map.md` row 5.

## Purpose
Fetches and caches company financial statements and earnings data from FMP, with MongoDB as the cache layer. Re-fetches quarterly or when a new period is detected.

## Functions

### `get_financials(ticker: str) -> dict`
Returns income statement, balance sheet, cash flow, and key ratios.

**Caching logic:**
1. Check MongoDB `financials_cache` collection for `{ ticker, fetched_at }` within the last 90 days
2. If cache hit → return cached document
3. If cache miss → call FMP, store result with `fetched_at: now`, return

```python
def get_financials(ticker: str) -> dict:
    cached = db.financials_cache.find_one(
        { "ticker": ticker, "fetched_at": { "$gt": ninety_days_ago() } }
    )
    if cached:
        return cached["data"]
    
    data = {
        "income_annual": fmp_get(f"v3/income-statement/{ticker}?period=annual&limit=4"),
        "income_quarterly": fmp_get(f"v3/income-statement/{ticker}?period=quarter&limit=8"),
        "balance_annual": fmp_get(f"v3/balance-sheet-statement/{ticker}?period=annual&limit=4"),
        "cashflow_annual": fmp_get(f"v3/cash-flow-statement/{ticker}?period=annual&limit=4"),
        "ratios": fmp_get(f"v3/ratios/{ticker}?period=annual&limit=4"),
        "key_metrics": fmp_get(f"v3/key-metrics/{ticker}?period=annual&limit=4"),
        "growth": fmp_get(f"v3/income-statement-growth/{ticker}")
    }
    db.financials_cache.replace_one(
        { "ticker": ticker }, { "ticker": ticker, "data": data, "fetched_at": now() }, upsert=True
    )
    return data
```

### `get_earnings_data(ticker: str) -> dict`
Fetches earnings history, estimates, and surprises. Uses yfinance as primary (no rate limit), FMP as supplement.

```python
def get_earnings_data(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    return {
        "earnings_dates": tk.get_earnings_dates(limit=8).reset_index().to_dict(orient="records"),
        "eps_trend": tk.get_eps_trend().to_dict(),
        "eps_revisions": tk.get_eps_revisions().to_dict(),
        "forward_estimates": tk.get_earnings_estimate().to_dict(),
        "analyst_recs": tk.get_recommendations().to_dict(orient="records")
    }
```

## FMP Helper

> **API version (verified 2026-08-02):** the legacy `/api/v3/...` endpoints return
> 403 for this account — FMP retired them for accounts created after their 2025
> migration. Use the **stable** API: `https://financialmodelingprep.com/stable/`
> with query-style paths (`income-statement?symbol=AAPL&period=annual&limit=4`).
> Constituent endpoints (`sp500-constituent`, `nasdaq-constituent`) are 402
> paid-tier — breadth's Wikipedia/slickcharts scrape fallback is the de facto
> constituent source on the free tier. Quarterly statements 402 beyond ~4
> periods of history (`limit=8` rejected, `limit=4` works) — income_quarterly
> uses `limit=4`.

```python
import httpx
FMP_BASE = "https://financialmodelingprep.com/stable/"
FMP_KEY = os.getenv("FMP_API_KEY")

def fmp_get(path: str) -> list | dict:
    sep = "&" if "?" in path else "?"
    url = f"{FMP_BASE}{path}{sep}apikey={FMP_KEY}"
    r = httpx.get(url, timeout=15)
    r.raise_for_status()
    return r.json()
```

## Rate Limit Protection
- FMP free tier: 250 calls/day
- Aggressive caching (90-day TTL for financials) means each ticker costs ~7 FMP calls on first fetch, then 0 for 90 days
- Track daily call count in MongoDB `fmp_usage` collection; log warning at 200 calls, skip non-essential endpoints at 240

## Dependencies
- `httpx`
- `yfinance`
- `pymongo`
