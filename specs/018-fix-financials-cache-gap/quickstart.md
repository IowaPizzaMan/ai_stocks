# Quickstart: Validating the Financials Cache Retry Fix

**Feature**: 018-fix-financials-cache-gap
**Contracts**: [contracts/financials-cache.md](contracts/financials-cache.md) · **Model**: [data-model.md](data-model.md)

## Prerequisites

- Docker Compose stack running (`docker compose up -d` from repo root)
- `FMP_API_KEY` set in `.env`
- agent-runner venv with dev deps for unit tests (`pip install -r agent-runner/requirements.txt`)

## 1. Unit suite (primary gate, no network)

```powershell
cd agent-runner
python -m pytest tests/test_financials.py -v
ruff check .
```

Expected: all tests pass, including the new cases — outcome recording on 402/budget,
per-key retry on warm cache, legacy-doc (no `outcomes`) self-correction, confirmed-empty
not retried, `fetched_at` preserved on partial retry.

Also run the untouched-consumer regressions:

```powershell
cd ../backend
python -m pytest tests/test_routers.py -v
```

Expected: pass with zero changes — response shape of `GET /stocks/{ticker}/financials`
is unchanged.

## 2. Live validation — the reported BSX case self-corrects

Before (reproduces the bug state — BSX doc dated 2026-08-09, all seven keys empty):

```powershell
docker exec stockai-mongodb-1 mongosh --quiet stockai --eval "const d=db.financials_cache.findOne({ticker:'BSX'}); print(d.fetched_at); Object.keys(d.data).forEach(k=>print(k+': '+d.data[k].length+' '+(d.outcomes?d.outcomes[k]:'(legacy)')))"
```

Trigger a fresh analysis for BSX from the frontend (Stock Detail → re-run analysis), or
queue it directly, then wait for the run to finish (`logs/agent-runner/agent-runner.log`
shows `BSX analysis done`).

After — expected outcome:

- The same mongosh command now shows non-zero lengths for the statement types FMP covers,
  each marked `confirmed`; `fetched_at` still shows the original full-fetch date
  (partial retry does not bump it).
- `GET http://localhost:8000/stocks/BSX/financials` returns populated statements.
- Stock Detail page for BSX displays financial data (spec SC-001).

## 3. Budget-path spot check (optional, no live 402 needed)

The budget guard path can't be triggered live while `FMP_DAILY_SOFT_CAP` is unset (it
defaults to disabled) — it is covered by the unit suite's budget-exceeded cases instead.
To exercise it end-to-end, set `FMP_DAILY_SOFT_CAP=1` in `.env`, restart agent-runner,
run one analysis (keys degrade to `unavailable`), unset the cap, re-run, and confirm the
keys promote to `confirmed`.

## Success criteria mapping

| Spec criterion | Validated by |
|---|---|
| SC-001 (empty-under-temporary self-heals within one run) | Step 2 |
| SC-002 (confirmed cache: no extra calls / latency) | Unit case "warm cache all confirmed → 0 calls" + Step 1 backend regression |
| SC-003 (no run aborts on temporary conditions) | Unit fail-soft cases; Step 2 log shows `analysis done` |
| SC-004 (retry volume bounded) | Contract invariant 2/4 unit cases (only `unavailable` keys re-fetched) |
