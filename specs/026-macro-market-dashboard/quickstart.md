# Quickstart & Validation: Macro Market Dashboard

**Feature**: `026-macro-market-dashboard` · Phase 1 output

How to run and prove this feature works end to end. Implementation detail belongs in `tasks.md`; this is the validation guide.

---

## Prerequisites

- Docker Compose stack up, or the three services running locally
- `FMP_API_KEY` set in `.env` — this feature's four endpoints all live on FMP's `stable` API
- `FMP_DAILY_SOFT_CAP` left at `0` (disabled) for the first run, or set high enough to absorb the ~8-call one-time backfill on top of normal traffic

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build --no-attach mongodb
```

---

## Step 1 — Verify provider access before building

The three limits below were verified on 2026-08-21 and each one constrains the design (research D2/D4/D5). Re-run these if anything behaves unexpectedly — a change in provider behavior invalidates specific decisions rather than the whole feature.

```bash
# D2: wide range is truncated to ~62 rows; narrow historical windows are honored
curl -s "https://financialmodelingprep.com/stable/treasury-rates?from=2023-08-01&to=2026-08-21&apikey=$FMP_API_KEY" | jq 'length'   # expect ~61
curl -s "https://financialmodelingprep.com/stable/treasury-rates?from=2025-08-01&to=2025-08-31&apikey=$FMP_API_KEY" | jq 'length'   # expect ~21

# D4: from/to is ignored on economic-indicators; depth varies wildly by series
curl -s "https://financialmodelingprep.com/stable/economic-indicators?name=GDP&apikey=$FMP_API_KEY" | jq 'length'            # expect 1
curl -s "https://financialmodelingprep.com/stable/economic-indicators?name=inflationRate&apikey=$FMP_API_KEY" | jq 'length'  # expect ~62

# D5: no date field on market-risk-premium
curl -s "https://financialmodelingprep.com/stable/market-risk-premium?apikey=$FMP_API_KEY" | jq '.[0] | keys'
# expect ["continent","country","countryRiskPremium","totalEquityRiskPremium"] — no "date"
```

**If D2's narrow-window call stops returning history, stop.** The backfill decision (Q3) depends on it, and without it FR-012's year-ago overlay is unbuildable as specified.

---

## Step 2 — Run the pull

The worker runs on `agent-runner`'s daily timer after `ECONOMICS_REFRESH_HOUR_UTC`. To force it immediately:

```bash
docker compose exec agent-runner python -c "
from tools.economics import run_economics_pull
from tools.db import get_db
print('rows written:', run_economics_pull(get_db()))
"
```

First run performs the one-time ~2-year Treasury backfill (~8 calls) and is noticeably slower than subsequent runs.

**Verify what landed:**

```bash
docker compose exec mongodb mongosh stockai --quiet --eval '
  print("treasury_rates:", db.treasury_rates.countDocuments({}));
  print("  oldest:", db.treasury_rates.find().sort({date:1}).limit(1).toArray()[0]?.date);
  print("  newest:", db.treasury_rates.find().sort({date:-1}).limit(1).toArray()[0]?.date);
  print("calendar:", db.economic_calendar_events.countDocuments({}));
  print("indicators:", db.economic_indicators.countDocuments({}));
  print("risk premium:", db.market_risk_premium.countDocuments({}));
  printjson(db.dataset_meta.findOne({dataset:"economics"}));
