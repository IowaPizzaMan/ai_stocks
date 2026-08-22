# Research: Dashboard Tweaks Batch

**Feature**: 028-dashboard-tweaks-batch | **Date**: 2026-08-22 | **Phase**: 0

All Technical Context unknowns are resolved below. Each decision records what was
chosen, why, and what was rejected. Several were resolved by reading existing code
and prior specs rather than by open-ended research — those are marked **(from
codebase)** and cite the file that settled them.

---

## R1 — The Portfolio Summary blank-page bug **(from codebase)**

**Decision**: Change the highlight link in `PortfolioDigestPanel.tsx` from
`/stocks/${ticker}` to `/stock/${ticker}`, and add a catch-all `*` route rendering a
small NotFound element in `App.tsx`.

**Rationale**: The cause is exact and confirmed, not inferred. `App.tsx:22` registers
`/stock/:ticker` (singular). `PortfolioDigestPanel.tsx:101` links to
`/stocks/${h.ticker}` (plural). React Router's `<Routes>` has no catch-all, so an
unmatched path renders nothing at all inside `<main>` — a structurally blank page,
exactly as reported. The one-word link fix resolves FR-001 completely.

The catch-all is added because this batch introduces three *new* families of ticker
links (Congress rows, Top Traded rows, and existing panels), and the current failure
mode for any future path typo is a silent blank page with no console error. A visible
"page not found" turns a silent structural failure into an obvious one. This is a
5-line addition, not new infrastructure (Principle V).

**Alternatives rejected**:
- *Add a `/stocks/:ticker` route alias* — would make both paths work and let the
  inconsistency spread. One canonical ticker path is the point.
- *Catch-all that redirects to `/`* — hides the mistake instead of surfacing it;
  a developer would see a working app and never learn a link was wrong.

---

## R2 — Applying the feed filter to the digest highlights

**Decision**: `PortfolioDigestPanel` reads the active filter from URL search params
itself (`useSearchParams`, the same source `Stocks.tsx` already uses) and filters the
already-fetched `highlights` array client-side through a pure
`filterHighlights(highlights, filters)` function in `frontend/src/lib/`. No new
network request, no new prop-drilling, no LLM call. The overview paragraph is
rendered unchanged with a scope label whenever any filter is active (FR-004a/b).

Additionally, `sector` is added to each stored highlight so all four filter
dimensions work uniformly (see R3).

**Rationale**: Filter state already lives in URL search params
(`FilterBar.tsx` writes them; `Stocks.tsx:50-55` reads them), which is the
constitution's mandated pattern ("filter state in URL search params"). Reading them in
the panel keeps the panel self-contained and avoids threading props through
`Stocks.tsx`'s tab/column layout. Clarification Q1 settled that no regeneration
occurs, so this is pure client-side array filtering — instant, and it satisfies SC-002's
"without waiting on any AI regeneration".

Extracting the predicate as a pure function (rather than inlining it in JSX) is what
makes the four filter dimensions and their combinations cheap to test exhaustively per
Principle I.

**Alternatives rejected**:
- *Pass filters down from `Stocks.tsx` as props* — `Stocks.tsx` already reads them, but
  the panel sits in a sibling column and the prop would exist solely to relay
  already-global state.
- *Server-side filtering via query params on `GET /portfolio/digest`* — the digest is a
  single cached document of at most 25 highlights; round-tripping to filter an array
  the client already holds adds latency and an endpoint variant for zero benefit.

---

## R3 — Making `sector` available to highlight filtering

**Decision**: Add `sector` to `tools/portfolio.py`'s `_PROJECTION` and join it onto each
highlight **after** the LLM returns, by ticker lookup against the gathered documents.
Persist it in the stored highlight. Do not add `sector` to the agent's JSON schema.

**Rationale**: The filter bar's dimensions are ticker, signal, conviction, and sector
(`Stocks.tsx:50-55`; sector arrives via URL when navigating from the Sectors page).
Highlights currently carry ticker/signal/conviction but not sector, so a sector filter
would silently match nothing.

