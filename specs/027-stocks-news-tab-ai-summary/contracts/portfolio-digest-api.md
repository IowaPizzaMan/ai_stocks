# Contract: `GET /portfolio/digest` + `POST /portfolio/digest/regenerate`

New `backend/routers/portfolio.py` router. Serves/regenerates the cross-stock AI
summary panel on the Stocks page's default tab. Field shapes: [data-model.md](../data-model.md).
Job dispatch: [research.md R4](../research.md#r4--regeneration-runs-through-the-existing-currently-unused-admin-job-path).

## `GET /portfolio/digest`

No parameters — filter-independent by requirement (FR-007a), always reads every
tracked stock's stored analysis.

### Response `200`

```json
{
  "as_of": "2026-08-21T18:04:00Z",
  "overview": "Across 22 analyzed names, momentum skews bullish in semis while...",
  "highlights": [
    { "ticker": "NVDA", "signal": "bullish", "conviction": "high",
      "note": "Fresh institutional accumulation flag alongside a TFC continuation." }
  ],
  "stock_count": 22,
  "total_tracked_count": 22,
  "capped": false,
  "stale": false
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `as_of` | string \| null | `generated_at` of the last successful synthesis. `null` before the very first regeneration ever completes (FR-011 empty state). |
| `overview` | string \| null | Synthesized narrative. `null` iff `as_of` is `null`. |
| `highlights` | array | Stock-specific guidance items. Empty array is valid (e.g. every tracked stock reads neutral with nothing notable). |
| `stock_count` | integer | Stocks actually fed into the last successful synthesis. |
| `total_tracked_count` | integer | Total stocks with a stored analysis as of that synthesis. |
| `capped` | boolean | `true` when `stock_count < total_tracked_count` (the 25-stock cap, R5, was hit). |
| `stale` | boolean | `true` when a regeneration attempt failed more recently than the last success (FR-012). |

Always `200` — same reasoning as `GET /market/news`: this backs a panel on the app's
home page, where a hard error would be worse than an honest empty/stale state.

### Behavior

- Reads the singleton `portfolio_digest_cache` document. No document yet ⇒ all
  success fields `null`/empty/`0`, `stale: false` (nothing has failed either — FR-011's
  empty state, not an error state).
- `stale` is computed by the endpoint (`last_error_at` present and newer than
  `generated_at`), not stored pre-computed — keeps the write side (the job handler)
  simple and the read side as the single source of truth for "what does the user see."
- Never triggers a regeneration itself (unlike `/market/news`'s fetch-if-stale) — this
  endpoint is a pure read; only `POST /regenerate` enqueues work (FR-008: rerunning is
  an explicit action, never on page load).

## `POST /portfolio/digest/regenerate`

No body.

### Response `200`

```json
{ "status": "enqueued", "job_id": "66c1..." }
```

or, when one is already in flight:

```json
{ "status": "already_queued", "job_id": "66c1..." }
```

### Behavior

- Inserts `{"job_type": "portfolio_digest", "status": "pending", "created_at": ...,
  "updated_at": ...}` into `work_queue` — no `ticker` field.
- Dedup: if a `portfolio_digest` job is already `pending` or `running`, returns
  `already_queued` with that job's id instead of inserting a second one (mirrors
  `queue.py`'s per-ticker `_enqueue` dedup).
- Does **not** touch any per-ticker `analyses` document or trigger a per-ticker Pull
  (FR-009) — it only queues the synthesis step.

### Status codes

| Code | When |
|------|------|
| `200` | Always — enqueue always succeeds or finds an existing job; there is no user input to reject. |

## Agent-runner side: `job_type: "portfolio_digest"` handler

Registered in `agent-runner/tools/admin_jobs.py`'s `JOB_HANDLERS`, dispatched by the
existing (previously unexercised) `claim_and_run_next` → `_run_admin_job` branch in
`queue_worker.py`. Handler signature matches the existing convention: `(db) ->
int` (record count, here `stock_count`, for consistency with other admin jobs — this
job type is deliberately **not** added to `JOB_DATASETS`, since freshness for this
feature is read from `portfolio_digest_cache` directly, not `dataset_meta`, per R6).

On success: upserts `portfolio_digest_cache` with `generated_at`, `overview`,
`highlights`, `stock_count`, `total_tracked_count`, `capped` — leaves
`last_error`/`last_error_at` untouched (still readable for `stale`, but now older than
the new `generated_at`, so the endpoint reports `stale: false`).

On failure (LLM error, DB error): sets `last_error`/`last_error_at` on
`portfolio_digest_cache` (leaving prior success fields untouched), then re-raises so
`queue_worker`'s existing exception handling marks the `work_queue` job `"failed"` —
the two effects are independent (R6): the queue job's terminal state is for
operational visibility, the cache document's error fields are what the API actually
reads.

When zero stocks have a stored analysis: writes `generated_at`/`stock_count: 0`/
`total_tracked_count: 0`/`overview: null`/`highlights: []` rather than failing —
FR-011's empty state is a valid successful outcome, not an error (a portfolio digest
job over zero portfolios has nothing to say, but nothing went wrong either).

## Tests

`backend/tests/test_portfolio.py`:
- No document yet → `as_of: null`, `overview: null`, `stale: false`.
- Document with only success fields → `stale: false`.
- Document with `last_error_at` newer than `generated_at` → `stale: true`.
- Document with `last_error_at` older than `generated_at` (a since-fixed failure) →
  `stale: false`.
- `POST /regenerate` inserts a `job_type="portfolio_digest"` doc with no `ticker`.
- `POST /regenerate` while one is pending/running → `already_queued`, no second insert.

`agent-runner/tests/test_admin_jobs.py` (new) / `test_portfolio_digest.py` (new):
- Zero `analyses` documents → success outcome, `stock_count: 0`, no LLM call.
- More than 25 `analyses` documents → exactly 25 fed to the agent, sorted
  conviction-first, `capped: true`.
- ≤ 25 documents → `capped: false`, all included.
- LLM failure → `last_error`/`last_error_at` written, exception re-raised (so
  `queue_worker` marks the job failed), prior `generated_at`/`overview` untouched.

`agent-runner/tests/test_queue_worker.py` (extend):
- A `work_queue` document with `job_type="portfolio_digest"` and no `ticker` is claimed
  and dispatched to the registered handler (first real exercise of the
  `_run_admin_job` branch for a job type other than `economics_pull`).
