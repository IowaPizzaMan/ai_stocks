# Quickstart: Earnings Page Readability & Filters

**Feature**: `025-earnings-page-filters` | **Date**: 2026-08-17

How to run and validate the feature end to end. Each step maps to success criteria in
[spec.md](./spec.md). Shapes and rules are in [data-model.md](./data-model.md) and
[contracts/earnings-calendar.md](./contracts/earnings-calendar.md) — not repeated here.

## Prerequisites

- Docker Compose stack up, `FMP_API_KEY` set in `.env`
- Some daily FMP budget left (`fmp_usage` for today, below `FMP_DAILY_SOFT_CAP`)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --no-attach mongodb
```

---

## 1. Automated gates

Both must pass before anything below counts (Constitution Principles I and the workflow
quality gates).

```bash
# Backend
docker compose exec backend pytest tests/test_earnings.py tests/test_earnings_data.py -v
ruff check backend/

# Frontend
cd frontend && npm test -- src/components/earnings src/pages/EarningsScan
```

The surprise-derivation unit tests are the highest-value assertions in the suite. Confirm
these specific cases are present and green (data-model.md §4):

- `−0.20` actual against `−0.30` estimate → **`+33.33`, classified a beat**
- zero estimate → `null`, not infinity, not a beat
- actual present with null estimate → `null` surprise, actual still displayed
- past date with both actuals null → `reporting_state: "awaiting"`, **not** a miss

## 2. Endpoint contract

```bash
# Default window
curl -s "http://localhost:8000/earnings/calendar?from=$(date -d '2 days ago' +%F)&to=$(date -d '2 days' +%F)" | python -m json.tool | head -40

# Inverted range → 422, never a silent swap
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/earnings/calendar?from=2026-08-19&to=2026-08-15"

# Over-wide span → 422
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/earnings/calendar?from=2026-01-01&to=2026-12-31"
```

Expect: an object with `entries`, `total_before_screen`, `stale`, `fetched_at`; then `422`,
`422`.

Verify ordering and screening hold (SC-007):

```bash
curl -s "http://localhost:8000/earnings/calendar?from=2026-08-10&to=2026-08-15" | python -c "
import sys, json
d = json.load(sys.stdin)
caps = [e['market_cap'] for e in d['entries']]
print('rows:', len(caps), 'of', d['total_before_screen'], 'raw')
print('descending by market cap:', caps == sorted(caps, reverse=True))
print('all above \$500M floor:', all(c >= 5e8 for c in caps))
print('no duplicate tickers:', len({e['ticker'] for e in d['entries']}) == len(caps))
print('reported rows with surprise:', sum(1 for e in d['entries'] if e['eps_surprise_pct'] is not None))
"
```

## 3. Budget accounting

Confirms the call site counts — the KNOWN_ISSUES item this feature closes (research.md D6).

```bash
docker compose exec mongodb mongosh stockai --quiet --eval \
  'db.fmp_usage.find({}).sort({date:-1}).limit(1).toArray()'
```

Request an uncached window, re-run, and confirm the counter incremented by exactly one —
the second identical request must be a cache hit that spends nothing (FR-027d).

## 4. The page

Open `http://localhost:5173/earnings`.

| Check | Expect | Criterion |
|---|---|---|
| Page on arrival | Rows appear with **no button pressed**; no scan controls anywhere | SC-001, SC-001a |
| Date range shown | today−2 through today+2, `±2 days` preset highlighted | SC-001 |
| Reported rows | Actual EPS/revenue and a signed surprise, beats and misses visually distinct — not by sign character alone | SC-005, FR-012 |
| Upcoming rows | Estimates only; actual and surprise columns read "—", never `0` or `null` | FR-014 |
| Row order | Descending market cap regardless of report date | SC-007 |
| Ticker click | Navigates to `/stock/{TICKER}`; does **not** fire the row's Queue action | SC-008, FR-024 |
| Keyboard | Tab to a ticker, press Enter → same navigation | FR-023 |

## 5. Filters

| Action | Expect | Criterion |
|---|---|---|
| Drag revenue or EPS slider | Table updates instantly (<200ms), **zero network requests** in devtools | SC-004, SC-009 |
| Click through all six presets | Exactly one request per click; re-clicking a visited preset serves from cache | SC-009a, FR-027d |
| Type a custom date | One request on commit — not one per keystroke | FR-027a |
| Enter an end date before the start | Rejected, no request issued, current rows remain | FR-004 |
| Toggle "big movers only" on a future-only window | Table empties **and says the toggle caused it** | FR-016d, spec Edge Cases |
| Reload the page mid-session | Filters restore from the URL | FR-018, D8 |

Watch the network tab throughout step 5 — the request counts *are* the assertion here.

## 6. Payload size

Spot-check the widest window the UI can request (research.md D5 estimates 1–3k rows):

```bash
curl -s -o /dev/null -w "size: %{size_download} bytes, time: %{time_total}s\n" \
  "http://localhost:8000/earnings/calendar?from=$(date -d '30 days ago' +%F)&to=$(date -d '30 days' +%F)"
```

If this is slow enough to be felt, revisit D5 — but do not optimize preemptively.

## 7. Degradation

Set `FMP_DAILY_SOFT_CAP=1` in `.env`, restart the backend, and request an **uncached**
window.

- With a cached doc present: `200` with `"stale": true`, rows still render, banner shows
  the age.
- With nothing cached: `503` and an explicit error state.
- **Neither case may render an empty table** — that reads as "nobody reports this week"
  (SC-010).

Restore the cap afterward.

## 8. Regression sweep

The scan removal touches shared surfaces:

- `POST /earnings/analyze` still works from the table's Queue button
- `/earnings` no longer issues any polling request — confirm no repeating XHR in the
  network tab while the page sits idle (Constitution Principle V)
- No console errors from removed components or now-unused types
- Other pages still build: `cd frontend && npm run build`

---

## Definition of done

- [ ] Step 1 gates green, including the four named surprise cases
- [ ] Steps 2–3: contract, ordering, screening, dedupe, budget accounting verified
- [ ] Steps 4–5: every table row checked, network counts confirmed
- [ ] Step 7: both degraded paths render something honest
- [ ] Step 8: no polling, no dead-component errors, build clean
- [ ] `KNOWN_ISSUES.md` updated — stale FMP truncation constraint corrected, budget-bypass
      item closed, agent-runner provider seam and dormant scan endpoints logged
- [ ] Component specs updated under `specs/component-specs/` for the changed router and
      replaced components (Constitution Principle II)
