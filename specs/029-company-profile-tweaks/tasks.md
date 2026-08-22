# Tasks: Company Profile, Peers & Navigation Tweaks

**Input**: Design documents from `/specs/029-company-profile-tweaks/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included — constitution Principle I is NON-NEGOTIABLE for this project ("A pull request that adds behavior without a corresponding test is incomplete"). Backend routers and agent-runner tools get pytest coverage of their contracts; frontend components with user-facing logic get Vitest + RTL coverage.

**Organization**: Grouped by user story per spec.md's priorities (US1/US2/US3 = P1, US4/US5/US6 = P2, US7 = P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps the task to spec.md's user stories (US1–US7)
- Every task names an exact file path

---

## Phase 1: Setup

**Purpose**: Prerequisites that cost nothing to do first and unblock everything else.

- [X] T001 [P] Add `"stock_peers": "stock-peers?symbol=AAPL"` and `"employee_count": "historical-employee-count?symbol=AAPL"` to `PROBE_ENDPOINTS` in `agent-runner/tools/fmp_client.py` (research R4)
- [X] T002 [P] Add `db[COMPANY_INFO].create_index([("ticker", ASCENDING)], unique=True)` to `ensure_indexes()` in `agent-runner/tools/db.py` (data-model.md §1)

**Checkpoint**: Entitlement probe covers all three new families; the collection this feature populates has its index.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The company-profile data pipeline. **Blocks US2, US3, US5, US6, US7.** Does **not** block US1 (News nav) or US4 (Sectors chart) — both are pure UI changes with zero dependency on profile data, and may be built in parallel with this phase.

**⚠️ CRITICAL**: No task in US2/US3/US5/US6/US7 may start until this phase's checkpoint.

- [X] T003 [P] Contract test: `get_profile()` fetch + cache-window + degradation matrix (confirmed/unavailable/retry-on-next-pull) in `agent-runner/tests/test_company_profile.py` (contracts/company-profile-api.md, research R2)
- [X] T004 [P] Contract test: `get_peers()` fetch + 90-day window in `agent-runner/tests/test_company_profile.py`
- [X] T005 [P] Contract test: `get_employee_counts()` fetch + 90-day window in `agent-runner/tests/test_company_profile.py`
- [X] T006 Contract test: `refresh_company_info()` orchestration (depends on T003-T005 existing in the same file) — delta mode respects each dataset's own window, `mode="full"` bypasses all three, an `unavailable` outcome is retried next pull without sliding the other datasets' `fetched_at` (018-lesson regression test) in `agent-runner/tests/test_company_profile.py`
- [X] T007 Implement `get_profile(ticker, db=None)` in `agent-runner/tools/company_profile.py` — calls `fmp_get("profile?symbol={t}")` through `tools/fmp_client`, normalizes camelCase→snake_case, sets `default_image`-aware `image`/`logo_url` handling (research R6, contracts/company-profile-api.md)
- [X] T008 Implement `get_peers(ticker, db=None)` in `agent-runner/tools/company_profile.py` — calls `fmp_get("stock-peers?symbol={t}")`
- [X] T009 Implement `get_employee_counts(ticker, db=None)` in `agent-runner/tools/company_profile.py` — calls `fmp_get("historical-employee-count?symbol={t}")`
- [X] T010 Implement `refresh_company_info(ticker, mode="delta", db=None)` in `agent-runner/tools/company_profile.py` — `CACHE_DAYS = 90`; profile always refetched; peers/employee_counts refetched only when `*_fetched_at` older than 90d, `unavailable` outcome, or `mode="full"`; writes/upserts the `company_info` document with all `*_fetched_at`/`*_outcome` markers per data-model.md §1; catches `requests.HTTPError` (402/403→`unavailable`) and `FmpBudgetExceededError` per the degradation matrix; never raises
- [X] T011 Denormalize `sector`, `industry`, `name`, `logo_url` onto the ticker's `ticker_index` document inside `refresh_company_info` (data-model.md §2) — `logo_url` is `null` when `default_image` is true or no profile exists
- [X] T012 Register `refresh_company_info` as a stage in `Crew._prefetch`'s `jobs` dict in `agent-runner/crew.py`, passing `mode` through so a full refresh bypasses the cache windows (FR-008b) — verify the analyses document's shape is otherwise unchanged (research R5: no `sector` added to it)
- [X] T013 [P] Backend contract test: `GET /stocks/{ticker}/profile` — 200 with correct field mapping (`range` split into `range_low`/`range_high`), 404 when no profile stored, `price`/`change`/`change_percentage`/`volume` absent from the response (FR-011b) in `backend/tests/test_company_profile.py`
- [X] T014 [P] Backend contract test: `GET /stocks/{ticker}/peers` — sorted market cap descending, nulls last, ties broken by symbol; empty list is 200 in `backend/tests/test_company_profile.py`
- [X] T015 [P] Backend contract test: `GET /stocks/{ticker}/employee-count` — sorted `period_of_report` ascending; empty list is 200 in `backend/tests/test_company_profile.py`
- [X] T016 Implement `GET /stocks/{ticker}/profile` in `backend/routers/stocks.py` — reads `company_info`, splits `range` string into `range_low`/`range_high`, omits price/change/volume, returns 404 on no document (contracts/company-profile-api.md)
- [X] T017 Implement `GET /stocks/{ticker}/peers` in `backend/routers/stocks.py` — server-side sort by market cap descending/nulls-last/symbol tiebreak
- [X] T018 Implement `GET /stocks/{ticker}/employee-count` in `backend/routers/stocks.py` — server-side sort by `period_of_report` ascending
- [X] T019 [P] Add `CompanyProfile`, `Peer`, `EmployeeCountRecord` types to `frontend/src/api/types.ts` matching the three new endpoint responses
- [X] T020 [P] Implement `components/shared/CompanyLogo.tsx` — `src`/`ticker`/`size` props, null-src and `onError` both fall back to a monogram tile, `loading="lazy"`, fixed dimensions to prevent layout shift (research R6, contracts/company-profile-api.md)
- [X] T021 [P] Vitest for `CompanyLogo`: null src → fallback immediately (no network attempt asserted); `onError` fires → fallback swaps in; valid src → renders `<img>` in `frontend/src/components/shared/CompanyLogo.test.tsx`
- [X] T022 [P] Implement `hooks/useCompanyProfile.ts` exporting `useCompanyProfile(ticker)`, `usePeers(ticker)`, `useEmployeeCounts(ticker)` — TanStack Query, `refetchInterval: false`, `staleTime` 1h matching `usePriceHistory`; 404 on profile is a valid answer, not a retry-triggering error

**Checkpoint**: `company_info` populates on every pull; `ticker_index.sector`/`.industry`/`.logo_url` populate alongside it; all three read endpoints work; the frontend has types, a logo component, and data hooks ready to consume. US2, US3, US5, US6, US7 can now proceed (in parallel with each other).

---

## Phase 3: User Story 1 - News Is a Top-Level Destination (Priority: P1)

**Goal**: Market news reachable from the main nav; the Stocks page carries no News tab at all.

**Independent Test**: Click News in the nav from any page → market news renders on its own page. Visit the Stocks page → no News tab, grid is the only content. Zero dependency on Phase 2.

### Tests for User Story 1

- [X] T023 [P] [US1] Move `frontend/src/pages/Stocks.market-news.test.tsx` to `frontend/src/pages/News.test.tsx`, re-target it at the new `News` page component instead of `Stocks` (same fixtures/mocks, same assertions on content/behavior per FR-002)
- [X] T024 [P] [US1] Vitest: Navbar renders a News link and marks it active on `/news` in `frontend/src/components/layout/Navbar.test.tsx`
- [X] T025 [P] [US1] Vitest: Stocks page renders no `TabBar` / no News tab and the grid uses full width in `frontend/src/pages/Stocks.test.tsx`

### Implementation for User Story 1

- [X] T026 [US1] Create `frontend/src/pages/News.tsx` rendering `MarketNewsPanel` as the page's sole content (research R9)
- [X] T027 [US1] Add `<Route path="/news" element={<News />} />` to `frontend/src/App.tsx`
- [X] T028 [US1] Add a `{ to: "/news", label: "News" }` entry (after Stocks) to the `links` array in `frontend/src/components/layout/Navbar.tsx`
- [X] T029 [US1] In `frontend/src/pages/Stocks.tsx`: remove `TABS`, `DEFAULT_TAB`, the hash-tab `activeTab` logic, the `TabBar` render, and the `MarketNewsPanel` import/render — the page renders the grid unconditionally (research R9, FR-003)
- [X] T030 [US1] Update `specs/component-specs/frontend/pages/Stocks.md` to drop the News tab section

**Checkpoint**: News is a top-level nav destination; Stocks page has no tab bar. Independently shippable.

---

## Phase 4: User Story 2 - Company Profile Header on the Stock Page (Priority: P1)

**Goal**: The Overview tab's topmost section is company identity + headline stats; the page header shows the company logo.

**Independent Test**: Open a tracked stock's detail page → logo next to the ticker in the header; Overview tab's first section is the profile, with price/change/volume matching the Charts tab.

**Depends on**: Phase 2 checkpoint.

### Tests for User Story 2

- [X] T031 [P] [US2] Vitest `CompanyProfileSection`: renders identity + stats fields; price/change/volume computed from bars (not from the profile payload) and match a two-bar fixture's last-close math; single-bar fixture omits change without `NaN`; `is_etf`/`is_fund` fixture omits CEO/employees/industry; 404/no-profile fixture shows the unavailable state in `frontend/src/components/stock/CompanyProfileSection.test.tsx`

### Implementation for User Story 2

- [X] T032 [US2] Implement `frontend/src/components/stock/CompanyProfileSection.tsx` — identity row (logo, name, exchange, sector, industry, country), stats grid (price/change/change%/volume from `useStockPriceHistory` bars per research R7; market cap/beta/last dividend/52-week range/average volume from `useCompanyProfile`), description, website link, CEO, employees, IPO date, "profile as of {fetched_at}" line (FR-007, FR-010, FR-011, FR-011a)
- [X] T033 [US2] ETF/fund field omission: when `is_etf` or `is_fund` is true, omit CEO/employees/industry rows in `CompanyProfileSection.tsx` (edge case)
- [X] T034 [US2] "Profile unavailable" fallback state when the profile 404s, rendered without blocking the rest of the Overview tab, in `CompanyProfileSection.tsx` (FR-009)
- [X] T035 [US2] Render `CompanyProfileSection` as the first child of `OverviewTab`, above the existing Verdict `Section`, in `frontend/src/pages/StockDetail.tsx`
- [X] T036 [US2] Render `<CompanyLogo>` next to the ticker in the `StockDetail` page header, sourced from `useCompanyProfile`, in `frontend/src/pages/StockDetail.tsx` (FR-012)

**Checkpoint**: Overview tab has a working profile header; independently shippable alongside US1.

---

## Phase 5: User Story 3 - Logo and AI Summary on Hover, Portfolio Summary Retired (Priority: P1)

**Goal**: Portfolio digest subsystem fully removed; hover card shows full summary + logo; grid tiles carry a logo chip; grid spans full width.

**Independent Test**: Stocks page has no digest panel and a full-width grid; hovering a tile shows its complete AI summary with logo and name; no digest code, endpoint, or stored record remains anywhere.

**Depends on**: Phase 2 checkpoint (for `logo_url` on the feed response).

### Tests for User Story 3

- [X] T037 [P] [US3] Backend test: `GET /analysis/feed` response items carry `name`/`logo_url` sourced from `ticker_index`, fetched in one query per page (not per item) in `backend/tests/test_routers.py`
- [X] T038 [P] [US3] Vitest: `AnalysisTile` renders a logo chip beside the ticker without displacing the conviction dots; ticker remains legible; fallback renders when `logo_url` is null in `frontend/src/components/feed/AnalysisTile.test.tsx`
- [X] T039 [P] [US3] Vitest: `TilePreview` renders the full (untruncated) summary, logo, and company name; a stock with no analysis shows "no summary available"; a long summary stays scrollable/contained within the viewport in `frontend/src/components/feed/TilePreview.test.tsx`
- [X] T040 [P] [US3] Vitest: `Stocks` page renders no `PortfolioDigestPanel` and the grid container has no two-column wrapper in `frontend/src/pages/Stocks.test.tsx`

### Implementation for User Story 3 — hover card & tiles

- [X] T041 [US3] Enrich `GET /analysis/feed` in `backend/routers/analysis.py`: one `ticker_index` query for the page's tickers (`{"ticker": {"$in": page_tickers}}`), attach `name`/`logo_url` to each returned item (contracts/sector-and-industry.md)
- [X] T042 [P] [US3] Add `logo_url?: string | null` and confirm `name?: string | null` on `AnalysisFeedItem` in `frontend/src/api/types.ts`
- [X] T043 [P] [US3] Update `frontend/src/components/feed/AnalysisTile.tsx`: render a small `<CompanyLogo size="sm">` beside the ticker text (FR-021a)
- [X] T044 [P] [US3] Update `frontend/src/components/feed/TilePreview.tsx`: remove the `line-clamp-3` truncation, add `<CompanyLogo size="sm">` + company name next to the ticker, add a "no summary available" branch when `analysis.summary` is empty, keep the card's content scrollable if it exceeds viewport height (FR-020, FR-021, FR-022, FR-023)
- [X] T045 [US3] In `frontend/src/pages/Stocks.tsx`: remove the `PortfolioDigestPanel` import/render and the `lg:flex-row` two-column wrapper around the grid; grid renders alone at full width (FR-018)

### Implementation for User Story 3 — portfolio digest teardown (contracts/portfolio-digest-removal.md)

- [X] T046 [P] [US3] Delete `agent-runner/agents/portfolio_digest.py`
- [X] T047 [P] [US3] Delete `agent-runner/tools/portfolio.py`
- [X] T048 [P] [US3] Delete `agent-runner/tests/test_portfolio_digest.py`
- [X] T049 [P] [US3] Delete `backend/routers/portfolio.py`
- [X] T050 [P] [US3] Delete `backend/tests/test_portfolio.py`
- [X] T051 [P] [US3] Delete `frontend/src/components/feed/PortfolioDigestPanel.tsx` and `PortfolioDigestPanel.test.tsx`
- [X] T052 [P] [US3] Delete `frontend/src/hooks/usePortfolioDigest.ts` and `usePortfolioDigestRegenerate.ts`
- [X] T053 [P] [US3] Delete `frontend/src/lib/filterHighlights.ts` and `filterHighlights.test.ts`
- [X] T054 [US3] Remove the `"portfolio_digest"` entry and its import from `JOB_HANDLERS` in `agent-runner/tools/admin_jobs.py`
- [X] T055 [US3] Remove `PORTFOLIO_DIGEST_CACHE` constant from `agent-runner/tools/db.py`
- [X] T056 [US3] Reword the `run_portfolio_digest`-referencing docstring comment in `agent-runner/tools/market_movers.py:17` — comment only, no logic change (research R14 footgun)
- [X] T057 [US3] Remove the `portfolio` import and `app.include_router(portfolio.router)` from `backend/main.py`
- [X] T058 [US3] Remove `PORTFOLIO_DIGEST_CACHE` constant from `backend/db.py`
- [X] T059 [US3] Remove the `["portfolio-digest"]` query invalidation in `frontend/src/hooks/useQueue.ts` (~line 24-25)
- [X] T060 [US3] Remove portfolio-digest types (~line 648) from `frontend/src/api/types.ts` — **leave `pct_of_portfolio` (~line 519) untouched, it belongs to institutional holdings** (research R14 footgun)
- [X] T061 [US3] Remove digest-registration assertions from `agent-runner/tests/test_admin_jobs.py` and `agent-runner/tests/test_queue_worker.py`
- [X] T062 [US3] Verify `frontend/src/pages/Stocks.test.tsx` has no remaining digest assertions (superseded by T040, confirm no leftovers)
- [X] T063 [US3] Update `specs/component-specs/frontend/pages/Stocks.md` to remove the Portfolio Summary section
- [X] T064 [US3] Run the grep/curl/mongosh verification block from `contracts/portfolio-digest-removal.md`'s Verification section and confirm all four checks pass (code references gone except the reworded comment, endpoint 404s, collection dropped, no orphaned queue jobs)

**Checkpoint**: No portfolio-digest surface remains anywhere; grid is full-width with logo tiles and full-summary hover cards. Independently shippable.

---

## Phase 6: User Story 4 - Sectors Page: Taller Chart with Toggleable Series (Priority: P2)

**Goal**: Sector momentum chart is materially taller with per-series legend toggling.

**Independent Test**: Open Sectors page → chart is visibly taller; click a legend ticker → its line hides and the Y-axis re-fits; click again → returns; window change preserves hidden state; hiding all shows a distinct empty-plot state. Zero dependency on Phase 2 — pure frontend chart change.

### Tests for User Story 4

- [X] T065 [P] [US4] Vitest: `SectorEtfChart` renders at the new 440px height in `frontend/src/components/sectors/SectorEtfChart.test.tsx`
- [X] T066 [P] [US4] Vitest: clicking a legend entry hides that series (and toggles visible styling), clicking again restores it, in `SectorEtfChart.test.tsx`
- [X] T067 [P] [US4] Vitest: hidden-series state survives a window change (1M→1Y) in `SectorEtfChart.test.tsx`
- [X] T068 [P] [US4] Vitest: hiding every series renders a distinct "all series hidden" message, not the existing "no data" message, in `SectorEtfChart.test.tsx`
- [X] T069 [P] [US4] Vitest: a legend entry is keyboard-focusable and Enter/Space triggers the same toggle as a click in `SectorEtfChart.test.tsx`

### Implementation for User Story 4

- [X] T070 [US4] Raise `ResponsiveContainer height` from `280` to `440` in `frontend/src/components/sectors/SectorEtfChart.tsx` (research R10, FR-028)
- [X] T071 [US4] Add `hidden: Set<string>` component state and a toggle handler in `SectorEtfChart.tsx`
- [X] T072 [US4] Pass `hide={hidden.has(s.ticker)}` to each `<Line>` so Recharts excludes hidden series from Y-domain computation (research R11, FR-030)
- [X] T073 [US4] Implement a custom `<Legend content={...}>` renderer using real `<button>` elements (`role="button"`/native button, `aria-pressed`) so entries are keyboard-focusable and activatable, with reduced-opacity/line-through styling for hidden entries (FR-029, research R11)
- [X] T074 [US4] Render an "all series hidden" empty-plot message when `hidden.size === TICKER_COLORS` keys length, distinct from the existing no-data message (FR-032)

**Checkpoint**: Taller, toggleable sector chart. Independently shippable, no dependency on any other phase.

---

## Phase 7: User Story 5 - Sector Classification and Industry Filter from the Profile (Priority: P2)

**Goal**: Sectors page and feed filters read `ticker_index.sector`/`.industry` (the single source of truth); a new industry filter narrows the Stocks grid.

**Independent Test**: Sectors page shows real, populated buckets (closing the KNOWN_ISSUES bug) instead of a permanent empty state; clicking a sector's link returns exactly the count shown in its rollup; the Stocks page industry dropdown narrows the grid and is shareable via URL.

**Depends on**: Phase 2 checkpoint (`ticker_index.sector`/`.industry` populated).

### Tests for User Story 5

- [X] T075 [P] [US5] Backend test: `GET /sectors` rolls up by `ticker_index.sector` (not `analyses.sector`), buckets a sector-less tracked ticker into `"Unclassified"`, and does not drop it, in `backend/tests/test_sectors.py`
- [X] T076 [P] [US5] Backend test: a sector's rollup count equals the item count `GET /analysis/feed?sector={x}` returns for the same sector (FR-026a consistency check) in `backend/tests/test_sectors.py`
- [X] T077 [P] [US5] Backend test: `GET /analysis/feed?industry={x}` narrows correctly; `GET /analysis/feed?industry=NoSuchIndustry` returns an **empty** result, not the unfiltered feed (the 028 `$in: []` invariant) in `backend/tests/test_routers.py`
- [X] T078 [P] [US5] Backend test: `GET /stocks/industries` returns sorted distinct industries from tracked (non-removed) tickers, `[]` before any profile exists, in `backend/tests/test_routers.py`
- [X] T079 [P] [US5] Vitest: `FilterBar` industry `<select>` is hidden when the industries list is empty, populated from `useIndustries()` otherwise, and selecting/clearing updates the `industry` search param in `frontend/src/components/feed/FilterBar.test.tsx`
- [X] T080 [P] [US5] Vitest: `Sectors.tsx` renders the `"Unclassified"` bucket last with distinct copy, not as a literal sector name, in `frontend/src/pages/Sectors.test.tsx`

### Implementation for User Story 5

- [X] T081 [US5] Rewrite `GET /sectors` in `backend/routers/sectors.py`: aggregate latest-per-ticker from `analyses` (drop the `$match` on `sector`), join tickers to `ticker_index` for `sector`/`industry` in one query, bucket in Python with `"Unclassified"` for missing/empty sector (contracts/sector-and-industry.md, FR-026, FR-027)
- [X] T082 [US5] Update `GET /sectors/{sector}` and `GET /analysis/sector/{sector}` in `backend/routers/sectors.py` / `backend/routers/analysis.py` to resolve tickers via `ticker_index.sector` before matching `analyses`
- [X] T083 [US5] Add `sector`/`industry` two-step ticker resolution to `GET /analysis/feed` in `backend/routers/analysis.py`, appended to the existing `ticker_conditions` list alongside the `sentiment` step — **empty match must still append `{"ticker": {"$in": []}}`, never be skipped** (contracts/sector-and-industry.md, the 028 invariant)
- [X] T084 [US5] Implement `GET /stocks/industries` in `backend/routers/stocks.py` — distinct non-null/non-empty `industry` from `ticker_index` where `status != "removed_from_market"`, sorted
- [X] T085 [P] [US5] Implement `frontend/src/hooks/useIndustries.ts`
- [X] T086 [US5] Add an industry `<select>` to `frontend/src/components/feed/FilterBar.tsx`, bound to the `industry` search param following the existing `setFilter` toggle convention, hidden when `useIndustries()` returns `[]` (research R13); update the mount-guard comment (~line 27-33) to no longer reference the removed `#news` anchor while **keeping the guard itself** (`StockDetail`'s hash tabs still need it)
- [X] T087 [US5] Update `frontend/src/pages/Sectors.tsx`: render the `"Unclassified"` bucket with distinct copy, pinned last regardless of alphabetical sort, in `SectorRow`/`SectorCard`
- [X] T088 [US5] Confirm the existing "No sector data yet" empty-state copy in `Sectors.tsx` (now finally accurate rather than permanently misleading) needs no further change

