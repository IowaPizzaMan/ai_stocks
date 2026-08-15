# Contract: analysis write path (`agent-runner/queue_worker.py::claim_and_run_next`)

This is an internal interface contract, not an HTTP endpoint — `claim_and_run_next` has no
external caller-facing surface beyond "a completed job's `analyses` document." Documented
because it's the root-cause fix this feature depends on (`research.md` D1).

## Before (current behavior)

`agent-runner/queue_worker.py:72`:

```python
db[ANALYSES].insert_one(result)
```

Every completed job creates a new document — a ticker analyzed N times has N documents.

## After (this feature)

```python
write_db(ANALYSES, result, upsert_key="ticker", db=db)
```

using the existing helper at `agent-runner/tools/db.py:83-88`:

```python
def write_db(collection: str, data: dict, upsert_key: str | None = None, db=None) -> None:
    db = db if db is not None else get_db()
    if upsert_key:
        db[collection].replace_one({upsert_key: data[upsert_key]}, data, upsert=True)
    else:
        db[collection].insert_one(data)
```

i.e. `db[ANALYSES].replace_one({"ticker": result["ticker"]}, result, upsert=True)`. A
completed job for a ticker that already has a stored analysis **replaces** the existing
document wholesale (matching FR-004/FR-008); a ticker with no prior analysis gets one
created (matching Acceptance Scenario 1 of User Story 2).

**Atomicity** (FR-004): `replace_one` is a single atomic MongoDB operation on the matched
document — it either fully replaces the previous analysis or, on failure, leaves it entirely
untouched. There is no intermediate state where the ticker has a partial or missing record,
satisfying FR-004's failed-write requirement with no additional error handling needed.

**Concurrency note** (Edge Cases, spec.md): if two jobs for the same ticker finish close
together, `replace_one` is atomic per-call but the two calls are not coordinated — whichever
call's `replace_one` executes last wins, leaving exactly one document reflecting that job's
result. This matches the spec's explicit "last write wins, no locking required" scoping
(Assumptions section) — no additional coordination is added.

## Consumers to update (tracked for /speckit-tasks, not this plan)

- `agent-runner/queue_worker.py:15` — import `write_db` alongside the existing `ANALYSES` import.
- `agent-runner/tests/test_queue_worker.py:61` (`test_successful_job_writes_analysis_and_marks_done`) —
  add a companion assertion/test that a second run for the same ticker leaves
  `count_documents({"ticker": "AAPL"}) == 1` and the stored doc reflects the second run's data.
