# Phase 0 Research: News Semantic Search with Tag Prefiltering

**Feature**: `036-news-semantic-search` | **Date**: 2026-08-30

Decisions that shape the design, each with what was rejected and why. Referenced from
[plan.md](plan.md) and [data-model.md](data-model.md).

---

## R1 — Embedding model: `nomic-embed-text`, resident alongside `qwen3:14b`, named in a setting

**Decision**: Pull `nomic-embed-text` into the existing `ollama` service and use it for
both article and question embeddings. 768 dimensions. The model name is a setting
(`ollama_embed_model`), mirrored in both services' `settings.py`.

**Rationale**: `qwen3:14b` is a generative model; asking it for embeddings gives
low-quality vectors slowly (14 B params over every article). A purpose-built embedding
model is the right tool. Among local options, `nomic-embed-text` is ~275 MB, loads and
runs comfortably resident next to a Q4 `qwen3:14b`, produces 768-dim vectors (small
enough that 25 000 of them are ~150 MB in Mongo and ~15 MB as a float32 matrix in
memory), has an 8 K token context (covers a news lead comfortably), and is well
exercised through Ollama's `embed` API. Naming it in a setting means FR-013's
"method changed" path is a config edit plus a re-enrichment pass, not a code change.

**Alternatives considered**:
- *`bge-m3` / `mxbai-embed-large` (1024-dim)* — rejected: larger footprint and 33 %
  wider vectors for a quality gain that does not matter for single-user topical news
  retrieval.
- *`qwen3-embedding:0.6b`* — viable and a natural pairing; kept as the documented
  fallback if `nomic-embed-text` under-performs on the golden set during
  implementation. Not chosen first only because it is larger and less battle-tested in
  this stack.
- *Embeddings from `qwen3:14b` via Ollama's `embed` endpoint* — rejected on quality and
  latency as above.
- *A hosted embedding API (OpenAI, Cohere, Voyage)* — rejected under constitution V
  (local-first, offline) and IV (no new metered external dependency).

---

## R2 — Retrieval rides the existing query-generation call — no new intent classifier

**Decision**: Extend the single `generate_pipeline()` call. When the model targets
`news_articles`, `QUERY_SCHEMA` additionally requires a `news_search` object:

```json
{"mode": "recency" | "semantic",
 "ticker": "NVDA" | null,
 "query_text": "why nvidia stock fell",
 "candidate_tags": ["chip export restrictions", "semiconductators"]}
```

`chat.py` branches on `news_search.mode`. `semantic` → `news_rank.py`. `recency` →
the model's generated pipeline runs exactly as today.

**Rationale**: 035 research.md R2 already rejected stacking a second intent-classifier
LLM call in front of every question — it compounds the 031 SC-001 latency budget. The
model already chooses the collection in that one call; choosing the *news retrieval
mode* in the same call is the same idea one field deeper. The three spec modes
(FR-010a) map to: `mode: recency` (plain ticker latest-news), `mode: semantic` +
`ticker` set (ticker-reason), `mode: semantic` + `ticker` null (topic).

**Alternatives considered**:
- *A dedicated `news_search.detect()` classifier like `strategy_picks.detect()`* —
  rejected: third sequential LLM call on every question, and 033 FR-004 already
  established that question→query translation should be centralized in one place, not
  re-implemented per feature.
- *Always run both the pipeline and the semantic ranker, then merge* — rejected:
  doubles work per question and produces incoherent citations when a recency-shaped
  question incidentally has strong semantic neighbors.
- *Keep `$text` as the topic path and add semantic only as a re-ranker over `$text`
  hits* — rejected: that inherits `$text`'s recall gap (the reworded-question failure
  in spec US1 scenario 1 is exactly a case `$text` returns nothing to re-rank).

**Consequence**: `mode: semantic` ignores the model's generated `pipeline` entirely —
`news_rank.py` builds its own Mongo filter deterministically. The generated pipeline is
still parsed and kept on the response's `generated_query` for transparency (FR-013 of
031), and is the fallback executed if question embedding fails (R8).

