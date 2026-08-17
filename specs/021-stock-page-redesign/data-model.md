# Data Model: Stock Page Redesign (021)

Entities keyed to spec Key Entities; field shapes derive from the verified FMP responses (research D1). MongoDB collection names follow existing `*_cache` conventions; both Python services use identical field names (constitution Principle VI).

## 1. News Article (in `news` sub-report and `stock_news_cache`)

| Field | Type | Notes |
|-------|------|-------|
| `date` | string (ISO date) | from FMP `publishedDate` (date part) |
| `datetime` | string (ISO) | full FMP `publishedDate` for intra-day ordering |
| `source` | string | FMP `publisher` (fall back `site`) |
| `headline` | string | FMP `title` |
| `url` | string | FMP `url` |
| `text_excerpt` | string | first ~400 chars of FMP `text` (raw body stays in cache, not on the analysis doc) |
| `bullish_count` | int ≥ 0 | deterministic tally over `title + text` |
| `bearish_count` | int ≥ 0 | deterministic tally over `title + text` |
| `ai_summary` | string \| null | 1–3 sentences; only the 15 newest articles get one (D6) |

Validation: the full 30-day window is retained (measured ~630 articles for AAPL, ~29 for a thinly covered name); publishedDate within 30 days of pull; articles with zero recognized terms keep `0/0` (neutral — never treated as bearish, per spec edge case). A hard ceiling of `PAGE_SIZE × MAX_PAGES` (1250) guards against runaway paging.

## 2. Sentiment Timeline Point (in `news` sub-report, rendered by News + Sentiment tabs)

| Field | Type | Notes |
|-------|------|-------|
| `date` | string (ISO date) | one point per calendar date having ≥1 article |
| `bullish` | int | sum of `bullish_count` across that date's articles |
| `bearish` | int | sum of `bearish_count` |
| `article_count` | int | articles contributing |

Timeline-level: `trend` ∈ `bullish | bearish | mixed` — sign of net (bullish − bearish) summed over the most recent 7 days with articles (deterministic, pytest-covered).

## 3. News sub-report (`analysis.sub_reports.news`) — NEW

```
{
  articles: NewsArticle[],            // newest first, full 30-day window
  timeline: TimelinePoint[],          // ascending by date
  trend: "bullish" | "bearish" | "mixed",
  stance: {
    direction: "bullish" | "neutral" | "bearish",
    reasoning: string                 // LLM, must cite ≥1 headline
  } | null,                           // null when no articles
  news_count: int,
  days_covered: int,                  // dates in the window that had coverage
  window_days: int,                   // window requested (30)
  as_of: string | null                // newest article date
}
```

Sizing note: a mega-cap's month is ~630 articles ≈ 370 KB on the analysis document (article bodies from FMP average ~250 characters, and only a 400-character excerpt is stored). Well inside MongoDB's 16 MB document limit, and the UI reveals 25 articles at a time.

## 4. Insider Statistics Period (extends `analysis.sub_reports.insider`)

New field `quarterly_stats` (array, newest first, from `insider-trading/statistics`):

| Field | Type | Source field |
|-------|------|--------------|
| `year` / `quarter` | int | `year`, `quarter` |
| `acquired_transactions` | int | `acquiredTransactions` |
| `disposed_transactions` | int | `disposedTransactions` |
| `acquired_disposed_ratio` | float | `acquiredDisposedRatio` |
| `total_acquired` | int | `totalAcquired` (shares) |
| `total_disposed` | int | `totalDisposed` (shares) |
| `total_purchases` / `total_sales` | int | `totalPurchases`, `totalSales` |

Existing fields (`net_direction`, `recent_transactions`, `cluster_signal`, …) unchanged. UI derives the quarterly acquired-vs-disposed bars and ratio trend from `quarterly_stats`; open-market distinction for the 90-day table continues to come from the existing Finnhub transaction feed (FR-017).

## 5. Beneficial Ownership Filing (extends `analysis.sub_reports.institutional`; cached in `beneficial_ownership_cache`)

New field `beneficial_filings` (array, newest first, from `acquisition-of-beneficial-ownership`):

| Field | Type | Source field |
|-------|------|--------------|
| `filer` | string | `nameOfReportingPerson` |
| `filing_date` | string | `filingDate` |
| `shares` | int | `amountBeneficiallyOwned` (string → int) |
| `pct_of_class` | float | `percentOfClass` (string → float) |
| `filer_type` | string | `typeOfReportingPerson` (IA, HC, …) |
| `url` | string | SEC filing link |

Derived (deterministic): `beneficial_direction` ∈ `accumulating | distributing | mixed | null` — per-filer comparison of successive `pct_of_class` values, majority vote across filers with ≥2 filings; `null` when no filer repeats. Combined institutional verdict = `beneficial_direction`, falling back to existing `recent_activity_direction` from the cached 13F snapshot (research D2), each labeled with its as-of date.

## 6. Timeframe Indicator Series (frontend-only, computed in `lib/indicators/`)

Input: `OHLCVBar[]` for one resolution. Outputs per indicator (aligned to bar dates, `null` during warm-up):

- **MACD**: `{macd, signal, histogram}` — EMA 12/26, signal EMA 9. Warm-up: needs ≥ 35 bars. **Daily/weekly/monthly only** — not rendered on the yearly timeframe (clarified 2026-08-16: a 35-year warm-up is unreachable for almost every ticker, so the panel would only ever show "insufficient history").
- **Stochastic**: `{k, d}` — %K 14-bar, %D 3-SMA. Range [0,100]; overbought 80 / oversold 20 zones rendered. All four timeframes.
- **ATR%**: `{atrPct}` — 14-bar Wilder ATR ÷ close × 100. Needs ≥ 15 bars. All four timeframes.
- **Z-score**: `{zscore}` — (close − SMA20) ÷ σ20. Needs ≥ 20 bars. All four timeframes.

Insufficient-history rule (FR-008): if a timeframe has fewer bars than an indicator's warm-up, the panel renders the "insufficient history" state (e.g., monthly MACD on a ticker with <3 years of history).

## 7. Changes Since Last (`analysis.changes_since_last`) — NEW top-level, nullable

```
{
  previous_timestamp: string,
  signal: { from: string, to: string, changed: bool },
  conviction: { from: string, to: string, changed: bool },
  flags_added: string[],
  flags_removed: string[]
}
```

Computed in `crew.py` from the prior analysis document before the new one is written (research D9). Absent (`null`/missing) on first-ever pulls — AI Summary hides the section.

## 8. Cache collections (new)

| Collection | Key | TTL | Contents |
|------------|-----|-----|----------|
| `stock_news_cache` | `ticker` | 24h (TTL index on `fetched_at`) | raw FMP articles (incl. full `text`) from last fetch |
| `beneficial_ownership_cache` | `ticker` | 7d | raw filings array + `fetched_at` |

Both are written through the pull path only; on `FmpBudgetExceededError` or HTTP error the last cached doc is served regardless of TTL (fail-soft, FR-026) and the sub-report keeps the previous `as_of`.

## 9. Price bars (existing `OHLCVBar` — unchanged shape, new resolution)

`GET /stocks/{ticker}/price?resolution=yearly` returns the same `{date, open, high, low, close, volume}` bars, one per calendar year, ≤ 15 years (contract: [contracts/price-endpoint.md](./contracts/price-endpoint.md)). `price_cache` keying (`ticker` + `resolution`) already accommodates the new value.
