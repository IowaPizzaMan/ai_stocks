# agent-runner/tools/insider.py

## Purpose
Fetches Form 4 insider transactions and Finnhub MSPR (insider sentiment ratio) for a ticker. Uses FMP as primary, Finnhub as supplement for MSPR, SEC EDGAR as fallback.

## Functions

### `get_insider_activity(ticker: str) -> dict`

```python
def get_insider_activity(ticker: str) -> dict:
    # FMP insider transactions (last 90 days)
    transactions = fmp_get(f"v4/insider-trading?symbol={ticker}&limit=50")
    
    # Finnhub MSPR — monthly insider sentiment ratio
    to_date = today()
    from_date = three_months_ago()
    mspr = finnhub_get(f"stock/insider-sentiment?symbol={ticker}&from={from_date}&to={to_date}")
    
    # Finnhub raw insider transactions (cross-reference)
    fh_transactions = finnhub_get(f"stock/insider-transactions?symbol={ticker}")
    
    return {
        "transactions_fmp": transactions,
        "transactions_finnhub": fh_transactions.get("data", []),
        "mspr_monthly": mspr.get("data", [])
    }
```

## Transaction Normalization
Both FMP and Finnhub return slightly different field names. Normalize to:
```python
{
    "name": str,
    "title": str,
    "transaction_type": "purchase" | "sale" | "option_exercise" | "gift",
    "shares": int,
    "price_per_share": float,
    "total_value": float,
    "date": "YYYY-MM-DD",
    "filing_date": "YYYY-MM-DD",
    "is_open_market": bool  # True for purchase/sale, False for option exercise
}
```

## EDGAR Fallback
If FMP quota is near limit, fall back to SEC EDGAR:
```python
def edgar_get_form4(ticker: str) -> list:
    # 1. Get CIK for ticker
    # 2. Query submissions endpoint for Form 4 filings
    # 3. Parse XML of each filing (last 10)
    # Rate limit: 10 req/sec, sleep 0.1s between requests
    pass
```

## Dependencies
- `httpx`
- `pymongo` (for FMP quota tracking)
- `time` (rate limit sleep for EDGAR)