'
```

**Expected**: ~500 treasury rows spanning ~2 years; a few dozen calendar events (US, High/Medium only — no `Baker Hughes Oil Rig Count`); one row per indicator reading retained; exactly one risk-premium row; `dataset_meta.economics.last_run_status == "success"`.

**Idempotence** — run the pull a second time. `treasury_rates` count must not change materially, and the backfill must not re-run (guarded by the `economics_backfill` marker, data-model §5).

---

## Step 3 — Validate the endpoints

```bash
curl -s localhost:8000/market/treasury-curve | jq '{session, spreads: [.spreads[] | {key, current_bps, inverted}], comparison_sessions}'
curl -s localhost:8000/market/economic-calendar | jq '{timezone, upcoming: (.upcoming|length), reported: (.reported|length)}'
curl -s localhost:8000/market/economic-indicators | jq '.indicators[] | {key, value, as_of, direction, lagging}'
curl -s localhost:8000/market/risk-premium | jq
```

**Checks that map to requirements:**

| Check | Requirement |
|---|---|
| `spreads` has exactly 3 entries, keys `10y-2y`, `30y-10y`, `10y-3m` | FR-013 |
| A negative `current_bps` carries `inverted: true`; exactly `0` does not | FR-015 |
| `comparison_sessions.year_ago` is non-null after backfill | FR-012, Q3 |
| `curve[]` maturities carry proportional `months`, nulls where a maturity is absent | FR-011 |
| No calendar row has `impact: "Low"`; no row has `country != "US"` | FR-019 |
| A `reported` row with `estimate: null` has `comparison: null`, **not** `"in_line"` | FR-021c |
| No response field anywhere asserts good/bad or market direction | FR-021b, SC-004a |
| `GDP` indicator has `direction: null` on a fresh install | FR-024a |
| Most indicators carry `lagging: true` | FR-026a |

**Fail-soft check** — stop the provider path (unset `FMP_API_KEY` and force a pull, or set `FMP_DAILY_SOFT_CAP=1`). Every endpoint must still return **200** with the previous data and `stale: true` (FR-028). Any 5xx here is a defect.

---

## Step 4 — Validate the page

```
http://localhost:5173/macro
```

| Check | Requirement |
|---|---|
| Exactly **one** breadth chart on the page | FR-001, SC-001 |
| It is the outlined card — not a plain bordered section | FR-002 |
| Both NYMO and NAMO are visible as two lines in **one** oscillator pane | FR-007, Q2 |
| **Zero** sector cards — no "Technology" heading anywhere | FR-003, SC-001 |
| Section order: breadth → curve → calendar → indicators | FR-005 |
| Every section carries an as-of line | FR-006, SC-004 |
| No horizontal scroll at 1280px | SC-008 |

**Quiet-market check (FR-002a, Q1)** — the important regression this feature introduces. Clear the events and confirm breadth survives:

```bash
docker compose exec mongodb mongosh stockai --quiet --eval 'db.market_flow_events.deleteMany({})'
```

Reload `/macro`. The breadth panel **must still render**, in a neutral outline, with both oscillators and the current divergence text, and no event headline. If the panel disappears, FR-002a is not met — this is exactly the behavior the current code has and the feature exists to change.

**Independent-failure check (FR-027)** — drop one collection and reload:

```bash
docker compose exec mongodb mongosh stockai --quiet --eval 'db.treasury_rates.drop()'
```

The curve section shows unavailable; breadth, calendar and indicators all still render normally. Repeat per collection. Then drop all four plus breadth → a **single** page-level empty state, no error (FR-031).

---

## Step 5 — Test suites

```bash
# Backend
cd backend && .venv/Scripts/python -m pytest tests/test_market_economics.py -q

# Agent-runner
cd agent-runner && .venv/Scripts/python -m pytest tests/test_economics.py -q

# Frontend
cd frontend && npm run test -- Macro YieldCurve SpreadTiles EconomicCalendar IndicatorTiles BreadthDivergence

# Lint gate (constitution: must pass before mergeable)
ruff check backend/
ruff check agent-runner/ scripts/
```

**Coverage the suites must include** (constitution I — the pure functions in data-model §6 are the high-value deterministic surface):

- `spread_bps` with a null maturity → `null`, not `0`
- `session_change` across a weekend gap → compares stored sessions, not calendar days
- `is_inverted(0.0)` → `false`
- `nearest_session` when history doesn't reach the target → `null`
- `classify(actual, None)` → `null`, never `"in_line"`
- `direction(latest, None)` → `null`, never `"flat"`
- Backfill windowing produces non-overlapping ranges covering ~2 years, and does not re-run when the marker exists
- Daily incremental resumes from the last stored session after a simulated multi-day gap
- A provider failure mid-pull leaves `last_success_at` untouched

---

## Rollback

No migration, so rollback is a revert plus optional cleanup. The four collections are additive — leaving them populated is harmless, and keeping `treasury_rates` avoids paying the backfill again on a re-apply.

```bash
docker compose exec mongodb mongosh stockai --quiet --eval '
  db.economic_calendar_events.drop(); db.economic_indicators.drop();
  db.market_risk_premium.drop(); db.dataset_meta.deleteOne({dataset:"economics"});
'
```

Note `tools/macro.py`'s FRED path and `macro_cache` are untouched by this feature — the sector macro worker keeps running throughout, and `GET /market/macro` keeps serving sector reads for the future Sectors-page work (FR-004).