**Checkpoint**: Sectors page populates for the first time ever; industry filter works end to end. Independently shippable.

---

## Phase 8: User Story 6 - Peers Section on the Overview Tab (Priority: P2)

**Goal**: Overview tab lists peer companies with symbol/name/price/market cap, each linking to its own stock page.

**Independent Test**: Open a stock with peers → Peers section lists them sorted by market cap descending; clicking one navigates to `/stock/{symbol}` even if untracked.

**Depends on**: Phase 2 checkpoint. Independent of US2/US3/US5 (adds its own section to the Overview tab; does not require the profile header to exist first).

### Tests for User Story 6

- [X] T089 [P] [US6] Vitest `PeersSection`: renders symbol/name/price/market cap rows sorted by market cap descending; market cap abbreviated (e.g. `4.04T`); missing market cap renders `—` not `0`; empty list renders an empty state; each row links to `/stock/{symbol}` in `frontend/src/components/stock/PeersSection.test.tsx`

### Implementation for User Story 6

- [X] T090 [US6] Implement `frontend/src/components/stock/PeersSection.tsx` using `usePeers(ticker)` — abbreviated market-cap formatter, `—` for null, `Link to="/stock/{symbol}"` per row, empty state (FR-014, FR-016, FR-017, research R8)
- [X] T091 [US6] Render `PeersSection` inside `OverviewTab` in `frontend/src/pages/StockDetail.tsx`

