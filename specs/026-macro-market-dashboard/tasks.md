# Tasks: Macro Market Dashboard

**Input**: Design documents from `/specs/026-macro-market-dashboard/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/macro-api.md](contracts/macro-api.md), [quickstart.md](quickstart.md)

**Tests**: Included and REQUIRED — constitution Principle I is NON-NEGOTIABLE ("Every feature MUST ship with tests before it is considered done"). Every new backend endpoint gets a contract test; every new pure function gets a unit test; every new/changed frontend component gets Vitest coverage.

**Organization**: Tasks are grouped by user story (spec.md P1–P4) so each ships and is independently testable. Phase 2 (Foundational) is the shared economics data pipeline — it blocks **US2, US3, US4** but **not US1**, which is a pure frontend cleanup with no dependency on the new collections.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependency)
- **[Story]**: US1 / US2 / US3 / US4, mapped to spec.md's four user stories
- File paths are exact; open [data-model.md](data-model.md) §6 and [contracts/macro-api.md](contracts/macro-api.md) alongside the endpoint tasks — the response shapes and pure-function signatures are pinned there, not repeated here.

---

## Phase 1: Setup

- [X] T001 Add `economics_refresh_hour_utc: int = 22` to `agent-runner/settings.py`, mirroring the existing `breadth_refresh_hour_utc` pattern (same file, same docstring style)

---

## Phase 2: Foundational — economics data pipeline

**Purpose**: Implement the `economics_pull` job that spec `017-fmp-migration-admin` reserved (collections, job registry entry, dataset name) but never wrote. One job fills all four collections; splitting it per-story would contradict 017's contract ("writes four collections but reports as one job/dataset").

**⚠️ Blocks US2, US3, US4. Does NOT block US1** — US1 can start immediately after Phase 1 in parallel with this phase.

- [X] T002 [P] Add unique/compound indexes for the four economics collections to `agent-runner/tools/db.py::ensure_indexes` — `treasury_rates.date` unique; `economic_calendar_events (date, event)` unique + `date` descending; `economic_indicators (indicator, date)` unique + `(indicator, date DESC)`; `market_risk_premium.country` unique. See [data-model.md](data-model.md) §1–4.
- [X] T003 [P] Mirror the same four indexes in `backend/db.py::ensure_indexes` (constitution VI — both services declare them; `create_index` is idempotent)
- [X] T004 [P] Write `agent-runner/tests/test_economics.py` covering, against `mongomock`: Treasury backfill windowing produces non-overlapping ~90-day chunks spanning ~2 years; backfill does not repeat once its completion marker exists; the daily incremental call resumes from the last stored session (not "yesterday") after a simulated multi-day gap; the calendar pull keeps only `country == "US"` and `impact in {High, Medium}` and drops everything else; the indicator pull upserts so a second run accumulates a prior reading rather than overwriting it; the risk-premium pull keeps only the `"United States"` row from a multi-country response; a simulated provider failure leaves `dataset_meta.last_success_at` untouched and prior data intact (FR-028). Write this **first** — it must fail until T005–T009 exist.
- [X] T005 Implement `pull_treasury_rates(db)` in `agent-runner/tools/economics.py` — one-time ~2-year backfill in ≤90-day windows guarded by an `economics_backfill` marker (FR-017a), then a single incremental call per day that requests from the last stored session forward (FR-017b). Route every call through `tools/fmp_client.fmp_get` for throttle + budget guard (constitution IV). Store `null` for a maturity absent from the response, never `0`.
- [X] T006 Implement `pull_economic_calendar(db)` in `agent-runner/tools/economics.py` — fetch `today − 7d … today + 14d`, filter to US + High/Medium at collect time (research D6), upsert on `(date, event)`, prune stored rows outside the window on each successful run.
- [X] T007 Implement `pull_economic_indicators(db)` in `agent-runner/tools/economics.py` — one call per series (`GDP`, `inflationRate`, `unemploymentRate`, `federalFunds`, plus optional `retailSales`/`consumerSentiment`), upsert on `(indicator, date)`, never delete — retention is what satisfies FR-024b on later runs.
- [X] T008 Implement `pull_market_risk_premium(db)` in `agent-runner/tools/economics.py` — fetch, filter to `country == "United States"`, `replace_one` upsert keyed on `country` (research D5 — no provider date field, so `collected_at` is the as-of proxy).
- [X] T009 Implement `run_economics_pull(db) -> int` in `agent-runner/tools/economics.py` — orchestrates T005–T008, sums `record_count`, and calls `tools/db.write_dataset_meta("economics", status, record_count, source="fmp", db=db)` on completion (success or failure per its existing "only success advances `last_success_at`" contract). Returns the record count for `admin_jobs` to report.
- [X] T010 Register the job in `agent-runner/tools/admin_jobs.py`: `JOB_HANDLERS["economics_pull"] = run_economics_pull`, `JOB_DATASETS["economics_pull"] = "economics"`, `STALE_MINUTES["economics_pull"] = 15` — values pinned by `specs/017-fmp-migration-admin/contracts/admin-jobs-api.md`'s registry table, not invented here.
- [X] T011 [P] Write `agent-runner/tests/test_economics_worker.py` for the daily-timer scheduling logic, mirroring `agent-runner/tests/test_breadth_worker.py`'s three cases: runs once after the refresh hour, skips before it, runs again on a new day. Write **first** — must fail until T012 exists.
- [X] T012 Implement `agent-runner/economics_worker.py::run_daily_economics_if_due(now, db=None, refresh=None)`, mirroring `agent-runner/breadth_worker.py`'s `_scheduled_due`/meta-flag pattern exactly (same `_get_meta`/`_set_meta` shape, own meta key).
- [X] T013 Wire `run_daily_economics_if_due` into the loop in `agent-runner/main.py`, alongside the existing `run_daily_breadth_if_due` and `run_macro_refresh_if_due` calls.

**Checkpoint**: `run_economics_pull` fills all four collections end-to-end (verify with [quickstart.md](quickstart.md) Step 2); the daily timer and the admin-job path both reach it. US2/US3/US4 can now proceed.

> Note: the `017-fmp-migration-admin/data-model.md` shape amendment for `economic_indicators` (drops the FRED-exclusion restriction) and `market_risk_premium` (drops the assumed `date` key) was already applied during `/speckit-plan` — no task needed here. See that file's dated amendment note.

---

## Phase 3: User Story 1 — Clean, non-duplicated breadth read (P1) 🎯 MVP

**Goal**: Exactly one breadth visualization (the outlined market-flow card), showing NYMO **and** NAMO together, rendering whether or not a market-flow event is currently active, with zero sector-commentary cards anywhere on the page.

**Independent Test**: Load `/macro` with breadth data present. Exactly one breadth chart renders inside the outlined card, both oscillators are visible as separate lines in one pane, and no sector card appears — with and without an active market-flow event.

**Depends on**: Phase 1 only. **Does not depend on Phase 2.**

### Tests for User Story 1

- [X] T014 [P] [US1] Extend `frontend/src/components/stock/BreadthDivergenceChart.test.tsx` — assert `namo` renders as a second, visually distinguishable line sharing the oscillator pane's axis with `nymo`; assert the divergence overlay (`showDivergence`) still binds to NYMO only when a divergence is present; assert the `oscillator` prop/toggle buttons are gone. Update, don't just append — some existing cases assert the now-removed toggle UI.
- [X] T015 [P] [US1] Create `frontend/src/components/feed/MarketFlowCard.test.tsx` — assert a neutral `border-zinc-800` outline and no headline row when `event` is omitted, and today's tinted-outline + headline behavior when `event` is present; assert the chart renders in both cases.
- [X] T016 [P] [US1] Rewrite `frontend/src/pages/Macro.test.tsx` — replace every sector-card assertion (all five existing tests reference `SectorMacroRead`/sector cards) with: exactly one breadth visualization present when breadth data exists; it renders even when `flowEvents` is empty (FR-002a); zero elements matching a sector name or sector commentary text anywhere on the page; the "not computed yet" state when breadth is null.

### Implementation for User Story 1

- [X] T017 [US1] Edit `frontend/src/components/stock/BreadthDivergenceChart.tsx` — add `namo` as a second `<Line>` on the existing oscillator `<ComposedChart>` (color `CHART_DEFAULTS.bfPriorColor`, recessive vs. NYMO's `bfActiveColor` per research D8); remove the `oscillator` prop, the `useState` toggle, and its button row; keep `showDivergence` bound to NYMO only (FR-008); confirm the Y-domain auto-fit callbacks still fit correctly with two series on the axis.
- [X] T018 [US1] Edit `frontend/src/components/feed/MarketFlowCard.tsx` — make the `event` prop optional (`event?: MarketFlowEvent`); when absent, render the card with a neutral `border-zinc-800` outline, a static "Market breadth" label in place of the headline row, and the chart + divergence caption still shown (research D9); add a `neutral` entry to the `TONE` map.
- [X] T019 [US1] Rewrite `frontend/src/pages/Macro.tsx` — delete the standalone `Section title="Market breadth"` block that duplicates the chart (FR-001); delete `SectorCard` and the sector grid entirely (FR-003) — but keep the `useMacroReads()` import removed from *rendering* only, do not touch `hooks/useMacro.ts` or `GET /market/macro` (FR-004 requires the endpoint to keep serving sector reads for a future Sectors page); render exactly one `MarketFlowCard` whenever `breadth` data exists, passing the most recent pinned event (if any) or nothing; retain the "not computed yet" state for no breadth data at all; leave clearly-marked placeholders for the curve/calendar/indicator sections in FR-005's order (filled in by Phases 4–6).
- [X] T020 [US1] Remove the now-unused `SIGNAL_BADGE`/`SectorMacroRead` imports from `frontend/src/pages/Macro.tsx`. **Deviation from original wording**: kept `MARKET_EVENT_MAX_AGE_DAYS`, repurposed as the cutoff for whether an event still counts as *active* enough to decorate the panel, rather than deleting it outright — FR-002a only requires removing its role as the panel's *existence* gate, and dropping the recency concept entirely would let a stale event decorate the panel forever.

**Checkpoint**: Run `frontend: npm run test -- Macro BreadthDivergenceChart MarketFlowCard`, then validate the "quiet-market check" in [quickstart.md](quickstart.md) Step 4 by hand — clearing `market_flow_events` must **not** make the breadth panel disappear.

---

## Phase 4: User Story 2 — Yield curve and rates (P2)

**Goal**: Treasury yield curve for the latest session with month-ago/year-ago overlays, plus 10y–2y / 30y–10y / 10y–3m spreads with change, inversion, and trend.

**Independent Test**: With `treasury_rates` populated (via Phase 2), `GET /market/treasury-curve` returns a curve and three spreads verifiable against the raw stored rates; the page renders them.

**Depends on**: Phase 2 (needs `treasury_rates` data).

### Tests for User Story 2

- [X] T021 [P] [US2] Write `backend/tests/test_market_economics.py::TestTreasuryCurve` — `GET /market/treasury-curve` contract tests using `mongomock`: curve covers every maturity in the latest session ordered by `months`; a `null` maturity is skipped, never zero; `spreads` always contains exactly the three keys in the pinned order even when a maturity is missing; `change_bps` compares against the previous **stored** session, not calendar-yesterday, across a simulated weekend gap; a negative spread is `inverted: true`, exactly `0.0` is not; `comparison_sessions.year_ago` is `null` when history doesn't reach back that far, and the overlay is then absent from `curve[]`'s `year_ago` fields; an empty collection returns 200 with `session: null`, `curve: []`, `spreads` still carrying all three null-valued keys. Write **first**.
- [X] T022 [P] [US2] Write `frontend/src/lib/yieldCurve.test.ts` — pure function tests for reshaping the API's `curve[]` (with `current`/`month_ago`/`year_ago` per point) into Recharts-ready series keyed by `months`, and for spread-tile formatting (bps display, inverted styling flag). Write **first**.
- [X] T023 [P] [US2] Create `frontend/src/components/macro/YieldCurveChart.test.tsx` and `SpreadTiles.test.tsx` — curve renders three distinguishable lines with a gap (not a dip to zero) where a maturity is null; a missing `year_ago` overlay is simply absent, not drawn as a flat line; each spread tile shows value, change, and an inverted badge only when `inverted: true`.

### Implementation for User Story 2

- [X] T024 [US2] Implement the pure functions from [data-model.md](data-model.md) §6 "Yield spreads" and "Curve comparison" in `backend/routers/market.py`: `spread_bps`, `spread_series`, `session_change`, `is_inverted`, `nearest_session`, `align_curve`
- [X] T025 [US2] Implement `GET /market/treasury-curve` in `backend/routers/market.py` per [contracts/macro-api.md](contracts/macro-api.md) — `lookback_days` query param (default 180, 30–750) bounding only the spread trend series; always-200 with the freshness envelope (`as_of`, `stale`)
- [X] T026 [P] [US2] Implement `frontend/src/lib/yieldCurve.ts` — the reshaping/formatting functions covered by T022
- [X] T027 [US2] Implement `frontend/src/components/macro/YieldCurveChart.tsx` — Recharts line chart, three overlaid curves (current/month-ago/year-ago) on a `months`-proportional X axis (not evenly-spaced categories — research D7), gaps at null maturities, legend distinguishing the three lines, session date label
- [X] T028 [US2] Implement `frontend/src/components/macro/SpreadTiles.tsx` — three tiles (10y–2y, 30y–10y, 10y–3m): current bps, change since prior session, inverted badge/styling, small trend sparkline from `series[]`
- [X] T029 [US2] Add `useTreasuryCurve()` to `frontend/src/hooks/useEconomics.ts` — `staleTime: 24h`, `refetchInterval: false`, matching the `useMacroReads`/`useMarketBreadth` pattern already in the codebase
- [X] T030 [US2] Wire `YieldCurveChart` + `SpreadTiles` into `frontend/src/pages/Macro.tsx` as the second section (FR-005), with its own as-of line and a visible age/`stale` badge when `stale: true`

**Checkpoint**: `GET /market/treasury-curve` matches [quickstart.md](quickstart.md) Step 3's checks table; page section renders independently of US1/US3/US4.

---

## Phase 5: User Story 3 — Economic calendar (P3)

**Goal**: Upcoming US high/medium-impact releases (14 days forward) and recently reported ones (7 days back) with a neutral above/below/in-line comparison — no market-direction judgment anywhere.

**Independent Test**: With `economic_calendar_events` populated, `GET /market/economic-calendar` returns correctly split, chronologically ordered lists verifiable against the source window; the page renders them with no color-by-outcome.

**Depends on**: Phase 2 (needs `economic_calendar_events` data).

### Tests for User Story 3

- [X] T031 [P] [US3] Write `backend/tests/test_market_economics.py::TestEconomicCalendar` — `GET /market/economic-calendar` contract tests: an event later today lands in `upcoming`, not `reported` (split on `date > now`, not calendar day — FR-023); an event is `reported` only once `actual != null`; `comparison` is `null` when `estimate` is `null` and is **never** defaulted to `"in_line"` (FR-021c); response contains no field anywhere asserting good/bad or market direction (FR-021b) — assert the full response body has no such key; `timezone` is present and labeled; an empty window returns 200 with both arrays empty. Write **first**.
- [X] T032 [P] [US3] Create `frontend/src/components/macro/EconomicCalendarPanel.test.tsx` — reported rows render `above`/`below`/`in_line` in neutral styling (assert no green/red/success/danger class tied to the comparison value); a row with `comparison: null` shows the estimate as explicitly unavailable, not a blank cell; empty state reads "no major releases scheduled," not an empty box.

### Implementation for User Story 3

- [X] T033 [US3] Implement the pure functions from [data-model.md](data-model.md) §6 "Calendar outcome" in `backend/routers/market.py`: `classify(actual, estimate)`, `surprise(actual, estimate)` — no polarity mapping exists anywhere in this module
- [X] T034 [US3] Implement `GET /market/economic-calendar` in `backend/routers/market.py` per [contracts/macro-api.md](contracts/macro-api.md) — `forward_days` (default 14) / `back_days` (default 7) query params, `upcoming`/`reported` split, always-200
- [X] T035 [US3] Add `useEconomicCalendar()` to `frontend/src/hooks/useEconomics.ts`
- [X] T036 [US3] Implement `frontend/src/components/macro/EconomicCalendarPanel.tsx` — upcoming list (chronological) and reported list (reverse-chronological), each row's impact level shown, times rendered in US/Eastern with an explicit label, neutral comparison styling per FR-021b, missing-estimate and empty-window states
- [X] T037 [US3] Wire `EconomicCalendarPanel` into `frontend/src/pages/Macro.tsx` as the third section (FR-005)

**Checkpoint**: `GET /market/economic-calendar` matches [quickstart.md](quickstart.md) Step 3's checks; section renders independently of US1/US2/US4.

---

## Phase 6: User Story 4 — Growth, inflation and risk backdrop (P4)

**Goal**: Four headline indicator tiles (growth, inflation, employment, policy rate) with direction-vs-prior and a lagging marker past 90 days, plus a single US equity risk-premium tile.

**Independent Test**: With `economic_indicators`/`market_risk_premium` populated, the two endpoints return correctly shaped tiles, independently of breadth/curve/calendar; a series with only one stored reading omits direction rather than showing "flat."

**Depends on**: Phase 2 (needs both collections' data).

### Tests for User Story 4

- [X] T038 [P] [US4] Write `backend/tests/test_market_economics.py::TestEconomicIndicators` — `GET /market/economic-indicators`: `direction`/`change` are `null` (not `"flat"`/`0`) when no prior reading is retained; `lagging: true` when `as_of` is more than 90 days old; tiles appear in the fixed order growth → inflation → employment → policy_rate → optional; a series never fetched is omitted from the array, not included with nulls. Write **first**.
- [X] T039 [P] [US4] Write `backend/tests/test_market_economics.py::TestRiskPremium` — `GET /market/risk-premium`: returns the single stored US row; empty collection returns 200 with all value fields `null`. Write **first**.
- [X] T040 [P] [US4] Create `frontend/src/components/macro/IndicatorTiles.test.tsx` — a tile with `direction: null` renders with no up/down glyph (not a flat dash implying "unchanged"); `lagging: true` shows a visible marker next to the tile's own as-of date; the risk-premium tile is labeled as a slow-moving valuation input, distinct from the other four.

### Implementation for User Story 4

- [X] T041 [US4] Implement the pure functions from [data-model.md](data-model.md) §6 "Indicator direction" in `backend/routers/market.py`: `direction(latest, prior)`, `is_lagging(as_of, now)`
- [X] T042 [US4] Implement `GET /market/economic-indicators` in `backend/routers/market.py` per [contracts/macro-api.md](contracts/macro-api.md) — fixed tile order, always-200
- [X] T043 [US4] Implement `GET /market/risk-premium` in `backend/routers/market.py` — single-document read, always-200
- [X] T044 [P] [US4] Add `useEconomicIndicators()` and `useRiskPremium()` to `frontend/src/hooks/useEconomics.ts`
- [X] T045 [US4] Implement `frontend/src/components/macro/IndicatorTiles.tsx` — four indicator tiles (value, own as-of date, direction glyph or omitted, lagging badge) plus the risk-premium tile
- [X] T046 [US4] Wire `IndicatorTiles` into `frontend/src/pages/Macro.tsx` as the fourth and final section (FR-005)

**Checkpoint**: Both endpoints match [quickstart.md](quickstart.md) Step 3's checks; all four user stories now independently functional and composed on one page in FR-005 order.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Requirements that only make sense once every section exists (FR-027, FR-031, SC-008), plus the constitution's mandatory quality gates.

- [X] T047 Implement the page-level composed empty state in `frontend/src/pages/Macro.tsx` (FR-031) — render the single "no macro data yet" message only when breadth is absent **and** all four economics sections resolved empty; verify no individual section renders its own error box in this state
- [X] T048 Add failure-isolation Vitest cases to `frontend/src/pages/Macro.test.tsx` asserting that when one section's query rejects, the other sections still render fully (FR-027). **Deviation from original wording**: per-component empty-state cases were already covered by each component's own test file in Phases 4–6 (e.g. `YieldCurveChart`'s "no session" state, `SpreadTiles`' "not available yet"); testing a component in isolation can't actually prove *cross-section* independence, since nothing else is mounted alongside it to be protected. The meaningful assertion — one query failing doesn't take down its siblings — only exists where the sections are composed together, i.e. the page. Exercises the independent-failure behavior from [quickstart.md](quickstart.md) Step 4.
- [X] T049 [P] Verify `frontend/src/pages/Macro.tsx` and its four new child components are usable at a 1280px viewport with no horizontal scroll (SC-008) — manual check plus a Vitest/RTL viewport assertion where practical
- [X] T050 Run `ruff check backend/` and `ruff check agent-runner/ scripts/` and fix any violations (constitution: mergeable gate)
- [X] T051 [P] Update `specs/component-specs/backend/routers/market.md` — document the four new endpoints (currently only documents `/breadth`, `/flow-events`, `/macro`, `/news`)
- [X] T052 [P] Update `specs/component-specs/frontend/pages/Macro.md` — replace its "Layout" section (still describes the sector-card grid and the duplicated chart) with the four-section dashboard this feature builds
- [X] T053 Run the full [quickstart.md](quickstart.md) validation end to end (Steps 1–5), including the fail-soft check (FMP key removed/budget exhausted → every endpoint still 200s with `stale: true`) and the independent-failure check (drop one collection at a time)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — one settings edit, trivially parallel with nothing to conflict with.
- **Foundational (Phase 2)**: Depends on Phase 1 (needs the setting). **Blocks US2, US3, US4.**
- **User Story 1 (Phase 3)**: Depends on Phase 1 only. Can run **concurrently with Phase 2** — it touches only frontend breadth/card/page files that Phase 2 never writes to.
- **User Stories 2–4 (Phases 4–6)**: Each depends on Phase 2 (needs its respective collection populated) and on Phase 1. They do **not** depend on each other or on US1 — each adds a section to `Macro.tsx` that the others don't touch, though all four sequentially edit that one file (see Parallel Opportunities note below).
- **Polish (Phase 7)**: Depends on all four user stories being complete — FR-031's composed empty state and FR-027's isolation checks need every section to exist first.

### Within Each Phase

- Tests are written first and MUST fail before their implementation task (constitution I, template convention) — each phase lists tests before implementation for this reason.
- Within Phase 2: pure pull functions (T005–T008) before the orchestrator (T009); orchestrator before job registration (T010); worker tests (T011) before the worker (T012); worker before wiring it into `main.py` (T013).
- Within Phases 4–6: pure backend functions before the endpoint that uses them; endpoint before the frontend hook; hook before the component; component before wiring it into `Macro.tsx`.

### Parallel Opportunities

- T002/T003 (index files) are independent of each other and of T004 (test file) — all three `[P]`.
- T005–T008 all edit the **same** new file (`agent-runner/tools/economics.py`) — not marked `[P]` despite being logically independent; do them in sequence to avoid merge churn within one file.
- Once Phase 2 completes, **Phases 4, 5, and 6 can proceed in parallel** by different people/sessions for their backend and pure-function work (different endpoints, different test classes in the same `test_market_economics.py` file — coordinate on that one file, or split it per-story if working simultaneously). Their final "wire into `Macro.tsx`" task (T030, T037, T046) is the one point of contention — that file is edited by T019/T020 (US1), T030 (US2), T037 (US3), T046 (US4) in sequence; land US1 first since it establishes the section-order scaffold the others slot into.
- All `[P]`-marked test-writing tasks within a phase (e.g., T021/T022/T023, or T038/T039/T040) can be written in parallel — different files.

---

## Parallel Example: Phase 2 kickoff

```
# After T001 completes, launch together:
Task: "Add indexes to agent-runner/tools/db.py::ensure_indexes"        (T002)
Task: "Mirror indexes in backend/db.py::ensure_indexes"                 (T003)
Task: "Write agent-runner/tests/test_economics.py"                      (T004)

