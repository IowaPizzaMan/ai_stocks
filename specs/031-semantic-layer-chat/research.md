# Phase 0 Research: Semantic Layer Chat Assistant

**Feature**: `031-semantic-layer-chat` | **Date**: 2026-08-23

All findings below were measured directly against the running MongoDB instance
(`mongodb://localhost:27017/stockai`) and the local Ollama runtime, not inferred.

---

## R1. Can `qwen3:14b` generate a usable query? (the blocking spike)

**Decision**: Yes — but **only** against a flat, pre-computed collection. Query generation
against the raw nested collections fails.

**Evidence**: The flagship question from the spec was put to `qwen3:14b` twice, at
`temperature=0`, changing only how the schema was presented.

| Schema presented | Output valid JSON? | Output valid MongoDB? | Latency |
|---|---|---|---|
| **Flat** `screener` collection with pre-computed fields | **Yes** | **Yes** — correct collection, sensible `$match` | 12.8s (cold) |
| **Nested** raw `price_history` + `financials_cache` | **No** | **No** | 6.9s |

The flat-schema run produced exactly the shape the design wants:

```json
{"collection": "screener", "pipeline": [{"$match": {
  "zscore_20d": {"$lt": 0}, "weekly_change_pct": {"$gt": 0},
  "financials_trend": "improving", "fcf_exceeds_debt": true}}]}
```

The nested-schema run produced syntactically impossible MongoDB before it even finished —
`{"$arrayElemAt": ["$financials.data.cashflow_annual", 0].freeCashFlow` — attempting JS
property access inside an aggregation expression, and never closed its JSON.

**Rationale**: This is the empirical justification for FR-010 (pre-compute signals). It is
not a stylistic preference — the nested path demonstrably does not work with this model.

**Alternatives considered**:
- *Nested schema + few-shot examples*: might improve reliability, but the failure was
  structural (invalid operator syntax), not stylistic. Rejected as unreliable.
- *Larger/cloud model*: would likely handle nesting, but violates the local-first stack
  constraint and the project's zero-external-cost posture. Rejected.

---

## R2. Latency budget vs. SC-001 (10 seconds)

**Decision**: SC-001 is achievable **only with the model kept resident**. Cold start alone
consumes roughly the entire budget.

**Measured**:

| Stage | Cold | Warm (extrapolated from measured token rate) |
|---|---|---|
| Query generation (66 output tokens) | 12.8s @ ~5 tok/s | ~1–2s @ 54 tok/s |
| Query execution (full 556-doc universe) | <0.1s | <0.1s |
| Answer interpretation (166 output tokens) | 3.1s @ 54 tok/s | ~3.1s |
| **End-to-end** | **~16s** | **~5–8s** |

The 5 tok/s vs 54 tok/s gap is model load time, not generation speed.

**Implications for implementation**:
- Ollama must be called with a long `keep_alive` so the model stays resident between
  questions. Without it, every first question of a session busts SC-001.
- `think` must be disabled (`"think": false`). `qwen3` is a reasoning model; leaving
  thinking enabled adds a large hidden token budget before any answer tokens appear.
- `temperature=0` for query generation — determinism matters more than variety here.

**Open risk**: SC-001 says "within 10 seconds for the majority of questions." Warm
performance meets this; a cold first question does not. Either accept a slower first
question, or pre-warm the model at service start. Recommend pre-warm.

---

## R3. Where do pre-computed signals live?

**Decision**: A new, flat, denormalized **`screener`** collection — one document per ticker,
all queryable fields top-level, written by `agent-runner`, read by `backend`.

**Rationale**:
1. R1 proves the model can only query a flat shape reliably.
2. It keeps all arithmetic in deterministic Python (constitution Principle III), leaving the
   model only selection/filtering.
3. It collapses a would-be multi-collection `$lookup` join into a single-collection `$match`,
   which is both the cheapest query plan and the easiest for a model to produce.
4. It is the mechanism that makes the 15x requirement tractable (see R5).

**Alternatives considered**:
- *Add signal fields onto `price_history`*: rejected — `price_history` holds 556 docs
  spanning the full index universe, is 64.6MB with large `bars` arrays, and mixing a small
  hot screening doc with a 121KB payload makes every screening read expensive.
- *MongoDB views over existing collections*: rejected — a view cannot pre-compute cheaply on
  read at scale, and would reintroduce the nested shapes R1 showed the model cannot handle.

