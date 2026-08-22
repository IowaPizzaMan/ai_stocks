# Quickstart Validation: Stocks Page News Tab and Cross-Stock AI Summary (027)

Checks that prove the feature works end to end. Contract:
[portfolio-digest-api.md](./contracts/portfolio-digest-api.md); shapes:
[data-model.md](./data-model.md); layout/queue-reuse rationale: [research.md](./research.md).

## Prerequisites

- Docker Compose stack up: `docker compose up -d`
- At least ~10 analyzed tickers (a mix of signals/convictions) so the grid overflows
  one screen and the digest has real material to synthesize
- Ollama reachable (`OLLAMA_URL`) — the digest regeneration is an LLM call like every
  other agent in this app

## Automated gates (must pass first)

```powershell
# Backend: digest endpoint states, regenerate dedup
cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_portfolio.py -q

# Full backend suite
cd backend; .\.venv\Scripts\python.exe -m pytest tests -q

# Agent-runner: handler, cap/priority logic, admin-job dispatch
cd agent-runner; .\.venv\Scripts\python.exe -m pytest tests/test_portfolio_digest.py tests/test_admin_jobs.py tests/test_queue_worker.py -q

# Full agent-runner suite
cd agent-runner; .\.venv\Scripts\python.exe -m pytest tests -q

# Frontend: tabs, bounded layout markup, digest panel states, grid load-more
cd frontend; npx vitest run

# Lint (constitution gate)
ruff check backend/
ruff check agent-runner/ scripts/
```

## Scenario 1 — News moves to its own tab (US1)

1. Open `http://localhost:5173/` (Stocks page).
2. **Expect**: the default view shows the filter bar and stock grid; no market news
   list appears anywhere on it.
3. Click the **News** tab.
4. **Expect**: the same market-wide headline list that used to sit below the grid —
   up to 20 articles, newest first, ticker links, external article links, no further
   loading on scroll (spec 022 behavior unchanged).
5. Copy the URL while on the News tab, open it in a new tab. **Expect**: it loads
   directly onto the News tab (bookmarkable, like the detail page's tabs).
6. Navigate to an unrecognized tab anchor (e.g. edit the URL to an unknown hash).
   **Expect**: falls back to the default grid tab.

## Scenario 2 — No auto-scroll fetching, no page scroll (US2)

1. With enough tracked stocks to overflow one screen, open the Stocks page's default
   tab.
2. **Expect**: the browser window itself does not need scrolling to see the filter bar
   and tab bar — they stay in view.
3. Scroll inside the grid area. **Expect**: only the grid's own content moves; no
   network request fires from scrolling alone (watch the browser network tab).
4. **Expect**: a "Load more" control is visible once more analyses exist beyond the
   first page. Click it. **Expect**: additional tiles append inside the same bounded
   area, and exactly one `GET /analysis/feed?page=2...` request fires.

## Scenario 3 — Cross-stock AI summary, first-time empty state (US3)

1. Fresh install / before any regeneration has ever run:
   `curl http://localhost:8000/portfolio/digest` → `{"as_of": null, "overview": null,
   "highlights": [], "stock_count": 0, "total_tracked_count": 0, "capped": false,
   "stale": false}`.
2. Open the Stocks page. **Expect**: the summary panel shows a clear empty/prompt
   state, not an error.

## Scenario 4 — Regeneration produces guidance (US3)

1. Click the summary panel's regenerate control.
2. **Expect**: the panel shows a busy/in-progress state immediately.
3. Confirm the job landed: `curl http://localhost:8000/queue` → a `pending` or
   `running` entry with no `ticker` field.
4. Wait for it to complete (poll `GET /queue` or just wait — the frontend's existing
   `useQueueStatus` polling handles this automatically).
5. **Expect**: the panel updates with fresh `overview` text and a `highlights` list
   that names specific tracked tickers (not generic boilerplate) and a new "as of"
   timestamp — verify against `curl http://localhost:8000/portfolio/digest`.
6. Click regenerate again immediately. **Expect**: `POST
   /portfolio/digest/regenerate` returns `already_queued` if the first job is still
   running, and the button reflects the busy state rather than queuing a second job.

## Scenario 5 — Failure keeps the last summary, marked stale (US3)

1. With a successful digest already stored, stop Ollama:
   `docker compose stop ollama`.
2. Trigger a regeneration. **Expect**: the `work_queue` job ends `"failed"`
   (`curl http://localhost:8000/queue` shows it leave `pending`/`running`; check
   agent-runner logs for the failure).
3. `curl http://localhost:8000/portfolio/digest` → **same `overview`/`highlights`/
   `as_of` as before the failed attempt**, but `"stale": true`.
4. Reload the Stocks page. **Expect**: the previous summary is still visible, marked
   stale — never a blank or broken panel (FR-012).
5. Restart Ollama (`docker compose start ollama`) and regenerate again. **Expect**:
   `stale` returns to `false` once the new attempt succeeds.

## Scenario 6 — Filter independence (FR-007a)

1. Apply a sector or signal filter that narrows the grid substantially.
2. **Expect**: the summary panel is unchanged — same overview, same highlights, no
   network request fired by the filter change.

## Scenario 7 — Cap and priority when tracked stocks are numerous (FR-014, R5)

Requires 26+ analyzed tickers spanning multiple conviction levels.

1. Regenerate the digest.
2. `curl http://localhost:8000/portfolio/digest` → `"stock_count": 25`,
   `"total_tracked_count"` equal to the actual analyzed count, `"capped": true`.
3. **Expect**: the UI surfaces "not all tracked stocks were included" (or equivalent)
   when `capped` is `true`.
4. Spot-check (agent-runner test, not manual): the 25 stocks actually sent to the LLM
   are the highest-conviction ones (high before medium before low), not an arbitrary
   or alphabetical subset.

## Scenario 8 — Market news content itself is unchanged (no regression)

1. On the News tab, confirm behavior identical to pre-migration spec 022: exactly ≤20
   articles, no infinite scroll, ~60-minute reuse window
   (`curl http://localhost:8000/market/news` twice in a row → same `as_of`).
