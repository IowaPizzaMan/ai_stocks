# Contract: `scripts/dedupe_analyses.py` (new)

CLI script — this feature's interface for FR-006/FR-007 (one-time cleanup of pre-existing
duplicate analysis records). Modeled on the existing `scripts/backfill_financials.py`
precedent (`research.md` D5).

## Invocation

```text
python scripts/dedupe_analyses.py
```

Run manually, outside Docker, from the repo root — same convention as
`scripts/backfill_financials.py`. No arguments; it operates on the whole `analyses`
collection (there is no per-ticker scoping need — the whole collection either has
duplicates or it doesn't).

## Behavior

```python
def dedupe(db) -> int:
    """Collapses each ticker's analysis docs to just the most recent.
    Returns the number of documents removed. Safe to re-run (FR-007)."""
```

1. Aggregates `analyses` grouped by `ticker`, sorted by `timestamp` descending, collecting
   the `_id` to keep (`$first`) and all `_id`s in the group. A missing/malformed `timestamp`
   sorts as older than any valid timestamp for free: BSON's type-ordering ranks `null` and
   most non-Date types below `Date`, so in a `{timestamp: -1}` sort a valid date always
   precedes a null/malformed one — no special-casing needed beyond using `$sort` rather than
   assuming every doc has a valid timestamp — see spec.md FR-006.
2. For each group with more than one `_id`, deletes every `_id` except the one to keep. If
   two records tie on `timestamp`, whichever one the aggregation's `$first` happens to pick
   is kept — no deterministic tie-break is required (spec.md FR-007 / Edge Cases).
3. Calls `ensure_indexes(db)` afterward so the new unique index on `ticker` (see
   `data-model.md` Index changes, `research.md` D6) can be created now that no duplicates
   remain.
4. Prints a summary: tickers processed, documents removed, final `ensure_indexes` result.

Because each ticker's group is resolved independently, an interrupted run (process killed
partway through) simply leaves some tickers already deduplicated and others not yet —
re-running finds nothing left to do for the former and finishes the latter, satisfying
FR-007's "safe after an interrupted run" requirement with no extra bookkeeping.

## Idempotency (FR-007)

A second run finds every group already reduced to size 1 — nothing to delete, `dedupe()`
returns `0`, `ensure_indexes(db)` is a no-op on an index that already exists. No separate
"already ran" flag or bookkeeping collection is needed; idempotency falls out of the
aggregation itself operating on current state, not a stored history of prior runs.

## Consumers to update (tracked for /speckit-tasks, not this plan)

- New `scripts/dedupe_analyses.py`.
- New test (colocated with `agent-runner/tests/` since the script imports `agent-runner/tools/db.py`,
  matching where `ANALYSES`/`ensure_indexes` already live) covering: multi-doc ticker → 1 doc
  (latest kept, by `timestamp`), single-doc ticker unchanged, re-run is a no-op
  (`research.md` D7, SC-003).
