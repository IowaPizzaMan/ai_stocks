# Contract: Admin Jobs API & work_queue Job Shape

**Feature**: `017-fmp-migration-admin` · Phase 1 output
**Consumers**: `frontend` (via `lib/api.ts` → `useAdminJobs.ts`) · `backend/routers/admin.py` · `agent-runner/queue_worker.py`

This file pins the cross-layer vocabulary (constitution VI). Both services duplicate these values as constants; a mismatch with this file is a bug.

## Job registry (shared constants)

| `job_type` / name | Description (plain language, shown in UI) | Dataset fed (`dataset_meta.dataset`) | `stale_minutes` |
|---|---|---|---|
| `breadth_refresh` | Refresh index-universe closes and recompute NYMO/NAMO breadth signals | `breadth` | 30 |
| `earnings_calendar_scan` | Scan the upcoming earnings calendar and rank candidates | `earnings_calendar` | 30 |
| `fmp_entitlement_probe` | Test which FMP endpoint families this API key can access | `fmp_entitlements` | 10 |
| `sector_performance_pull` | Pull today's sector performance snapshot | `sector_performance` | 10 |
| `market_movers_pull` | Pull today's biggest gainers, losers, and most-active stocks | `market_movers` | 10 |
| `economics_pull` | Pull economics data: releases calendar, treasury yield curve, indicators, market risk premium | `economics` | 15 |
| `congress_trades_pull` | Pull latest senate & house trading disclosures | `congress_trades` | 15 |
| `insider_feed_pull` | Pull the latest market-wide insider trades across all tickers | `insider_feed` | 15 |
| `fund_holdings_pull` | Pull ETF & mutual-fund holdings (replaces the retired Dataroma scraper) | `fund_holdings` | 30 |
| `market_news_pull` | Pull general market news, FMP editorial articles, and stock-specific news (three feeds) into a queryable archive | `news_articles` | 20 |

All rows are user-adopted (gap review finalized 2026-08-15). `superinvestor_pull` does NOT exist — the Dataroma scraper is retired (research D11). The registry constant in code is the runtime truth of "available jobs" and `GET /admin/jobs` serves exactly that list. `economics_pull` writes four collections (see [data-model](../data-model.md)) but reports as one job/dataset for freshness purposes.

`market_news_pull` was implemented by `specs/035-chat-and-news-upgrade` (2026-08-25), which diverged from this row as originally reserved: scope grew from one feed to three (general/FMP-article/stock, `news_articles` not `market_news`), it now backfills 30 days rather than only capturing forward, and `stale_minutes` moved from 10 to 20 to match the added I/O of three sequential paged feeds per run (closer to `congress_trades_pull`'s order of magnitude than a single-call job). See `specs/035-chat-and-news-upgrade/contracts/news-api.md` for the current contract.

`ticker_analysis` (or absent `job_type`) is reserved for the existing per-ticker flow and never appears in the admin registry.

## REST endpoints (backend)

### `GET /admin/jobs`

Returns every registered admin job merged with its latest run and dataset freshness.

```jsonc
{
  "jobs": [
    {
      "name": "fund_holdings_pull",
      "description": "Pull ETF & mutual-fund holdings (replaces the retired Dataroma scraper)",
      "dataset": "fund_holdings",
      "current_run": {              // null when no pending/running job
        "job_id": "66c0…",
        "status": "running",        // "pending" | "running"
        "started_at": "2026-08-15T14:02:11Z"
      },
      "last_run": {                 // null when never run
        "job_id": "66bf…",
        "status": "done",           // "done" | "failed"
        "completed_at": "2026-08-14T21:00:41Z",
        "error": null               // human-readable reason when failed (FR-012)
      },
      "freshness": {                // from dataset_meta; null when job feeds no dataset
        "last_success_at": "2026-08-14T21:00:41Z",
        "record_count": 118
      }
    }
  ]
}
```

### `POST /admin/jobs/{name}/run`

Enqueues the job on `work_queue` with `{job_type: name, source: "admin"}`.

- **200** `{ "name": "...", "job_id": "...", "status": "enqueued" }`
- **200** `{ "name": "...", "job_id": "<existing>", "status": "already_queued" }` — duplicate active run refused, existing id returned (FR-011; mirrors `/queue` ticker behavior)
- **404** `{ "detail": "unknown job" }` — name not in registry

### `GET /admin/jobs/{name}/runs?limit=20`

Recent run history, newest first, straight from `work_queue` filtered on `job_type`.

```jsonc
{ "runs": [ { "job_id": "...", "status": "done", "created_at": "...", "started_at": "...",
              "completed_at": "...", "error": null, "source": "admin" } ] }
```

## work_queue document shape (admin jobs)

```jsonc
{
  "job_type": "fund_holdings_pull",   // registry name; NO ticker field
  "status": "pending",                // pending | running | done | failed
  "source": "admin",
  "created_at": "…", "updated_at": "…",
  "started_at": "…",                  // set on claim
  "completed_at": "…",                // set on done/failed
  "error": "FMP request timed out after 30s"     // failed only — human-readable (FR-012)
}
```

Worker dispatch: `claim_and_run_next` claims oldest `pending` regardless of type, then routes: no/`ticker_analysis` `job_type` → existing crew path (unchanged); registry `job_type` → handler function; unknown `job_type` → mark `failed` with error `"no handler for job_type"` (forward-compat guard). Stale-recovery uses the registry's per-job `stale_minutes` (default 30).

## Frontend behavior contract

- Admin page fetches `GET /admin/jobs` on navigation and on a manual refresh button only — `refetchInterval: false`, no background polling (constitution).
- Trigger button disabled while `current_run` is non-null, with the reason shown ("already running/queued").
- A `failed` last run surfaces `error` verbatim next to a retry affordance.
- Reaching any admin action ≤3 clicks from app load (SC-004): nav link → page → button.
