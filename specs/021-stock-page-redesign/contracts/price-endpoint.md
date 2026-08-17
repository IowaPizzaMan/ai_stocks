# Contract: Price Endpoint — `yearly` resolution

`GET /stocks/{ticker}/price?resolution={daily|weekly|monthly|yearly}`

Existing endpoint ([backend/routers/price.py](../../../backend/routers/price.py)); this feature adds the `yearly` value. All other behavior (1h Mongo cache in `price_cache`, 404 on no data, 422 on bad resolution) is unchanged.

## Request

| Param | Values | Change |
|-------|--------|--------|
| `resolution` | `daily`, `weekly`, `monthly`, **`yearly` (new)** | `RESOLUTIONS["yearly"] = ("15y", "1y")` |

## Response (unchanged shape)

```json
{
  "ticker": "AAPL",
  "resolution": "yearly",
  "bars": [
    { "date": "2012-12-31", "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0 }
  ]
}
```

## Semantics

- Yearly bars = pandas `resample("YE")` over the full FMP EOD history: `Open=first, High=max, Low=min, Close=last, Volume=sum`, rows with no data dropped.
- Sliced to the most recent 15 years (`_slice_period` with `"15y"`); tickers with shorter history return all complete years available — never an error (FR-006).
- Bars ascending by date; `date` is the resample bin label (year end). The in-progress year appears as its year-to-date aggregate (same convention as the existing monthly resample's current month).
- Frontend mapping (displayWindow.ts): panels D/W/M/Y → resolutions `daily/weekly/monthly/yearly`; display windows D=90, W=78, M=36, Y=15 bars.

## Tests (backend/tests/test_price.py)

- `yearly` accepted; unknown resolution still 422.
- Resampled yearly bars: one bar per calendar year, correct first/max/min/last/sum aggregation from a synthetic daily fixture.
- 20-year fixture → 15 bars returned; 2-year fixture → 2 bars, no error.
- Cache round-trip keyed on (`ticker`, `yearly`).