**Checkpoint**: Peers section live. Independently shippable.

---

## Phase 9: User Story 7 - Employee Count Graph on the Overview Tab (Priority: P3)

**Goal**: Overview tab charts reported employee headcount over time.

**Independent Test**: Open a stock with employee-count history → chronological chart with readable headcount ticks and a tooltip showing period/headcount/filing type.

**Depends on**: Phase 2 checkpoint. Independent of every other story.

### Tests for User Story 7

- [X] T092 [P] [US7] Vitest `EmployeeCountChart`: renders points oldest-to-newest; tick labels abbreviated (`166000 → 166k`); a single-record fixture renders a visible point (not an invisible zero-length line); empty fixture renders an empty state in `frontend/src/components/stock/EmployeeCountChart.test.tsx`

### Implementation for User Story 7

- [X] T093 [US7] Implement `frontend/src/components/stock/EmployeeCountChart.tsx` using `useEmployeeCounts(ticker)` — Recharts `LineChart`, abbreviated Y-axis ticks, tooltip with period/headcount/`form_type`, single-point `dot` visibility, empty state (FR-015, FR-017, research R12)
- [X] T094 [US7] Render `EmployeeCountChart` inside `OverviewTab` in `frontend/src/pages/StockDetail.tsx`

**Checkpoint**: Employee-count chart live. All seven user stories now independently functional.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide consistency and closing the loop on the bug this feature fixes.

