# Data Model: Stocks Page News Tab and Cross-Stock AI Summary

## New MongoDB collection: `portfolio_digest_cache`

Singleton document (no key field — `find_one({})`/`replace_one({}, ..., upsert=True)`,
matching the existing `MARKET_RISK_PREMIUM` singleton pattern in
`backend/db.py`/`agent-runner/tools/db.py`). No TTL: unlike `market_news_cache` this
document is not a time-boxed refetch cache — it's replaced only when a regeneration
job runs, and the "is this fresh" question is answered by comparing its own timestamp
fields, not by expiry.

```jsonc
{
  // last successful synthesis — absent (whole doc missing) before the first
  // regeneration ever completes
  "generated_at": "2026-08-21T18:04:00Z",
  "overview": "Across 22 analyzed names, momentum skews bullish in semis while...",
  "highlights": [
    { "ticker": "NVDA", "signal": "bullish", "conviction": "high",
      "note": "Fresh institutional accumulation flag alongside a TFC continuation — the strongest setup in the set." },
    { "ticker": "CAH", "signal": "bearish", "conviction": "medium",
      "note": "Conviction dropped since the last analysis on a fundamental margin flag; worth a fresh Pull." }
  ],
  "stock_count": 22,          // stocks actually fed into this synthesis
  "total_tracked_count": 22,  // total analyzed stocks in `analyses` at generation time
  "capped": false,            // true when stock_count < total_tracked_count (R5's 25-stock cap)

  // last failed regeneration attempt — independent of the success fields above,
  // so a failure never overwrites the last good synthesis (R6)
  "last_error": "ollama: connection refused",
  "last_error_at": "2026-08-22T09:00:00Z"
}
```

**Field notes**

- `highlights[].ticker` always refers to a document currently present in `analyses`;
  entries for stocks that get removed from the market between generation and viewing
  are left as-is (the UI's existing ticker-link behavior already handles a since-removed
  ticker gracefully, same as `MarketNewsPanel`'s ticker links).
- `capped`/`total_tracked_count` exist so the UI can render FR-014's "not all tracked
  stocks were included" note without a second query.
- `last_error`/`last_error_at` are cleared to `null` implicitly only by never being
  read once a newer `generated_at` exists — the API layer (not storage) decides
  `stale` by comparing the two timestamps (R6), so a stored-but-superseded error is
  harmless.

## Extended `work_queue` usage (no schema change)

No new fields — this feature is the first real user of the `job_type`-dispatch branch
`agent-runner/queue_worker.py` already has:

```jsonc
{ "job_type": "portfolio_digest", "status": "pending", "created_at": "...", "updated_at": "..." }
```

No `ticker` field, matching how `claim_and_run_next` already branches: `job_type =
job.get("job_type"); if job_type and job_type != "ticker_analysis": return
_run_admin_job(db, job)`. Dedup rule mirrors `queue.py`'s `_enqueue`: the enqueue
endpoint refuses to insert a second `portfolio_digest` job while one is already
`pending`/`running`.

## Backend collection constant

`backend/db.py` and `agent-runner/tools/db.py` (kept in sync per Constitution VI):

```python
PORTFOLIO_DIGEST_CACHE = "portfolio_digest_cache"
```

## Frontend type additions (`frontend/src/api/types.ts`)

```ts
export interface PortfolioDigestHighlight {
  ticker: string;
  signal: Signal;
  conviction: Conviction;
  note: string;
}

export interface PortfolioDigestResponse {
  as_of: string | null;       // generated_at, ISO — null before the first successful run
  overview: string | null;
  highlights: PortfolioDigestHighlight[];
  stock_count: number;
  total_tracked_count: number;
  capped: boolean;
  stale: boolean;             // true when a later failure exists than the last success
}
```

`QueueJob.ticker` changes from required to optional, since an admin job (this feature's
`portfolio_digest` job, and any future one) carries no ticker:

```ts
export interface QueueJob {
  ticker?: string;
  job_type?: string;          // absent = ordinary per-ticker analysis job
  status: string;
  source?: string;
  created_at: string;
  mode?: PullMode;
}
```

## No changes to the `Analysis` document shape

The digest reads existing `analyses` documents as-is (`ticker`, `signal`, `conviction`,
`summary`, `key_trends`, `flags`, and `sub_reports.news.stance` for the news-stance
line) — nothing about the per-ticker analysis pipeline (`crew.py`, sub-report shapes)
changes.
