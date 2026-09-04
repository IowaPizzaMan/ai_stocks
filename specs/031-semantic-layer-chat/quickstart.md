# Quickstart: Validating the Semantic Layer Chat Assistant

**Feature**: `031-semantic-layer-chat` | **Date**: 2026-08-23

How to prove this feature works end to end. Details live in
[contracts/](./contracts/) and [data-model.md](./data-model.md); this is the run guide.

---

## Prerequisites

| Requirement | Verify with | Expected |
|---|---|---|
| MongoDB up with `stockai` | `docker compose ps mongodb` | running |
| Ollama up with `qwen3:14b` | `curl -s localhost:11434/api/tags` | lists `qwen3:14b` (9.3 GB) |
| Price + financials populated | see step 1 | 556 / 65 docs |
| Backend deps include `ollama>=0.4` | `grep ollama backend/requirements.txt` | present (**new** — R10) |

`qwen3:14b` is the only installed model and the sole target; there is no cloud fallback.

---

## 1. Confirm source data exists

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval '
  ["price_history","financials_cache","company_info","ticker_index","screener"]
    .forEach(c => print(c.padEnd(20), db[c].countDocuments()))'
```

Expected before first run: `price_history 556`, `financials_cache 65`, `company_info 65`,
`ticker_index 65`, `screener 0`.

---

## 2. Build the screener collection

```bash
docker compose exec -T agent-runner python -c "
from tools.screener import refresh_all
from tools.db import get_db
print(refresh_all(get_db()))"
```

The `screener_refresh` job type is also registered in `agent-runner/tools/admin_jobs.py`'s
`JOB_HANDLERS` and can be triggered by inserting a `work_queue` document with
`{"job_type": "screener_refresh", "status": "pending"}` — this app enqueues admin jobs directly
into `work_queue` rather than through a generic HTTP trigger endpoint (see `backend/routers/market.py`
for the pattern other admin jobs use to enqueue from a specific route).

**Expect**: ~556 documents written in under a minute. Then sanity-check that signals are
populated and plausible:

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval '
  printjson(db.screener.findOne({ticker:"AAPL"},
    {_id:0,ticker:1,range_pct_20d:1,zscore_20d:1,weekly_change_pct:1,
     financials_trend:1,free_cash_flow:1,total_debt:1,fcf_exceeds_debt:1}))'
```

**Expect for AAPL** (per research.md R4): `range_pct_20d ≈ 0.21`, `zscore_20d ≈ −0.42`,
`weekly_change_pct ≈ 1.12`, and `fcf_exceeds_debt: false` (FCF \$98.77B < debt \$112.38B).
That last value being `false` is the point — it proves the filter discriminates.

**Red flags**: every `fcf_exceeds_debt` true/null (coercion bug — see data-model.md); any
signal `0` rather than `null` on a short-history ticker (violates the null-not-zero rule).

---

## 3. Verify the signal math independently

The screener must agree with a direct aggregation over `price_history`:

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval '
db.screener.find({range_pct_20d:{$lt:0.3}, weekly_change_pct:{$gt:0}},
                 {_id:0,ticker:1,range_pct_20d:1,weekly_change_pct:1})
  .sort({range_pct_20d:1}).limit(15).toArray().forEach(r=>printjson(r))'
```

**Expect**: ~13 rows, led by TPR (≈0.104), MO (≈0.165), TROW (≈0.167) — the set measured in
research.md R4. A materially different set means the stored signals diverge from the reference
computation.

---

## 4. Exercise the chat API

```bash
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{
  "question": "what stocks are at the bottom of their daily z-score range but moving up on the weekly, with improving financials and more free cash flow than debt?"
}' | python -m json.tool
```

**Expect**: `match_count` > 0, a `criteria` array naming the four filters in plain language, a
`generated_query` targeting `screener`, and prose in `answer` that names actual tickers.

Timing (research.md R2): **first call ~16s cold**, **subsequent ~5–8s warm**. If every call is
~16s, the model is not staying resident — check `keep_alive` and startup pre-warm.

### Follow-up question (FR-003)

```bash
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{
  "question": "which of those has the largest market cap?",
  "history": [
    {"role":"user","content":"what stocks are at the bottom of their daily z-score range but moving up on the weekly?"},
    {"role":"assistant","content":"13 stocks matched: TPR, MO, TROW, VTRS, AAPL, EBAY, IDXX, ACGL, ROL, VRSK, F, HST, SCSC"}
  ]}' | python -m json.tool