Joining deterministically after the LLM call — rather than asking the model to emit a
sector — is required by Principle III: sector is a known fact already stored on the
analysis document, so the model must not be given the chance to invent or mistype it.
This mirrors how the agent is already forbidden from overriding stored signal/conviction.

**Alternatives rejected**:
- *Add `sector` to the agent's response schema* — invites hallucinated sectors for a
  value we already know exactly. Direct Principle III violation.
- *Filter sector by looking up the feed items client-side* — the panel would need the
  feed's paginated data, which it does not have and should not couple to.

---

## R4 — How the new datasets get refreshed (no admin router exists) **(from codebase)**

**Decision**: Each new data surface gets its own `POST /<area>/refresh` endpoint that
enqueues its admin job into `work_queue` with the existing duplicate-run guard, exactly
mirroring `backend/routers/portfolio.py::regenerate_digest`. The page renders a
Refresh button and an empty state pointing at it. No admin router is built.

**Rationale**: This was the single most important thing to check, and the answer is not
what the prior spec implies. `agent-runner/tools/admin_jobs.py:11` refers to
"`backend/routers/admin.py`'s ADMIN_JOBS constant" — **that file does not exist**.
`backend/main.py` registers twelve routers and none is an admin router. Spec 017
designed `GET /admin/jobs` and `POST /admin/jobs/{name}/run` but they were never
implemented, so `congress_trades_pull` and `market_movers_pull` are registered names
with no trigger path whatsoever.

Rather than implement another feature's unbuilt admin API as a side effect of this one,
this batch reuses the pattern that *is* built and proven: spec 027's digest panel
enqueues its own job from its own endpoint with a `{job_type, status ∈ pending|running}`
dedupe check. That is ~12 lines per surface, needs no new UI concept, and puts the
refresh control where the user actually is. Constitution Principle V explicitly warns
against adding infrastructure ahead of demonstrated need.

**Alternatives rejected**:
- *Build 017's admin router now* — implementing an unrelated spec's contract inside this
  batch would expand scope substantially and leave 017 half-delivered and confusing.
- *Auto-fetch on page load with a TTL* (the pattern `market.py::get_market_news` uses) —
  puts a blocking provider call in a GET request path; the queue exists precisely so slow
  provider work happens off the request path.
