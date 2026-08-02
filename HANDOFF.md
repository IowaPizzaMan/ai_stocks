# Handoff — Picking Up on the GPU Machine

> Written 2026-08-02, after the scaffold was committed on branch `new-new`.
> Read this first, then delete it (or update it) when the info goes stale.

## Where things stand

| Done | What |
|---|---|
| ✅ | Specs reviewed; stack + build plan consolidated in [project-proposal.md](project-proposal.md) |
| ✅ | Breadth sourcing fixed: `$NYMO`/`$NAMO` aren't API-fetchable anywhere — we compute the McClellan Oscillator locally (verified working). See `specs/component-specs/agent-runner/tools/breadth.md` |
| ✅ | Full scaffold committed: compose stack (5 services), FastAPI backend with all routers as 501 stubs, agent-runner with dual-loop `main.py` + 11 agent / 10 tool / 5 skill stubs, React frontend shell with routing. All tests green (backend pytest, agent-runner smoke, frontend typecheck + build + vitest) |
| ⬜ | Phase 0 finish: bring the stack up on the GPU machine, pull the model |
| ⬜ | Phase 1: cache-aware data layer (first real code) |

Workflow agreement: **feature by feature, commit after each working chunk** — no big-bang builds. Phases are in project-proposal.md §6.

## Setup on this machine

```sh
git clone https://github.com/IowaPizzaMan/ai_stocks.git && cd ai_stocks
git checkout new-new
cp .env.example .env
```

Then fill `.env` with the real API keys — they are **not in git**. They live in
`c:\Users\nealc\git\ai-stock\.env` on the Windows dev machine (FMP, Finnhub +
webhook secret, FRED). Copy them over or regenerate from each provider's dashboard.

GPU prerequisite: NVIDIA container toolkit. Sanity check:

```sh
docker run --rm --gpus all ubuntu nvidia-smi
```

Bring it up:

```sh
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
docker compose exec ollama ollama pull qwen2.5:14b
```

Phase 0 is done when:
- http://localhost:8000/health → `{"status":"ok"}`
- http://localhost:8000/docs shows the full stubbed API surface
- http://localhost:5173 renders the dark StockAI shell
- `ollama pull` completed and `docker compose logs agent-runner` shows it idling (stubs raise NotImplementedError by design — the loop logs "not implemented yet; idling")

## Next up: Phase 1 — data layer (one commit per chunk)

Goal: cache-aware fetching so FMP stays under 250 calls/day. `agent-runner/data_fetcher.py`
(copied from specs) already implements the gap-fill pattern — adapt, don't rewrite.

Suggested commit sequence:
1. `tools/db.py` — Mongo helpers (`query_db`, `write_db`, `register_ticker`, `mark_ticker_removed`) + indexes. Spec: `specs/component-specs/agent-runner/tools/db.md`
2. `tools/price.py` — `get_price_history`, `get_technical_indicators`, `is_ticker_valid` (yfinance). Spec: `tools/price.md`
3. `tools/financials.py` — FMP + cache, quarterly re-fetch logic. Spec: `tools/financials.md`
4. `tools/macro.py` — FRED + 24h TTL cache. Spec: `tools/macro.md`
5. `tools/breadth.py` — computed NYMO/NAMO per the updated spec (a working prototype of the math exists — see "Breadth notes" below)
6. `scripts/seed_watchlist.py` + `scripts/backfill_financials.py` — make them real

Each tool spec is in `specs/component-specs/agent-runner/tools/`. Verify each chunk with
pytest in `agent-runner/tests/` before committing.

## Breadth notes (so the verification work isn't redone)

- Verified 2026-08-02: `$NYMO`, `^NYMO`, `$NAMO`, `^NYAD`, `^TRIN` all return **zero rows** from Yahoo. Do not burn time retrying symbols.
- Working approach (tested end-to-end): S&P 500 constituents from Wikipedia ("List of S&P 500 companies", first table, `Symbol` column, needs a browser User-Agent header — default urllib gets 403) → one batched `yf.download` → count advancers/decliners → `RANA = 1000*(adv-dec)/(adv+dec)` → `EMA19(RANA) - EMA39(RANA)`.
- The Nasdaq-100 Wikipedia page's constituents table did NOT parse via `pandas.read_html` when tested — use FMP `v3/nasdaq_constituent` or slickcharts as the NASDAQ-100 source.
- Zone thresholds (±60) need calibration against StockCharts since we use proxy universes.

## Gotchas already hit (don't rediscover these)

- **vitest must be v3** with vite 6 (vitest 2 bundles vite-5 types → plugin type clash). Already fixed in package.json.
- `defineConfig` in `vite.config.ts` imports from `"vitest/config"`, not `"vite"` — that's what makes the `test` key typecheck.
- Tailwind v4 is CSS-first: no `tailwind.config.ts` exists on purpose (`@import "tailwindcss"` in `src/index.css`).
- Wikipedia 403s pandas/urllib's default User-Agent — always pass a browser UA.
- The old SPEC.md scaffold said `api/`; the code uses `backend/` to match the component-specs tree. `backend/db.py` and `agent-runner/tools/db.py` intentionally duplicate collection-name constants — keep them in sync by hand.
