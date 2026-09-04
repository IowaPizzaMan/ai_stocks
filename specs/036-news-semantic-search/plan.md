# Implementation Plan: News Semantic Search with Tag Prefiltering

**Branch**: `036-news-semantic-search` | **Date**: 2026-08-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/036-news-semantic-search/spec.md`

## Summary

Give the chat a meaning-based way to find news, without adding infrastructure.

1. **Every news article gets an embedding and topic tags at ingestion.** `news_pull.py`
   grows an enrichment step: one embedding call (new local model `nomic-embed-text`) over
   `title + body_text`, and one `qwen3:14b` call returning 3–6 free-form lowercase topic
   tags. Both are stored on the `news_articles` document. A paced, resumable backfill
   pass enriches the existing archive, reusing the job's existing checkpoint machinery.
2. **A tag registry collection.** `news_tags` holds each distinct normalized tag with its
   own embedding and a usage count — this is FR-002b's "queryable list of in-use tags"
   and the thing question-derived tags are matched against.
3. **The chat's single query-generation call also picks a news retrieval mode.** When the
   model targets `news_articles` it now also returns a `news_search` object:
   `{mode: recency|semantic, ticker, query_text, candidate_tags}`. No new LLM call — the
   035 decision to ride the existing call (research.md R2 there) is preserved.
4. **`semantic/news_rank.py` — a new pure module.** For `mode: semantic`, chat.py builds
   a candidate filter deterministically (ticker hard-filter and/or matched-tag filter,
   else a recency-bounded window), loads just the candidates' embeddings, and ranks them
   in NumPy by cosine similarity multiplied by an exponential recency decay. Top-N feed
   the existing answer-interpretation + citation path unchanged.
5. **`mode: recency`** (plain "latest NVDA news") keeps running the model's generated
   pipeline exactly as today. Screener questions are untouched.
6. **No frontend work.** FR-016: tags are an internal retrieval aid, absent from the
   News API and UI.

The deliberate choices: brute-force NumPy cosine over an in-memory candidate set instead
of a vector index or a new datastore (constitution V; [research.md](research.md) R3);
tags matched by embedding cosine so "interest rates" finds "monetary policy" (FR-005,
R5); recency folded into ranking as a tunable half-life so "why did it drop today"
surfaces today's coverage (R6).

## Technical Context

**Language/Version**: Python 3.12 (backend + agent-runner). No TypeScript/React changes.

**Primary Dependencies**: FastAPI, Pydantic v2, PyMongo (sync), Ollama. **New**: a
second Ollama model `nomic-embed-text` (768-dim embeddings, ~275 MB, runs resident
alongside `qwen3:14b`); `numpy` promoted to an explicit entry in
`backend/requirements.txt` (currently only transitive via `pandas`) and used directly
for cosine math. No new services, no vector database, no new Python packages beyond the
numpy line.

**Storage**: MongoDB 7.x. `news_articles` gains six additive fields (`embedding`,
`embedding_model`, `embedding_dim`, `embedded_at`, `tags`, `tags_generated_at`). One new
collection `news_tags`. No migration of existing collections; enrichment is a backfill.

**Testing**: pytest (backend + agent-runner). Pure functions —
tag normalization, cosine+decay ranking, question→tag matching, candidate-filter
construction — are exhaustively unit-tested without the LLM (constitution I, III).
Cross-service field vocabulary mirrored per constitution VI
([contracts/news-collection-v2.md](contracts/news-collection-v2.md)).

**Target Platform**: Self-hosted Docker Compose stack, single user, local-first, offline.

**Project Type**: Web application — `backend/` (FastAPI) + `agent-runner/` (queue
worker) touched; `frontend/` untouched.

**Performance Goals**: End-to-end topic or ticker-reason answer within the existing ~10 s
chat target inherited from 031 SC-001 — no second intent-classifier LLM call. NumPy
cosine over the capped candidate set (≤ 5 000 × 768 float32 ≈ 15 MB) completes in well
under 150 ms. Per-article enrichment adds one embed call (~50–300 ms) + one tag call
(~1–3 s), absorbed by the ingestion job, not the request path.

**Constraints**: `qwen3:14b` stays the only chat/tagging model — a fixed constraint of
the deployment. The embedding model must fit resident alongside it (chosen model is
< 300 MB). MongoDB auth is still off, so `query_guard`'s allowlist remains the only
read-only enforcement; the semantic ranking path does not execute model-authored
pipelines, so it does not widen that surface. FMP daily soft cap is unaffected —
enrichment calls the local model, not FMP.

**Scale/Scope**: Target 25 000 articles (~90-day retention, spec FR-014). `news_articles`
grows ~150 MB at that size with 768-dim float64 arrays; `news_tags` stays in the low
thousands of rows. ~4 user stories, 1 new backend module + 1 new collection, 1 new
agent-runner enrichment step, 0 new endpoints, 0 frontend files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| **I. Test-First & Comprehensive Coverage** | New pure functions each get exhaustive pytest suites: `normalize_tags` (case/punct/length/dedupe), `cosine_rank` + `recency_decay` (known vectors, tie-breaks, empty pool, dim-mismatch rows skipped), `match_question_tags` (exact, near-miss via embedding threshold, no-match fallback), `build_candidate_filter` (ticker-only, tag-only, both, neither). Agent-runner: enrichment normalizer + backfill checkpoint pacing + budget-free failure path. Integration: chat `mode: semantic` end-to-end against a seeded corpus; `mode: recency` regression; embedding-unavailable degradation. | PASS |
| **II. Spec-Driven Development** | Originates from `specs/036-news-semantic-search/spec.md`, clarified via `/speckit-clarify` (3 questions, Session 2026-08-30). Extends the semantic-layer path 031/035 established rather than adding a parallel one. | PASS |
| **III. Deterministic Core, LLM at the Edges** | Ranking, recency decay, tag normalization, tag matching, candidate-filter construction, dim-mismatch handling — all pure deterministic Python, no model calls. The LLM is used only where it already is (query generation, answer prose) plus two new *bounded* uses at the ingestion edge: per-article tagging and per-article/-question embedding. Neither decides an answer — they produce inputs the deterministic ranker consumes. Embedding failure has a deterministic fallback (the existing `$text` pipeline). | PASS |
| **IV. Cache-Aware, Budget-Conscious Data Access** | No new external data-source calls. Enrichment uses the local Ollama runtime only; FMP budget is untouched. Backfill is paced and resumable via the same `dataset_meta` checkpoint pattern `news_pull.py` already uses, and fails soft to "what was enriched this run". | PASS |
| **V. Simplicity & Local-First Scope** | No vector database, no `mongot`/Atlas Search, no new container, no scheduler — brute-force NumPy cosine over an in-memory candidate set, which is fast enough at single-user scale (research.md R3). One new collection is the minimum for the tag registry FR-002b requires. One new resident model is unavoidable for embeddings and is the smallest that does the job. No shared package between services — the tag-vocabulary contract stays a mirrored test. | PASS |
| **VI. Consistency Across Layers** *(v1.1.0)* | `news_articles`' new fields are written by agent-runner and read by backend, so they extend the mirrored field-vocabulary contract test (`test_news_contract.py` in both services). The 768-float `embedding` and its sidecar fields are **deliberately not** added to `NEWS_SCHEMA` (the model must never `$match`/`$sort` a raw vector); instead the mirrored test grows an explicit `NEWS_ARTICLE_INTERNAL_FIELDS` set asserted *present in the writer and intentionally absent from the schema*, so "invisible field" stays a conscious, tested decision rather than an accident. `tags` **is** added to `NEWS_SCHEMA` (groupable, model-legible). See the post-design re-check. | PASS |

**Gate result: PASS** — no violations, Complexity Tracking section omitted.

### Post-design re-check against constitution v1.1.0

Principle VI requires that any collection in `query_guard.READABLE_COLLECTIONS` — which
already includes `news_articles` — has every writer-produced field either described in
the semantic schema or explicitly accounted for, with a mirrored assertion in both
services.

This feature adds six fields to `news_articles`. The design splits them:

- **`tags`** → added to `NEWS_SCHEMA["fields"]` with an `aggregation: "groupable"` hint
  and a description telling the model the chat engine performs tag filtering
  automatically, so a hand-written `$match` on `tags` is rarely needed. Added to the
  mirrored `NEWS_ARTICLE_FIELDS` set.
- **`embedding`, `embedding_model`, `embedding_dim`, `embedded_at`,
  `tags_generated_at`** → collected in a new `NEWS_ARTICLE_INTERNAL_FIELDS` set in
  [contracts/news-collection-v2.md](contracts/news-collection-v2.md). Both
  `test_news_contract.py` files assert the writer produces
  `NEWS_ARTICLE_FIELDS ∪ NEWS_ARTICLE_INTERNAL_FIELDS` and that `NEWS_SCHEMA` describes
  exactly `NEWS_ARTICLE_FIELDS` — i.e. the internal fields are *provably* excluded on
  purpose. This is the same anti-"silent invisibility" intent as the original rule,
  applied to a field class (raw vectors) that must not enter model-authored queries.

`news_tags` is **written by agent-runner** (`news_enrich.upsert_tag_registry()`, called
from the `news_pull.py` job) and **read by backend** (`news_rank.match_question_tags()`).
It is **not** admitted to `READABLE_COLLECTIONS` — chat never generates a pipeline
against it; `news_rank.py` reads it directly with a fixed projection — so it needs a
mirrored field-set constant but not a `NEWS_SCHEMA` entry. Its field set is pinned in
the same contract doc.

**Re-check result: PASS.**

Constitution-relevant notes carried into design:

- **New resident model** (`nomic-embed-text`) is a Technology Stack addition under the
  "new datastore / framework swap requires justification" clause. Justified in
  [research.md](research.md) R1 and recorded here: embeddings cannot be produced by
  `qwen3:14b` usefully, the model is < 300 MB, pulled into the existing `ollama`
  service, and named in a setting so it is swappable (FR-013 already anticipates a
  method change).
- **`numpy` becomes an explicit backend dependency.** It is already installed
  transitively via `pandas`; using it directly without listing it is a latent breakage
  if `pandas` ever drops it. One line added to `backend/requirements.txt`.
- **`news_pull.py` already runs in agent-runner**, so the enrichment step and the
  `news_tags` writes live there, keeping "the writer" single-service and the mirrored
  contract meaningful.

## Project Structure

### Documentation (this feature)

```text
specs/036-news-semantic-search/
├── plan.md                       # This file
├── research.md                   # Phase 0 output
├── data-model.md                 # Phase 1 output
├── quickstart.md                 # Phase 1 output
├── contracts/                    # Phase 1 output
│   ├── news-collection-v2.md     # extended field vocabulary + internal-field split (constitution VI)
│   └── chat-news-retrieval.md    # the news_search object + mode routing behavior
├── checklists/
│   └── requirements.md           # (from /speckit-specify + /speckit-clarify)
└── tasks.md                      # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── requirements.txt                 # + explicit numpy line
├── settings.py                      # + ollama_embed_model, news_rank_* tunables
├── db.py                            # + NEWS_TAGS const + index; + news_articles enrichment-field indexes are not needed (brute force)
├── llm.py                           # + embed() wrapper (client.embed, keep_alive, timeout, LLMError)
├── semantic/
│   ├── schema.py                    # NEWS_SCHEMA gains a `tags` field entry only
│   ├── screener_query.py            # QUERY_SCHEMA + system prompt gain the news_search object + mode guidance
│   ├── chat.py                      # news branch: mode==semantic → news_rank path; mode==recency → existing pipeline
│   ├── news_rank.py                 # NEW — pure: cosine_rank, recency_decay, match_question_tags, build_candidate_filter, rank_articles(db, ...)
│   └── query_guard.py               # unchanged (semantic path runs no model-authored pipeline); news_tags NOT added to READABLE_COLLECTIONS
└── tests/
    ├── test_news_rank.py            # NEW — pure-function coverage
    ├── test_chat_news_semantic.py   # NEW — end-to-end semantic + recency-regression + degradation
    ├── test_news_contract.py        # extended — NEWS_ARTICLE_FIELDS ∪ INTERNAL, schema-describes-FIELDS-only
    └── test_screener_query.py       # extended — news_search object shape

