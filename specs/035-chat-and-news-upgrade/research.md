# Phase 0 Research: Chat AI & News Platform Upgrade

**Feature**: `035-chat-and-news-upgrade` | **Date**: 2026-08-25

Decisions that shape the design, each recorded with what was rejected and why.
Referenced from [plan.md](plan.md) and [data-model.md](data-model.md).

---

## R1 — News storage: a new collection, not an extension of `market_news_cache`

**Decision**: Create `news_articles`, a real document-per-article collection.
Leave `market_news_cache` in place, untouched, as the single-row cache it is.

**Rationale**: `market_news_cache` stores *one document per source key* whose
`articles` field is an embedded array (`backend/routers/market.py:236`). That
shape is deliberately a cache — the whole array is replaced wholesale on each
refresh, it is capped at 20 items, and `db.py:118-121` explicitly documents why
it carries no TTL index. None of that supports what FR-007 needs: per-article
documents that a chat-generated aggregation pipeline can `$match`, `$sort`, and
text-search across. Embedding tens of thousands of backfilled articles in one
document would also breach MongoDB's 16MB document ceiling well before the
30-day backfill completed.

**Alternatives considered**:
- *Extend `market_news_cache` with a second document shape* — rejected: two
  incompatible shapes in one collection, and the wholesale-replace semantics
  that make it a good cache make it a bad archive.
- *Reuse `STOCK_NEWS_CACHE`* — rejected: it is a per-ticker cache with the same
  replace-wholesale semantics, and `db.py` records that the bare `STOCK_NEWS`
  name was previously retired; resurrecting that lineage invites confusion.

**Consequence**: `MarketNewsPanel`'s existing `/market/news` endpoint keeps
working throughout implementation; the News tab is cut over to the new
`/news` endpoint as a discrete, revertible step.

---

## R2 — News retrieval rides the existing query-generation call, not a new intent classifier

**Decision**: Make the semantic layer multi-collection. The single existing
`generate_pipeline()` call sees both `screener` and `news_articles` described in
its system prompt and returns which collection it chose; `query_guard` admits
the second collection; `chat.py` executes against the chosen one.

**Rationale**: 033 established `strategy_picks.detect()` as an intent classifier
that runs on *every* question, and its own spec recorded the added latency as an
"explicitly accepted tradeoff." Adding a second such classifier for news would
stack a third sequential LLM call in front of ordinary screener questions —
compounding exactly the latency 031 SC-001 budgeted at 10 seconds. The existing
`generate_pipeline()` already returns a `collection` field and `query_guard`
already takes a `collection` parameter; the multi-collection path is the one the
code was shaped for and never finished.

**Alternatives considered**:
- *A dedicated deterministic news-retrieval tool with its own intent detector* —
  rejected on latency (third LLM call) and on redundancy: it would reimplement
  question→query translation that `screener_query.py` already centralizes, which
  is the precise duplication 033 FR-004 refactored away.
- *Always query both collections and merge* — rejected: doubles Mongo work on
  every question and produces incoherent answers when a screener question
  incidentally matches news text.

**Consequence — a latent bug becomes live**: `semantic/chat.py:143` reads
`rows = list(db[SCREENER].aggregate(...))` while lines 128–132 derive and
validate a `collection` variable. Today `READABLE_COLLECTIONS = {"screener"}`
makes the mismatch unreachable. The moment `news_articles` is admitted, every
news question would silently execute its news pipeline against the screener
collection and return nothing. **Fixing this is in scope**, and the test that
would have caught it (executing against a non-screener readable collection)
is part of this feature's suite.

---

## R3 — News text search: MongoDB text index, documented as an idiom in the schema

**Decision**: A compound text index on `news_articles` over `title` and
`body_text`. The `NEWS_SCHEMA` description explicitly teaches the model the
`{"$match": {"$text": {"$search": "..."}}}`-as-first-stage idiom, and
`query_guard` gains a rule enforcing that placement.

**Rationale**: This deployment is self-hosted MongoDB 7.x, not Atlas — Atlas
Search / `$search` is unavailable, so a text index is the only indexed
full-text option. MongoDB requires `$text` to appear in the first pipeline
stage; a model that emits it in a later `$match` produces a runtime error rather
than a wrong answer, so the guard converts that into the existing plain-language
"couldn't answer that safely" path (FR-012) instead of a 500.

**Alternatives considered**:
- *Unindexed `$regex` over title/body* — rejected: a collection scan with a
  case-insensitive regex across tens of thousands of documents on every news
  question, and no relevance ranking to order citations by.
- *Embedding-based semantic search* — rejected under constitution V: it needs an
  embedding model, a vector store, and a re-index pipeline, none of which exist
  yet and none of which this feature's questions require.

**Note on stopwords**: text indexes apply language-specific stemming and
stopword removal. Ticker symbols are unaffected, but a question like "news about
IT" degrades. Ticker-scoped news questions should prefer the indexed `tickers`
array over text search — taught in the schema description as the preferred
idiom, with text search reserved for topical questions.

