# Contract: Chat History API

**Feature**: `035-chat-and-news-upgrade` | Serves US5 (FR-015…FR-020).

Extends the existing `backend/routers/chat.py` (`/chat` prefix). The existing
`GET /chat/schema` and `POST /chat` remain; `POST /chat` gains two fields.

---

## `POST /chat` — additive changes

Backward compatible: a request omitting `conversation_id` behaves exactly as
today, except that the exchange is now persisted and the response carries the
new conversation's id.

**Request** (added field in **bold**)

```json
{
  "question": "what's the latest news on NVDA?",
  "history": [{ "role": "user", "content": "…" }],
  "conversation_id": "66c9f0a1e4b0d2c3f4a5b6c7"
}
```

- `conversation_id` absent or `null` ⇒ a new conversation is created and its id
  returned.
- `conversation_id` present ⇒ the exchange is appended to it. An id that does
  not exist returns `404`.

**Response** — the existing body plus:

```json
{
  "answer": "…[NVDA](/stock/NVDA) rose…",
  "criteria": [], "match_count": 0, "rows": [],
  "generated_query": null, "excluded_for_missing_data": 0,
  "signals_as_of": null, "degraded": false, "note": null,
  "strategy_picks": null,

  "conversation_id": "66c9f0a1e4b0d2c3f4a5b6c7",
  "conversation_title": "NVDA recent news",
  "citations": [
    {
      "title": "Nvidia beats on datacenter revenue",
      "url": "https://…",
      "published_date": "2026-08-24",
      "publisher": "CNBC"
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `conversation_id` | string | Always present now. |
| `conversation_title` | string | Present on the response that created the conversation; `null` on later turns (the title does not change — research.md R6). |
| `citations` | array | Empty for non-news answers. Populated when the answer drew on `news_articles` (FR-008). |

**`answer` is now linkified** (FR-013, research.md R5): recognized tickers arrive
as `[TICKER](/stock/TICKER)` markdown, and news citations as ordinary markdown
links to their source URL. The stored copy is the linkified one, so a reloaded
conversation renders identically to a live one.

**Persistence failure is non-fatal**: if the conversation write fails, the
answer is still returned (with `conversation_id: null`). A history outage must
not cost the user the answer they waited for.

---

## `GET /chat/conversations`

The sidebar list (FR-017). Titles and dates only — messages are not included.

**Response `200`**

```json
{
  "conversations": [
    {
      "id": "66c9f0a1e4b0d2c3f4a5b6c7",
      "title": "NVDA recent news",
      "created_at": "2026-08-25T14:02:11Z",
      "updated_at": "2026-08-25T14:06:40Z",
      "message_count": 4
    }
  ]
}
```

Ordered by `updated_at` descending. Returns `{"conversations": []}` when empty —
never a `404`.

---

## `GET /chat/conversations/{id}`

Full conversation for reopening (FR-018).

**Response `200`**

```json
{
  "id": "66c9f0a1e4b0d2c3f4a5b6c7",
  "title": "NVDA recent news",
  "created_at": "2026-08-25T14:02:11Z",
  "updated_at": "2026-08-25T14:06:40Z",
  "messages": [
    { "role": "user", "content": "what's the latest news on NVDA?", "timestamp": "2026-08-25T14:02:11Z" },
    { "role": "assistant", "content": "[NVDA](/stock/NVDA) rose…", "timestamp": "2026-08-25T14:02:29Z" }
  ]
}
```

`404` when the id is unknown or malformed. A malformed ObjectId returns `404`,
not `500` — an unparseable id is indistinguishable from a deleted one from the
caller's perspective.

---

## `DELETE /chat/conversations/{id}`

FR-019. Hard delete.

**Response `204`** — no body.

`404` when the id is unknown. Deleting an already-deleted conversation is a
`404`, not a silent success, so the client can reconcile a stale sidebar.

---

## Title generation

One `llm.generate_text()` call, made **after** the first exchange's answer is
already returned to the user, constrained to ≤6 words. On `LLMError`, falls back
to the first question truncated to 6 words. Never regenerated on later turns.

The user-visible consequence of the fallback is a slightly clumsier title, not a
missing conversation — persistence never depends on the model succeeding
(research.md R6).
