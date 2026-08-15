# Quickstart Validation: Decouple Macro Analysis From Ticker Research

**Feature**: `specs/020-surface-macro-ui`

Prerequisites: compose stack up (`docker compose up -d`, or with GPU per README), at least one ticker registered in `ticker_index` with a sector, Ollama model pulled.

## 1. Automated suites (fastest signal)

```bash
# agent-runner: crew no longer calls macro; worker scheduling; sector-based analyst
docker compose exec agent-runner pytest tests/test_crew.py tests/test_macro_worker.py \
  tests/test_macro_analyst_cache.py tests/test_phase5_agents.py -q

# backend: /market/macro contract
docker compose exec backend pytest tests/test_market.py -q

# frontend: Stocks rename + Macro page
cd frontend && npx vitest run src/pages/Stocks.test.tsx src/pages/Macro.test.tsx

# lint gates (constitution)
ruff check backend/ && ruff check agent-runner/ scripts/
```

Expected: all pass. Key assertions: crew makes 7 LLM calls (was 8) and `sub_reports` has no `macro` key ([contracts/macro-worker.md](contracts/macro-worker.md) Part C); `/market/macro` matches [contracts/macro-api.md](contracts/macro-api.md).

## 2. US1 — ticker research runs no macro (SC-003)

```bash
# trigger an analysis and watch the run
curl -X POST http://localhost:8000/queue -H "Content-Type: application/json" -d '{"ticker":"NVDA"}'
docker compose logs -f agent-runner   # no macro-analyst activity during the crew run

# when it lands, the stored doc has no macro sub-report:
curl -s http://localhost:8000/analysis/NVDA | python -c "import json,sys; print(sorted(json.load(sys.stdin)['sub_reports']))"
# → ['fundamental', 'insider', 'institutional', 'recommendation', 'sentiment', 'technical']
```

## 3. US2 — independent macro refresh + Macro page (SC-001/002/004)

```bash
# worker sweep runs within the hour (or restart agent-runner to reset the throttle);
# after it, per-sector reads exist without any ticker analysis having triggered them:
curl -s http://localhost:8000/market/macro | python -m json.tool
# → sectors[] with computed_at ≈ now for each active sector, as_of set
```

Browser: open the app → click **Macro** in the nav →
- market-breadth divergence cards + NYMO/SPY chart at the top,
- one card per sector with inflation/rate/recession/consumer/rotation reads, signal badge, confidence, and a freshness line,
- fresh-install check (optional): `docker compose exec mongodb mongosh --eval 'db.getSiblingDB("stockai").macro_analysis_cache.drop()'` then reload → clean empty state, no error.

## 4. US3 — Stocks page simplified (SC-005)

Browser: open the app root (`/`) →
- nav link and browser tab read **Stocks** (not "Feed"); URL unchanged,
- no breadth/NYMO cards above the tile board — filter bar and tiles only,
- filtering (ticker/signal/sector/conviction), infinite scroll, and empty states behave exactly as before.

## 5. Verdict-input change is in force (FR-003)

```bash
grep -i "macro" agent-runner/agents/portfolio_strategist.py
# → no macro-weighting language remains in SYSTEM/prompt
```

## Spec-sync check (constitution Principle II)

Confirm the component specs updated alongside code: `specs/component-specs/agent-runner/crew.md`, `agents/macro_analyst.md`, `main.md`, `frontend/pages/Feed.md` (→ Stocks), plus a new `frontend/pages/Macro.md` and the market-router spec entry for `/market/macro`.
