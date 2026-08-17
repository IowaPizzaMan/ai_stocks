# Quickstart: Validating Delta-Only Data Pulls

**Feature**: `specs/024-delta-data-pulls` | **Date**: 2026-08-17

How to prove this feature works end to end. Scenarios map to the spec's user stories
and success criteria; details live in [data-model.md](./data-model.md) and
[contracts/](./contracts/).

---

## Prerequisites

```powershell
docker compose up -d mongodb backend agent-runner frontend
```

`FMP_API_KEY` and `FINNHUB_API_KEY` set in `.env`. Scenarios 3–7 spend real API budget
— check headroom first:

```powershell
docker compose exec mongodb mongosh stockai --quiet --eval `
  "db.fmp_usage.find().sort({date:-1}).limit(1).toArray()"
```

---

## One-time migration

Two operational steps, neither of which is a code change. Both are safe to re-run.

**1. Drop the news TTL index.** It deletes the document a delta baseline lives in, so
leaving it in place silently restores full-window fetching (see data-model.md).

```powershell
docker compose exec mongodb mongosh stockai --quiet --eval `
  "db.stock_news_cache.getIndexes().filter(i => i.expireAfterSeconds !== undefined)"
docker compose exec mongodb mongosh stockai --quiet --eval `
  "db.stock_news_cache.dropIndex('fetched_at_1')"
```

**2. Drop the retired price cache.** Pure cache — nothing is lost.

```powershell
docker compose exec mongodb mongosh stockai --quiet --eval "db.price_cache.drop()"
```

No backfill is needed. Existing `stock_news_cache` documents have no `coverage` block,
which reads as "no baseline" and triggers one full-window fetch that writes the
envelope (FR-021).

---

## Automated tests

Run these before any manual scenario. Constitution Principle I — a change without a
test is incomplete.

```powershell
docker compose exec agent-runner python -m pytest tests/ -q
docker compose exec backend python -m pytest tests/ -q
cd frontend; npm run test -- --run
```

Lint gate:

```powershell
ruff check backend/; ruff check agent-runner/ scripts/
```

**The test that matters most**: the shared merge case table must pass **identically** in
both services. That is what enforces cross-container consistency (Principle VI,
research D4) — divergence there is a bug, not a cosmetic difference.

```powershell
docker compose exec agent-runner python -m pytest tests/test_price_store.py -q
docker compose exec backend python -m pytest tests/test_price_store.py -q
```

---

## Scenario 1 — Stage costs are visible (US1, SC-006)

1. Open a stock page, press `Pull ▶`, wait for the queue to drain.
2. Expand the pull-cost panel.

**Expect**: stages listed most-expensive-first, each showing elapsed time, request
count, bytes, and whether it was incremental, full, or served from stored data. Pull
mode and outcome shown. Unaccounted time displayed rather than hidden.

```powershell
curl "http://localhost:8000/stocks/AAPL/pull-metrics"
```

**Fails if**: stages are unsorted, `requests`/`bytes` are all zero (attribution broken —
check the thread-local under parallel prefetch, research D7), or `total_ms` does not
reconcile with observed wall time.

---

## Scenario 2 — Chart resolutions cost nothing (US2, SC-004)

With a stock already pulled, watch the FMP counter while switching chart resolutions:

```powershell
docker compose exec mongodb mongosh stockai --quiet --eval `
  "db.fmp_usage.find({date: new Date().toISOString().slice(0,10)}).toArray()"
```

Click through daily → weekly → monthly → yearly, then re-read the counter.

**Expect**: unchanged. Every resolution resamples from the one stored daily series.

**Fails if**: the counter moves at all — a per-resolution fetch path survived.

---

## Scenario 3 — The second pull is a delta (US2, SC-001, SC-002)

1. Pull a stock. Note `stages[].bytes` for `price` and the FMP counter.
2. Pull the same stock again.

**Expect**: `retrieval: "incremental"` on the second pull, `bytes` for `price` down by
a wide margin, `price_history.coverage.extended_at` advanced while `established_at` is
**unchanged**, and total pull time lower.

```powershell
docker compose exec mongodb mongosh stockai --quiet --eval `
  "db.price_history.findOne({ticker:'AAPL'}, {bars:0})"