- [X] T095 Move the "Analysis documents never get a `sector`" entry in `KNOWN_ISSUES.md` from Open bugs to the Fixed section, pointing at this spec (quickstart.md's closing note; verified once T075/T076 pass)
- [ ] T096 Run the one-time migration from `quickstart.md`: `db.portfolio_digest_cache.drop()` and `db.work_queue.deleteMany({ job_type: "portfolio_digest" })` — **only after** T054–T064 are deployed, never before (research R14 ordering)
- [X] T097 [P] Run `ruff check backend/` and `ruff check agent-runner/ scripts/`, fix any findings
- [X] T098 [P] Run `pytest` in `backend/` and `agent-runner/`, confirm full suite green including all new/deleted test files
- [X] T099 [P] Run `npm test` in `frontend/`, confirm full suite green including all new/deleted test files
- [X] T100 Walk `quickstart.md`'s Validation walkthrough end to end (steps 0–6) against a running local stack, including the day-one "everything unclassified" state before pulling anything

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks US2, US3, US5, US6, US7.**
- **US1 (Phase 3)** and **US4 (Phase 6)**: Depend only on Setup — may start immediately, in parallel with Phase 2 and with each other.
- **US2, US3, US5, US6, US7 (Phases 4, 5, 7, 8, 9)**: All depend on the Phase 2 checkpoint. Once it's reached, all five may proceed in parallel with each other — none blocks another.
- **Polish (Phase 10)**: Depends on every story the release includes being complete. T096 specifically depends on US3's teardown tasks (T054–T064) having shipped first.

### User Story Dependencies

| Story | Depends on | Notes |
|---|---|---|
| US1 — News nav | Setup only | Fully independent |
| US2 — Profile header | Foundational | Independent of US3/US5/US6/US7 |
| US3 — Hover card + digest removal | Foundational (for `logo_url`) | Digest-removal subtasks (T046–T064) have no data dependency and could start even earlier, but are grouped here per the spec's story boundary |
| US4 — Sectors chart | Setup only | Fully independent, pure frontend |
| US5 — Sector/industry | Foundational | Independent of US2/US3/US6/US7 |
| US6 — Peers | Foundational | Independent; shares the Overview tab with US2/US7 but no code dependency |
| US7 — Employee chart | Foundational | Independent; shares the Overview tab with US2/US6 but no code dependency |

### Within Each User Story

- Tests are written first and should fail before their implementation task lands.
- Backend/agent-runner data layer before backend endpoints before frontend hooks before frontend components before page wiring.
- A story's checkpoint marks it independently testable per its spec.md Independent Test.

### Parallel Opportunities

- T001–T002 (Setup) run together.
- T003–T005 (Foundational tests) run together; T013–T015 (backend contract tests) run together.
- T019–T022 (frontend foundational pieces: types, `CompanyLogo` + its test, hook) run together once T016–T018 exist.
- Once Phase 2's checkpoint is reached: **US1, US2, US4, US5, US6, US7 can all be staffed in parallel** (US3 needs T041 first for its own `[P]` tile/preview tasks, but T046–T053's deletions are parallel with everything).
- Within US3's teardown, T046–T053 (8 independent file deletions) are fully parallel.
- T097–T099 (lint/test suites) run together in Phase 10.

