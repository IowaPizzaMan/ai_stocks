# Data Model: Dashboard Tweaks Batch

**Feature**: 028-dashboard-tweaks-batch | **Phase**: 1

Net effect on storage: **zero new collections, one dropped.** The two "new" datasets use
collection constants spec 017 already declared in both `db.py` files but never wrote to.
Everything else is an additive nullable field on an existing document.

All collection constants must stay identical in `backend/db.py` and
`agent-runner/tools/db.py` (Principle VI).

---

## Changed: `ticker_index` — like/dislike tag

The tracked-ticker registry (`registry.py::register_ticker`). One field added.

| Field | Type | Notes |
|---|---|---|
| `ticker` | string (unique) | unchanged — the tracked universe |
| `sentiment` | `"liked"` \| `"disliked"` \| absent | **NEW.** Absent means untagged. Never both (FR-007) — a single field makes mutual exclusion structural rather than enforced |
| `sentiment_at` | datetime, nullable | **NEW.** When the tag was last set; absent when untagged |
| *(existing fields unchanged)* | | `sources`, `status`, `name`, `sector`, `first_seen_at`, `last_seen_at` |

**Why here** (R11): membership in `ticker_index` *is* the definition of "tracked" that
FR-006a needs, so the tag and the precondition for showing its control live in one
document. A tag for an untracked ticker is structurally impossible.

**Lifecycle**: set/cleared only by `PUT`/`DELETE /stocks/{ticker}/sentiment`. Never
written by any pull, analysis, or job — it is user opinion, not derived data.

**Removal interaction**: removing a stock from the watchlist deletes its `watchlist` row,
not its `ticker_index` row, so the tag survives and is restored if re-added (spec Edge
Cases). No cascade delete is needed or wanted.

**No migration**: absent `sentiment` is the correct state for every existing document.

**Index**: none added. The tagged set is a few dozen documents at most; a collection scan
filtered on `sentiment` is cheaper than maintaining an index for it.

---

## Changed: `portfolio_digest_cache` — sector on highlights

Singleton document written by the `portfolio_digest` job. One field added *inside* each
highlight entry.

| Field | Type | Notes |
|---|---|---|
| `highlights[].ticker` | string | unchanged |
| `highlights[].signal` | enum | unchanged — LLM-emitted, constrained by schema |
| `highlights[].conviction` | enum | unchanged — LLM-emitted, constrained by schema |
| `highlights[].note` | string | unchanged — LLM-emitted |
| `highlights[].sector` | string, nullable | **NEW.** Joined deterministically from the analysis document by ticker *after* the model returns (R3) — never model-emitted |
| *(envelope unchanged)* | | `generated_at`, `overview`, `stock_count`, `total_tracked_count`, `capped`, `last_error`, `last_error_at` |

**Why**: the filter bar filters on ticker, signal, conviction, **and** sector. The first
three are already on each highlight; without sector, a sector filter would silently match
nothing (R3).

**Principle III boundary**: `sector` is deliberately absent from the agent's JSON schema.
It is a known stored fact, so the model must not have the opportunity to invent it —
the same reason the agent is already forbidden from overriding stored signal/conviction.

**Backfill**: none. Existing highlights simply lack `sector` until the next regeneration;
a nullable sector matches no sector filter, which is the correct behavior for a stale
document.

---

## Activated: `congress_trades`

Constant already declared in both `db.py` files (017); never written to until now. Schema
is **exactly** the one spec 017 pinned — reused rather than redesigned (R7, Principle VI).

Provider field names confirmed against a live response (R7).

