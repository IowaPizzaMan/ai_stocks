# agent-runner/tools/institutional.py

> **Sourcing updated 2026-08-15** (specs/017-fmp-migration-admin): this module is now **read-only**. It previously fetched live from yfinance (13F/institutional endpoints all 402/403'd on FMP for this account). yfinance is retired, and the user confirmed 13F is **not entitled** on the paid FMP plan either. `get_institutional_holdings()` now serves only whatever was cached before the migration — no live fetch of any kind — always flagged `stale: true`. The `fund_holdings` (ETF/fund holdings, entitled) and `insider_feed` (market-wide insider activity, entitled) datasets from specs/017-fmp-migration-admin are the intended replacement signals. The pseudocode below describes the pre-migration fetch behavior; see `agent-runner/tools/institutional.py` for the current read-only implementation.

## Purpose (historical — see note above)
Fetches 13F institutional holdings data from FMP. Tracks QoQ changes in institutional ownership. SEC EDGAR as fallback.

## Functions

### `get_institutional_holdings(ticker: str) -> dict`

```python
def get_institutional_holdings(ticker: str) -> dict:
    # Check cache (13F data updates quarterly — 90 day TTL)
    cached = db.institutional_cache.find_one({
        "ticker": ticker,
        "fetched_at": { "$gt": ninety_days_ago() }
    })
    if cached:
        return cached["data"]
    
    # Get CIK for ticker
    cik_result = fmp_get(f"v3/cik-search/{ticker}")
    
    # Get all 13F filing dates for this ticker
    # Note: FMP's 13F endpoints are by fund CIK — search by ticker instead
    # Use stock screener or institutional holders endpoint
    holders = fmp_get(f"v3/institutional-holder/{ticker}")
    
    data = {
        "current_holders": holders,
        "total_institutional_pct": sum_institutional_pct(holders),
        "fetched_quarter": current_quarter()
    }
    
    db.institutional_cache.replace_one(
        { "ticker": ticker }, { "ticker": ticker, "data": data, "fetched_at": now() }, upsert=True
    )
    return data
```

### `compute_qoq_changes(ticker: str) -> dict`
Compares current quarter's holdings to last quarter stored in MongoDB to compute net additions/reductions.

### `get_recent_13f_changes(since: datetime, universe: list[str] | None = None) -> list[dict]`
Market-wide variant used by `InstitutionalFlowScannerAgent` (`institutional_flow_scanner.md`). Scans 13F changes filed since `since` across a tracked universe rather than fetching one ticker's holders.

```python
def get_recent_13f_changes(since: datetime, universe: list[str] | None = None) -> list[dict]:
    # Default universe: watchlist tickers ∪ any ticker with a prior analysis document
    tickers = universe or (db.watchlist.distinct("ticker") + db.analyses.distinct("ticker"))

    changes = []
    for ticker in set(tickers):
        holders = get_institutional_holdings(ticker)  # cached, 90-day TTL — cheap to re-check
        filed_since = [h for h in holders["current_holders"] if h["filing_date"] >= since]
        changes.extend({**h, "ticker": ticker} for h in filed_since)
    return changes
```

Deliberately reuses the existing per-ticker cache rather than a separate bulk 13F pull — FMP's 250 call/day limit means this loop only does real work for tickers whose cache is stale.

## Dependencies
- `httpx`
- `pymongo`

## Used By
- `agents/institutional_analyst.md` (`get_institutional_holdings`, per-ticker)
- `agents/institutional_flow_scanner.md` (`get_recent_13f_changes`, market-wide)
