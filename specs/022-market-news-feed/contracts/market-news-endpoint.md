# Contract: `GET /market/news`

New endpoint on the existing `market` router ([backend/routers/market.py](../../../backend/routers/market.py)), alongside `/market/breadth`, `/market/flow-events`, and `/market/macro`. Read-through cache over FMP `news/stock-latest`. Field shapes: [data-model.md](../data-model.md).

## Request

`GET /market/news`

No parameters. Deliberately takes no filter, ticker, or limit argument — the panel is filter-independent by requirement (FR-001b) and fixed at 20 articles (FR-002). Adding a filter parameter later would be a spec change, not a drop-in.

## Response `200`

```json
{
  "articles": [
    {
      "ticker": "NBIS",
      "datetime": "2026-08-16 20:13:07",
      "date": "2026-08-16",
      "source": "Seeking Alpha",
      "headline": "Nebius: Why Its Post-Earnings Momentum Has Staying Power",
      "url": "https://…",
      "text_excerpt": "…"
    }
  ],
  "as_of": "2026-08-16T20:15:00Z",
  "stale": false
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `articles` | array | ≤ 20, newest first. Empty array is valid (provider returned nothing, or nothing has ever been cached). |
| `as_of` | string \| null | When these articles were retrieved (`fetched_at`). `null` only when nothing has ever been cached. |
| `stale` | boolean | `true` when the cached copy could not be refreshed (provider failure or budget exhausted). The panel labels the list rather than erroring. |

`articles[].ticker` is `null` for untagged market commentary; the row renders without a ticker badge.

## Behavior

- **Fresh cache** (< 60 min): served directly, zero external calls. This is the common path (FR-011).
- **Cold cache**: one FMP call through the backend budget guard, then normalize → sort newest-first → cap at 20 → upsert → serve.
- **Provider error / budget exceeded on a cold cache**: returns `200` with the previously cached `articles` and `stale: true` — never `5xx`. A news outage must not surface as a page error (FR-012, FR-013).
- **Never** writes to `analyses` or any per-ticker collection (FR-008).

## Status codes

| Code | When |
|------|------|
| `200` | Always, including provider failure (degrades via `stale`) |

There is deliberately no error status: the caller is a panel on the app's home page, and a red error state for missing news would be worse than an empty, labeled list.

## Budget guard contract (`backend/fmp.py`)

The new helper mirrors `agent-runner/tools/fmp_client.py` so both services agree on the day's spend:

- Increments `fmp_usage` on the UTC `%Y-%m-%d` day bucket via an upserting `find_one_and_update`, returning the new count.
- Raises `FmpBudgetExceededError` once `settings.fmp_daily_soft_cap` is passed; `0` (the default) disables the cap.
- Callers **must** catch that error and degrade — it never escapes as a 500.

## Tests (`backend/tests/test_market_news.py`, `test_fmp_guard.py`)

- Fresh cache serves without calling the provider; cold cache calls exactly once.
- Response is capped at 20 even when the provider returns more, and keeps the newest.
- Articles are normalized (camelCase → snake_case) and untitled/URL-less rows dropped.
- `ticker` is `null`-safe for untagged stories.
- Provider raises → `200` with prior articles and `stale: true`.
- Budget exceeded → `200`, `stale: true`, no crash.
- Guard increments the shared counter; soft cap of `0` never raises.