agent-runner/
├── settings.py                      # + ollama_embed_model (mirrors backend)
├── llm.py                           # + embed() wrapper (mirrors backend/llm.py)
├── tools/
│   ├── db.py                        # + NEWS_TAGS const + index bootstrap
│   ├── news_pull.py                 # + _enrich(article): embed + tag; + paced backfill checkpoint "news_enrich"
│   └── news_enrich.py               # NEW — pure: normalize_tags, build_embed_text, tag prompt/schema; upsert_tag_registry
└── tests/
    ├── test_news_enrich.py          # NEW — normalize_tags, build_embed_text, registry upsert/count
    ├── test_news_pull.py            # extended — enrichment invoked on new articles; backfill pacing
    └── test_news_contract.py        # extended — mirror of backend's split
```

**Structure Decision**: Existing three-service layout unchanged; frontend not touched.
The new ranking logic goes in `backend/semantic/` beside `chat.py` / `screener_query.py`
as a sibling pure module (`news_rank.py`), matching how `linkify.py`, `strategy_picks.py`,
and `condition_filter.py` were added in 034/032/033. Enrichment logic splits into a pure
`agent-runner/tools/news_enrich.py` (testable without Ollama) called from the existing
`news_pull.py` job — the same pure-core / IO-shell split `news_pull.py` already uses for
`_normalize`. No service layer, no new router, no new container.

## Complexity Tracking

*No constitution violations — section intentionally empty.*