---

## R4 — "More verbose semantic model" means per-field metadata plus worked examples

**Decision**: Extend each entry in `SCREENER_SCHEMA["fields"]` with optional
`unit`, `enum`, and `aggregation` keys, and extend `build_system_prompt()` with
three worked few-shot pipelines — one filter, one sort+limit, and critically one
`$group` aggregation.

**Rationale**: The user's report ("I don't think it's always doing that… so the
model can understand how to do aggregations on fields") points at a specific
gap: the current prompt lists field names, types, and prose descriptions, and
its single worked example is a `$match` + `$sort` + `$limit` pipeline. There is
no example anywhere showing `$group`, and no per-field signal about which fields
are meaningfully groupable (`sector`, `weekly_trend`, `financials_trend`) versus
aggregatable (`market_cap`, `weekly_change_pct`). Few-shot examples of the exact
output shape are the highest-leverage fix available without changing models.

**Constraint discovered**: `SCREENER_SCHEMA["fields"]` names are a cross-service
contract asserted equal in `backend/tests/test_screener_contract.py:26` and
mirrored in `agent-runner/tests/test_screener.py`. That test compares the set of
`name` values only (`{field["name"] for field in ...}`), and a second test
requires every field to carry `type` and `description`. **Adding new keys to
each field dict is therefore safe; adding or renaming a field is not** — it
requires the mirrored update in both services. The verbosity work adds keys
only, so the contract tests continue to pass unchanged.

**Alternatives considered**:
- *Switch to a larger model* — rejected: out of scope, and `qwen3:14b` is a
  fixed constraint of the local-first deployment.
- *Hand-write deterministic query templates for common question shapes* —
  rejected: that is the "keyword pre-filter" approach 033 FR-001 explicitly
  removed after finding no fixed list reliably recognizes phrasing.

---

## R5 — Ticker linkification: deterministic, backend-side, before persistence

**Decision**: A pure function in `semantic/linkify.py` rewrites recognized
tickers in the answer text to `[NVDA](/stock/NVDA)` markdown, run after the
interpretation LLM call and before the response is returned or stored.
`AnswerText`'s anchor renderer routes root-relative hrefs through react-router
`Link` and leaves absolute URLs as new-tab anchors.

**Rationale**: Backend-side placement means the linkified form is what gets
*persisted* into `chat_conversations`, so a reloaded conversation renders
identically to a live one without re-running linkification on read. It also
keeps the ticker universe where it already lives (`ticker_index` / `screener`)
rather than shipping the whole ticker set to the browser. Making it a pure
function satisfies constitution III and makes FR-014's "must not link
lookalikes" exhaustively testable without the LLM in the loop.

**Rules the pure function must honor** (each a test case):
- Only tokens matching a known ticker are linked — the universe is read from
  `screener`/`ticker_index`, satisfying FR-014.
- Never rewrite inside fenced or inline code spans.
- Never rewrite text that is already inside a markdown link.
- Match on word boundaries and case-sensitively for the ticker's own casing, so
  prose words that collide with tickers ("IT", "ALL", "ON", "A") are not
  linkified from lowercase usage.

**Alternatives considered**:
- *Frontend linkification against a fetched ticker list* — rejected: requires a
  ticker-universe endpoint and re-derives the same result on every render, and
  stored history would need the same pass applied on read.
- *Ask the LLM to emit the links* — rejected outright under constitution III:
  the model would invent links for lookalikes, which is exactly FR-014's failure
  mode.

**Bug found while reading the current code**: `MarketNewsPanel.tsx:89` links to
`/stocks/${a.ticker}` but `App.tsx:27` registers the route as `/stock/:ticker`
(singular) — every ticker chip in the existing market-news panel is a dead link
to the NotFound page. Not caused by this feature, but it lands in the code this
feature rewrites, so it is fixed here and logged in `KNOWN_ISSUES.md`.

---

## R6 — Conversation titles: one extra LLM call, first exchange only, with a deterministic fallback

**Decision**: After the first exchange of a new conversation completes, make one
additional short `generate_text()` call asking for a ≤6-word title. On
`LLMError`, fall back to a truncated first question. Titles are never
regenerated on later turns.

**Rationale**: The clarification session chose AI summarization over mechanical
truncation. Bounding it to the first exchange means the cost is one extra call
per *conversation*, not per turn, and it happens after the user already has
their answer — so it does not sit in the latency path of the response they are
waiting on. The deterministic fallback keeps a model outage from blocking
conversation persistence entirely (a title is cosmetic; the messages are not).

**Alternatives considered**:
- *Regenerate the title as the conversation evolves* — rejected: cost per turn,
  and a title that changes under the user is disorienting in a history list.
- *Generate titles lazily when the sidebar is first rendered* — rejected: makes
  a read endpoint perform model calls and write to the database.

---

## R7 — Backfill pacing: resumable, checkpointed, budget-guarded