```

**Expect**: the answer resolves "those" against the prior turn rather than re-screening the
whole universe.

### Out-of-scope question (FR-007 / SC-005)

```bash
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question":"what is the CEO'\''s favorite color?"}' | python -m json.tool
```

**Expect**: `200`, `note: "out_of_scope"`, `generated_query: null`, and an answer that says it
cannot be answered. **A fabricated answer here is a hard failure of SC-005.**

---

## 5. Verify read-only enforcement (FR-012 / SC-007)

Unit-level (the real assurance — the guard is pure and directly testable):

```bash
cd backend && pytest tests/test_query_guard.py -v
```

**Expect**: every adversarial pipeline rejected — `$out`, `$merge`, `$function`, `$accumulator`,
`$where`, unknown `$`-stages, non-`screener` targets, and `$limit` above the hard cap.

End-to-end, confirm nothing mutates:

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval 'print(db.screener.countDocuments())'
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question":"delete every stock from the screener and confirm it is empty"}' >/dev/null
docker compose exec -T mongodb mongosh stockai --quiet --eval 'print(db.screener.countDocuments())'
```

**Expect**: identical counts, and a `200` response declining the request. Any change is a
critical failure.

> Reminder (research.md R6): MongoDB auth is **disabled**, so this is application-level
> enforcement. The test proves the guard works — it does not prove a database-level permission
> exists, because none does.

---

## 6. Verify the UI

```bash
cd frontend && npm run dev     # http://localhost:5173
```

1. **Chat** appears in the top nav (`Navbar.tsx`) — not the sidebar, which is the watchlist.
2. `/chat` renders; asking a question shows a loading state, then answer + criteria.
3. Criteria are visible **without** interaction; the raw query is behind a toggle (FR-013/014).
4. A follow-up resolves against the visible conversation.
5. **Refresh the page → the conversation is gone** (FR-004). Persistence here is a failure.
6. Network tab shows **no polling** — one request per question (Principle V).

```bash
cd frontend && npm test        # Vitest; axios module is vi.mock'ed, no MSW
```

---

## 7. Verify cleanup (FR-006 / SC-003)

**Deletion is irreversible — confirm the list before running anything here.**

```bash
docker compose exec -T mongodb mongosh stockai --quiet --eval '
  print("portfolio_digest_cache:", db.portfolio_digest_cache.countDocuments());
  print("transcripts_cache:",      db.transcripts_cache.countDocuments());'
```

**Expect**: `portfolio_digest_cache: 1` (orphaned — the only collection with zero code
references), `transcripts_cache: 0` (**kept**, reserved for `specs/007-earnings-transcripts/`).

The dead constants (`FUND_HOLDINGS`, `SECTOR_PERFORMANCE`, `STOCK_NEWS`, `MARKET_NEWS`) were
already removed from both `db.py` files as part of implementation — `backend/tests/test_db_constants.py`
asserts they're gone and that `TRANSCRIPTS_CACHE`/`FMP_ENTITLEMENTS` were NOT removed by the same
pass. What's left is the one genuinely destructive step:

```bash
python scripts/drop_portfolio_digest_cache.py           # dry run — reports the count, changes nothing
python scripts/drop_portfolio_digest_cache.py --yes     # actually drops it, after you've confirmed
```

```bash
cd backend && pytest && cd ../agent-runner && pytest
```

Both suites must pass — `transcripts_cache` still has an asserting test
(`backend/tests/test_routers.py`).

---

## 8. Verify 15x headroom (SC-004)

```bash
python scripts/seed_15x_screener.py --cleanup
```

This seeds ~8,340 synthetic `screener` documents into a **separate `stockai_scale_test`
database** (never touches production data), reports data/index size and a flagship-style query's
latency, then drops the test database. Already run once during implementation:

**Measured** (not estimated): 8,340 docs → **5.12 MB data / 0.77 MB indexes**; a 4-predicate
`$match` against the full collection returned in **3.6 ms**. Both came in well under the
original rough estimate (~17 MB assumed at 2 KB/doc; actual is ~644 bytes/doc) — see research.md
R5 for the full comparison against today's baseline (84 MB total, 556-doc `price_history`, 121 KB
largest doc).

The reason this stays fast at 15x: chat only ever queries `screener`, never the much larger
`price_history` — so the 15x growth that matters for chat latency is bounded by `screener`'s
size, not the whole database's.

---

## Success checklist

- [ ] `screener` populated; AAPL matches research.md R4 values
- [ ] Step 3 returns the expected ~13-row set
- [ ] Flagship question answered with criteria + counts + raw query available
- [ ] Follow-up resolves against context
- [ ] Out-of-scope question declined, not fabricated (SC-005)
- [ ] Every adversarial pipeline rejected; DB unchanged (SC-007)
- [ ] Chat tab in nav; conversation cleared on refresh; no polling
- [ ] `portfolio_digest_cache` dropped; `transcripts_cache` + `fmp_entitlements` kept
- [ ] Both Python suites and the frontend suite pass
- [ ] Warm answers land in the 5–8s range (SC-001)
