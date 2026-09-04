# Contract: News API

**Feature**: `035-chat-and-news-upgrade` | Serves US2 (FR-005, FR-006).

New router `backend/routers/news.py`, mounted at `/news`. Supersedes
`/market/news` as the News tab's data source; `/market/news` itself is left in
place and unchanged (research.md R1).

---

## `GET /news`

The mixed, recency-ordered stream of all three feeds.

**Query parameters**

| Name | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | `50` | Capped at `200`. |
| `offset` | int | `0` | Page through history without a cursor; the collection is append-mostly and single-user. |
| `source_type` | string | *(unset)* | Optional filter: `general`, `fmp_article`, `stock`. Unset returns the mix FR-005 requires. |
| `ticker` | string | *(unset)* | Optional filter against the `tickers` array. |

**Response `200`**

```json
{
  "articles": [
    {
      "url": "https://www.cnbc.com/2026/08/25/...",
      "source_type": "general",
      "title": "Ukraine is targeting Russia's retail giants",
      "published_at": "2026-08-25T06:20:17Z",
      "published_date": "2026-08-25",
      "publisher": "CNBC",
      "site": "cnbc.com",
      "author": null,
      "body_html": null,
      "body_text": "Ukraine's drone campaign is expanding from…",
      "image_url": "https://images.financialmodelingprep.com/news/…",
      "tickers": []
    }
  ],
  "total": 4821,
  "as_of": "2026-08-25T14:00:00Z"
}
```

`as_of` is the most recent `ingested_at` in the collection, or `null` when
empty.

**Behavior**

- Always returns `200`. A news outage or an empty collection yields
  `{"articles": [], "total": 0, "as_of": null}` — never an error status. This
  matches the existing market-news contract's reasoning (`market.py:206-210`):
  the News tab showing a labeled empty state is better than a red error.
- Ordered by `published_at` descending.
- `source_type` and `ticker` compose (both applied when both are present).

---

## `POST /news/refresh`

Enqueues the `market_news_pull` job. Mirrors the existing
`POST /market/most-actives/refresh` shape exactly, so the frontend's
queue-drain invalidation pattern applies unchanged.

**Response `200`**

```json
{ "status": "enqueued", "job_id": "66c9f0a1e4b0d2c3f4a5b6c7" }
```

Returns `{"status": "already_queued", "job_id": "…"}` when a
`market_news_pull` job is already pending or running, per the existing
admin-job enqueue convention.

---

## Job contract: `market_news_pull`

Registered in `agent-runner/tools/admin_jobs.py`. The job type was already
reserved in `specs/017-fmp-migration-admin/contracts/admin-jobs-api.md`'s
registry table but never implemented; this feature implements it.

| Property | Value |
|---|---|
| `job_type` | `market_news_pull` |
| Handler | `tools.news_pull.run_market_news_pull` |
| `STALE_MINUTES` | `20` — three sequential paged feeds, more I/O than `congress_trades_pull`'s 15 |
| `JOB_DATASETS` | `news_articles` |
| Returns | count of articles upserted this run |

**Modes** (one job, two behaviors — research.md R7):

- *Incremental*: fetch page 1 of each feed, upsert, stop. The steady state.
- *Backfill*: continue paging back until an article older than the 30-day floor
  is reached, the feed is exhausted, or `FmpBudgetExceededError` is raised.

**Budget behavior**: `FmpBudgetExceededError` is caught and the handler returns
normally with whatever was ingested, recording a partial success. It must not
propagate — a blown budget is an expected daily condition, not a job failure
(constitution IV). Per-feed progress is checkpointed in `dataset_meta` so the
next run resumes rather than re-fetching from page 1.

**Idempotency**: guaranteed by the unique `url` index — an overlapping page
re-fetch upserts into no-ops, which is what makes resumption safe at an
approximate offset.

---

## Upstream field mapping

Three feeds, one stored shape. Mapping is deterministic and unit-testable
without network access.

| Stored field | `news/general-latest` | `news/stock-latest` | `fmp-articles` |
|---|---|---|---|
| `url` | `url` | `url` | `link` |
| `source_type` | `"general"` | `"stock"` | `"fmp_article"` |
| `title` | `title` | `title` | `title` |
| `published_at` | `publishedDate` | `publishedDate` | `date` |
| `publisher` | `publisher` → `site` | `publisher` → `site` | `author` → `site` |
| `site` | `site` | `site` | `site` |
| `author` | — | — | `author` |
| `body_html` | — | — | `content` |
| `body_text` | `text` | `text` | `content`, tags stripped |
| `image_url` | `image` | `image` | `image` |
| `tickers` | `[]` | `[symbol]` if present | `tickers`, prefix parsed |

**The FMP-articles row is the one that bites** (research.md R9): its link field
is named `link` not `url`, its body is HTML not plain text, and its tickers
arrive exchange-prefixed (`"NYSE:EXR"` → `"EXR"`). Getting any of those three
wrong produces silently wrong data rather than an error — an article that never
dedups, a body that indexes markup, or ticker-scoped queries that miss every FMP
article. Each mapping gets its own test.