**Decision**: `market_news_pull` pages backward through each of the three feeds
until it reaches an article older than the 30-day cutoff or the FMP budget guard
raises. Per-feed progress (last page reached, oldest `published_at` ingested) is
checkpointed so the next run resumes rather than restarting. Ordinary
incremental refresh and backfill are the same job in two modes.

**Rationale**: Constitution IV names the FMP daily cap as a hard constraint and
requires fail-soft degradation. Three feeds × 30 days cannot be assumed to fit in
one day's budget, and a non-resumable backfill would re-fetch the same first
pages every run, never converging. Catching `FmpBudgetExceededError` and
returning normally (rather than raising) records a partial success and lets the
next scheduled run continue — the same pattern `run_economics_pull` already uses
for its per-sub-pull isolation.

**Idempotency**: Because R9 makes `url` the unique key, re-fetching an overlapping
page is harmless — upserts collapse into no-ops. This is what makes an
interrupted backfill safe to resume at an approximate rather than exact offset.

**Alternatives considered**:
- *One-shot backfill script run manually outside the queue* — rejected under
  constitution V: "all analysis triggering flows through `work_queue`, never
  cron," and a script would not share the budget guard's accounting.
- *Fetch the full 30 days in a single job invocation* — rejected: guaranteed to
  exhaust the daily cap and take the whole app's FMP access down for a day,
  the exact risk constitution IV exists to prevent.

---

## R8 — News body HTML: store raw, derive text, sanitize at render

**Decision**: Store the provider's `body_html` verbatim, derive a tag-stripped
`body_text` at ingestion for the text index and for the LLM to read, and render
`body_html` through `rehype-raw` + `rehype-sanitize` in a **new** `NewsBody`
component. `AnswerText` is not given `rehype-raw`.

**Rationale**: The clarification chose sanitized rendering over stripping, so
formatting must survive to the browser. Deriving `body_text` at ingestion serves
two separate needs: MongoDB's text index should not index markup tokens, and the
answer-interpretation prompt should not spend context on `<strong>` tags.
Sanitizing at render (rather than at ingestion) preserves the spec's stated
assumption that stored content is as-supplied, and keeps the sanitizer
replaceable without re-ingesting.

**Critical scoping constraint**: 034 FR-004 deliberately established that
`AnswerText` uses *no* `rehype-raw`, so HTML embedded in a model-generated
answer stays inert text. That guarantee must not regress — a chat answer is
partly model-controlled, whereas news body HTML is provider-controlled. The two
render paths therefore stay separate components with different plugin sets, and
a test asserts `AnswerText` still renders embedded HTML inert.

**Alternatives considered**:
- *Server-side sanitization with `bleach` at ingestion* — rejected: adds a
  backend dependency, discards the original irreversibly, and contradicts the
  spec's stored-as-supplied assumption.
- *Strip all HTML and render plain text* — rejected: the clarification session
  explicitly chose the opposite.
- *`dangerouslySetInnerHTML` + DOMPurify* — viable, but adds a second HTML
  pipeline alongside the react-markdown one already in the app; `rehype-*`
  plugins compose with what is there.

---

## R9 — Deduplication by source URL

**Decision**: `url` is a unique index on `news_articles`; ingestion upserts on
it. No cross-source or near-duplicate detection.

**Rationale**: Directly from the clarification session. Provider feeds overlap
heavily between refreshes (a 60-minute window against a feed of recent stories
re-returns most of the same rows), so upsert-on-URL is what keeps repeated
refreshes from multiplying rows. The spec's Edge Cases explicitly accept that
the same event covered by two different feeds appears as two items.

**Consequence for FMP articles**: FMP editorial articles carry a `link` field
rather than `url`, and their ticker list arrives as an exchange-prefixed string
(`"NYSE:EXR"`). Normalization maps `link` → `url` and parses the prefix off the
ticker so `tickers: ["EXR"]` matches the same vocabulary `screener` uses —
without that, ticker-scoped news queries would silently miss every FMP article.

---

## R10 — Sidebar: sibling scroll regions, not nested scroll containers

**Decision**: `Sidebar` becomes a flex column with two `min-h-0`,
`overflow-y-auto` sections. Top Traded Stocks renders as a compact
ticker+change list, not the four-column table `MostActivesPanel` uses.

**Rationale**: FR-022 requires each list to scroll independently without
scrolling the page. In a flex column, a child only scrolls if it is allowed to
shrink below its content size — `min-h-0` is the non-obvious requirement, and
omitting it is the standard failure mode where the page scrolls instead. The
sidebar is `w-56`; the existing table's Ticker/Company/Price/Change columns do
not fit, so the sidebar variant shows ticker and change percent only.

**Alternatives considered**:
- *Reuse `MostActivesPanel` unchanged in the sidebar* — rejected: it is built
  around a wide table plus a Refresh button and section chrome sized for the main
  column.
- *Fixed pixel heights per section* — rejected: wastes space when one list is
  short; `flex-1` with `min-h-0` divides available height and adapts.
