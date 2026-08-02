# agent-runner/tools/macro.md

## Purpose
Fetches macroeconomic indicator time series from FRED. Data is cached in MongoDB with a 24-hour TTL (macro changes slowly — no need to re-fetch per ticker).

## Functions

### `get_macro_data(indicators: list[str] = None) -> dict`
Returns current and recent values for a set of FRED series.

**Default indicators fetched** (see DATA_SOURCES.md for full list):
`CPIAUCSL, PCEPI, FEDFUNDS, UNRATE, GDP, GDPC1, DGS10, DGS2, T10Y2Y, T10Y3M, VIXCLS, UMCSENT`

```python
FRED_BASE = "https://api.stlouisfed.org/fred/"
FRED_KEY = os.getenv("FRED_API_KEY")

def get_macro_data(indicators: list[str] = None) -> dict:
    if indicators is None:
        indicators = DEFAULT_INDICATORS
    
    # Check 24hr cache
    cached = db.macro_cache.find_one({ "fetched_at": { "$gt": one_day_ago() } })
    if cached:
        return { k: cached["data"][k] for k in indicators if k in cached["data"] }
    
    results = {}
    for series_id in indicators:
        url = f"{FRED_BASE}series/observations?series_id={series_id}&api_key={FRED_KEY}&file_type=json&sort_order=desc&limit=12"
        r = httpx.get(url, timeout=15)
        observations = r.json()["observations"]
        results[series_id] = [
            { "date": o["date"], "value": float(o["value"]) if o["value"] != "." else None }
            for o in observations
        ]
    
    db.macro_cache.replace_one({}, { "data": results, "fetched_at": now() }, upsert=True)
    return results
```

### `get_yield_curve_status() -> dict`
Derived helper — computes current spread values and inversion status.

```python
def get_yield_curve_status() -> dict:
    macro = get_macro_data(["T10Y2Y", "T10Y3M", "DGS10", "DGS2"])
    t10y2y = latest(macro["T10Y2Y"])
    t10y3m = latest(macro["T10Y3M"])
    return {
        "10y_2y_spread": t10y2y,
        "10y_3m_spread": t10y3m,
        "inverted": t10y2y < 0 or t10y3m < 0,
        "inversion_severity": "deep" if t10y2y < -0.5 else "mild" if t10y2y < 0 else "none"
    }
```

## Dependencies
- `httpx`
- `pymongo`
