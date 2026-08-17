# agent-runner/tools/financials.py

> **Sourcing updated 2026-08-15** (specs/017-fmp-migration-admin): `get_financials()`'s FMP fetch now routes through the shared `tools/fmp_client.py` (throttle + budget guard), and the old free-tier `WARN_AT`/`SKIP_NON_ESSENTIAL_AT` counters were removed in favor of that shared guard. `get_earnings_data()` previously fetched via yfinance (estimates/trend/revisions/recs); it's now FMP (`earnings`, `analyst-estimates`, `grades`). `eps_trend`/`eps_revisions` have no FMP equivalent on this plan and are a **documented drop** — kept as empty values for shape compatibility with `agents/fundamental_analyst.py`. See `contracts/fmp-migration-map.md` row 5.

## Purpose
Fetches and caches company financial statements and earnings data from FMP, with MongoDB as the cache layer. Re-fetches quarterly or when a new period is detected.

## Functions

### `get_financials(ticker: str) -> dict`
Returns income statement, balance sheet, cash flow, and key ratios.

**Caching logic** (specs/018-fix-financials-cache-gap): each of the seven statement
keys carries an `outcomes[key]` marker alongside `data[key]` in the `financials_cache`
document — `confirmed` (FMP answered 200 for that key; the payload may legitimately be
empty) or `unavailable` (the fetch degraded to `[]` on a temporary 402/403 plan
restriction or the daily budget cap). Only `unavailable` keys are eligible for retry.

1. Check MongoDB `financials_cache` for `{ ticker, fetched_at }` within the last 90 days.
2. **Cache miss** (no doc, or older than 90 days) → full fetch of all seven keys, each
   recording its own outcome; write `{ ticker, data, outcomes, fetched_at: now }`.
3. **Cache hit** → derive `outcomes` (legacy docs with no `outcomes` field get it lazily:
   empty value → `unavailable`, non-empty → `confirmed`). Re-fetch only the keys whose
   outcome is not `confirmed`, merge the results into `data`/`outcomes`, and persist with
   `$set` on `data` and `outcomes` only — **`fetched_at` is left untouched** so a partial
   retry doesn't slide the 90-day window. If every key is already `confirmed`, return the
   cached `data` with zero FMP calls.

This is what makes an all-402 fetch (e.g. a symbol not covered by the current plan on the
day it was first fetched) self-correct on a later run once FMP starts covering it, instead
of being served as "no data" for the rest of the 90-day window.

```python
def get_financials(ticker: str) -> dict:
    cached = db.financials_cache.find_one(
        { "ticker": ticker, "fetched_at": { "$gt": ninety_days_ago() } }
    )
    if cached:
        data, outcomes = cached["data"], cached.get("outcomes") or derive_legacy_outcomes(cached["data"])
        retry_keys = [k for k in ENDPOINTS if outcomes.get(k) != "confirmed"]
        if not retry_keys:
            return data
        for key in retry_keys:
            data[key], outcomes[key] = fetch_statement(ticker, key)  # ("[]", "unavailable") on 402/403/budget cap
        db.financials_cache.update_one({ "ticker": ticker }, { "$set": { "data": data, "outcomes": outcomes } })
        return data

    data, outcomes = {}, {}
    for key in ENDPOINTS:
        data[key], outcomes[key] = fetch_statement(ticker, key)
    db.financials_cache.replace_one(
        { "ticker": ticker }, { "ticker": ticker, "data": data, "outcomes": outcomes, "fetched_at": now() }, upsert=True
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
