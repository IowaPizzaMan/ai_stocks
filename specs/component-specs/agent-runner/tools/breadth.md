# agent-runner/tools/breadth.md

## Purpose
Provides McClellan Oscillator readings (NYMO for NYSE, NAMO for NASDAQ) — the primary market timing inputs for the RecommenderAgent and market_flow skill.

> **Sourcing (verified 2026-08-02, updated 2026-08-15):** the `$NYMO` / `$NAMO` symbols are StockCharts-proprietary and are **not fetchable** from Yahoo, FMP, Finnhub, or FRED. This tool therefore **computes the oscillator locally** from advance/decline counts over proxy universes. As of specs/017-fmp-migration-admin, universe closes are sourced from **FMP** (`historical-price-eod/full`, one call per symbol through the shared throttle) instead of a batched `yf.download` — see `contracts/fmp-migration-map.md` row 3 and research D4. A batch-quote endpoint could cut this to one call per universe if entitled; the per-symbol approach is the safe default that works regardless of plan tier.

## Approach

| Oscillator | Proxy universe | Constituent source |
|---|---|---|
| NYMO (NYSE) | S&P 500 | FMP `v3/sp500_constituent`; fallback: Wikipedia "List of S&P 500 companies" table (verified working) |
| NAMO (NASDAQ) | NASDAQ-100 | FMP `v3/nasdaq_constituent`; fallback: Wikipedia "Nasdaq-100" page / slickcharts.com |

Ratio-adjusted methodology (matches StockCharts' $NYMO definition):

```
RANA      = 1000 × (advancers − decliners) / (advancers + decliners)
McClellan = EMA19(RANA) − EMA39(RANA)
```

**Calibration caveat:** proxy universes (500/100 large caps) approximate but don't equal full-exchange breadth (~2,800 NYSE issues). Zone thresholds (±60 etc., from `market_flow_rules.md`) are starting points — validate against StockCharts' published values and adjust if the computed range runs systematically narrower or wider.

## Caching (MongoDB)

- `breadth_universe` — constituent lists, refreshed weekly (constituents change rarely)
- `breadth_cache` — one document per (exchange, date): `{ exchange, date, advancers, decliners, rana, mcclellan }`. Daily runs only fetch/compute the gap since the latest stored date (same gap-fill pattern as `data_fetcher.py`)
- **Divergence history** (added 2026-08-09) — when the daily run detects a
  divergence resolving, append `{ type, resolved, anchor_dates,
  spy_change_5d, spy_change_10d }` (forward SPY % changes filled in as
  sessions complete). Backs the `BreadthDivergenceChart` ▲/▼ resolution
  markers; can't be recomputed from a 30-day window. The same
  new-divergence transition (from `none`/other-type) also emits a
  `market_flow` feed event (see `BreadthDivergenceChart.md` → feed card).
- Cost: one batched `yf.download(universe, period=...)` call per universe per day — no per-ticker calls, no FMP budget impact when the Wikipedia fallback is used for constituents

## Functions

### `get_market_breadth(lookback_days: int = 90) -> dict`

```python
import yfinance as yf
import pandas as pd

def _compute_mcclellan(universe: list[str], lookback_days: int) -> pd.DataFrame:
    # EMA39 needs runway: fetch ~3x the lookback, seed from breadth_cache when available
    px = yf.download(universe, period=f"{lookback_days * 3}d",
                     interval="1d", auto_adjust=True, progress=False)["Close"]
    chg = px.diff()
    adv = (chg > 0).sum(axis=1)
    dec = (chg < 0).sum(axis=1)
    rana = 1000 * (adv - dec) / (adv + dec)
    mo = rana.ewm(span=19, adjust=False).mean() - rana.ewm(span=39, adjust=False).mean()
    return pd.DataFrame({"advancers": adv, "decliners": dec,
                         "rana": rana, "mcclellan": mo}).dropna()

def get_market_breadth(lookback_days: int = 90) -> dict:
    nymo_df = _compute_mcclellan(get_universe("sp500"), lookback_days)   # NYSE proxy
    namo_df = _compute_mcclellan(get_universe("nasdaq100"), lookback_days)  # NASDAQ proxy

    def to_records(df):
        return [{"date": d.date().isoformat(), "value": round(v, 1)}
                for d, v in df["mcclellan"].tail(lookback_days).items()]

    nymo_records = to_records(nymo_df)
    namo_records = to_records(namo_df)
    nymo_current = nymo_records[-1]["value"] if nymo_records else None
    namo_current = namo_records[-1]["value"] if namo_records else None

    return {
        "nymo": {
            "history": nymo_records,
            "current": nymo_current,
            "zone": classify_zone(nymo_current),       # "oversold" | "neutral" | "overbought"
            "trend": compute_trend(nymo_records[-5:])  # "rising" | "falling" | "flat"
        },
        "namo": {
            "history": namo_records,
            "current": namo_current,
            "zone": classify_zone(namo_current),
            "trend": compute_trend(namo_records[-5:])
        },
        "divergence": detect_divergence(nymo_records, namo_records),
        "method": "computed_ratio_adjusted",           # provenance flag for the UI/agents
    }
```

The return shape is unchanged from the original spec — downstream consumers (RecommenderAgent, market_flow skill, TechnicalsTab oscillator chart) are unaffected by the sourcing change. The added `method` field lets the UI label the chart "computed (S&P 500 / NDX proxy)".

### `get_universe(name: str) -> list[str]`
Returns cached constituent list from `breadth_universe`; on miss/stale (>7 days), refresh from FMP constituent endpoint, falling back to the Wikipedia table (`pandas.read_html` with a browser User-Agent — Wikipedia 403s the default urllib UA).

### Zone Classification
```python
def classify_zone(value: float | None) -> str:
    if value is None: return "unknown"
    if value < -60: return "oversold"
    if value > 60: return "overbought"
    return "neutral"
```

### Divergence Detection
Checks last 10 days for SPY vs. NYMO divergence patterns (bullish: SPY lower low + NYMO higher low; bearish: SPY higher high + NYMO lower high). SPY fetched inline for comparison.

```python
def detect_divergence(nymo_records, namo_records) -> dict:
    spy = yf.download("SPY", period="30d", interval="1d", progress=False)
    # Compare recent lows/highs between SPY and NYMO
    # Returns: { "type": "bullish" | "bearish" | "none", "description": str,
    #            "price_points": [{date, value} x2], "osc_points": [{date, value} x2] }
```

The `price_points` / `osc_points` anchor pairs (the two swing highs/lows on
each series that constitute the divergence) are required by the frontend
`BreadthDivergenceChart` (added 2026-08-09 — see
`component-specs/frontend/components/stock/BreadthDivergenceChart.md`), which
draws them as dot-marked, opposite-sloping trend lines instead of re-detecting
swings client-side. The backend serves the whole payload (SPY + NYMO/NAMO
history + divergence) from `breadth_cache` via a new `GET /market/breadth`
route.

## Dependencies
- `yfinance`
- `pandas`
- `requests` + `lxml` (Wikipedia constituent fallback)