| Field | Type | Notes |
|---|---|---|
| `trade_id` | string (unique) | **Composite hash** of (`chamber`, `person_id`\|`politician`, `ticker`\|`asset_description`, `transaction_date`, `transaction_type`, `amount_range`, `owner`). The provider supplies **no per-trade id**, so this is required, not a convenience |
| `chamber` | `"senate"` \| `"house"` | both chambers share one collection, distinguished here |
| `person_id` | string, nullable | provider's `senateId` — a **person** id (bioguide, e.g. `B001236`), repeated across all that member's rows. Preferred key for the person filter (R7) |
| `politician` | string | `firstName + " " + lastName`, falling back to `office` (which holds the full name in both chambers) |
| `district` | string, nullable | `"AR"` (senate) / `"FL23"` (house) |
| `owner` | string, nullable | `"Joint"` / `"Self"` / `"Spouse"`; **often empty** — part of `trade_id` so Joint and Self holdings of the same trade do not collide |
| `ticker` | string, nullable | provider `symbol`; **null (never `""`)** for non-equity disclosures — rendered without a link (FR-018) |
| `asset_description` | string, nullable | `"Broadcom Inc"`, `"Meta Platforms Inc (1)"` — what identifies a row when `ticker` is null |
| `asset_type` | string, nullable | `"Stock"` etc. The reliable equity/non-equity discriminator |
| `transaction_type` | string | **`"Purchase"` / `"Sale"` — capitalised words, not `buy`/`sell`.** Stored verbatim; the buy predicate normalises at read time |
| `amount_range` | string, nullable | the disclosed bracket verbatim (e.g. `"$1,001 - $15,000"`). **Stored and compared as a bracket; no point value is ever derived** (FR-016a) |
| `transaction_date` | date | when the trade occurred |
| `disclosure_date` | date | when it became public — **this is what the 90-day summary window filters on** (R8) |
| `link` | string, nullable | source disclosure URL |
| `source` | string | `"fmp"` |
| `collected_at` | datetime | provenance envelope |

House-only `capitalGainsOver200USD` is **not** stored — no consumer (Principle V).

**Person-filter improvement**: because `person_id` is stable per member, the spec's Edge
Case accepting unreconcilable name-spelling variants no longer applies — the filter matches
`person_id` when present and falls back to name substring.

**Legacy note**: the older `congressional_trades` name appears only in
`specs/data_fetcher.py` (a spec-era reference file, not live code) and in no module under
`backend/` or `agent-runner/`. Per 017's own instruction it stays retired.

**Indexes**: `trade_id` unique; `(disclosure_date DESC)` for the default listing and the
90-day window; `(ticker, disclosure_date DESC)` for the ticker filter; `(person_id)` for
the person filter.

**Retention**: no TTL. Disclosures are an accumulating historical record, and the 90-day
summary window is a query bound, not a storage bound.

---

## Activated: `market_movers`

Constant already declared in both `db.py` files (017); never written to until now. Schema
is 017's, including the `category` discriminator.

Provider field names confirmed against a live response (R9).

| Field | Type | Notes |
|---|---|---|
| `date` | date | unique with (`category`, `ticker`) |
| `category` | `"gainers"` \| `"losers"` \| `"actives"` | **This batch writes only `"actives"`** (R9); the other two remain valid values with no writer yet |
| `ticker` | string | provider `symbol`; links to the stock detail page (FR-023) |
| `company` | string, nullable | provider `name` |
| `price` | float, nullable | |
| `change` | float, nullable | **NEW.** Absolute move (`0.06`) |
| `change_pct` | float, nullable | provider `changesPercentage` — **already a percent** (`3.35196` = +3.35%); do not multiply by 100 |
| `exchange` | string, nullable | **NEW.** `"NASDAQ"` |
| `rank` | int | **NEW.** Provider array position. **Load-bearing** — see below |
| `volume` | float, nullable | **Always `None` for `actives`** — the `most-actives` endpoint returns no volume field |
| `source`, `collected_at` | — | provenance envelope |

**Index**: `(date DESC, category, rank ASC)` for the read path, plus
`(date, category, ticker)` unique — the latter makes same-day re-runs idempotent.

**Why `rank` is required**: `most-actives` returns rows already ordered by activity, but
the collection is keyed on `(date, category, ticker)` and written by upsert, so Mongo does
not preserve insertion order on read. Without storing the provider's position, the panel
would render in arbitrary order while looking authoritative. Sorting by `volume` — the
original plan — is impossible because the endpoint supplies none.