---

## Parallel Example: Phase 2 Foundational

```bash
# Contract tests together:
Task: "Contract test for get_profile() cache/degradation in agent-runner/tests/test_company_profile.py"
Task: "Contract test for get_peers() 90-day window in agent-runner/tests/test_company_profile.py"
Task: "Contract test for get_employee_counts() 90-day window in agent-runner/tests/test_company_profile.py"

# Backend contract tests together (after T007-T012 land):
Task: "Backend contract test GET /stocks/{ticker}/profile in backend/tests/test_company_profile.py"
Task: "Backend contract test GET /stocks/{ticker}/peers in backend/tests/test_company_profile.py"
Task: "Backend contract test GET /stocks/{ticker}/employee-count in backend/tests/test_company_profile.py"

# Frontend foundational pieces together:
Task: "Add CompanyProfile/Peer/EmployeeCountRecord types to frontend/src/api/types.ts"
Task: "Implement components/shared/CompanyLogo.tsx"
Task: "Implement hooks/useCompanyProfile.ts"
```

## Parallel Example: Post-Foundational Story Fan-Out

```bash
# Once Phase 2's checkpoint is reached, these can be staffed simultaneously:
Task: "US2 — CompanyProfileSection.tsx + StockDetail wiring"
Task: "US5 — sector/industry backend re-sourcing + industry filter"
Task: "US6 — PeersSection.tsx"
Task: "US7 — EmployeeCountChart.tsx"
# ...alongside US1 and US4, which never waited on Phase 2 at all.
```