- *A scheduler/cron* — forbidden by Principle V ("All analysis triggering flows through
  `work_queue`, never cron").

---

## R5 — Sector ETF price series **(from codebase)**

**Decision**: Reuse `price_store.get_series(ticker, refresh="delta", db)` for the 11
sector ETFs, storing into the existing `price_history` collection. Add one new admin job
`sector_etf_pull` that loops the 11 tickers, fail-soft per ticker.

**Rationale**: `agent-runner/tools/price_store.py` already does exactly what the sector
chart needs and nothing more: daily EOD bars, one document per ticker, incremental delta
refresh, budget-guarded via `fmp_client.fetch_eod_history`, and fail-soft — a provider
error serves stored bars with `outcome: "degraded"` rather than raising. Sector ETFs are
ordinary tickers to this module; no changes to it are required.

`price_history` has no TTL by design (`db.py:56-59`), which is what a chart needing up to
1 year of history requires.

**Alternatives rejected**:
- *Extend the registered `sector_performance_pull`* — its contracted description is
  "today's sector performance **snapshot**", a different dataset (`sector_performance`,
  current-day percentages). Overloading it would make one job write two unrelated shapes.
- *Fetch history on demand in the router* — same blocking-provider-call-in-GET problem as
  R4, times 11.
- *A new sector-specific price collection* — would duplicate `price_history`'s purpose and
  violate 017's "one home per dataset" rule.

---

## R6 — Percentage rebasing and window slicing

**Decision**: `GET /sectors/etf-series?window=1m|3m|6m|1y` returns raw `{date, close}`
arrays per ticker for the requested window. The frontend rebases via a pure
`rebaseToPercent(bars)` helper in `frontend/src/lib/`, covered by Vitest.

**Rationale**: The spec's data model states rebasing "is a presentation concern derived
from this series, not a stored form of it". Serving closes keeps the endpoint a plain
cache read consistent with every other router here, and keeps the one piece of arithmetic
in a pure, directly-tested function. Window slicing happens server-side so the payload
stays proportional to what is displayed.

Payload at the widest setting is ~252 sessions × 11 tickers ≈ 2,800 points — well within
a single JSON response, so no downsampling is needed (and downsampling would distort the
very inflections the chart exists to reveal).

**Rebasing rule**: each series is divided by its own first close *within the returned
window*, so every line starts at 0%. A ticker whose data starts late within the window
rebases from its own first available bar, and is marked partial rather than dropped
(FR-021).

**Alternatives rejected**:
- *Rebase server-side* — would bake a display choice into stored/served data and make the
  endpoint single-purpose.
- *Return all history and slice client-side* — sends up to 4× the needed data for the 1M
  view, every time.

---

## R7 — Congress disclosure ingestion **(reuses 017's pinned schema)**

**Decision**: Implement `congress_trades_pull` fetching `senate-latest` and `house-latest`
via `fmp_client.fmp_get`, normalizing both into the `congress_trades` collection using
**the schema spec 017 already pinned** (`specs/017-fmp-migration-admin/data-model.md`):
`trade_id` (unique hash), `chamber`, `politician`, `ticker` (nullable),
`transaction_type`, `amount_range`, `transaction_date`, `disclosure_date`, plus the
`source`/`collected_at` envelope. Upsert on `trade_id` so re-runs are idempotent.

The legacy `congressional_trades` collection is confirmed dead: it appears only in
`specs/data_fetcher.py` (a spec-era reference file, not live code) and in no module under
`backend/` or `agent-runner/`. Per 017's own instruction, `congress_trades` is therefore
the home and the legacy name stays retired.

**Rationale**: Principle VI requires the two services to agree on collection shapes, and
017 already did this design work with the user's endpoint entitlement confirmed
(`fmp-gap-review.md`: "Senate & house trading — adopt, user confirmed entitled"). Inventing
a second shape for the same dataset would be the exact divergence Principle VI forbids.
Both chambers share one collection distinguished by `chamber`, as 017 specified.

**Field mapping — RESOLVED (user-supplied live response, 2026-08-22)**. Both chambers
return the same core field set; House adds one extra. Display labels shown as the user
reported them; JSON keys are the conventional camelCase FMP form and must be confirmed
against the raw payload when the fixture is captured.

| Provider field | → `congress_trades` | Notes |
|---|---|---|
| `symbol` | `ticker` | **Empty for non-equity rows** — store `None`, never `""` (FR-018) |
| `senateId` | `person_id` | **NEW field.** A *person* id (bioguide, e.g. `B001236`), repeated across all of that member's rows — **not** a per-trade id |
| `disclosureDate` | `disclosure_date` | the 90-day summary window filters on this (R8) |
| `transactionDate` | `transaction_date` | |
| `firstName` + `lastName` | `politician` | joined with a space; falls back to `office` |
| `office` | — | holds the full name in both chambers (`"John Boozman"`), used as the fallback |
| `district` | `district` | **NEW field.** `"AR"` (senate) / `"FL23"` (house) |
| `owner` | `owner` | **NEW field.** `"Joint"`, `"Self"`, `"Spouse"`, or **empty** (the House sample has none) |
| `assetDescription` | `asset_description` | **NEW field.** `"Broadcom Inc"`, `"Meta Platforms Inc (1)"` |
| `assetType` | `asset_type` | **NEW field.** `"Stock"` — how non-equity rows are identified |
| `type` | `transaction_type` | **`"Purchase"` / `"Sale"`, capitalised words — not `buy`/`sell`** |
| `amount` | `amount_range` | `"$1,001 - $15,000"` — space-hyphen-space, as the parser assumed |
| `link` | `link` | **NEW field.** Source disclosure URL |
| `capitalGainsOver200USD` | — | House only; not stored, no consumer |

Four consequences that change the earlier design:

1. **There is no per-trade id from the provider.** `senateId` is a person id repeated
   across rows (both sample Boozman rows share `B001236`), so the composite `trade_id`
   hash is not merely convenient — it is required. It must include `transaction_type` and
   `owner`, or a same-day Purchase and Sale, or the same trade held Joint vs Self, would
   collide and silently overwrite each other.
2. **`transaction_type` is `"Purchase"`/`"Sale"`, not `buy`/`sell`.** The buy predicate in
   `rank_most_bought` matches case-insensitively on `"purchase"` and must also tolerate the
   partial-sale variants these filings commonly use (`"Sale (Full)"`, `"Sale (Partial)"`),
   which are sales and must never count as buys.
3. **`person_id` resolves the spec's known limitation.** The spec's Edge Cases accepted
   that a member appearing under varying name spellings could not be reconciled. A stable
   bioguide id per member means the person filter can match on `person_id` when one is
   present, falling back to name substring — so that limitation no longer applies.
4. **`asset_type` distinguishes equity from non-equity** far more reliably than inferring
   it from an empty symbol, which is what FR-018's link suppression needs.

The tolerant-normalizer design still stands (read each field from a candidate key set;
log-and-skip a row yielding neither ticker nor politician), because the exact JSON casing
is still unconfirmed. But capturing the fixture is now a verification step rather than a
discovery step.

**Alternatives rejected**:
- *Separate `senate_trades` / `house_trades` collections* — doubles every query and
  contradicts 017's pinned single-collection design.
- *Trusting assumed field names* — would produce a job that silently writes empty rows.

---

## R8 — Congress summary computation (deterministic)

**Decision**: Both summary measures are pure Python functions over already-stored
`congress_trades` rows, with no LLM involvement:

- `rank_most_bought(rows, now, days=90)` — counts rows where `transaction_type` is a
  buy and `disclosure_date` falls within 90 days, grouped by ticker, ranked by count
  descending then ticker ascending for a stable order.
- `high_dollar(rows, now, days=90)` — selects rows in the same window whose
  `amount_range` bracket **reaches** $100,001, by parsing the bracket's upper bound.

Bracket parsing extracts the numeric bounds from the disclosed string and compares the
upper bound against the threshold. No midpoint, average, or point estimate is ever
computed or displayed (FR-016a). A row with an unparseable or absent `amount_range` is
listed in the table but never flagged high-dollar (spec Edge Cases).

**Rationale**: Principle III — this is arithmetic over stored facts, so it belongs in
deterministic, exhaustively-tested code, not in a model. Clarification Q3 chose
count-based ranking specifically because summing brackets would require fabricating
values. Ranking ties broken by ticker keeps output stable across runs, which is what
makes it assertable in tests.

The 90-day window is evaluated against `disclosure_date` (when it became public), not
`transaction_date`, because disclosures are routinely filed weeks-to-months late; using
the trade date would make "recent" mean "recently traded but possibly long-since
disclosed", and would let the visible set change retroactively.

**Alternatives rejected**:
- *An LLM-written summary paragraph* — direct Principle III violation for a computable
  result, and unverifiable.
- *Midpoint-based dollar totals* — explicitly rejected by clarification Q3.
- *Windowing on `transaction_date`* — see above; would silently hide newly-disclosed old
  trades, which are the most newsworthy kind.

---

## R9 — `market_movers_pull` scope **(reuses 017's pinned schema)**

**Decision**: Implement `market_movers_pull` pulling **only** `most-actives`, writing to
`market_movers` with `category: "actives"` — the discriminator 017 already pinned
(`gainers | losers | actives`). Gainers and losers are left unimplemented.

**Rationale**: This batch needs only most-actives (FR-022). 017's registered job
description covers all three, and its collection schema already carries the `category`
field, so adding the other two later is a pure addition with no schema change or
migration. Building them now would fetch and store data no surface displays, against
Principle V.

This is recorded explicitly (rather than quietly implementing a subset) so a later reader
does not assume the registered job is fully delivered.

**Field mapping — RESOLVED (user-supplied live response, 2026-08-22)**:

| Provider field | → `market_movers` | Notes |
|---|---|---|
| `symbol` | `ticker` | |
| `name` | `company` | 017's schema calls this `company` |
| `price` | `price` | |
| `change` | `change` | **NEW field.** Absolute move (`0.06`) |
| `changesPercentage` | `change_pct` | Already a percent (`3.35196` = +3.35%), **not** a fraction — do not multiply by 100 |
| `exchange` | `exchange` | **NEW field.** `"NASDAQ"` |
| — | `rank` | **NEW field.** Provider's array position — see below |

**`most-actives` returns no `volume` field.** 017's schema anticipated one, and the
contract for this feature originally specified ordering by volume descending. Neither is
possible: `volume` stays declared in the schema but is `None` for every `actives` row (a
future gainers/losers pull may or may not populate it).

Ordering therefore comes from the provider, which already returns most-actives in activity
order. Because the collection is keyed on `(date, category, ticker)` and written by upsert,
Mongo will not preserve insertion order on read — so the job **must** stamp each row's
array index as `rank`, and the read endpoint sorts on `rank` ascending. Without this the
panel would render in arbitrary order while appearing authoritative, which is the quiet
kind of wrong worth designing out.

The panel consequently shows price/change/change % rather than volume, and is titled by
what the provider actually ranks — most-active — rather than implying a volume figure it
never supplied.

**Alternatives rejected**:
- *Implement all three categories* — two-thirds of the fetched data would have no consumer.
- *A new `most_actives` collection* — would fragment a dataset 017 already gave one home.
- *Sort by `change_pct` as a volume stand-in* — that is a different ranking entirely
  (biggest movers, not most traded) and would silently misrepresent the endpoint.

---

## R10 — Congress read endpoints: path choice

**Decision**: New `backend/routers/congress.py` with prefix `/congress`, superseding
017's provisional `GET /market/congress-trades` path. 017's contract file gets a note
recording the supersession. Most-actives instead goes into the existing `market.py` as
`GET /market/most-actives`.

**Rationale**: 017 sketched `/market/congress-trades` for a "Market Overview" page that
was never built, so no consumer exists and there is no compatibility cost to moving it.
This batch builds a dedicated Congress page needing a list endpoint, two filters, and a
summary endpoint — enough surface to justify its own module, especially as `market.py` is
already ~400 lines spanning breadth, news, macro, treasury, and economics. Most-actives is
a single read and stays in `market.py` where the `market_movers` dataset naturally sits.

Recording the supersession in 017's contract (rather than silently diverging) is what the
constitution requires: "when implementation reveals the spec is wrong or incomplete, the
spec is updated, not silently bypassed."

**Alternatives rejected**:
- *Honor `/market/congress-trades`* — pushes a substantial new surface into an
  already-crowded module for consistency with an unbuilt page.
- *Diverge without updating 017* — leaves two contradictory contracts in the tree.

---

## R11 — Like/dislike storage **(from codebase)**

**Decision**: Store as a nullable `sentiment` field (`"liked" | "disliked" | absent`) on
the existing `ticker_index` document. New endpoints `PUT /stocks/{ticker}/sentiment` and
`DELETE /stocks/{ticker}/sentiment`. The feed filter resolves the tagged ticker set from
`ticker_index` first, then constrains the `analyses` query with `ticker: {$in: [...]}`.

**Rationale**: `ticker_index` is described in the constitution as "the single universe of
tickers" and is the stable per-ticker record (`registry.py`); membership in it is exactly
the definition of "tracked" that clarification Q4 requires for FR-006a. Putting the tag
there means the "tracked" precondition and the tag live in the same document — the control
can be shown or hidden from one read, and a tag for an untracked ticker is structurally
impossible.

It also gives the retained-tag edge case for free: a stock removed from the watchlist
keeps its `ticker_index` row, so its tag survives and returns if re-added, with no
cascade-delete logic.

The two-step feed filter is used because `analyses` and `ticker_index` are separate
collections; the tagged set is at most a few dozen tickers, so an `$in` is cheaper and far
more readable than an aggregation `$lookup` on every feed page load.

**Alternatives rejected**:
- *A new `stock_sentiment` collection* — a new collection to hold one nullable enum per
  ticker, when a per-ticker document already exists (Principle V).
- *Store on the `analyses` document* — `analyses` is overwritten on every pull; a user
  preference must not live in a regenerated document.
- *`$lookup` aggregation in the feed* — rewrites a simple, well-tested query path for a
  join over a tiny set.

---

## R12 — Pull-metrics removal blast radius **(from codebase)**

**Decision**: Safe to remove completely. Delete in this order: frontend panel + hook +
`Pull`/`PullStage` types → `GET /stocks/{ticker}/pull-metrics` → `queue_worker`'s
`_write_pull_metrics`/`_record_pull_metrics` and their call sites → `PULL_METRICS`
constant and index declarations in both `db.py` files → a one-time `drop()` of the
collection.

**Rationale**: Every reference was enumerated. Writers: `queue_worker.py` only (lines
114-139, called at 180/191/199). Readers: `backend/routers/stocks.py:169` serving
`frontend/src/hooks/usePullMetrics.ts`, consumed only by `PullCostPanel` via
`StockDetail.tsx:57`. Index declarations: `agent-runner/tools/db.py:127-128`. Nothing in
the analysis pipeline, price baseline, or delta-pull decision path reads it — the
`price_history` baseline that delta pulls depend on is a separate collection
(`db.py:56-59`), so FR-026b holds structurally rather than by inspection.

The collection also already carried a 30-day TTL, so dropping it destroys at most 30 days
of diagnostics that nothing consumes.

The frontend layer is deleted first so no build ever references a removed endpoint.

**Alternatives rejected**:
- *Leave the writer and delete only the panel* — explicitly rejected by clarification Q5.
- *Keep the collection constant "just in case"* — leaves a name with no writer, reader, or
  data, which is the half-retired state Q5's answer chose against.

---

## R13 — FMP budget impact

**Decision**: Accept. A full refresh of everything this batch adds costs **14 FMP calls**:
11 (sector ETF deltas) + 2 (senate + house) + 1 (most-actives).

**Rationale**: Principle IV requires the daily budget to be respected and guarded. All 14
calls route through `fmp_client.fmp_get` (directly, or via `fetch_eod_history`), so the
throttle, the daily soft-cap check, and `FmpBudgetExceededError` fail-soft behavior all
apply without new code. Against the documented 250/day soft cap, 14 calls per manual
refresh is immaterial, and refreshes are user-triggered rather than scheduled, so there is
no background accrual.

Each of the three jobs must catch `FmpBudgetExceededError` per sub-unit and degrade to
stored data, following `economics.py`'s established per-sub-pull isolation: one ETF
failing must not abort the other ten (FR-021's partial-render requirement depends on this
holding at the data layer, not just the chart).

**Alternatives rejected**:
- *Batch the 11 ETFs into one request* — FMP's EOD endpoint is single-symbol; `price_store`
  is built around one document per ticker, and a batch path would bypass its delta logic.

---

## Resolved Technical Context unknowns

| Unknown | Resolution |
|---|---|
| Why the digest ticker link renders blank | R1 — `/stocks/` vs `/stock/`, no catch-all |
| How filter state reaches the digest panel | R2 — URL search params, pure client-side predicate |
| How sector filtering works on highlights | R3 — deterministic post-LLM join |
| How new datasets get refreshed with no admin router | R4 — per-surface refresh endpoint, mirroring spec 027 |
| Where sector ETF history comes from | R5 — existing `price_store`, new `sector_etf_pull` job |
| Where % rebasing happens | R6 — frontend pure function; server slices the window |
| Congress collection shape | R7 — 017's already-pinned `congress_trades` schema |
| Congress summary math | R8 — pure functions, bracket upper-bound test, `disclosure_date` window |
| Movers scope | R9 — `category: "actives"` only |
| Congress endpoint path | R10 — new `/congress` router, supersedes 017's sketch |
| Like/dislike storage | R11 — `sentiment` on `ticker_index` |
| Pull-metrics removal safety | R12 — fully enumerated, no analytical dependency |
| FMP budget cost | R13 — 14 calls per full refresh, all guarded |
