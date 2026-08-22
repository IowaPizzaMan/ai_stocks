# Quickstart: Dashboard Tweaks Batch

**Feature**: 028-dashboard-tweaks-batch | **Phase**: 1

How to verify each story end-to-end. Details live in [data-model.md](./data-model.md) and
[contracts/](./contracts/); this file is the run guide.

## Prerequisites

- Docker Compose stack up (`mongodb`, `backend`, `frontend`, `agent-runner`, `ollama`)
- `FMP_API_KEY` set in `.env` — required for US4/US5/US6 only
- At least one analyzed ticker (pull one from the Stocks page) for US1/US2/US3

```bash
docker compose up -d
docker compose ps          # all five healthy
```

## Gates (must pass before the change is done)

The running containers don't bind-mount source (see docker-compose.yml), so they only
reflect whatever was last built. For iterating without a full rebuild each time, run
against live source via a one-off `docker compose run` override (Windows/Git Bash needs
`MSYS_NO_PATHCONV=1` so the volume path isn't mangled):

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(pwd)/backend:/app" backend \
  sh -c "ruff check . && python -m pytest -q"

MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(pwd):/repo" -w /repo/agent-runner agent-runner \
  sh -c "cd /repo && ruff check agent-runner/ scripts/; cd agent-runner && python -m pytest -q"

MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(pwd)/frontend/src:/app/src" frontend \
  sh -c "npx vitest run && npx tsc --noEmit"
```

(`agent-runner`'s tests import `scripts/dedupe_analyses.py` from the repo root, hence the
full-repo mount rather than just `agent-runner/`.) Once everything passes, rebuild and
restart the real containers so manual testing below reflects the current code:

```bash
docker compose build backend agent-runner frontend
docker compose up -d
```

---

## US1 — Portfolio Summary ticker links (FR-001)

The original bug: links pointed at `/stocks/<T>` while the route is `/stock/<T>`, and no
catch-all existed, so the page rendered structurally empty.

1. Open `http://localhost:5173/`, default (Stocks) tab.
2. If the Portfolio Summary panel is empty, click **Regenerate** and wait for the queue
   chip to clear.
3. Click any ticker in the highlights list.

**Expected**: URL becomes `/stock/<TICKER>` and the detail page renders its header,
price panel, and tabs. **Not** a blank page.

4. Manually visit `http://localhost:5173/definitely-not-a-route`.

**Expected**: a "page not found" message — not an empty page.

---

## US2 — Filter narrows the highlights (FR-002 … FR-004b)

1. On the Stocks page with a populated summary, note which tickers appear in the
   highlights.
2. Click the **bearish** filter chip.

**Expected**: the highlights list narrows to bearish entries only. The overview paragraph
is **unchanged**, and a label appears indicating it describes all tracked stocks.

3. Open the browser Network tab, then toggle another filter chip.

**Expected**: **no** request to `/portfolio/digest` and no queue job — filtering is
entirely client-side (clarification Q1).

4. Type a ticker into the filter box that matches no highlight.

**Expected**: "No highlighted stocks match the current filter", with the overview still
displayed.

5. Clear all filters.

**Expected**: all highlights return; the scope label disappears.

---

## US3 — Like / dislike (FR-005 … FR-010)

1. Open a **tracked** stock's page.

**Expected**: thumbs-up and thumbs-down controls next to the ticker.

2. Click thumbs-up. **Expected**: it shows active.
3. Click thumbs-up again. **Expected**: it clears.
4. Click thumbs-up, then thumbs-down. **Expected**: disliked active, liked inactive —
   never both.
5. Return to the Stocks page and select the **liked** filter chip.

**Expected**: only liked stocks appear. Verify the empty case too — clear all tags and
filter by `liked`, which must show an empty feed, **not** every stock.

6. Open an **untracked** ticker (e.g. from the Congress or Top Traded list, or
   `/stock/ZZZZ`).

**Expected**: **no** thumbs controls at all — not disabled ones (FR-006a).

```bash
# API-level check
curl -X PUT localhost:8000/stocks/AAPL/sentiment -H 'Content-Type: application/json' \
     -d '{"sentiment":"liked"}'
curl -X PUT localhost:8000/stocks/ZZZZ/sentiment -H 'Content-Type: application/json' \
     -d '{"sentiment":"liked"}'      # expect 404 — not tracked
```

7. Restart the stack and reopen the stock. **Expected**: the tag persisted (FR-010).

---

## US4 — Congress disclosures (FR-011 … FR-018)

**Fixture status**: `agent-runner/tests/fixtures/senate_latest.json` / `house_latest.json`
are already pinned from the confirmed field set (research.md R7) — the camelCase keys
(`symbol`, `senateId`, `disclosureDate`, `transactionDate`, `firstName`, `lastName`,
`office`, `district`, `owner`, `assetDescription`, `assetType`, `type`, `amount`, `link`)
are a best guess pending a live call; if you have `FMP_API_KEY` set, worth a spot-check:

```bash
curl -s "https://financialmodelingprep.com/stable/senate-latest?apikey=$FMP_API_KEY" \
  | python -m json.tool | head -40
```

Confirm those keys match, and that `type` values are `"Purchase"`/`"Sale"` (capitalised)
with amounts like `"$1,001 - $15,000"`. If the live keys differ, the normalizer
(`agent-runner/tools/congress.py::_normalize_row`) reads from candidate key sets per field,
so a mismatch degrades to a warning-and-skip per row rather than a crash — but the fixture
and tests should still be updated to match reality. Note `senateId` repeats across a
member's rows — it identifies the *person* (used as `person_id`), not the trade.

1. Click **Congress** in the nav bar. **Expected**: the page loads; before any pull it
   shows an empty state naming the Refresh control.
2. Click **Refresh**, wait for the queue chip to clear, reload.

**Expected**: Senate and House disclosures listed, newest `disclosure_date` first.

3. Filter by ticker; then by politician (try both a name substring, e.g. "Boozman", and a
   bioguide-id-shaped value, e.g. "B001236" — the latter matches `person_id` exactly);
   then both filters together.

**Expected**: each narrows correctly; combined filters intersect.

4. Click a ticker. **Expected**: navigates to `/stock/<TICKER>`.
5. Find a row with no ticker (non-equity disclosure). **Expected**: shown as `—` with no
   clickable link (FR-018).
6. Check the summary section.

**Expected**: most-bought tickers ranked by buy count over 90 days; high-dollar trades
listed with their **bracket text** (e.g. `$250,001 - $500,000`) — never a single computed
number (FR-016a). If nothing qualifies, an explicit "none in this window" message rather
than a hidden section (FR-016b).

```bash
curl -s "localhost:8000/congress/summary" | python -m json.tool
```

7. Click Refresh twice quickly. **Expected**: second call returns
`{"status":"already_queued"}` — no duplicate job.

---

## US5 — Sector ETF chart (FR-019 … FR-021)

1. Open **Sectors**. Before any pull, the chart area shows an empty state naming Refresh.
2. Click **Refresh**, wait for the queue to drain (11 tickers, ~11 FMP calls), reload.

**Expected**: one line per ETF for all 11 tickers, each starting at **0%** on the left
edge, with a legend pairing color to ticker and sector name.

3. Switch the window between 1M / 3M / 6M / 1Y.

**Expected**: the chart redraws and every line re-rebases to 0% at the new window's start.
The URL carries `?window=`; reloading preserves the selection.

4. Sanity-check the comparison actually works: the strongest and weakest sectors should be
   visually separated, not stacked as parallel bands — that separation is the whole point
   of plotting percent rather than dollar price.

5. Confirm partial data degrades correctly:

```bash
curl -s "localhost:8000/sectors/etf-series?window=1y" \
  | python -c "import json,sys; d=json.load(sys.stdin); print([(s['ticker'], len(s['bars']), s['partial']) for s in d['series']])"
```

**Expected**: 11 entries always present. Any with zero bars are named in the chart's
note beneath, and the other lines still render (FR-021).

6. `curl "localhost:8000/sectors/etf-series?window=bogus"` → **422**.

---

## US6 — Top Traded Stocks (FR-022 … FR-024)

1. On the Stocks page (grid tab), scroll below the ticker tiles.

**Expected**: a "Top Traded Stocks" section — below the grid, within the grid column, not
beside the digest panel.

2. Click **Refresh**, wait, reload. **Expected**: most-active stocks listed with the
served session date, showing ticker, company, price, change, and change % — **no volume
column**, since the endpoint supplies none (R9).
3. Confirm ordering matches the provider's, not Mongo's:

```bash
curl -s "localhost:8000/market/most-actives?limit=5" \
  | python -c "import json,sys; print([(i['ticker'], i['rank']) for i in json.load(sys.stdin)['items']])"
# expect ranks 0,1,2,3,4 in order
```

4. Check a percentage renders correctly: a `change_pct` of `3.35196` must display as
`+3.35%`, not `+335.20%`.
5. Click a ticker. **Expected**: navigates to `/stock/<TICKER>`.
6. Simulate unavailability (stop the backend, or clear `market_movers`).

**Expected**: the unavailable message (FR-024) — never a blank or bare-heading section.

---

## US7 — Pull-cost removal (FR-025 … FR-026b)

1. Open any stock's detail page. **Expected**: no "Pull cost" section anywhere.

2. Confirm no references remain:

```bash
grep -ri "pull_metrics\|PullCost\|usePullMetrics" backend/ agent-runner/ frontend/src/
# expect: no output
```

3. Endpoint is gone:

```bash
curl -i localhost:8000/stocks/AAPL/pull-metrics    # expect 404
```

4. **The regression that matters most** — pull a ticker and confirm the analysis still
completes normally (FR-026b):

```bash
curl -X POST localhost:8000/queue/AAPL
# wait for the queue chip to clear, then confirm the analysis updated
```

5. Confirm nothing is written and the collection is gone:

```bash
docker compose exec mongodb mongosh --quiet --eval \
  'db.getSiblingDB("stockai").getCollectionNames().filter(c => c === "pull_metrics")'
# expect: []
```

**Drop order matters**: remove the index declarations from `agent-runner/tools/db.py` and
restart the worker *before* dropping, or the next `ensure_indexes` run recreates it.

---

## Budget check (Principle IV)

A full refresh of everything this batch adds costs **14 FMP calls**: 11 sector ETF deltas
+ 2 Congress chambers + 1 most-actives. All are user-triggered, none scheduled.

No `/market/fmp-usage` read endpoint exists — check the collection directly:

```bash
docker compose exec mongodb mongosh --quiet --eval \
  'db.getSiblingDB("stockai").fmp_usage.find().sort({_id:-1}).limit(1).toArray()'
```

Confirm the day's count rose by ~14 after refreshing all three, and that no refresh path
fires on page load — only on an explicit click.