**Why only `actives`**: FR-022 needs most-actives alone. Gainers/losers would be stored
with no consumer (Principle V). Because `category` already exists in the pinned schema,
adding them later is a pure addition with no migration.

---

## Reused unchanged: `price_history` (sector ETFs)

The 11 sector ETFs are stored as ordinary tickers in the existing `price_history`
collection via `price_store.get_series` — **no schema change, no new collection** (R5).

| Concern | Resolution |
|---|---|
| Tickers | `XLC XLY XLP XLE XLF XLI XLV XLB XLRE XLK XLU` — a fixed constant list |
| Shape | `{ticker, bars: [{date, open, high, low, close, volume}], coverage: {...}}` — unchanged |
| Refresh | `refresh="delta"` per ticker; incremental after the first full fetch |
| History depth | Must cover the widest window (1Y). `price_store`'s existing full-fetch default already exceeds this |
| TTL | None, by existing design — expiry would destroy the delta baseline (`db.py:56-59`) |

Only `close` and `date` are read by the sector chart endpoint; the other OHLCV fields are
stored because that is the module's existing shape, not because this feature needs them.

---

## Dropped: `pull_metrics`

Removed entirely — collection, both indexes, and the constant in both `db.py` files
(FR-026, FR-026a; clarification Q5).

| What | Where | Action |
|---|---|---|
| Writer | `agent-runner/queue_worker.py` `_write_pull_metrics` / `_record_pull_metrics` + 3 call sites | delete |
| Reader | `backend/routers/stocks.py` `GET /stocks/{ticker}/pull-metrics` | delete |
| Indexes | `agent-runner/tools/db.py:127-128` (`(ticker, started_at DESC)`, 30-day TTL) | delete declarations |
| Constant | `PULL_METRICS` in both `db.py` files | delete |
| Data | the collection itself | one-time `drop()` |

**Safety** (R12): nothing in the analysis pipeline, price baseline, or delta-pull decision
path reads this collection. The baseline delta pulls depend on is `price_history`, a
separate collection — so FR-026b holds structurally, not by inspection.

---

## Entity relationships

```text
ticker_index (the tracked universe)
  ├─ sentiment ──────────────► filters analyses feed via two-step $in (R11)
  └─ ticker ─────────────────► analyses.ticker (1:1, separate collections, no FK)

analyses
  └─ ticker, sector ─────────► joined onto portfolio_digest_cache.highlights[] after LLM (R3)

congress_trades
  └─ ticker (nullable) ──────► stock detail page link when present (FR-017/FR-018)
        └─ 90-day window on disclosure_date ──► computed summary (never stored)

market_movers (category="actives")
  └─ ticker ─────────────────► stock detail page link (FR-023)

price_history
  └─ 11 sector ETF tickers ──► window-sliced closes ──► rebased to % client-side (R6)
```

**Derived, never stored**: the Congress most-bought ranking and high-dollar list are
computed per request from `congress_trades` rows (R8), and the sector chart's percentage
rebasing is computed per render from closes (R6). Neither has a cache document, because
both are cheap arithmetic over already-cached data — caching them would add an
invalidation problem for no measurable gain.

---

## Validation rules

| Rule | Where enforced | Source |
|---|---|---|
| `sentiment` ∈ {liked, disliked} or absent | `PUT /stocks/{ticker}/sentiment` request model | FR-007 |
| Sentiment only settable on a tracked ticker | endpoint 404s when no `ticker_index` row exists | FR-006a |
| Setting the current value clears it (toggle) | endpoint compares before writing | FR-008 |
| `amount_range` never converted to a number | `high_dollar` parses bounds only, compares upper bound | FR-016a |
| Unparseable/absent `amount_range` never flagged | parser returns `None`; caller excludes | Edge Cases |
| Congress window filters `disclosure_date` | both summary functions | R8 |
| A ticker missing from a window still renders | chart marks partial rather than dropping | FR-021 |
| Job re-runs are idempotent | upsert on `trade_id` / `(date, category, ticker)` | — |
