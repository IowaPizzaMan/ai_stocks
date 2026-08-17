# Data Model: Market News Feed (022)

One entity and one cache collection. Field shapes derive from the live `news/stock-latest` response verified 2026-08-16 (research D2). Nothing here touches the `analyses` collection — that separation is the point of FR-008.

## 1. Market News Article

Served by `GET /market/news`, held in `market_news_cache`. Normalized from FMP's camelCase into the same snake_case shape the per-ticker news article already uses (spec 021), so the two news surfaces stay recognizably one system.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `ticker` | string \| null | `symbol` | The company the story concerns. `null` for untagged market commentary — the row still renders, just without a badge (spec edge case). |
| `datetime` | string | `publishedDate` | Full publish timestamp; drives ordering. |
| `date` | string (ISO date) | `publishedDate[:10]` | Date part, for display grouping. |
| `source` | string | `publisher`, falling back to `site` | Never empty; `"unknown"` if both are absent. |
| `headline` | string | `title` | |
| `url` | string | `url` | Opened in a new tab. |
| `text_excerpt` | string | `text[:400]` | FMP bodies average ~250 chars (measured in 021), so this is rarely truncated. |

**Validation rules**

- At most **20** articles are returned (FR-002); the newest by `datetime` win.
- Articles are sorted newest first before the cap is applied, so the cap never silently drops a newer story.
- An article missing `title` or `url` is dropped — a headline that cannot be read or followed is not useful.
- No deduplication across syndicated outlets in v1 (spec edge case: near-identical headlines may appear).
- No sentiment counting, timeline, or AI summary — deliberately absent (spec Assumptions); those belong to per-ticker news.

## 2. `market_news_cache` collection (new)

Single-document cache. One row, replaced wholesale on each refresh.

| Field | Type | Notes |
|-------|------|-------|
| `key` | string | Constant `"stock-latest"`; unique index. Names the source so a second market feed could be added later without a schema change. |
| `articles` | MarketNewsArticle[] | Already normalized and capped at 20. |
| `fetched_at` | datetime (UTC) | Freshness is compared against a 60-minute window in code; **no TTL index** (see below). |

**Lifecycle**

1. Request arrives → read the document.
2. **Fresh** (`fetched_at` within 60 minutes) → serve `articles` with `stale: false`; no external call.
3. **Cold** (absent, or `fetched_at` older than 60 minutes) → call FMP through the budget guard → normalize → cap at 20 → upsert → serve with `stale: false`.
4. **Cold + provider failure or budget exceeded** → serve the document's existing `articles` with `stale: true` (FR-013); if no document has ever been written, serve an empty list with `stale: true` and let the panel show its unavailable state.

> **Why no TTL index** (correcting the first instinct): a TTL index physically deletes the expired document, which is precisely the copy step 4 needs to fall back on. A TTL index and a serve-stale-on-failure requirement are mutually exclusive. Comparing `fetched_at` in code expires the data logically while keeping the fallback on disk — the same approach `routers/price.py` already takes.

## 3. FMP usage counter (existing, newly shared)

`fmp_usage` — already written by `agent-runner/tools/db.py::track_fmp_call`. The backend's new guard increments the **same** collection and document shape so both services throttle against one number (Principle VI).

| Field | Type | Notes |
|-------|------|-------|
| `date` | string | UTC `%Y-%m-%d` bucket. |
| `count` | int | Incremented via `find_one_and_update(..., upsert=True, return_document=AFTER)`. |

No schema change — the backend simply starts participating in a contract that already exists.

## 4. Frontend type

`MarketNewsArticle` in `frontend/src/api/types.ts` mirrors §1 exactly. It is **not** related to spec 021's `NewsArticle` type: that one carries `bullish_count`, `bearish_count`, and `ai_summary`, none of which exist here. Keeping them as separate types prevents a future change from implying market news has sentiment data it does not.
