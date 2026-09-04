# Phase 1 Data Model: Chat AI & News Platform Upgrade

**Feature**: `035-chat-and-news-upgrade` | **Date**: 2026-08-25

Two new MongoDB collections. No migration to existing collections; `screener`
gains no fields (only richer *descriptions* of the fields it already has — see
[research.md](research.md) R4).

---

## 1. `news_articles`

One document per news story, from any of the three FMP feeds. Written by
agent-runner's `market_news_pull` job, read by backend's `/news` router and by
chat-generated aggregation pipelines.

**Collection constant**: `NEWS_ARTICLES = "news_articles"` — hand-duplicated in
`backend/db.py` and `agent-runner/db.py` per the existing precedent for shared
collection names (constitution V/VI).

| Field | Type | Notes |
|---|---|---|
| `url` | string | **Unique key** (R9). The provider's article link; FMP articles' `link` field normalizes into this. |
| `source_type` | string | One of `general`, `fmp_article`, `stock`. Drives FR-006's type badge and lets chat scope a query to one feed. |
| `title` | string | Required — an article without one is dropped at normalization, as `market.py:_normalize` already does. |
| `published_at` | date | Parsed to a real BSON date, **not** the provider's string. Required for the 30-day cutoff, recency sort, and date-window chat queries. |
| `published_date` | string | `YYYY-MM-DD`. Denormalized for display and for cheap day-granularity `$match` without date arithmetic in a generated pipeline. |
| `publisher` | string | Provider's `publisher`, falling back to `site`, falling back to `"unknown"` — mirrors existing `_normalize` behavior. |
| `site` | string \| null | Domain (e.g. `cnbc.com`). Null where the feed omits it. |
| `author` | string \| null | Present on FMP articles only. |
| `body_html` | string \| null | Raw as supplied (R8). FMP articles carry real markup; the two news feeds carry plain text here. |
| `body_text` | string | Tag-stripped, derived at ingestion. What the text index covers and what the LLM reads. |
| `image_url` | string \| null | |
| `tickers` | array\<string\> | Bare symbols, exchange prefix parsed off (R9). Empty array for `general`. |
| `ingested_at` | date | When this row was first written. Distinguishes ingestion order from publication order for backfill diagnostics. |

### Indexes

```text
url                              unique      # R9 dedup; upsert target
published_at                     descending  # recency sort — the default read path
tickers                          multikey    # ticker-scoped news questions (preferred over $text)
source_type                      ascending   # feed-scoped filtering + type badge counts
(title, body_text)               text        # R3 topical search
```

No TTL index. Same reasoning `db.py:118` records for `market_news_cache`: a TTL
would delete the backfilled history this feature exists to accumulate.

### Validation rules

- An article with no `title` or no `url` is dropped, not stored (existing
  `_normalize` precedent — a headline that can't be read or followed is a dead
  row).
- `published_at` that fails to parse ⇒ the article is dropped rather than
  stored with a null date, since every read path sorts on it.
- `source_type` is closed to the three values above; an unrecognized feed is a
  programming error, not data to store.
- `tickers` entries are uppercased and stripped of any `EXCHANGE:` prefix.

### Backfill checkpoint

Progress lives in the existing `dataset_meta` collection rather than a new one,
keyed per feed (`news_general`, `news_fmp_articles`, `news_stock`), recording
the oldest `published_at` reached and whether the 30-day floor was met. This is
what makes an interrupted backfill resumable (R7).

---

## 2. `chat_conversations`

One document per saved conversation, messages embedded. Written and read by
backend only — agent-runner never touches it, so no cross-service mirroring is
required.

**Collection constant**: `CHAT_CONVERSATIONS = "chat_conversations"` in
`backend/db.py` only.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | Serialized as a string `id` in API responses. |
| `title` | string | ≤6 words, LLM-generated after the first exchange (R6); falls back to a truncated first question. |
| `created_at` | date | |
| `updated_at` | date | Sort key for the sidebar — FR-017's "most recent activity first". |
| `messages` | array\<Message\> | Ordered, oldest first. |

**Message** (embedded subdocument):

| Field | Type | Notes |
|---|---|---|
| `role` | string | `user` or `assistant`. Matches the existing `ChatTurn` shape the client already replays. |
| `content` | string | For assistant messages this is the **linkified** answer (R5) — stored post-rewrite so a reloaded conversation renders identically to a live one. |
| `timestamp` | date | |

Messages are embedded rather than a separate collection: they are only ever read
as a whole conversation, always written by appending to one conversation, and a
single-user chat history will not approach the 16MB document limit. A separate
`chat_messages` collection would add a join to every read for no benefit
(constitution V).

### Indexes

```text
updated_at    descending   # sidebar ordering
```

### Validation rules

- A conversation is persisted only once it has at least one complete exchange
  (FR-016's title needs the exchange to summarize) — a question that errors
  before producing an answer creates no row.
- Deleting a conversation removes the document outright; no soft-delete
  (FR-019 requires it be non-retrievable, and there is no audit requirement in a
  single-user local app).

### Lifecycle

```text
first question answered ──▶ insert {title: LLM-summarized, messages: [q, a]}
subsequent turns        ──▶ $push both messages, $set updated_at   (title unchanged)
user deletes            ──▶ deleteOne
```

---

## 3. Semantic-layer additions (no storage change)

`NEWS_SCHEMA` joins `SCREENER_SCHEMA` in `backend/semantic/schema.py`, describing
`news_articles` to the model in the same shape: `collection`, `description`,
`fields[]`. Its description carries the two retrieval idioms from R3 — prefer
the indexed `tickers` array for ticker-scoped questions, use
`$text` (first stage only) for topical ones.

`SCREENER_SCHEMA`'s existing field entries gain three optional keys. **No field
is added, removed, or renamed** — the mirrored contract test in both services
compares the set of `name` values only, so extra keys are safe (R4):

| Key | Purpose |
|---|---|
| `unit` | e.g. `USD`, `percent`, `fraction`, `ratio` — disambiguates `0.12 = +12%` style fields. |
| `enum` | Closed value lists for `weekly_trend`, `margin_trend`, `financials_trend`, `liked_status`. Stops the model inventing values that match nothing. |
| `aggregation` | Which operations make sense: `groupable` for categorical fields, `numeric` for averageable/summable ones. Directly serves FR-011. |

`query_guard` changes:

- `READABLE_COLLECTIONS` grows to `{"screener", "news_articles"}`.
- New rule: a `$text` operator may appear only inside the **first** stage, and
  that stage must be a `$match` — MongoDB rejects it anywhere else at runtime,
  and FR-012 requires that become a plain-language decline, not a 500.
