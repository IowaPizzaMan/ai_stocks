# Research: Deduplicate Analysis Feed & Storage

No open technical unknowns required external research — this feature changes existing,
fully-understood code paths (write path, two read paths, one index set, one new script).
The decisions below record the approach chosen for each functional requirement and why.

## D1. Write path: insert → upsert on ticker

**Decision**: Change `agent-runner/queue_worker.py:72` from `db[ANALYSES].insert_one(result)`
to an upsert keyed on `ticker` — `db[ANALYSES].replace_one({"ticker": result["ticker"]}, result, upsert=True)`,
using the existing `write_db(ANALYSES, result, upsert_key="ticker", db=db)` helper already
defined at `agent-runner/tools/db.py:83-88` (currently unused for analyses).

**Rationale**: This is the single insertion point for analysis documents (confirmed — no
other `insert_one`/`insert_many` call touches `ANALYSES` anywhere in `agent-runner/` or
`backend/`). Fixing it here makes "one stored analysis per ticker" true of the data itself
(FR-004), which is what lets every read path stay a plain query instead of needing
dedup logic. `write_db`'s upsert branch already does exactly this `replace_one(..., upsert=True)`
pattern — no new helper needed.

**Alternatives considered**: Deleting-then-inserting (two round trips, not atomic, no
benefit over `replace_one`'s single atomic upsert). Doing the dedup only at read time via
aggregation everywhere (rejected — spec explicitly calls this out as the wrong root-cause
fix in User Story 2's rationale, and it would leave the DB growing unboundedly).

## D2. Feed read path: no aggregation needed

**Decision**: Leave `backend/routers/analysis.py`'s `GET /analysis/feed` as a plain
`find().sort().skip().limit()` with `count_documents()` — no `$group` aggregation added.

**Rationale**: Once D1 guarantees at most one document per ticker exists at any time, the
existing plain query is already correct (FR-001, FR-002, FR-003) — every result row is
already the latest (only) analysis for its ticker. Adding a `$group`-by-ticker aggregation
here (mirroring the Sectors pattern) would be redundant complexity with no behavioral
effect, which conflicts with Constitution Principle V (Simplicity & Local-First Scope: don't
add complexity ahead of a demonstrated need).

**Alternatives considered**: Aggregate at read time like `get_sector_analyses` (`backend/routers/analysis.py:54-64`)
and `GET /sectors` (`backend/routers/sectors.py:20-29`). Rejected for the Feed specifically
because it would duplicate work the write-path fix already does for free. The Sectors
endpoints keep their existing aggregation unchanged — they are out of scope (spec's Edge
Cases: "No behavior change" for Sectors) and removing their now-redundant `$group` is not
required by any FR, so it is left alone to avoid unnecessary churn.

## D3. Per-ticker analysis lookup: list → single object

**Decision**: Change `GET /analysis/{ticker}` (`backend/routers/analysis.py:67-73`) from
`.find(...).sort(...).limit(limit)` (a list, default limit 10) to `.find_one(...)` returning
a single object or `null`/404 when none exists. Drop the `limit` query param.

**Rationale**: FR-005 requires per-ticker lookups return only the current analysis;
multi-analysis history views are removed. Once D1 holds, the collection only ever has ≤1 doc
per ticker anyway, so the list endpoint would just return a 0-or-1-element array — collapsing
it to a single object matches the data model and removes now-meaningless list-handling code
in the frontend.

**Alternatives considered**: Keep the endpoint returning a list and let the frontend just use
element `[0]` (this is what happens today, per `frontend/src/pages/StockDetail.tsx:54`,
`const latest = analyses?.[0]`). Rejected — the endpoint shape should reflect the new
invariant directly rather than carrying forward a list type that can only ever hold 0 or 1
items, per FR-005's explicit removal of history semantics.

## D4. Frontend: history hook/type simplification

**Decision**: `useTickerAnalysis` (`frontend/src/hooks/useAnalysis.ts:28-37`) changes its
return type from `Analysis[]` to `Analysis | null`. `StockDetail.tsx:43,54` drops the
`analyses?.[0]` indirection and uses the fetched analysis directly.

**Rationale**: Direct consequence of D3; keeps the frontend type honest about what the API
now returns. No standalone "Analysis History Timeline" UI component exists in the codebase
today (it was spec'd in `specs/component-specs/frontend/components/stock/AISummaryTab.md`
but never built — `AISummaryTab` only ever rendered from the latest analysis), so there is no
component to delete, only the data-shape plumbing to simplify. The stale spec section
documenting the never-built timeline should be removed for consistency (Principle II,
spec-driven development: specs should reflect intended reality) — tracked as a task, not a
plan-time doc edit.

## D5. One-time cleanup: dedupe script

**Decision**: New `scripts/dedupe_analyses.py`, modeled directly on the existing
`scripts/backfill_financials.py` precedent (same `sys.path` bootstrap into `agent-runner/`,
same `logging_config.get_logger(__name__, component="scripts")`, run manually outside Docker
via `python scripts/dedupe_analyses.py`). For each ticker, keeps the document with the
latest `timestamp` and deletes the rest, via an aggregation that groups by `ticker`, sorts by
`timestamp` descending, and collects all `_id`s per group:

```python
pipeline = [
    {"$sort": {"timestamp": -1}},
    {"$group": {"_id": "$ticker", "keep": {"$first": "$_id"}, "ids": {"$push": "$_id"}}},
]
for group in db[ANALYSES].aggregate(pipeline):
    stale_ids = [i for i in group["ids"] if i != group["keep"]]
    if stale_ids:
        db[ANALYSES].delete_many({"_id": {"$in": stale_ids}})
```

After cleanup, it calls `ensure_indexes(db)` so the new unique index (D6) can be created —
by that point no duplicates remain, so index creation succeeds.

**Rationale**: FR-006/FR-007 require a one-time, safely-re-runnable cleanup. This matches
the project's only existing precedent for this class of script (`scripts/backfill_financials.py`)
for consistency, and is naturally idempotent: a second run finds `ids` groups of size 1
everywhere (nothing left to delete), so it's a no-op — satisfying "safe to run more than
once without further changes" directly, no extra idempotency bookkeeping required.

**Alternatives considered**: A migration framework/tool (rejected — no `migrations/` folder
or framework exists anywhere in the repo; Constitution Principle V explicitly discourages
adding infrastructure ahead of demonstrated need for a single-user local-first project).
Running the cleanup automatically at backend/agent-runner startup (rejected — the spec frames
it as a one-time operator action, and an aggregation `$group` over the whole collection on
every service boot is unnecessary steady-state cost).

## D6. Uniqueness enforcement: new index, fail-soft creation

**Decision**: Add `db[ANALYSES].create_index([("ticker", ASCENDING)], unique=True)` to both
`ensure_indexes()` copies (`agent-runner/tools/db.py:45-62` and `backend/db.py`, which must
stay in sync per both files' existing header comments), wrapped so a `DuplicateKeyError` /
`OperationFailure` from pre-existing duplicates logs a warning and does not crash service
startup, e.g.:

```python
try:
    db[ANALYSES].create_index([("ticker", ASCENDING)], unique=True)
except OperationFailure:
    logger.warning("unique ticker index on analyses blocked by existing duplicates — run scripts/dedupe_analyses.py")
```

**Rationale**: Mongo refuses to build a unique index while duplicate keys exist, and this is
a single-operator local deployment with no staged rollout — the index-creation code and the
cleanup script ship in the same change, but there's no way to guarantee the operator runs
the script before the next container restart tries to build the index. Fail-soft matches
Constitution Principle IV's existing "fail soft — serve stale, log" posture (applied here to
index creation rather than data fetch) and keeps the service usable even if cleanup hasn't
run yet; the D1 upsert fix already prevents new duplicates from forming in the meantime, so
the unique index is a defense-in-depth guarantee, not the mechanism the correctness
guarantee actually depends on.

**Alternatives considered**: Making index creation fatal (rejected — would turn a stale
dev environment into a hard outage instead of a logged warning). Skipping the unique index
entirely and relying only on the upsert (rejected — the index is cheap, catches any future
regression where a direct `insert_one` sneaks back in, and costs nothing once cleanup has run).

## D7. Testing approach

**Decision**: Follow existing conventions exactly — `pytest` + `mongomock`, no new test
infrastructure.
- `agent-runner/tests/test_queue_worker.py`: extend the existing
  `test_successful_job_writes_analysis_and_marks_done` (line 61) coverage with a companion
  assertion that running a second job for the same ticker still leaves
  `count_documents({"ticker": "AAPL"}) == 1`, and that the stored document reflects the
  second run's data.
- `backend/tests/test_routers.py`: rewrite `test_ticker_history` (lines 56-63, currently
  asserts a 2-element list) to assert `GET /analysis/{ticker}` returns a single object
  matching the latest doc. `test_feed_pagination_and_projection` and `test_feed_filters`
  already construct one-doc-per-ticker fixtures, so they need no behavioral change, only
  continued passing.
- New `scripts/tests/test_dedupe_analyses.py` (or colocated under `backend/tests/` /
  `agent-runner/tests/`, whichever the implementer finds cleaner given the script imports
  from `agent-runner/tools/db.py`): seed a ticker with multiple docs at different
  timestamps, run the dedupe function, assert exactly one (latest) remains; run it again,
  assert no further changes (FR-007 / SC-003).

**Rationale**: No existing dedicated test file for the Feed/analysis storage exists beyond
`backend/tests/test_routers.py`; matching that file's existing `analysis_doc()` helper
(lines 7-14) and `mongomock` fixture conventions (`backend/tests/conftest.py:9-21`) is the
lowest-friction path and keeps Constitution Principle I's coverage requirement satisfied
without introducing new test tooling.