**Verified source fields exist** (sampled from live documents):
- `price_history.bars[]` → `{date, open, high, low, close, volume}`, up to 1258 bars/ticker.
- `financials_cache.data.cashflow_annual[].freeCashFlow` ✓
- `financials_cache.data.balance_annual[].totalDebt`, `.netDebt` ✓
- `financials_cache.data.growth[].growthRevenue`, `.growthNetIncome` ✓
- `financials_cache.data.ratios[].netProfitMargin`, `.grossProfitMargin` ✓
- `company_info.profile.{name,sector,industry,market_cap}` ✓

Values in `financials_cache` arrive as BSON `$numberLong` — signal computation must coerce
to plain numbers before storing, or comparisons in generated queries will behave oddly.

---

## R4. The signal math is proven against live data

The price-side half of the flagship question was executed as a real aggregation across all
556 `price_history` documents and returned **13 genuine matches** (TPR, MO, TROW, VTRS, AAPL,
EBAY, IDXX, ACGL, ROL, VRSK, F, HST, SCSC) in well under a second.

Signal definitions validated against live data:

| Signal | Definition as computed |
|---|---|
| `range_pct_20d` | `(last_close - min(low,20)) / (max(high,20) - min(low,20))`, guarded against a zero-width range |
| `zscore_20d` | `(last_close - mean(close,20)) / stdDevPop(close,20)`, guarded against zero stdev |
| `weekly_change_pct` | `(last_close - close[-6]) / close[-6] * 100` |
| `fcf_exceeds_debt` | `cashflow_annual[0].freeCashFlow > balance_annual[0].totalDebt` |

Spot-check: AAPL FCF 2025 = \$98.77B vs total debt \$112.38B → `fcf_exceeds_debt: false`.
The filter discriminates rather than matching everything.

Tickers with fewer than 25 bars must be skipped (guarded in the pipeline) — they yield null
signals rather than wrong ones. This is the FR/SC-008 "insufficient history" case.

---

## R5. 15x scale analysis

**Decision**: The design absorbs 15x without redesign. The pre-computed `screener` collection
is what makes this true.

**Current measured baseline**:

| Metric | Value |
|---|---|
| Total data size | 84.0 MB (88,117,270 bytes) |
| Storage size | 54.8 MB |
| Documents | 2,510 |
| Indexes / index size | 73 / 2.19 MB |
| `price_history` | 64.6 MB, 556 docs, ~121 KB/doc, max 1,258 bars |
| Tracked tickers (`ticker_index`) | 65 |