---

## Implementation Strategy

### MVP First

The spec's three P1 stories (US1, US2, US3) together are the smallest complete slice a user would notice as "the tweaks landed": news has its own nav entry, every stock page has a real identity header, and the portfolio digest is gone in favor of full summaries on hover.

1. Phase 1 (Setup) → Phase 2 (Foundational) — the data pipeline every P1/P2/P3 story but US1/US4 needs.
2. Phase 3 (US1) can be built in parallel with Phase 2 — ship it first if you want something visible immediately.
3. Phase 4 (US2) and Phase 5 (US3) once Phase 2's checkpoint lands.
4. **STOP and VALIDATE**: run quickstart.md steps 0, 1, 4, 5 — day-one state, profile header, hover card, news nav.
5. This is a shippable MVP even before US4–US7 exist.

### Incremental Delivery

1. Setup + Foundational → pipeline ready (with US1/US4 already shippable in parallel).
2. US1 → ship (News nav).
3. US2 → ship (profile header) → US3 → ship (hover card, digest gone) → **MVP complete**.
4. US4 → ship (chart usability) — independent, any time.
5. US5 → ship (real Sectors page, industry filter) — closes the KNOWN_ISSUES bug.
6. US6 → ship (peers).
7. US7 → ship (employee chart).
8. Phase 10 polish, including the KNOWN_ISSUES update and the one-time collection drop.

### Notes

- [P] tasks touch different files with no unmet dependency.
- Commit after each task or logical group (e.g., a full Foundational sub-block, or one story's Tests+Implementation).
- Verify each Tests block fails before starting that story's Implementation block.
- Do not run T096 (the `portfolio_digest_cache` drop) before US3's teardown code (T054–T064) is deployed — a running worker would recreate the collection.
- Do not delete `pct_of_portfolio` (T060's explicit carve-out) — it is institutional-holdings data, unrelated to the digest despite the name collision.