---

## R3 — Brute-force NumPy cosine over an in-memory candidate set — no index, no datastore

**Decision**: `news_rank.py` loads `{_id, url, title, published_at, tickers, embedding}`
for the candidate set only, stacks the vectors into a NumPy `float32` matrix, and
computes cosine similarity against the question vector in one matrix-vector product.

**Rationale**: This deployment is self-hosted MongoDB 7.x — no Atlas Search / no
`$vectorSearch` (that needs Atlas or a self-managed `mongot` search node, MongoDB
8.1+). Adding a vector database (Qdrant, Chroma, pgvector) is a new container and a new
operational surface, which constitution V forbids "ahead of a demonstrated need". At the
target scale the brute-force path is trivially fast: the largest candidate set is the
capped unfiltered fallback (`NEWS_RANK_MAX_CANDIDATES`, default 5 000) — 5 000 × 768
float32 ≈ 15 MB, a single BLAS `matmul` in a few milliseconds; the Mongo read of those
projected docs dominates at maybe 50–120 ms. Tag-filtered and ticker-filtered pools are
far smaller.

**Alternatives considered**:
- *MongoDB 8.1 Community + search node for native `$vectorSearch`* — rejected: a
  version bump from the pinned `mongo:7` plus a new component to operate, for a
  performance problem that does not exist at this scale. Recorded as the natural future
  step if the archive ever grows past a few hundred thousand articles.
- *`sqlite-vec` / FAISS as an in-process index* — rejected: still a new dependency and
  an index to keep in sync with Mongo, buying nothing below ~100 k vectors.
- *Precompute and cache the full matrix in process memory* — deferred: not needed
  while per-query Mongo reads stay under budget; revisit only if profiling shows the
  read is the bottleneck.

---

## R4 — Candidate set construction (deterministic, in `news_rank.build_candidate_filter`)

**Decision**: Given `news_search` and the matched tags (R5), build the Mongo filter:

| Case | Filter | Cap |
|---|---|---|
| Ticker-reason (`ticker` set) | `{"tickers": ticker}` — hard filter, **plus** matched-tag `$in` when tags also matched | all, then cap |
| Topic + tags matched | `{"tags": {"$in": matched_tags}}` | all, then cap |
| Topic, no tag match (FR-006) | `{"published_at": {"$gte": now - NEWS_RANK_FALLBACK_DAYS}}` | `NEWS_RANK_MAX_CANDIDATES` most recent |
| Ticker-reason, ticker has < `MIN_TICKER_POOL` articles | fall back to plain recency for that ticker (spec US4 behavior) | — |

All cases additionally require `embedding` present and `embedding_dim == current`
(R8/FR-012/FR-013). The cap is applied by `sort(published_at desc).limit(cap)` in Mongo
so the read itself is bounded.

**Rationale**: This is the mechanical translation of FR-004 / FR-005 / FR-006 / the spec
Edge Cases. Keeping it as a pure function that takes `news_search` + `matched_tags` +
`now` and returns a `dict` filter makes every row of that table a unit test with no
LLM and no live clock.

---

## R5 — Question→tag matching by embedding cosine, via the `news_tags` registry

**Decision**: Maintain `news_tags`: one row per distinct normalized tag, carrying its
own embedding and a usage `count`. At query time, embed each string in
`news_search.candidate_tags`, and match it to registry tags with cosine
≥ `NEWS_TAG_MATCH_THRESHOLD` (default 0.72, tunable). The union of matched tag names is
the prefilter set. Zero matches → FR-006 fallback.

**Rationale**: FR-005 explicitly requires near-miss tolerance — "interest rates"
matching a stored "monetary policy" — which has *no lexical overlap*, so `difflib` /
token-overlap cannot do it. Embedding cosine can, and reuses the embedding model already
in play (no new dependency, e.g. no RapidFuzz). The registry doubles as FR-002b's
"queryable list of in-use tags" and its `count` lets a future cleanup drop long-tail
singletons without touching this feature.