**Projected at 15x** (interpreting 15x as ticker-count growth at constant ~5yr depth, per the
spec's Assumptions):

| Metric | Projected | Assessment |
|---|---|---|
| Tracked tickers | ~975 | fine |
| `price_history` docs | ~8,340 | fine |
| `price_history` size | ~1.0 GB | fine on local disk |
| Total data size | ~1.3 GB | fits comfortably in RAM/WiredTiger cache |
| **`screener` collection** | ~8,340 docs × ~2 KB ≈ **17 MB** | trivial; fully indexable |
| Largest single document | ~121 KB (unchanged — depth-driven, not count-driven) | 0.75% of the 16 MB BSON cap |

**Why chat stays fast at 15x**: a chat query touches only `screener` (~17 MB, indexed), never
`price_history` (~1 GB). The expensive full-universe scan happens once per refresh cycle in
`agent-runner`, not once per question.

**The one case that would break it**: if historical *depth* also grew 15x (5yr → 75yr), each
`price_history` doc reaches ~1.8 MB and the collection ~15 GB. Still under the 16 MB per-doc
cap, but that is the point at which bucketing would need revisiting. Not a current concern —
flagged so it is not rediscovered late.

---

## R6. Read-only enforcement (FR-012)

**Decision**: Defense in depth — **two independent layers**, because either alone is
insufficient.

1. **Pipeline validation (primary)**: reject any generated pipeline containing a write-capable
   stage before it is sent to MongoDB. Denylist at minimum `$out`, `$merge`, `$function`,
   `$accumulator`, `$where`. Prefer an **allowlist** of read stages (`$match`, `$project`,
   `$group`, `$sort`, `$limit`, `$skip`, `$count`, `$addFields`, `$unwind`, `$lookup`,
   `$facet`, `$sample`) — an allowlist fails safe as MongoDB adds stages; a denylist does not.
2. **Connection-level (secondary)**: a dedicated MongoDB connection for chat, using a user
   granted only the `read` role on `stockai`.

**CONFIRMED: MongoDB auth is currently NOT enabled**, so layer 2 does not exist today:
- `docker-compose.yml:4-16` runs `mongod --quiet` with no `--auth` and no
  `MONGO_INITDB_ROOT_USERNAME`/`PASSWORD`.
- No init scripts anywhere (`/docker-entrypoint-initdb.d` is not mounted).
- Every connection string in the repo is credential-free (`.env`, both compose service
  blocks, both `settings.py` defaults).
- Port 27017 is published to the host unauthenticated.

Enabling auth is a **breaking, cluster-wide infra change**: add `--auth` and root credentials
to the mongo service, add an init script creating both an app user and a `read`-role user,
then update `MONGO_URI` in `.env`, both compose blocks, and both `settings.py` defaults.

**Consequence for FR-012**: the spec says "structurally enforced." With auth disabled, the
stage allowlist is the *only* real enforcement, and it is enforcement in application code, not
in the database. Two honest options:
- **(a) Allowlist only** — no infra change; FR-012's "structural" claim is satisfied in the
  sense that a validator sits between the model and the driver and cannot be bypassed by
  prompt content, but a bug in the validator is a hole. Lower blast radius, ships now.
- **(b) Allowlist + enable auth + read-only user** — genuinely structural, defence in depth,
  but a breaking change to local dev and both services' configuration.

Recommend **(a) for this feature**, with (b) recorded as a follow-up, and the limitation stated
plainly in the plan rather than letting "structurally enforced" imply a database-level
guarantee that does not exist. This should be surfaced to the user rather than decided
silently.

**Also required by FR-016**: every chat query gets a `$limit` appended if absent, plus a
`maxTimeMS` server-side cap. Both bound cost regardless of what the model generates.

**Rationale**: FR-012 says "structurally enforced." An allowlist executed before dispatch is
structural; trusting the model is not. The connection-level role is the stronger guarantee
where available, which is why the deployment's auth posture must be confirmed at
implementation time rather than assumed.

---

## R7. Unused-collection cleanup (FR-006) — corrected findings

The list carried in the spec's Assumptions was **partially wrong**, and re-verification
against both the live database and the source tree changed it materially.

**Method**: enumerated all 36 live collections, then grepped `backend/`, `agent-runner/`, and
`frontend/src/` for each collection-name literal.

| Collection | Live docs | Code refs | Verdict |
|---|---|---|---|
| `portfolio_digest_cache` | 1 | **0** | **DELETE** — genuinely orphaned |
| `transcripts_cache` | 0 | 2 | **Review** — see below |
| `fund_holdings` | *does not exist* | constant only | Remove dead constant only |
| `sector_performance` | *does not exist* | constant only | Remove dead constant only |
| `stock_news` | *does not exist* | constant only | Remove dead constant only |
| `market_news` | *does not exist* | constant only | Remove dead constant only |
| `fmp_entitlements` | *does not exist* | **actively written** | **KEEP** — not dead |

**Corrections to the spec's assumption list**:

1. **`portfolio_digest_cache` is the real find, and the spec did not list it.** It holds 1
   document and has **zero** references anywhere in the source tree.
   `agent-runner/tools/portfolio.py` no longer exists; the log at
   `logs/agent-runner/agent-runner.log.2026-08-22` still shows
   `no handler registered for job_type=portfolio_digest`. This collection was orphaned when
   the portfolio-digest feature was removed.

2. **Four of the five collections the spec named do not exist as collections at all.**
   `fund_holdings`, `sector_performance`, `stock_news`, and `market_news` are declared only as
   unused string constants in `backend/db.py` and `agent-runner/tools/db.py`. There is nothing
   to delete in MongoDB; the cleanup is removing dead constants.
   Caution: the literals `"sector_performance"` and `"fund_holdings"` **are** used as FMP probe
   family keys in `agent-runner/tools/fmp_client.py:148,153`. Those must not be touched.

3. **`fmp_entitlements` must NOT be deleted.** It is absent from the database only because no
   entitlement probe has run yet. It is actively written at
   `agent-runner/tools/fmp_client.py:191` and covered by
   `agent-runner/tests/test_fmp_client.py:139`.

4. **`transcripts_cache` needs a human decision, not automatic deletion.** It has 0 documents
   and no writer, but it is *not* unreferenced: an index is created for it
   (`agent-runner/tools/db.py:93`), it is cleaned up on ticker deletion
   (`backend/routers/stocks.py:107`), and that behavior is asserted by a test
   (`backend/tests/test_routers.py:460,470`). It also corresponds to an existing planned
   feature (`specs/007-earnings-transcripts/`). Under the spec's own assumption — which
   excludes "collections reserved for a planned-but-unbuilt feature" — it should be **kept**.
   Deleting it would require also removing the index bootstrap, the cleanup call, and the test.

**Recommendation**: delete `portfolio_digest_cache` only; remove the four dead constants;
keep `transcripts_cache` and `fmp_entitlements`. Present this list for explicit confirmation
before any deletion, per the spec's non-reversibility note.

---

## R8. Indexing

**Decision**: Index the `screener` collection for the filters generated queries will actually
produce; leave the existing collections' indexes alone except for two pre-existing gaps.

**New indexes on `screener`**:
- `{ticker: 1}` unique — identity/joins.
- Single-field indexes on the high-selectivity numeric signals actually filtered on:
  `range_pct_20d`, `zscore_20d`, `weekly_change_pct`, `fcf_exceeds_debt`, `financials_trend`.
- `{sector: 1}` — sector-scoped questions are an obvious follow-up pattern.

Deliberately **not** building wide compound indexes: generated queries combine predicates in
unpredictable orders, so a compound index would help one ordering and be ignored by others. At
~8,340 documents and ~17 MB even at 15x, the whole collection fits in cache and single-field
index intersection is more than sufficient. This is the honest engineering answer — building
speculative compound indexes here would be premature optimization.

**Pre-existing gaps worth fixing while in the area** (carried from the earlier audit, still
true):
- `institutional_cache` has no index beyond `_id` but is queried by ticker — add
  `{ticker: 1}` unique, matching its sibling cache collections.
- `earnings_cache` has no index beyond `_id` and mixes two document shapes written by two
  independent writers (`{type:"calendar", days:N}` vs `{type:"calendar_range", from, to}`).
  Not a performance problem at 53 docs; worth an index reflecting the real query shape.

**Not acting on**: `analyses` (4 indexes) and `congress_trades` (5 indexes) look over-indexed
for their size, but every collection's `$indexStats` counter reset at the last `mongod`
restart, so a zero there means "not queried since restart," not "unused." Dropping indexes on
that basis would be unjustified.

---

## R9. Conversation context (FR-003 / FR-004)

**Decision**: Conversation history lives in the browser only, and is replayed to the backend
with each turn. Nothing is persisted server-side.

**Rationale**: FR-004 forbids persistence; the frontend already holds per-page state, and the
constitution forbids adding storage infrastructure without demonstrated need. Sending the
prior turns with each request keeps the backend stateless, which also means a backend restart
mid-conversation degrades gracefully rather than corrupting a stored session.

**Bounding**: the replayed context must be capped (recommend the last ~6 turns, and truncate
result payloads to a summary rather than replaying full row sets). Without a cap, a long
conversation grows the prompt until latency regresses past SC-001.

---

## R10. Backend has no LLM capability today — this is net-new

**Finding**: `backend/` does **not** call Ollama anywhere. `backend/settings.py:9-10` declares
`ollama_url` and `ollama_model`, but nothing reads them. `ollama` is absent from
`backend/requirements.txt`, and the backend service has **no `depends_on: ollama`** in
`docker-compose.yml` (it depends only on mongodb).

**Required to serve chat from the backend**:
1. Add `ollama>=0.4` to `backend/requirements.txt`.
2. Add `depends_on: [ollama]` to the backend service in `docker-compose.yml`.
3. Port an `llm.py` equivalent into `backend/`, mirroring `agent-runner/llm.py`
   (hand-duplication with mirrored tests is the established convention here — see the header
   comment in `agent-runner/tools/price_store.py:4-10` — and matches the Q4 decision to scope
   the semantic layer to the chat-serving service).

**Important capability discovered — this strengthens R1**: `agent-runner/llm.py:34-60` calls
Ollama with `format=<JSON Schema dict>`, i.e. **constrained decoding**, not free-form
prompting:

```python
response = client.chat(model=..., messages=messages, format=schema,
                       options={"temperature": 0.2, "num_ctx": 8192})
return json.loads(response["message"]["content"])
```

My R1 spike used plain prompting, which is why the nested-schema run emitted unparseable JSON.
Using `format=` for query generation **guarantees structurally valid JSON output**, removing
the parse-failure class of error entirely. It does *not* guarantee the query is semantically
correct — that remains the real risk, and is what the golden-question test suite must cover.

**Gaps in the existing client to fix when porting**:
- **No timeouts anywhere.** No `timeout` is passed to `ollama.Client(...)` or `.chat(...)` in
  the repo. A chat endpoint without a timeout can hang a request indefinitely — must be added.
- Retries default to 1 (2 attempts) and then raise `LLMError`.
- Validation is `json.loads` only; the schema is enforced by Ollama, not re-checked in Python.
  For generated queries, add explicit Python-side validation (the R6 allowlist) regardless.
- `DEFAULT_OPTIONS = {"temperature": 0.2, "num_ctx": 8192}` — chat query generation should
  override to `temperature: 0`, and `num_ctx` may need raising to fit the schema description
  plus conversation context (R9).

## R11. Signals must live in their own collection — confirmed by a clobber hazard

R3 chose a separate `screener` collection. Inspection of the write path confirms this was not
merely preferable but **necessary**:

`price_history` is written by a **full-document `replace_one`** in *both* services
(`agent-runner/tools/price_store.py:211-216` and `backend/price_store.py:188-193`):

```python
db[PRICE_HISTORY].replace_one({"ticker": ticker},
    {"ticker": ticker, "bars": merged, "coverage": build_coverage(...)}, upsert=True)
```

Any signal fields added to that document would be **silently erased** by whichever service
wrote next, because the replacement payload is constructed from scratch and does not carry
unknown fields forward. Adding per-bar fields is worse still: `bars_to_frame` ends with
`return df[OHLCV_COLUMNS]`, silently dropping any extra column on every read, and `merge_bars`
replaces whole rows on collision, wiping computed per-bar values on refetch.

A separate collection sidesteps all of this. New collection names must be registered in **both**
`backend/db.py` and `agent-runner/tools/db.py` with matching `ensure_indexes` entries — the
hand-sync convention documented at `backend/db.py:13`.

## R12. Frontend integration points (corrected)

- **Nav lives in `frontend/src/components/layout/Navbar.tsx:4-12`**, a flat
  `{to, label}` array — *not* `Sidebar.tsx`, which renders only the watchlist. Adding Chat is
  three edits: the `links` array, an import + `<Route path="/chat" .../>` in `App.tsx:4-33`,
  and a new `frontend/src/pages/Chat.tsx`.
- **No icon library** — nav is text-label only; icons elsewhere are hand-rolled inline SVG.
- **The axios instance is `frontend/src/api/client.ts`** (not `lib/api.ts`): a 5-line
  `axios.create({baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000"})` with no
  interceptors and **no timeout** — worth setting a per-request timeout for chat given LLM
  latency.
- **Global no-polling is enforced** in `main.tsx:12-20` (`refetchInterval: false`,
  `refetchOnWindowFocus: false`). A chat POST → answer fits `useMutation` cleanly and needs no
  exception. `useQueue.ts:16-31` is the sole polling precedent and is explicitly justified.
- **Tests mock the axios module directly** (`vi.mock("../api/client", ...)`); there is no MSW.
  Vitest config lives inside `vite.config.ts`.

## Open items carried into Phase 1

| Item | Status | Needs user decision? |
|---|---|---|
| MongoDB auth is disabled → FR-012 "structural" enforcement is app-level only | **Resolved to option (a)** in R6; recommend allowlist-only now, enable-auth as follow-up | **Yes** — FR-012's wording implies a DB-level guarantee that will not exist |
| `transcripts_cache` keep vs delete | R7 recommends **keep** (reserved for `specs/007-earnings-transcripts/`, and its cleanup behavior is under test) | **Yes** — user asked to delete unused collections; this one is arguably reserved, not dead |
| Streaming responses (spec Assumption) | **Deferred** — warm latency ~5–8s likely makes it unnecessary; no streaming exists anywhere in the repo today, and adding SSE brushes against Principle V | No — revisit only if measured latency disappoints |
| SC-001 (10s) | Achievable **warm only**; cold start alone is ~10–13s. Requires Ollama `keep_alive` + pre-warm at startup | No — handled in design |