```

**Read the result honestly.** Delta price fetches save bytes, not API calls — a bounded
FMP request costs the same one call as an unbounded one (research D1). If SC-001's 50%
target is missed because LLM agent time dominates, that is the measurement doing its
job: restate the target against the fetch portion of the pull and record it in the spec
rather than quietly declaring success.

---

## Scenario 4 — No dataset is fetched twice in one pull (SC-003)

On any pull, inspect the metrics record.

**Expect**: exactly **one** stage reports a price retrieval; `indicators` reports
`retrieval: "stored"` with `requests: 0`. This is the duplicate full download identified
in research D0.

**Fails if**: two stages both report `requests: 1` against the price endpoint — a caller
was missed. Check all three sites in [contracts/price-store.md](./contracts/price-store.md).

---

## Scenario 5 — News pages collapse (US3)

Pull a heavily-covered mega-cap (`NVDA`, `AAPL`) twice.

**Expect**: first pull 2–5 requests on the `news` stage; second pull 1. Articles aged
past the 30-day window dropped from storage; no duplicate URLs; trend and timeline
computed over the full retained window, not just the new arrivals (FR-018).

```powershell
docker compose exec mongodb mongosh stockai --quiet --eval `
  "var d=db.stock_news_cache.findOne({ticker:'NVDA'}); [d.articles.length, new Set(d.articles.map(a=>a.url)).size, d.coverage]"
```

**Fails if**: the two counts differ — deduplication by URL is broken.

---

## Scenario 6 — Full refresh (US5, SC-010, SC-011)

1. Corrupt a stored series deliberately:

```powershell
docker compose exec mongodb mongosh stockai --quiet --eval `
  "db.price_history.updateOne({ticker:'AAPL'}, {\$set: {'bars.0.close': 99999}})"
```

2. Press `Full Refresh ⟳` on the stock page, confirm, wait for the queue to drain.

**Expect**: one action covers price, news, and event feeds — no dataset picker (SC-011).
The corrupted bar is gone. `established_at` **and** `extended_at` both advanced. The
analysis re-ran on the refreshed data (FR-026) — check `analyses.timestamp` moved.
`pull_metrics.mode` is `"full"` and every delta-maintained stage reports
`retrieval: "full"`.

```powershell
curl -X POST "http://localhost:8000/queue/AAPL?mode=full"
```

**Fails if**: `mode` echoes `delta`, or the analysis timestamp is unchanged.

---

## Scenario 7 — Full refresh degrades under a spent budget (US5, FR-027, SC-009)

Force the cap low and trigger a full refresh:

```powershell
# .env → FMP_DAILY_SOFT_CAP=1, then:
docker compose restart backend agent-runner
```

**Expect**: the pull **completes**. Stored data served with a staleness indicator,
stages marked `outcome: "degraded"`, `pull_metrics.outcome: "degraded"`, and the UI
saying the refresh could not complete. Stored data is **not** wiped.

**Fails if**: the job lands in `failed`, the cap is exceeded, or the stored series is
emptied — FR-030 means a refresh that cannot finish must leave the prior series intact.

Restore your real cap afterwards.

---

## Scenario 8 — Queue upgrade race (research D8)

```powershell
curl -X POST "http://localhost:8000/queue/AAPL"            # delta, sits pending
curl -X POST "http://localhost:8000/queue/AAPL?mode=full"  # while still pending
```

**Expect**: second response `status: "upgraded_to_full"`, `mode: "full"`. The pending
job's `mode` is now `"full"`.

**Fails if**: the response is `already_queued` — the operator would be told their
request was handled and then silently receive a delta pull. This is the specific bug
the upgrade rule exists to prevent.

---

## Scenario 9 — Interrupted full refresh preserves data (SC-013, FR-030)

Start a full refresh and kill the worker mid-flight:

```powershell
curl -X POST "http://localhost:8000/queue/AAPL?mode=full"
docker compose restart agent-runner   # while the price stage is running
```

**Expect**: `price_history` for that ticker still holds its **previous** complete
series — same `bar_count`, same `established_at`. Never an empty or truncated `bars`.
The stale job resets to `pending` on startup and re-runs
(`queue_worker.recover_stale_jobs`).

**Fails if**: `bars` is empty or shortened — the write is not building in memory before
the atomic swap.

---

## Known limitation to verify is *documented*, not fixed

A stock that splits between pulls keeps stale pre-split bars until someone presses
`Full Refresh ⟳`. Nothing detects or warns about this — the spec's deliberate accepted
risk (Assumptions; clarification Q5).

Before calling this feature done, add it to `KNOWN_ISSUES.md` under **Design
limitations (accepted for now)**, per the spec's Assumptions section. Shipping the
limitation without recording it is the actual failure mode here.
