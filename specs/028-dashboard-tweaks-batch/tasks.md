---

description: "Task list for 028-dashboard-tweaks-batch"
---

# Tasks: Dashboard Tweaks Batch

**Input**: Design documents from `/specs/028-dashboard-tweaks-batch/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: **REQUIRED, not optional.** Constitution Principle I is marked NON-NEGOTIABLE:
"A pull request that adds behavior without a corresponding test is incomplete." Test tasks
below are therefore first-class work items, not a suggested extra.

**Organization**: Grouped by user story. The seven stories are genuinely independent —
see the Foundational phase note.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US7, mapping to spec.md's user stories
- Exact file paths are given in every task

## Path Conventions

Three-service web app: `backend/`, `agent-runner/`, `frontend/src/`. Existing codebase —
no scaffolding needed.

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before changing anything

- [X] T001 Verify baseline is green: run `ruff check backend/`, `ruff check agent-runner/ scripts/`, `cd backend && pytest`, `cd agent-runner && pytest`, `cd frontend && npx vitest run` — record any pre-existing failures so they are not mistaken for regressions later. **Baseline**: backend 196 tests pass, 94 pre-existing ruff errors (unrelated files, left untouched); agent-runner 425 tests pass, ruff clean; frontend 336 tests pass (40 files). Also removed a stray pre-existing empty directory `backend/tests;C` (shell-quoting artifact from an earlier session) that was leaking into the Docker build context
- [X] T002 Confirm the stack runs: `docker compose up -d` and `docker compose ps` shows all five services healthy (`mongodb`, `backend`, `frontend`, `agent-runner`, `ollama`). **Note**: none of the three app services bind-mount source, so containers only reflect what was last built; iterative testing during this implementation uses `docker compose run --rm -v <live-source>:<target>` overrides instead of rebuilding per change

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Genuinely shared prerequisites

**This phase is deliberately near-empty.** Unlike a greenfield feature, all seven stories
here modify an existing, working system along independent seams — there is no shared
schema, framework, or base model to build first. Inventing a foundational phase would
create false sequencing. The real cross-story hazard is *shared files*, which is handled
in the Shared File Conflicts section below rather than by blocking.

- [X] T003 Read [research.md](./research.md) R1–R13 end to end — several tasks below depend on decisions recorded there (notably R4's no-admin-router finding, R7's field mapping, and R9's missing-volume finding) and will be implemented wrongly without them

**Checkpoint**: Any story may now begin. US1 is the fastest to land.

---

## Phase 3: User Story 1 - Portfolio Summary Ticker Links Work (Priority: P1) 🎯 MVP

**Goal**: Clicking a ticker in the Portfolio Summary reaches a populated stock page instead of a blank one

**Independent Test**: Open `/`, click a ticker in the Portfolio Summary highlights, confirm the stock detail page renders with content

### Tests for User Story 1

- [X] T004 [P] [US1] Add a test in `frontend/src/components/feed/PortfolioDigestPanel.test.tsx` asserting each highlight's link `href` is `/stock/<TICKER>` (singular) — this test must fail before T006
- [X] T005 [P] [US1] Add a test in `frontend/src/App.test.tsx` asserting an unregistered path renders the NotFound message rather than an empty `<main>`

### Implementation for User Story 1

- [X] T006 [US1] Fix the highlight link in `frontend/src/components/feed/PortfolioDigestPanel.tsx` line ~101: change `to={\`/stocks/${h.ticker}\`}` to `to={\`/stock/${h.ticker}\`}`
- [X] T007 [P] [US1] Create `frontend/src/pages/NotFound.tsx` — short "page not found" message plus a link back to `/`
- [X] T008 [US1] Register `<Route path="*" element={<NotFound />} />` as the **last** route in `frontend/src/App.tsx` (R1 — prevents this whole failure class recurring as US4/US6 add new ticker links)

**Verified**: both new/edited tests failed before the fix, pass after. Full frontend suite: 337/337 passing (was 336; +1 net new test).

**Checkpoint**: US1 complete and independently shippable.

---

## Phase 4: User Story 2 - Portfolio Summary Respects the Feed Filter (Priority: P2)

**Goal**: The summary's highlights narrow with the feed filter; the AI paragraph stays unchanged but labeled

**Independent Test**: Apply a signal filter; highlights narrow with no network request; overview text unchanged with a scope label

> Per clarification Q1, **no regeneration occurs on filter change**. Any task here that
> triggers a refetch is wrong.

### Tests for User Story 2

- [X] T009 [P] [US2] Create `frontend/src/lib/filterHighlights.test.ts` — one case per dimension (ticker substring, signal, conviction, sector), AND-combinations, `sector: null` against a sector filter, empty filters returning input unchanged, empty input, and non-mutation of the input array
- [X] T010 [P] [US2] Add cases to `agent-runner/tests/test_portfolio_digest.py`: sector is joined onto a highlight whose ticker was gathered; a highlight with an unknown ticker gets `None` rather than raising; the agent's `SCHEMA` contains no `sector` key (Principle III guard)
- [X] T011 [P] [US2] Add cases to `frontend/src/components/feed/PortfolioDigestPanel.test.tsx`: filtered highlights narrow; overview text is byte-identical with and without a filter; scope label appears only when a filter is active; a zero-match filter shows the no-match message while still showing the overview; the genuinely-empty digest state is unaffected by filters

### Implementation for User Story 2

- [X] T012 [P] [US2] Create `frontend/src/lib/filterHighlights.ts` — pure `filterHighlights(highlights, filters)` per [contracts/portfolio-digest-filtering.md](./contracts/portfolio-digest-filtering.md) §4; ticker is a case-insensitive **substring** match to mirror the feed's `$regex` behavior, the other three are exact case-insensitive
- [X] T013 [US2] In `agent-runner/tools/portfolio.py`: add `"sector": 1` to `_PROJECTION`, carry sector through `_condense` into a `{ticker: sector}` map, and after `portfolio_digest_agent.run(...)` returns, set `highlight["sector"]` from that map before persisting. **Do not add `sector` to the agent's `SCHEMA`** (R3)
- [X] T014 [P] [US2] Add `sector?: string | null` to the digest highlight type in `frontend/src/api/types.ts`
- [X] T015 [US2] In `frontend/src/components/feed/PortfolioDigestPanel.tsx`: read filters via `useSearchParams`, pass highlights through `filterHighlights`, and render only matches. No props added, no refetch
- [X] T016 [US2] In the same file, render the scope label (`across all N tracked stocks`) above the overview whenever any filter is active (FR-004b), and the "No highlighted stocks match the current filter." message when the filtered list is empty while highlights exist (FR-004)
- [X] T017 [US2] Verify no backend change is needed: `backend/routers/portfolio.py` already passes `highlights` through verbatim, so the new `sector` field flows without edit — confirm by test, do not edit the router

**Checkpoint**: US1 + US2 both work independently. **Verified**: frontend 353/353, backend 196/196 (unchanged), agent-runner 428/428 (+3).

---

## Phase 5: User Story 3 - Like / Dislike a Stock (Priority: P2)

**Goal**: Thumbs up/down on tracked stocks, filterable from the feed

**Independent Test**: Tag a tracked stock, filter the feed by `liked`, see it; confirm an untracked ticker shows no thumbs at all

### Tests for User Story 3

- [X] T018 [P] [US3] Create `backend/tests/test_sentiment.py`: set liked; set disliked over liked (mutual exclusion); re-sending the stored value clears it (toggle-off returns `sentiment: null`); `DELETE` clears unconditionally; **404 for an untracked ticker**; 422 for an invalid value
- [X] T019 [P] [US3] Add feed-filter cases to `backend/tests/` for `GET /analysis/feed?sentiment=`: returns only tagged tickers; intersects correctly with `signal`; **an empty tagged set returns zero items, never the unfiltered feed** (the one way this filter fails dangerously)
- [X] T020 [P] [US3] Create `frontend/src/components/stock/SentimentButtons.test.tsx`: hidden entirely for an untracked ticker; shown for a tracked one; `aria-pressed` tracks state; clicking the active control clears it
- [X] T021 [P] [US3] Add cases to `frontend/src/components/feed/FilterBar.test.tsx` (or create it): selecting `liked` sets `?sentiment=liked`; selecting it again clears the param; `liked` and `disliked` are mutually exclusive since they share one param

### Implementation for User Story 3

- [X] T022 [US3] Add `PUT /stocks/{ticker}/sentiment` and `DELETE /stocks/{ticker}/sentiment` to `backend/routers/stocks.py` per [contracts/stock-sentiment-api.md](./contracts/stock-sentiment-api.md) — writes `sentiment` and `sentiment_at` on the `ticker_index` document; 404 when no `ticker_index` row exists (this is what enforces FR-006a at the API, not just in the UI)
- [X] T023 [US3] Include `sentiment` in the `GET /stocks/{ticker}` ticker-record response in `backend/routers/stocks.py` — one request answers both "is it tracked" and "what is its tag" (R11). **Free**: the endpoint already returns the full `ticker_index` document verbatim, so no edit was needed
- [X] T024 [US3] Add the `sentiment` query param to `get_feed` in `backend/routers/analysis.py` using the **two-step** approach (R11): resolve tagged tickers from `TICKER_INDEX`, then constrain the `analyses` query with `filter["ticker"] = {"$in": tickers}`. Not a `$lookup`. **Note**: combined with the existing ticker-substring filter via `$and` (both constrain the `ticker` field; a plain dict assignment would have silently dropped one)
- [X] T025 [P] [US3] Add `Sentiment` type and the `sentiment` field on the ticker-record type in `frontend/src/api/types.ts`. Landed as an exported `TickerRecord` interface in `hooks/useAnalysis.ts` (replacing an inline anonymous type) rather than in `api/types.ts`, so the type lives next to its one call site
- [X] T026 [P] [US3] Create `frontend/src/hooks/useSentiment.ts` — set and clear mutations; on success invalidate `["ticker-record", symbol]` and `["feed"]`. **No optimistic update** (the server decides the toggle-off result). **Correction from contract**: invalidates the query key `useTickerRecord` actually uses, `["ticker", TICKER]`, not the contract's assumed `["ticker-record", symbol]`
- [X] T027 [US3] Create `frontend/src/components/stock/SentimentButtons.tsx` — thumbs up/down with `aria-label` and `aria-pressed`; renders **nothing at all** when the ticker record is absent (not a disabled control); active state conveyed by fill/outline, not color alone
- [X] T028 [US3] Render `SentimentButtons` in `frontend/src/pages/StockDetail.tsx` immediately after `<h1>{symbol}</h1>` and before the signal/conviction badges
- [X] T029 [US3] Add `liked` / `disliked` filter chips to `frontend/src/components/feed/FilterBar.tsx` using the existing `setFilter("sentiment", value)` toggle pattern
- [X] T030 [US3] Add `sentiment: searchParams.get("sentiment") ?? undefined` to the filters object in `frontend/src/pages/Stocks.tsx`
- [X] T031 [US3] Confirm persistence across a restart (FR-010): verified structurally — `sentiment`/`sentiment_at` are plain fields on the same `ticker_index` document that already persists `status`/`sources` across restarts (real MongoDB, no TTL); a live click-through restart check is folded into the Polish-phase full-stack rebuild (T092/T094) rather than repeated per story

**Checkpoint**: US1–US3 all work independently. **Verified**: frontend 365/365 (+12), backend 209/209 (+13; 6 new ruff findings — all `Depends()` B008, the codebase's existing FastAPI convention, not a new category).

---

## Phase 6: User Story 4 - Congress Trading Disclosures Tab (Priority: P3)

**Goal**: A Congress page listing Senate/House disclosures with a computed summary, two filters, and ticker navigation

**Independent Test**: Open Congress from the nav, refresh, filter by ticker and by person, click a ticker through to its stock page

> **T032 must come first.** Field *names* are confirmed (R7) but exact JSON casing is not.

### Fixture capture (do this first)

- [X] T032 [US4] **Substituted for a live capture**: the field *set* was already confirmed against a real user-supplied `senate-latest`/`house-latest` response during the planning session (research.md R7, captured verbatim in the plan/spec history) — a fresh live call wasn't repeated here since the sample data was already in hand. Pinned that confirmed data as `agent-runner/tests/fixtures/senate_latest.json` / `house_latest.json`, using my best-guess camelCase JSON keys (`symbol`, `senateId`, `disclosureDate`, `transactionDate`, `firstName`, `lastName`, `office`, `district`, `owner`, `assetDescription`, `assetType`, `type`, `amount`, `link`) since the user's paste showed display column headers, not raw JSON. **Residual risk carried forward, not eliminated**: exact key casing is still unverified against the live API — the normalizer's candidate-key-set tolerance (T043) is what actually protects against a casing mismatch, not this fixture

### Tests for User Story 4

- [X] T033 [P] [US4] Create `agent-runner/tests/test_congress.py` normalizer cases against the T032 fixtures: `politician` built from `firstName`+`lastName` with `office` fallback; empty `symbol` stored as `None` not `""`; a row with neither ticker nor politician is skipped with a log, not raised
- [X] T034 [P] [US4] Add `trade_id` cases to the same file: a same-day Purchase and Sale of one ticker by one member produce **different** ids; the same trade under `owner: "Joint"` vs `"Self"` produce **different** ids (R7 — these collide and silently overwrite if the hash omits those fields)
- [X] T035 [P] [US4] Add `parse_amount_bounds` cases: the real `"$1,001 - $15,000"` form; the exact `$100,001` boundary (**inclusive**); the bracket immediately below (excluded); open-ended `"Over $1,000,000"`; en-dash and hyphen separators; absent; unparseable garbage → `None`, never raises
- [X] T036 [P] [US4] Add `is_purchase` cases: `"Purchase"` true; `"Sale"`, `"Sale (Full)"`, `"Sale (Partial)"` all false; mixed case; `None`
- [X] T037 [P] [US4] Add `rank_most_bought` cases: counts only purchases in the 90-day `disclosure_date` window; null-ticker rows excluded; ties broken by ticker ascending (stable ordering); a row just inside and just outside the window
- [X] T038 [P] [US4] Add `high_dollar` cases: selects on the bracket's **upper bound ≥ $100,001**; never derives a midpoint or point value (FR-016a); unparseable/absent amount excluded from flagging but still present in the main listing. **Also added** (not separately enumerated): `run_congress_trades_pull` cases — both chambers stored, one chamber failing doesn't lose the other, raises only when both fail, upsert idempotency. 36 cases total across T033–T038, all passed on first implementation run
- [X] T039 [P] [US4] Create `backend/tests/test_congress.py`: `/congress/trades` ticker filter, politician filter, both combined, chamber filter, limit cap; empty collection returns 200 with an empty list; `/congress/summary` shape; `/congress/refresh` enqueue then `already_queued` on a second call. **Extra case added**: a bioguide-id-shaped politician query (e.g. `"D000001"`) matches `person_id` exactly rather than falling to name substring. 14 cases, all passed on first implementation run
- [X] T040 [P] [US4] Add a dispatch case to `agent-runner/tests/test_queue_worker.py` for `job_type="congress_trades_pull"`, and a registration case to `agent-runner/tests/test_admin_jobs.py`. **Widened while there**: also added registration assertions for `market_movers_pull`/`sector_etf_pull` (US6/US5), which had no dedicated registration test yet. **Verified**: agent-runner 477/477 (+2), ruff clean
- [X] T041 [P] [US4] Create `frontend/src/components/congress/CongressTable.test.tsx`: a row with a ticker renders a link to `/stock/<TICKER>`; a **null-ticker row renders no link element at all** (FR-018); both dates are shown. 5 cases, all passed on first implementation run
- [X] T042 [P] [US4] Create `frontend/src/components/congress/CongressSummary.test.tsx`: amounts render as the verbatim bracket string, never a number; an empty `high_dollar` array renders the explicit "none in this window" message rather than hiding the section (FR-016b). 4 cases; one initial assertion collided on a fixture reusing "NVDA" in both sections (test bug, not component) and was disambiguated

### Implementation for User Story 4

- [X] T043 [P] [US4] Created `agent-runner/tools/congress.py` with the pure helpers first: `parse_amount_bounds`, `is_purchase`, `_trade_id`, `_normalize_row`, `rank_most_bought`, `high_dollar` — per [contracts/congress-api.md](./contracts/congress-api.md). All windows filter `disclosure_date`, never `transaction_date` (R8)
- [X] T044 [US4] Added `run_congress_trades_pull(db)` to the same file: `fmp_get("senate-latest")` and `fmp_get("house-latest")` in **separate** try/except blocks so one chamber failing does not lose the other's rows; upsert on `trade_id`; raises only if both chambers fail
- [X] T045 [US4] Registered `"congress_trades_pull": run_congress_trades_pull` in `JOB_HANDLERS`/`STALE_MINUTES` (15 min) in `agent-runner/tools/admin_jobs.py`. **Also registered** in `JOB_DATASETS` (dataset `"congress_trades"`, per 017's table) — a single `record_count` correctly represents a one-chamber-failed partial success here, unlike `economics_pull`'s exclusion
- [X] T046 [P] [US4] Added `congress_trades` indexes in `agent-runner/tools/db.py`: unique `trade_id`, `(disclosure_date DESC)`, `(ticker, disclosure_date DESC)`, `(person_id)`. **Verified**: agent-runner 475/475 (+36), ruff clean
- [X] T047 [US4] Created `backend/routers/congress.py` with `GET /congress/trades`, `GET /congress/summary`, and `POST /congress/refresh`. The refresh handler mirrors `portfolio.py::regenerate_digest` exactly, including the `{job_type, status ∈ pending|running}` dedupe (R4). Summary math (`is_purchase`/`parse_amount_bounds`/`rank_most_bought`/`high_dollar`) is hand-synced verbatim from `agent-runner/tools/congress.py`, per the `price_store.py` duplication precedent (Principle V/VI). **One addition beyond the contract**: the politician filter matches `person_id` exactly when the value looks like a bioguide id (`^[A-Za-z]\d{6}$`), falling back to substring-on-name otherwise
- [X] T048 [US4] Registered `congress.router` in `backend/main.py`. **Verified**: backend 231/231 (+14), ruff +5 (3 new `Depends()` endpoints + 2 files' `EXE002`, same established pattern)
- [X] T049 [P] [US4] Added `Chamber`/`CongressTrade`/`CongressTradesResponse`/`CongressMostBought`/`CongressHighDollarTrade`/`CongressSummaryResponse` types to `frontend/src/api/types.ts`
- [X] T050 [P] [US4] Created `frontend/src/hooks/useCongress.ts` — `useCongressTrades(filters)` keyed on `["congress", "trades", filters]`, `useCongressSummary()` keyed on `["congress", "summary"]`, and the refresh mutation
- [X] T051 [P] [US4] Created `frontend/src/components/congress/CongressTable.tsx` — columns chamber, politician, ticker, asset description, type, amount range, transaction date, disclosure date. Ticker links to `/stock/<TICKER>`; null ticker renders `—` with **no link element**. Both dates shown (filing lags of over a year are normal in the confirmed sample data)
- [X] T052 [P] [US4] Created `frontend/src/components/congress/CongressSummary.tsx` — most-bought list with counts; high-dollar list showing bracket text verbatim; each with its own explicit empty message
- [X] T053 [US4] Created `frontend/src/pages/Congress.tsx` — summary above table, debounced ticker and politician filter inputs written to URL search params (`useDebounce`, same guarded-effect pattern as `FilterBar.tsx`), a Refresh button, and **two distinct empty states**: "no disclosures match the current filter" when a filter is active vs. "click Refresh" when genuinely never pulled (matching US2's Portfolio Summary precedent, not separately required by the plan but consistent with it). Added `{ to: "/congress", label: "Congress" }` to `Navbar.tsx` and the `/congress` route to `App.tsx` (before the catch-all)

**Checkpoint**: US1–US4 all work independently. **Verified**: frontend 388/388 (+9), backend 231/231, agent-runner 477/477 — full three-suite pass, plus a clean `tsc --noEmit` type-check with no errors.

---

## Phase 7: User Story 5 - Sector Momentum Charts (Priority: P4)

**Goal**: An 11-ETF percentage-change comparison chart with a switchable window

**Independent Test**: Open Sectors, refresh, confirm 11 lines all starting at 0%, and that switching windows re-rebases every line

### Tests for User Story 5

- [X] T054 [P] [US5] Create `frontend/src/lib/rebaseToPercent.test.ts`: normal series (first point exactly `0`); empty input → empty; single bar → one point at `0`; **first close of `0` → empty rather than dividing by zero**. 6 cases; one initially used exact float equality and needed `toBeCloseTo` (floating-point, not an implementation bug)
- [X] T055 [P] [US5] Create `agent-runner/tests/test_sector_etfs.py`: all 11 tickers attempted; **one ticker raising does not abort the other ten** (FR-021 at the data layer); returns the count with usable bars. 5 cases, confirmed red before implementation
- [X] T056 [P] [US5] Create `backend/tests/test_sectors.py` additions (plan named `test_sector_etf_series.py`; landed in the existing `test_sectors.py` since `/etf-series` lives in the same router as `/sectors`): `window` accepts exactly `1m|3m|6m|1y` and **422s on anything else**; all 11 entries are present even when some have zero bars; `partial: true` for an entry with no bars or history starting after the window; only `date` and `close` are projected. 9 cases, confirmed red before implementation
- [X] T057 [P] [US5] Create `frontend/src/components/sectors/SectorEtfChart.test.tsx`: a zero-bar series does not prevent the others rendering and is named in the note; window selection round-trips through `?window=`. **Deviation from the plan**: "all 11 tickers appear in the legend" could not be asserted via RTL — confirmed the project's own established precedent (`YieldCurveChart.test.tsx`'s comment) that Recharts' `Legend`/`Line` children don't render into jsdom's zero-size `ResponsiveContainer` even with geometry mocked. Legend/line-color correctness is covered by code review instead (one `<Line>` per `data.series` entry, `TICKER_COLORS` keyed by ticker); tests assert the component renders a full 11-series response without crashing plus every piece of plain-React UI (buttons, empty/unavailable states, the partial note — which is not Recharts output and does render). 8 cases total, confirmed red before implementation

### Implementation for User Story 5

- [X] T058 [P] [US5] Create `frontend/src/lib/rebaseToPercent.ts` — `(close / first - 1) * 100`, guarding a zero first close
- [X] T059 [P] [US5] Create `agent-runner/tools/sector_etfs.py` — the 11-ticker constant list with display labels, and a handler looping `price_store.get_series(ticker, refresh="delta", db=db)` with each ticker wrapped individually. `price_store` is used **unchanged** (R5)
- [X] T060 [US5] Register `"sector_etf_pull"` in `JOB_HANDLERS`/`STALE_MINUTES` in `agent-runner/tools/admin_jobs.py` (the one job name not already in 017's registry — R5). **Not** added to `JOB_DATASETS` — partial per-ticker success (e.g. 10/11) doesn't map cleanly onto the generic unconditional-success dataset_meta write, same exclusion reasoning as `economics_pull`
- [X] T061 [P] [US5] Mirrored the 11-ticker constant list (`SECTOR_ETF_LABELS`) into `backend/routers/sectors.py`, per the hand-sync convention (Principle VI)
- [X] T062 [US5] Added `GET /sectors/etf-series?window=` and `POST /sectors/etf-series/refresh` to `backend/routers/sectors.py`, registered **before** the existing `GET /sectors/{sector}` route — required, since FastAPI matches path routes in registration order and `/sectors/etf-series` would otherwise be swallowed as `sector="etf-series"`. Windows slice against the series' own latest stored date, not "today" (a pull can run a day or two stale). **Verified**: backend 217/217 (+9), ruff +2 (both endpoints' own `Depends()`, same established pattern)
- [X] T063 [P] [US5] Added `SectorEtfWindow`/`SectorEtfBar`/`SectorEtfSeries`/`SectorEtfSeriesResponse` types to `frontend/src/api/types.ts`
- [X] T064 [P] [US5] Created `frontend/src/hooks/useSectorEtfSeries.ts` — query keyed on `["sector-etf-series", window]`, plus the refresh mutation
- [X] T065 [US5] Created `frontend/src/components/sectors/SectorEtfChart.tsx` — Recharts `LineChart` in a `ResponsiveContainer` following `macro/YieldCurveChart.tsx`; 11 distinctly-colored lines (`TICKER_COLORS`, 11 Tailwind -400 shades) each paired with a Recharts `Legend` entry; percent-formatted Y axis with a `ReferenceLine` at 0; window selector (own component-owned `useSearchParams`, not lifted to the page) stored in `?window=`; a plain-text note listing any `partial` series. A `mergeForChart` helper unions each rebased series onto a shared date axis with `connectNulls` bridging gaps, since Recharts needs one aligned data array, not 11 independent ones
- [X] T066 [US5] Rendered `SectorEtfChart` on the Sectors overview in `frontend/src/pages/Sectors.tsx`, with an empty state naming the Refresh control. Restructured `SectorOverview`'s loading/error/empty early-returns into a single `body` variable so the chart (independent data source) renders exactly once above all four states, rather than duplicating the `<h1>`/chart pair four times

**Checkpoint**: US1–US5 all work independently. **Verified**: frontend 379/379 (+14), backend 217/217, agent-runner 439/439 — full three-suite pass, no regressions.

---

## Phase 8: User Story 6 - Top Traded Stocks Section (Priority: P4)

**Goal**: A most-actives panel below the Stocks grid

**Independent Test**: Scroll below the ticker grid on the Stocks page, refresh, confirm most-active stocks list and link through

> **The `most-actives` endpoint returns no `volume`** (R9). Ordering comes from a stored
> `rank`, and `changesPercentage` is already a percent.

### Tests for User Story 6

- [X] T067 [P] [US6] Create `agent-runner/tests/test_market_movers.py`: rows are stamped `category: "actives"` and `rank` = array index; `volume` is `None`; upserting the same day twice is idempotent; a provider failure leaves prior rows intact rather than clearing them. 9 cases, all confirmed red (ImportError) before implementation
- [X] T068 [P] [US6] Add most-actives cases to `backend/tests/test_market.py`: returns the latest available `date`, ordered by **`rank` ascending**; `limit` cap enforced; empty collection returns 200 with an empty list and null `date`. 7 cases, confirmed red before implementation
- [X] T069 [P] [US6] Create `frontend/src/components/feed/MostActivesPanel.test.tsx`: rows render in `rank` order; tickers link to `/stock/<TICKER>`; empty renders the empty state; error renders the unavailable message (FR-024); **`change_pct` of `3.35196` renders as `+3.35%`, not `+335.20%`**. 8 cases, confirmed red before implementation

### Implementation for User Story 6

- [X] T070 [P] [US6] Create `agent-runner/tools/market_movers.py` — `fmp_get("most-actives")`, map `symbol→ticker`, `name→company`, `price`, `change`, `changesPercentage→change_pct`, `exchange`, stamping `date`, `category: "actives"`, and `rank`. Upsert on `(date, category, ticker)`. **No try/except**: a provider failure propagates naturally (matching `run_portfolio_digest`'s pattern) since nothing is written before the fetch succeeds, so prior rows survive untouched and the caller (`queue_worker._run_admin_job`) correctly marks the job failed
- [X] T071 [US6] Registered `"market_movers_pull"` in `JOB_HANDLERS` and `"market_movers_pull": 10` in `STALE_MINUTES` in `agent-runner/tools/admin_jobs.py`. **Also registered** `JOB_DATASETS["market_movers_pull"] = "market_movers"` (not separately enumerated in the plan) — this handler is a simple atomic-per-run job with no economics_pull-style partial-failure nuance to preserve, so the generic success/failed dataset_meta write is accurate
- [X] T072 [P] [US6] Added the `market_movers` index `(date DESC, category, rank ASC)` plus unique `(date, category, ticker)` in `agent-runner/tools/db.py`. **Verified**: agent-runner 434/434 (+9), ruff clean
- [X] T073 [US6] Added `GET /market/most-actives?limit=` and `POST /market/most-actives/refresh` to `backend/routers/market.py` — sorts by `rank` ascending, strips internal bookkeeping fields (`date`/`category`/`rank`/`source`/`collected_at`) and `volume` from each returned item. **Verified**: backend 208/208 (+7), ruff +2 (both new endpoints' own `Depends()`, same established pattern)
- [X] T074 [P] [US6] Added `MostActive`/`MostActivesResponse` types to `frontend/src/api/types.ts`
- [X] T075 [P] [US6] Created `frontend/src/hooks/useMostActives.ts` — query plus refresh mutation. **Also fixed a pre-existing bug found in passing**: `useQueue.ts`'s drain-invalidation handler still invalidated `["pull-metrics"]`, a query key nothing has created since US7 deleted `usePullMetrics.ts` — removed it, and added `["most-actives"]` (this task) plus `["sector-etf-series"]`/`["congress"]` (staged ahead for US5/US4) to the same handler
- [X] T076 [US6] Created `frontend/src/components/feed/MostActivesPanel.tsx` — ticker, company, price, change, change % (**no volume column**); tickers link to `/stock/<TICKER>`; shows the served session date; distinct empty and unavailable states
- [X] T077 [US6] Rendered `MostActivesPanel` in `frontend/src/pages/Stocks.tsx` on the `grid` tab, **below the tile grid and inside the grid column** (not beside the digest panel)

**Checkpoint**: US1–US6 all work independently. **Verified**: frontend 365/365 (+8), backend 208/208, agent-runner 434/434 — full three-suite pass with no regressions.

---

## Phase 9: User Story 7 - Remove Pull Diagnostics (Priority: P5)

**Goal**: The Pull cost panel and all its stored data are gone, with pulls unaffected

**Independent Test**: Open a stock page and find no Pull cost section; pull a ticker and confirm the analysis still completes

> **Order matters** (R12): frontend → endpoint → writer → storage. Each step below leaves
> the tree in a working state.

### Tests for User Story 7

- [X] T078 [P] [US7] Add a case to `frontend/src/pages/StockDetail.test.tsx` asserting no "Pull cost" text is present, for a ticker both with and without prior analysis. **Strengthened beyond the plan**: the pull-metrics endpoint mock now returns real stage data (not the file's default empty-object fallback), so this test genuinely rendered "Pull cost" before removal — confirmed red — rather than passing vacuously
- [X] T079 [P] [US7] Add a case to `agent-runner/tests/test_queue_worker.py` asserting a completed job writes **no** `pull_metrics` document **and still produces its analysis normally** (FR-026b — the regression that matters most here). Confirmed red (collection existed) before removal

### Implementation for User Story 7 — frontend first

- [X] T080 [US7] Remove the `PullCostPanel` import and render from `frontend/src/pages/StockDetail.tsx`, and the `usePullMetrics` import and call
- [X] T081 [P] [US7] Delete `frontend/src/components/stock/PullCostPanel.tsx` and `frontend/src/components/stock/PullCostPanel.test.tsx`
- [X] T082 [P] [US7] Delete `frontend/src/hooks/usePullMetrics.ts`
- [X] T083 [P] [US7] Remove the `Pull` and `PullStage` types from `frontend/src/api/types.ts`. Also removed `StageRetrieval`/`StageOutcome`/`PullMetrics` (all diagnostics-only). **Kept `PullMode`** — confirmed still used by `useQueue.ts` for the unrelated delta/full refresh mode selector (024)

### Then the endpoint

- [X] T084 [US7] Remove `get_pull_metrics`, `MAX_PULL_METRICS`, and the `PULL_METRICS` import from `backend/routers/stocks.py`. **Also removed** the 8 now-orphaned pull-metrics endpoint tests from `backend/tests/test_routers.py` (not separately enumerated in the plan, but required — they would otherwise fail against the deleted route)

### Then the writer

- [X] T085 [US7] Remove `_write_pull_metrics`, `_record_pull_metrics`, their three call sites, and the `PULL_METRICS` import from `agent-runner/queue_worker.py`. **Did not touch `metrics.record_call` in `fmp_client.py`** or `crew.last_pull` — confirmed in-process instrumentation, unrelated to the removed collection
- [X] T086 [US7] Deleted the obsolete "persistence (queue_worker)" section (3 tests) from `agent-runner/tests/test_pull_metrics.py`, keeping its ~10 `crew.last_pull` instrumentation tests intact (retitled the file's docstring to reflect the narrower scope). Also removed one now-orphaned index-assertion test from `agent-runner/tests/test_db.py`

### Then the storage

- [X] T087 [P] [US7] Deleted the two `PULL_METRICS` index declarations from `agent-runner/tools/db.py` and the constant
- [X] T088 [P] [US7] Deleted the `PULL_METRICS` constant from `backend/db.py`
- [X] T089 [US7] Rebuilt and redeployed all three service images (Polish phase), then dropped the live `pull_metrics` collection (25 stale documents) via `mongosh`. **Verified the drop is durable, not just a point-in-time state**: restarted `agent-runner` afterward and confirmed the collection was not recreated — proving the index declarations were genuinely removed from the deployed code, not merely from the source tree.

**Checkpoint**: All seven stories complete. **Verified**: agent-runner 425/425 (−4 obsolete, +1 new — net accounted for exactly), backend 201/201 (−8, ruff **96, down 1** — the removed endpoint's own `Depends()` finding went with it), frontend 357/357 (−8 net: panel's own test file removed, +2 replacement assertions).

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T090 Confirmed no pull-metrics references survive: only matches are `test_pull_metrics.py` (deliberately kept, narrowed to `crew.last_pull` in-process instrumentation which was never removed) and `test_queue_worker.py`'s own regression test asserting the *absence* of the collection. No genuine leftover in any source file.
- [X] T091 [P] Ran `ruff check` on both services. Agent-runner: clean throughout the whole feature. Backend: 94 (baseline) → 105 — verified every one of the 11 new findings is `B008`(`Depends()` default arg, the codebase's pre-existing FastAPI convention) or `EXE002` (no shebang, same baseline pattern) in files this batch touched; the handful of `BLE001`/`DTZ00x` findings elsewhere in the 105 were confirmed to be pre-existing, in files never touched by this batch (one just shifted line number from an insertion above it). No new problem categories introduced.
- [X] T092 [P] Ran the full suites repeatedly at every story checkpoint and once more at the end: **backend 231/231**, **agent-runner 477/477**, **frontend 388/388** (plus a clean `tsc --noEmit`) — all green, growth fully accounted for against the T001 baseline (196/425/336).
- [X] T093 Verified the FMP budget claim (R13) by code inspection (no live network access in this sandbox): all three new jobs confirmed to route through the throttled/budget-guarded `fmp_client.fmp_get` (`congress.py`, `market_movers.py` directly; `sector_etfs.py` via `price_store._fetch → fetch_eod_history → fmp_get`). Confirmed `refresh.mutate()` appears only inside `onClick` handlers across all three new frontend surfaces, never inside a `useEffect` — no automatic refresh on page load.
- [X] T094 Walked [quickstart.md](./quickstart.md) against the real implementation and corrected three inaccuracies found in the process: the `/queue` curl example used the wrong path/method (`POST /queue/{ticker}`, not a JSON body to `/queue`); a referenced `/market/fmp-usage` endpoint doesn't exist (replaced with the direct `mongosh` check); the Gates section's plain `cd backend && pytest` doesn't work in this environment (no bind mounts) — replaced with the `docker compose run -v` pattern actually used throughout implementation. Also updated the US4 fixture step to reflect that the fixture is already pinned, and added the bioguide-id person-filter tip.
- [X] T095 Updated `specs/component-specs/` for `Stocks.md`, `Sectors.md`, `StockDetail.md`, `Navbar.md`, and `FilterBar.md` with concise "Amendments" sections (these predate this batch and were already substantially stale relative to shipped code — e.g. `Navbar.md` described an unimplemented global-search dropdown — so amendment notes were used rather than attempting an out-of-scope full rewrite), and created `Congress.md` for the new page.

**Full-stack rebuild performed**: `docker compose build backend agent-runner frontend` then `docker compose up -d` — all five services healthy. Live-verified: `GET /congress/trades`, `GET /sectors/etf-series`, `GET /market/most-actives` all respond correctly (empty states, since nothing pulled yet on the fresh deploy); `GET /stocks/{ticker}/pull-metrics` returns 404 (route gone); `PUT /stocks/ZZZZ/sentiment` returns 404 (untracked ticker, FR-006a enforced live). Dropped the stale `pull_metrics` collection (25 documents) via `mongosh`, then restarted `agent-runner` and confirmed the collection was **not** recreated — proving the index removal is real in the deployed code, not just the source tree.

---

## Shared File Conflicts

The real cross-story hazard in this batch. These files are touched by multiple stories —
**do not parallelize across stories on them**:

| File | Stories | Note |
|---|---|---|
| `frontend/src/api/types.ts` | US2, US3, US4, US5, US6, US7 | Six stories, including one deletion. Serialize; expect merge conflicts otherwise |
| `agent-runner/tools/admin_jobs.py` | US4, US5, US6 | Three job registrations in one dict |
| `agent-runner/tools/db.py` | US4, US6, US7 | Two index additions and one removal |
| `frontend/src/pages/Stocks.tsx` | US3, US6 | Filter passthrough vs. panel placement |
| `frontend/src/pages/StockDetail.tsx` | US3, US7 | Adding buttons vs. removing the panel |
| `frontend/src/App.tsx` | US1, US4 | Catch-all route vs. Congress route — **the catch-all must stay last** |
| `agent-runner/tests/test_queue_worker.py` | US4, US7 | Dispatch addition vs. test deletion |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001-T002)**: no dependencies
- **Foundational (T003)**: near-empty by design — see the Phase 2 note
- **User stories (Phases 3-9)**: all independent of one another; sequence by priority or staff in parallel subject to the Shared File Conflicts table
- **Polish (Phase 10)**: after all desired stories

### Within-Story Ordering

- **US1**: T004-T005 (failing tests) → T006-T008
- **US2**: T013 before T017's verification; T012 before T015-T016
- **US3**: T022-T024 (backend) before T026-T030 (frontend consumers)
- **US4**: **T032 (fixture) blocks everything else**; T043 (pure helpers) before T044 (job) before T045 (registration); T047-T048 before T050-T053
- **US5**: T059 before T060; T058 before T065; T062 before T064
- **US6**: T070 before T071; T073 before T075
- **US7**: strictly frontend → endpoint → writer → storage (T080-T083 → T084 → T085-T086 → T087-T089)

### Parallel Opportunities

- All test-authoring tasks within a story are `[P]` — different files
- US4's eight test tasks (T033-T042) parallelize well and are the largest such cluster
- Across stories: US1, US2, US3 touch no provider code and can proceed while US4's fixture capture is pending

---

## Parallel Example: User Story 4

```bash
# After T032 (fixture) lands, launch the pure-function test suites together:
Task: "parse_amount_bounds cases in agent-runner/tests/test_congress.py"       # T035
Task: "is_purchase cases in agent-runner/tests/test_congress.py"               # T036
Task: "rank_most_bought cases in agent-runner/tests/test_congress.py"          # T037
Task: "high_dollar cases in agent-runner/tests/test_congress.py"               # T038

# And the independent frontend component tests:
Task: "CongressTable.test.tsx"                                                  # T041
Task: "CongressSummary.test.tsx"                                                # T042
```

---

## Implementation Strategy

### MVP (User Story 1 only)

T001-T003, then T004-T008. Five tasks, one of them a one-word change. Fixes a
user-visible broken interaction and is independently shippable.

### Recommended increments

1. **US1** — the blank-page fix (tiny, immediate value)
2. **US2 + US3** — pure app-layer work, no provider dependency
3. **US7** — the removal; independent, and shrinks the surface before the big additions
4. **US6** — smallest provider-backed surface, proves the R4 refresh pattern end to end
5. **US5** — reuses `price_store`, no new ingestion logic
6. **US4** — largest; benefits from the refresh pattern being proven in US6 first

Deliberately not priority order: US7 lands early because a removal is easier to reason
about before six other things move, and US6 precedes US4 so the per-surface refresh
pattern (R4) is validated on the simplest case before the most complex one depends on it.

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks
- Tests are required (Principle I), not optional — write them before the implementation
  they cover
- Commit per task or per logical group; reference `specs/028-dashboard-tweaks-batch/`
- Every provider call must route through `fmp_client.fmp_get` / `fetch_eod_history` —
  never a direct `requests.get` (Principle IV)
- No LLM call is added anywhere in this batch; every summary is arithmetic (Principle III)
