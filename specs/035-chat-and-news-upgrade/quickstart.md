# Quickstart: Validating the Chat AI & News Platform Upgrade

**Feature**: `035-chat-and-news-upgrade` | **Date**: 2026-08-25

How to prove this feature works end to end. Field shapes live in
[data-model.md](./data-model.md) and endpoint shapes in [contracts/](./contracts/);
this is the run guide.

Steps map to user stories, so a partially-implemented feature can still be
validated up to the story it reaches.

---

## Prerequisites

| Requirement | Verify with | Expected |
|---|---|---|
| Stack up | `docker compose ps` | `mongodb`, `backend`, `frontend`, `agent-runner`, `ollama` running |
| Ollama has `qwen3:14b` | `curl -s localhost:11434/api/tags` | lists `qwen3:14b` |
| FMP key set | `docker compose exec -T backend python -c "from settings import settings; print(bool(settings.fmp_api_key))"` | `True` |
| FMP budget has room | see step 1 | today's call count well under the cap |
| Screener populated | `docker compose exec -T mongodb mongosh stockai --quiet --eval 'print(db.screener.countDocuments())'` | non-zero |

The 30-day backfill consumes FMP calls. Run step 2 early in the day, or accept
that it will pause and resume tomorrow — that pause is correct behavior
(FR-024, research.md R7), not a failure.

---

## 1. Check the FMP budget before backfilling

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval '
  const today = new Date().toISOString().slice(0,10);
  printjson(db.fmp_usage.findOne({date: today}) || {note: "no calls yet today"})'
```

---

## 2. Ingest news — US2 (FR-001…FR-004, FR-024)

Enqueue the job the same way other admin jobs are triggered:

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval '
  db.work_queue.insertOne({job_type: "market_news_pull", status: "pending", created_at: new Date()})'
```

Watch it drain, then confirm all three feeds landed:

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval '
  db.news_articles.aggregate([{$group: {_id: "$source_type", n: {$sum: 1}}}]).forEach(printjson)'
```

**Expect** three groups — `general`, `stock`, `fmp_article` — all non-zero. A
missing `fmp_article` group is the single most likely failure: that feed maps
`link`→`url` and needs its `NYSE:EXR`-style tickers parsed (contracts/news-api.md).

Verify the dedup key and the ticker parsing actually hold:

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval '
  print("dupe urls:", db.news_articles.aggregate([
    {$group: {_id: "$url", n: {$sum: 1}}}, {$match: {n: {$gt: 1}}}, {$count: "n"}
  ]).toArray().length);
  print("prefixed tickers:", db.news_articles.countDocuments({tickers: /:/}));
  printjson(db.news_articles.find().sort({published_at: 1}).limit(1).next().published_date)'
```

**Expect** `dupe urls: 0`, `prefixed tickers: 0`, and an oldest `published_date`
approaching 30 days back (or partway there if the budget paused the backfill).

**Re-run the job.** The count should barely move and still show zero duplicate
URLs — that is FR-001a's idempotent upsert working.

---

## 3. News tab shows the mixed stream — US2 (FR-005, FR-006, FR-006a)

```bash
curl -s 'localhost:8000/news?limit=5' | python -m json.tool
curl -s 'localhost:8000/news?source_type=fmp_article&limit=2' | python -m json.tool
```

Then open `http://localhost:5173/news` and confirm:

- Stories from all three feeds are **interleaved by recency**, not grouped by
  source (FR-005).
- Each row shows which type it is (FR-006).
- An FMP article's body renders with its **formatting intact** — bullets and
  bold, not escaped tag text and not stripped-flat prose (FR-006a).

---

## 4. Chat searches news — US3 (FR-007, FR-008, FR-009)

Ask a ticker-scoped and a topical question:

```bash
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question": "what is the latest news on NVDA?"}' | python -m json.tool
```

**Expect** `citations` non-empty, and `generated_query.collection` ==
`news_articles`. If `collection` says `news_articles` but rows are empty, check
the R2 bug first — `chat.py` must aggregate against the *chosen* collection, not
a hardcoded `db[SCREENER]`.

Then the negative case (FR-009):

```bash
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question": "what is the latest news on ZZZZNOTAREALTICKER?"}' | python -m json.tool
```

**Expect** an answer that says it found nothing. An answer that invents a
headline is an FR-009 failure and the most important thing this step catches.

---

## 5. Aggregation questions actually aggregate — US1 (FR-010, FR-011, FR-012)

The regression this feature exists to fix:

```bash
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question": "what is the average weekly change percent by sector?"}' | python -m json.tool
```

**Expect** `generated_query.pipeline` to contain a `$group` stage, and the answer
to report per-sector numbers. A pipeline that only `$match`es and returns raw
rows means the few-shot examples in `build_system_prompt()` are not landing
(research.md R4).

Out-of-scope handling (FR-012):

```bash
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question": "what is the CEO'\''s home address for AAPL?"}' | python -m json.tool
```

**Expect** `note: "out_of_scope"` and a plain-language decline — not a
fabricated answer, not a 500.

---

## 6. Tickers and citations are clickable — US4 (FR-013, FR-014)

Backend first — the answer text itself should carry the links:

```bash
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question": "which tracked stocks are up this week?"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["answer"])'
```

**Expect** `[AAPL](/stock/AAPL)`-style markdown in the raw answer.

In the browser at `http://localhost:5173/chat`, confirm ticker links navigate
**in-app** (no full page reload) while a news citation opens its source in a new
tab. Then check FR-014's negative case: an answer containing a word like "IT" or
"ALL" in ordinary prose must not become a link.

Run the linkifier's unit tests, which cover the lookalike cases exhaustively:

```bash
docker compose exec -T backend pytest tests/test_linkify.py -q
```

---

## 7. Chat history persists — US5 (FR-015…FR-020)

```bash
CID=$(curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question": "which stocks have improving financials?"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["conversation_id"])')

curl -s localhost:8000/chat/conversations | python -m json.tool
curl -s "localhost:8000/chat/conversations/$CID" | python -m json.tool
```

**Expect** a short descriptive title (not the raw question echoed back — that is
the R6 fallback, meaning the title LLM call failed), and both messages stored
with the assistant's content **already linkified**.

In the browser: reload `/chat`, confirm the conversation appears in the sidebar
with title and date, reopen it, start a new chat, then delete one and confirm it
disappears and stays gone after a reload.

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE "localhost:8000/chat/conversations/$CID"   # 204
curl -s -o /dev/null -w '%{http_code}\n' "localhost:8000/chat/conversations/$CID"             # 404
```

---

## 8. Sidebar holds both lists — US6 (FR-021, FR-022, FR-023)

At `http://localhost:5173/` on a viewport ≥768px wide:

- The left sidebar shows **both** Watchlist and Top Traded Stocks.
- Top Traded Stocks is **gone from the Stocks page** (FR-023 — a move, not a copy).
- Scrolling a long list scrolls **only that list**: the other list stays put and
  the page does not move (FR-022). If the page scrolls instead, the flex child
  is missing `min-h-0` (research.md R10).

---

## 9. Full suite

```bash
docker compose exec -T backend pytest -q
docker compose exec -T agent-runner pytest -q
docker compose exec -T frontend npm test
ruff check backend/ && ruff check agent-runner/ scripts/
```

All four must pass — constitution Principle I and the Development Workflow gate.
Pay particular attention to the mirrored contract tests
(`test_news_contract.py` in **both** services), which are what keep the writer
and the model's view of `news_articles` from drifting apart
(contracts/news-collection.md).