# Meanwhile, independently, US1 can already be running:
Task: "Extend BreadthDivergenceChart.test.tsx"                          (T014)
Task: "Create MarketFlowCard.test.tsx"                                  (T015)
Task: "Rewrite Macro.test.tsx"                                          (T016)
```

## Parallel Example: Phases 4–6 kickoff (after Phase 2 checkpoint)

```
Task: "TestTreasuryCurve contract tests"        (T021, US2)
Task: "TestEconomicCalendar contract tests"     (T031, US3)
Task: "TestEconomicIndicators contract tests"   (T038, US4)
Task: "TestRiskPremium contract tests"          (T039, US4)
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (T001)
2. Phase 3 / US1 (T014–T020) — Phase 2 is **not** required for this
3. **STOP and VALIDATE**: breadth dedup, NAMO, always-on panel, zero sector cards — this alone fixes all three problems the user originally flagged
4. Ship if that's the whole ask; continue below for the three new sections

### Incremental delivery

1. Phase 1 + Phase 3 (US1) → deploy the cleanup (MVP)
2. Phase 2 (Foundational) → data pipeline live, nothing user-visible yet
3. Phase 4 (US2, yield curve) → deploy → the user's explicit "I would love a yield curve" ask is met
4. Phase 5 (US3, calendar) → deploy
5. Phase 6 (US4, indicator backdrop) → deploy — page now matches spec.md in full
6. Phase 7 (Polish) → composed empty state, isolation tests, lint gate, doc sync

### Suggested execution order for a single implementer

T001 → T002…T013 (Phase 2, sequential within the file-conflict notes above) → T014…T020 (US1) → T021…T030 (US2) → T031…T037 (US3) → T038…T046 (US4) → T047…T053 (Polish). US1 can be pulled forward to run before or alongside Phase 2 if two work-streams are available.

---

## Task Count Summary

| Phase | Tasks | Story |
|---|---|---|
| 1. Setup | 1 | — |
| 2. Foundational | 12 | — (blocks US2–US4) |
| 3. User Story 1 | 7 | US1 (P1) |
| 4. User Story 2 | 10 | US2 (P2) |
| 5. User Story 3 | 7 | US3 (P3) |
| 6. User Story 4 | 9 | US4 (P4) |
| 7. Polish | 7 | — |
| **Total** | **53** | |