**Alternatives considered**:
- *Exact normalized string match only* — rejected: fails FR-005's near-miss case
  outright; free-form tags would fragment ("fed" / "federal reserve" / "monetary
  policy") and prefiltering would rarely fire.
- *A hand-maintained synonym map* — rejected: it is the curated taxonomy the
  clarification session declined, wearing a different hat.
- *Skip tag matching; always semantic-rank the recency window* — rejected: defeats the
  user's stated goal of tag prefiltering and leaves the brute-force set larger than it
  needs to be.

**Threshold tuning**: 0.72 is a starting point to be calibrated against the golden set
during implementation; it is a setting, and a wrong value degrades gracefully (too high
→ FR-006 fallback; too low → a slightly broader pool).

---

## R6 — Recency folded into the rank as an exponential half-life decay

**Decision**: `final_score = cosine_similarity * 0.5 ** (age_days / NEWS_RANK_HALF_LIFE_DAYS)`.
`NEWS_RANK_HALF_LIFE_DAYS` default 14, a setting (spec FR-004a).

**Rationale**: The clarification session chose "blend similarity with a tunable
age-decay". A multiplicative half-life is the intuitive knob: at the half-life a story
needs ~2× the similarity to tie a fresh one; a three-week-old near-perfect match is
demoted but not buried. "Why did NVDA drop today" then reliably surfaces today's
explanatory coverage over a month-old thematically-similar piece.

**Alternatives considered**:
- *Additive penalty `cosine - λ * age_days`* — rejected: requires matching the scales
  of a [-1,1] cosine and an unbounded day count; λ has no intuitive meaning.
- *Pure similarity, then date-sort the top N* (a clarification option) — not chosen:
  the user picked the blended option; recorded here as the trivial config to emulate it
  (`NEWS_RANK_HALF_LIFE_DAYS` → very large makes decay ≈ 1).
- *Hard recency window only, no decay* — rejected: too blunt; a highly relevant story
  from just outside the window vanishes.

---

## R7 — Enrichment at ingestion, backfill paced through the existing job

**Decision**: `news_pull.py` calls `news_enrich._enrich(article)` for each article it
is about to upsert that lacks a current embedding: one `llm.embed()` call over
`build_embed_text(article)` and one `llm.generate_json()` tag call. A separate
checkpoint `dataset_meta["news_enrich"]` drives a bounded backfill —
`ENRICH_BATCH_PER_RUN` (default 200) unenriched or stale-model articles per job run —
so the 25 000-article backfill spreads across runs instead of blocking one for hours.

**Rationale**: `news_pull.py` is already a paced, resumable, fail-soft job with
per-feed `dataset_meta` checkpoints (035 R7). Enrichment is the same shape: steady state
is a handful of new articles per refresh, enriched inline in well under the job's
budget; the one-time archive backfill is just another checkpointed loop. A tag call
through `qwen3:14b` is ~1–3 s, so 25 000 × ~2 s ≈ 14 h of model time — untenable as one
run, fine as ~125 runs of 200. Embedding calls are ~50–300 ms and not the constraint.

**Alternatives considered**:
- *A one-shot backfill script outside the queue* — rejected under constitution V ("all
  analysis triggering flows through `work_queue`, never cron").
- *A new dedicated `news_enrich` job type* — rejected as unnecessary surface;
  enrichment is intrinsic to having ingested an article, so it belongs in the pull job.
  (Revisit only if enrichment needs an independent cadence.)
- *Tag via clustering the embeddings instead of an LLM call* — rejected: no natural
  cluster labels, needs a clustering pass and a labeler, more moving parts than one
  constrained `generate_json` call.

---

## R8 — Degradation and stale-vector handling

**Decision**:
- **Question embedding fails** (Ollama down / timeout): `chat.py` catches `LLMError`
  from `llm.embed()`, executes the model's already-generated `$text` pipeline instead,
  and appends a short note (FR-011). Never a 500.
- **Article missing an embedding**: excluded from the candidate filter
  (`embedding: {"$exists": true}`), still reachable by ticker match and the recency
  stream (FR-012).
- **Dimension / model mismatch** (FR-013): the filter also requires
  `embedding_model == settings.ollama_embed_model`; `news_rank` additionally drops any
  loaded row whose vector length ≠ the question vector length as a belt-and-braces
  guard before the matmul. Mismatched articles are picked up by the R7 backfill
  (its query is `embedding_model != current OR embedding missing`).

**Rationale**: Direct restatements of FR-011/012/013. Filtering on `embedding_model`
rather than a version integer means a model swap is self-healing: change the setting,
the backfill re-enriches, and until it does those articles simply sit out the semantic
rank rather than corrupting it.

---

## R9 — Constitution VI: the internal-field split

**Decision**: Of the six new `news_articles` fields, only `tags` enters
`NEWS_SCHEMA["fields"]`. `embedding`, `embedding_model`, `embedding_dim`, `embedded_at`,
`tags_generated_at` go into a new `NEWS_ARTICLE_INTERNAL_FIELDS` set. Both
`test_news_contract.py` files assert: writer produces
`NEWS_ARTICLE_FIELDS ∪ NEWS_ARTICLE_INTERNAL_FIELDS`; `NEWS_SCHEMA` describes exactly
`NEWS_ARTICLE_FIELDS`.

**Rationale**: Principle VI exists so a writer-produced field is never *accidentally*
invisible to the model. A raw 768-float vector is a field the model must never touch in
a generated pipeline — describing it invites `$sort`/`$project` disasters, and
`query_guard` would then need a special case to strip it. The internal-field set makes
the exclusion explicit and *tested*: if someone later adds a seventh field and forgets
both the schema and the internal set, the mirrored assertion fails. `tags` is genuinely
model-legible (a groupable category) so it is described normally.

**Alternatives considered**:
- *Describe `embedding` in `NEWS_SCHEMA` with a "do not query" description* — rejected:
  relies on the model obeying prose, and 031 III assumes it will not.
- *Add a `query_guard` rule stripping `embedding` from any pipeline* — rejected as
  more code guarding against a problem the internal-field split prevents by not
  advertising the field at all.

---

## R10 — What text gets embedded

**Decision**: `build_embed_text(article) = article["title"] + "\n\n" +
article["body_text"][:NEWS_EMBED_MAX_CHARS]`, `NEWS_EMBED_MAX_CHARS` default 2000, a
setting. Deterministic head truncation.

**Rationale**: A news story's lead carries the topic; the tail rarely adds retrieval
signal and costs embed latency. 2000 chars is comfortably inside `nomic-embed-text`'s
context and keeps enrichment fast. Deterministic truncation satisfies the spec Edge Case
"the same article always yields the same representation". Tunable so it can be widened if
the golden set shows long-form FMP articles losing signal.

---

## R11 — Tagging prompt shape (reusability over specificity)

**Decision**: One `llm.generate_json()` call per article, schema
`{"tags": {"type": "array", "items": {"type": "string"}}}`, `temperature: 0`. System
prompt: *return 3–6 broad, reusable topic labels a reader would browse by (e.g.
"monetary policy", "semiconductors", "mergers and acquisitions", "oil prices") — not
headline-specific phrases, dates, or single company names*. `normalize_tags()` then
lowercases, strips punctuation, collapses whitespace, trims to ≤ 4 words / ≤ 40 chars,
drops empties, dedupes.

**Rationale**: Free-form tags are only useful for prefiltering if they *recur* across
articles. Steering the model toward broad topics and away from entities/dates keeps the
`news_tags` registry from filling with singletons, which is the main failure mode of
open tagging (spec Edge Case "free-form tag drift"). Company-name topics are redundant
with the existing `tickers` array. Deterministic normalization is the pure, tested half.

**Alternatives considered**:
- *Let the model tag freely with no reusability steer* — rejected: registry
  fragmentation, weak prefilter.
- *Cap the global tag vocabulary and force the model to pick from the current registry*
  — rejected: that is a self-growing curated taxonomy, declined in clarification; also a
  cold-start problem and a much larger prompt.
