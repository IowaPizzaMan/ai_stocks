# Contract: Portfolio digest teardown

**Story**: US3 (FR-018, FR-019)
**Research**: R14 | **Clarification**: "Remove the feature entirely"

Full removal — panel, generation job, endpoints, stored records, and the collection.
Precedent: spec 028's Pull Cost teardown.

---

## Delete outright

| Path | What it is |
|---|---|
| `agent-runner/agents/portfolio_digest.py` | The LLM agent |
| `agent-runner/tools/portfolio.py` | `run_portfolio_digest` job handler |
| `agent-runner/tests/test_portfolio_digest.py` | Its tests |
| `backend/routers/portfolio.py` | `GET /portfolio/digest`, `POST /portfolio/digest/regenerate` |
| `backend/tests/test_portfolio.py` | Its tests |
| `frontend/src/components/feed/PortfolioDigestPanel.tsx` | The panel |
| `frontend/src/components/feed/PortfolioDigestPanel.test.tsx` | Its tests |
| `frontend/src/hooks/usePortfolioDigest.ts` | Read hook |
| `frontend/src/hooks/usePortfolioDigestRegenerate.ts` | Regenerate mutation |
| `frontend/src/lib/filterHighlights.ts` | Digest-only helper (028) |
| `frontend/src/lib/filterHighlights.test.ts` | Its tests |

## Edit

| Path | Change |
|---|---|
| `agent-runner/tools/admin_jobs.py` | Drop the `"portfolio_digest"` entry from `JOB_HANDLERS` and its import |
| `agent-runner/tools/db.py` | Remove `PORTFOLIO_DIGEST_CACHE` constant |
| `agent-runner/tools/market_movers.py:17` | **Docstring only** — reword the sentence citing `run_portfolio_digest`'s pattern. No logic change. |
| `agent-runner/tests/test_admin_jobs.py` | Drop digest registration assertions |
| `agent-runner/tests/test_queue_worker.py` | Drop digest dispatch cases |
| `backend/main.py` | Remove the `portfolio` import and `app.include_router(portfolio.router)` |
| `backend/db.py` | Remove `PORTFOLIO_DIGEST_CACHE` constant |
| `frontend/src/pages/Stocks.tsx` | Remove the panel import/render and the two-column wrapper; grid goes full width (FR-018) |
| `frontend/src/pages/Stocks.test.tsx` | Drop digest assertions; add a full-width/no-panel assertion |
| `frontend/src/hooks/useQueue.ts:24-25` | Remove the `["portfolio-digest"]` invalidation |
| `frontend/src/api/types.ts` | Remove digest types (~line 648). Keep the `job_type` comment at ~460 but re-example it against a surviving admin job. |
| `specs/component-specs/frontend/pages/Stocks.md` | Update the page's component spec |

### Do not touch

- `frontend/src/api/types.ts:519` `pct_of_portfolio` — institutional holdings, unrelated.
  A grep-and-delete on "portfolio" breaks the Institutional tab (R14).
- `specs/027-*` and `specs/028-*` documents — historical records of shipped work. They
  stay accurate as history; this spec supersedes them.

---

## Runtime data

Services never drop collections (`ensure_indexes` only creates), so this is a one-time
manual step, documented in [quickstart.md](../quickstart.md):

```js
db.portfolio_digest_cache.drop()
```

**Order matters**: deploy the code that stops writing *first*, then drop. Dropping while a
worker could still run the job would recreate the collection on the next write.

Also clear any queued work: `db.work_queue.deleteMany({ job_type: "portfolio_digest" })` —
otherwise a pending job outlives the handler and `queue_worker` logs an unknown-job-type
error on every poll.

---

## Verification (FR-019, SC-009)

```bash
# No source reference survives (specs/ and this contract excluded)
grep -rn "portfolio_digest\|PortfolioDigest\|portfolio-digest\|PORTFOLIO_DIGEST" \
  backend/ agent-runner/ frontend/src/ --include=*.py --include=*.ts --include=*.tsx
# → only agent-runner/tools/market_movers.py if its docstring is left un-reworded

# Endpoints gone
curl -s -o /dev/null -w "%{http_code}" localhost:8000/portfolio/digest   # → 404

# Collection gone
mongosh stockai --eval 'db.getCollectionNames().includes("portfolio_digest_cache")'  # → false

# No orphaned jobs
mongosh stockai --eval 'db.work_queue.countDocuments({job_type: "portfolio_digest"})' # → 0
```
