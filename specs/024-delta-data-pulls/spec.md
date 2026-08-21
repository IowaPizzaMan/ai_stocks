# Feature Specification: Delta-Only Data Pulls

**Feature Branch**: `024-delta-data-pulls`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: "I want to change that so the API's only pull the data they need, aka just pull deltas. I need to try to find out how I can make the pull faster and this is one way."

## Problem Context

Today, every data refresh for a stock re-downloads the **entire** dataset from the
external provider, even when the system already holds all but the last day or two of
it. Caches are purely time-based: when a cache entry ages out, the whole thing is
discarded and re-fetched from scratch. Nothing asks "what has changed since last
time?"

Three compounding effects make a pull slower than it needs to be:

1. **Full re-downloads.** A ticker's complete daily price history (years of bars) is
   re-fetched to learn about one new trading day. The same applies to the 30-day
   news window, the 90-day insider window, and per-quarter filing feeds.
2. **Repeated identical downloads inside a single pull.** The same full price history
   is downloaded more than once during one pull, because separate stages each request
   it independently with nothing sharing the result between them.
3. **Per-view re-downloads.** Viewing a stock's chart at different time resolutions
   triggers a separate full history download per resolution, even though every
   resolution is derivable from the same daily series.

The user's stated goal is to **make a pull faster**, and delta fetching is one lever.
This feature covers identifying where pull time actually goes and then eliminating
redundant data transfer.

Delta retrieval becomes the **default** path for every dataset that supports it. A
complete re-download still happens, but only when a stock has never been pulled
before or when the operator explicitly asks for one.

## Clarifications

### Session 2026-08-17

- Q: When the full-refresh control is used on a stock, which datasets are forced back to a complete re-download? → A: All delta-maintained data for that stock — price history, news, and event feeds — under a single control.
- Q: Should a full refresh also re-run the analysis, or only re-fetch the raw data? → A: Re-fetch and re-analyze. A full refresh is a normal pull with the delta shortcuts disabled.
- Q: How should a full refresh interact with the daily provider request cap? → A: It respects the cap and fails soft, exactly like any other pull.
- Q: Should the system still re-baseline stored data on its own schedule? → A: No. No automatic refreshes of any kind. Full retrieval happens only on a first-ever pull or on operator request.
- Q: With nothing refreshing automatically, how should drift in stored data be surfaced? → A: It isn't. No drift detection is built — the operator notices and triggers a full refresh. Accepted risk, revisit later.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See where pull time actually goes (Priority: P1)

As the operator of the system, when a stock pull finishes I can see a breakdown of
how long it took, split by stage, so I can tell which stages dominate and confirm
whether delta fetching is actually the right lever before investing in it.

**Why this priority**: The user explicitly wants to *find out* how to make pulls
faster. Without measurement, every optimization is a guess, and a delta rewrite that
targets a stage worth 5% of wall time is wasted effort. This story is also the
smallest useful slice — it delivers value on its own and it is the yardstick every
later story is judged against.

**Independent Test**: Trigger a pull for a stock and confirm a per-stage timing
record is produced showing elapsed time, number of external provider requests, and
volume of data transferred for each stage — with the stages ranked by cost.

**Acceptance Scenarios**:

1. **Given** a stock with no cached data, **When** a pull is triggered, **Then** a
   timing record is produced listing every data stage with its elapsed time, request
   count, and transferred data volume, and the total reconciles to the observed
   wall-clock time of the pull.
2. **Given** a stock whose data was pulled minutes ago, **When** a pull is triggered
   again, **Then** the timing record distinguishes stages that were served from
   existing stored data from stages that contacted the provider.
3. **Given** several pulls have completed, **When** the operator reviews the records,
   **Then** the stages can be ranked by their contribution to total pull time across
   pulls, not just for a single run.
4. **Given** a stage fails or degrades to stored data, **When** the pull completes,
   **Then** the timing record marks that stage's outcome rather than silently
   reporting it as a success.

---

### User Story 2 - Price history fetched incrementally (Priority: P2)

As the operator, when a stock is pulled and the system already holds most of its
price history, only the genuinely new trading days are retrieved from the provider —
while the stored history stays numerically correct.

**Why this priority**: Price history is the single largest payload in a pull, is
requested by more stages than any other dataset, and grows without bound as history
accumulates — so it is where delta fetching pays the most. It is prioritized below
measurement only because the measurement story proves the size of the prize.

**Independent Test**: Pull a stock, wait for the next trading day, pull again, and
confirm the second pull retrieves only the new day(s) while the resulting history is
identical to what a full re-download would have produced.

**Acceptance Scenarios**:

1. **Given** stored price history ending on a known date, **When** a pull runs,
   **Then** only trading days after that date are requested from the provider, and
   the stored history is extended rather than replaced.
2. **Given** no stored price history for a stock, **When** a pull runs, **Then** the
   full available history is retrieved and stored as the baseline.
3. **Given** stored history with a gap in the middle (e.g. the system was offline for
   a period), **When** a pull runs, **Then** the missing span is retrieved and the
   stored history ends up continuous with no missing trading days.
4. **Given** a corporate action (such as a split) that retroactively changes the
   values of already-stored historical bars, **When** a delta pull runs, **Then** the
   stored history is extended without correcting the earlier bars — a known and
   accepted consequence of delta-by-default, for which an operator-triggered full
   refresh (US5) is the remedy.
5. **Given** a single pull in which multiple stages need price history, **When** the
   pull runs, **Then** that history is retrieved at most once and shared across those
   stages within the pull.
6. **Given** a user viewing a stock's chart and switching between time resolutions,
   **When** each resolution is displayed, **Then** no additional full history download
   occurs — every resolution is derived from the one stored daily series.
7. **Given** the provider is unavailable or the daily request budget is exhausted,
   **When** a pull runs, **Then** the stored history is served as-is with a staleness
   indicator, and the pull completes rather than failing.

---

### User Story 3 - News fetched incrementally (Priority: P3)

As the operator, when a stock is pulled, only articles published since the most
recent stored article are retrieved, rather than re-downloading the whole coverage
window.

**Why this priority**: News is the second-largest payload (article bodies, multiple
pages for well-covered names) and refreshes far more often than filings, so it is the
next-best delta candidate after price. It is below price because it affects fewer
downstream stages.

**Independent Test**: Pull a stock, then pull again shortly after, and confirm the
second pull requests only the period since the newest stored article while the
resulting article set and derived tone summary match a full-window fetch.

**Acceptance Scenarios**:

1. **Given** stored articles with a known most-recent publication date, **When** a
   pull runs, **Then** only the period from that date forward is requested.
2. **Given** newly retrieved articles overlap with stored ones, **When** they are
   merged, **Then** each article appears exactly once in the result.
3. **Given** articles that have aged beyond the coverage window, **When** a pull
   completes, **Then** they are dropped from the stored set so it does not grow
   without bound.
4. **Given** no stored articles for a stock, **When** a pull runs, **Then** the full
   coverage window is retrieved.
5. **Given** an incremental fetch, **When** the tone summary and trend are computed,
   **Then** they are derived from the full retained window, not only the newly
   arrived articles.

---

### User Story 4 - Filings and event feeds fetched incrementally (Priority: P4)

As the operator, when a stock is pulled, event-shaped datasets — insider
transactions, ownership filings, and historical earnings results — are retrieved only
from the point the system last saw an event, rather than re-fetching the full
lookback window.

**Why this priority**: These datasets are smaller than price and news and change on
slow filing cadences, so the per-pull saving is real but modest. They are worth doing
for consistency once the pattern from the earlier stories is established.

**Independent Test**: Pull a stock twice in succession and confirm each event feed
requests only the period since its newest stored event, while the merged result
matches a full-window fetch.

**Acceptance Scenarios**:

1. **Given** stored events with a known newest event date, **When** a pull runs,
   **Then** only the period from that date forward is requested for that feed.
2. **Given** a filing that is amended or restated after it was first stored, **When**
   it is retrieved again, **Then** the stored copy is updated rather than duplicated.
3. **Given** a feed the current data plan does not cover, **When** a pull runs,
   **Then** the feed degrades to stored data exactly as it does today, and the rest of
   the pull proceeds.

---

### User Story 5 - Force a full refresh when data looks wrong (Priority: P2)

As the operator, when a stock's data looks wrong, I can trigger a full refresh for
that stock that ignores every delta shortcut, re-downloads its datasets from scratch,
and re-runs the analysis on the result.

**Why this priority**: This control is what makes delta-by-default safe to ship. With
no automatic re-baselining and no drift detection, it is the *only* way to correct
stored data that has gone wrong — so it gates US2, US3, and US4 being switched on as
the default path. It shares P2 with the first delta story because neither should ship
without the other.

**Independent Test**: Leave a stock's stored data deliberately stale or wrong, trigger
a full refresh, and confirm the stored datasets afterwards match a from-scratch
download and that the analysis has been re-run on top of them.

**Acceptance Scenarios**:

1. **Given** a stock with stored data, **When** a full refresh is triggered, **Then**
   every delta-maintained dataset for that stock — price history, news, and event
   feeds — is re-downloaded in full and replaces the stored copy, in a single action.
2. **Given** price history left stale by a corporate action that a delta pull appended
   straight past, **When** a full refresh is triggered, **Then** the stored history
   afterwards matches a from-scratch download exactly.
3. **Given** a full refresh completes, **When** it finishes, **Then** the analysis has
   been re-run on the refreshed data, so no stored conclusion remains derived from the
   data the operator just replaced.
4. **Given** the daily provider request budget is already spent, **When** a full
   refresh is triggered, **Then** it degrades to stored data with a staleness
   indicator and reports that it could not complete — it neither exceeds the cap nor
   fails outright.
5. **Given** a full refresh fails partway through, **When** it stops, **Then** the
   stored data is no less usable than it was before the refresh started.
6. **Given** a stock with no stored data at all, **When** a full refresh is triggered,
   **Then** it behaves exactly as a first-ever pull.
7. **Given** a completed pull, **When** the operator reviews it, **Then** they can tell
   whether it was a delta pull or a full refresh, and whether it completed or degraded.

---

### Edge Cases

- **First-ever pull of a stock**: there is no stored baseline, so a delta request is
  meaningless — the system must fall back to a full retrieval.
- **Retroactive value changes**: splits and dividend adjustments rewrite historical
  values, so appending alone leaves stored history silently wrong. By decision the
  system does not detect this — an operator-triggered full refresh is the only remedy
  (see Assumptions: silent drift is an accepted risk).
- **Restated or amended records**: a filing or earnings result already stored can be
  corrected upstream. Delta logic keyed purely on "newer than X" will not see the
  correction; same remedy as above.
- **Full refresh with the day's budget already spent**: the refresh must not push past
  the cap, and must not leave the operator believing it succeeded.
- **Full refresh interrupted partway**: replacing stored data must not be able to
  destroy a good copy and leave nothing usable behind.
- **Full refresh while a delta pull for the same stock is already running**: the two
  must not interleave into a corrupted stored dataset.
- **Clock and timezone boundaries**: "since the last record" must not skip or
  duplicate a day when the last record's date and the provider's day boundary are in
  different timezones.
- **Long dormancy**: a stock not pulled for months has a delta window so large that a
  full retrieval is cheaper — the system must recognize this rather than paging
  through an enormous incremental range.
- **Non-trading days**: a pull on a weekend or holiday yields no new records; this is
  a normal outcome, not a failure, and must not trigger a full re-download.
- **Provider ignores or misinterprets a range request**: if the provider returns the
  full dataset despite a bounded request, the system must still produce correct stored
  data and must not double-count records.
- **Concurrent pulls of the same stock**: two overlapping pulls must not corrupt the
  stored history or each duplicate the same fetch.
- **Budget exhaustion mid-pull**: partial delta progress must be retained rather than
  discarded, and the pull must complete on stored data.

## Requirements *(mandatory)*

### Functional Requirements

#### Measurement (US1)

- **FR-001**: The system MUST record, for each completed pull, a per-stage breakdown
  containing elapsed time, count of external provider requests, and volume of data
  transferred.
- **FR-002**: Each stage entry MUST record its outcome — served from stored data,
  retrieved fresh, degraded to stored data after a failure, or skipped — and whether
  the retrieval was incremental or full.
- **FR-003**: Per-stage records MUST be retained across pulls so stages can be ranked
  by cost over time, not only within one run.
- **FR-004**: The system MUST record total pull wall-clock time alongside the stage
  breakdown, so unaccounted time is visible rather than hidden.
- **FR-005**: Measurement MUST NOT itself add a material cost to a pull, and a failure
  in measurement MUST NOT fail the pull.

#### Incremental retrieval — general (US2, US3, US4)

- **FR-006**: For each dataset that supports it, the system MUST track the coverage it
  already holds — at minimum the most recent record's date — and request only the
  period beyond that coverage.
- **FR-007**: The system MUST fall back to a full retrieval whenever no usable stored
  baseline exists.
- **FR-008**: Newly retrieved records MUST be merged into stored data such that the
  result is identical to what a full retrieval would produce — no duplicates, no
  gaps, no ordering differences.
- **FR-009**: Delta retrieval MUST be the default behavior for every dataset that
  supports it. Full retrieval occurs only in the cases named in FR-007 (no baseline),
  FR-011 (gap too large to be worth an incremental request), and FR-023 (operator
  request) — never as a routine part of a pull.
- **FR-010**: The system MUST NOT perform any automatic or scheduled full
  re-establishment of stored data, and MUST NOT attempt to detect drift between stored
  data and the provider. Correcting stored data is an operator-initiated action (US5).
- **FR-011**: When the gap between stored coverage and the present exceeds the point
  where incremental retrieval is cheaper than a full one, the system MUST perform a
  full retrieval instead.
- **FR-012**: All incremental retrieval MUST continue to route through the existing
  cache-first, budget-guarded data access path, and MUST continue to fail soft —
  serving stored data with a staleness indicator rather than failing the pull.
- **FR-013**: An incremental retrieval that fails partway MUST retain the records
  already obtained rather than discarding the partial progress.
- **FR-014**: Records already retrieved during a pull MUST be shared across every
  stage of that pull that needs them, so no dataset is downloaded more than once per
  pull.

#### Dataset-specific

- **FR-015**: Price history MUST be maintained as a single stored daily series per
  stock, extended incrementally, from which every coarser time resolution is derived
  without additional retrieval.
- **FR-016**: Requests for a stock's price at any time resolution MUST be satisfied
  from that single stored daily series.
- **FR-017**: News retrieval MUST request only the period since the most recent stored
  article, and MUST discard stored articles that have aged out of the coverage window.
- **FR-018**: Derived news outputs (tone counts, timeline, trend) MUST be computed
  over the full retained window, not only the newly retrieved articles.
- **FR-019**: Event feeds (insider transactions, ownership filings, historical
  earnings results) MUST request only the period since their newest stored event, and
  MUST update rather than duplicate a record that is retrieved again.

#### Behavior preservation

- **FR-020**: The data made available to downstream analysis MUST be unchanged in
  shape and content from what a full retrieval produces — this feature changes how
  data is obtained, not what analysis sees.
- **FR-021**: Existing stored data MUST remain usable as a baseline without requiring
  a wipe-and-refetch of every stock.
- **FR-022**: The number of external provider requests per pull MUST NOT increase for
  any dataset relative to today's behavior.

#### Operator-initiated full refresh (US5)

- **FR-023**: The system MUST provide an operator-initiated control that forces a
  complete re-download for a single stock, bypassing every delta shortcut.
- **FR-024**: A full refresh MUST cover every delta-maintained dataset for that stock
  in one action — price history, news, and event feeds — rather than requiring the
  operator to identify which dataset is at fault.
- **FR-025**: A full refresh MUST replace the stored data for those datasets and
  establish a new coverage baseline, rather than merging into the existing one.
- **FR-026**: A full refresh MUST re-run the analysis on the refreshed data, so no
  stored conclusion is left derived from data the operator has just replaced.
- **FR-027**: A full refresh MUST respect the daily provider request cap and fail soft
  exactly as a normal pull does — degrading to stored data with a staleness indicator
  rather than exceeding the cap or failing outright.
- **FR-028**: The operator MUST be able to tell, while a pull is running and after it
  completes, whether it was a delta pull or a full refresh, and whether it completed or
  degraded.
- **FR-029**: A full refresh MUST be available whether or not the stock currently has
  stored data; with none, it behaves as a first-ever pull.
- **FR-030**: A full refresh that fails partway MUST leave the stored data no less
  usable than it was before the refresh began — replacing a dataset must never be able
  to destroy the existing copy and leave nothing in its place.
- **FR-031**: A full refresh and a delta pull for the same stock MUST NOT be able to
  run concurrently in a way that corrupts the stored data.

### Key Entities

- **Pull**: One refresh of a single stock's data, composed of multiple stages. Has a
  start time, end time, an overall outcome, and a **mode** — *delta* (the default) or
  *full refresh* (operator-initiated).
- **Stage**: One dataset's retrieval within a pull (price, news, financials, insider,
  ownership, earnings, sentiment, breadth). Has elapsed time, request count,
  transferred volume, and an outcome.
- **Coverage record**: What the system already holds for a given stock and dataset —
  the span it covers, the newest record it contains, when it was last extended, and
  when it was last fully established (only ever by a first-ever pull or an
  operator-initiated full refresh). This is the input that makes a delta request
  possible.
- **Stored dataset**: The accumulated records for a stock and dataset (price series,
  article set, event feed), maintained across pulls rather than replaced wholesale.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** *(revised 2026-08-17 after US1 measurement — see Measured Outcomes
  Addendum below)*: The **data-fetch portion** of a repeat pull completes in at least
  30% less time than it does today. The original target — 50% off total pull time —
  was withdrawn as unreachable: measurement showed fetching is ~9% of a pull, so even
  eliminating it entirely could not move the total by 50%.
- **SC-002**: The total volume of data transferred from external providers for a
  repeat pull is reduced by **at least 80%** for the delta-maintained datasets
  (price, news, insider). Datasets outside this feature's scope are excluded from the
  measurement.
- **SC-003**: No dataset is transferred more than once within a single pull —
  measured as zero duplicate identical retrievals per pull, down from at least one
  today.
- **SC-004**: Switching between time resolutions on a stock's chart triggers **zero**
  additional history downloads once that stock's history is held, down from one per
  resolution today.
- **SC-005**: For a stock with no retroactive adjustment since its last pull, the data
  produced by a delta pull is **byte-for-byte equivalent** to the data produced by a
  full refresh of the same stock at the same moment, verified across a representative
  sample.
- **SC-006**: The operator can identify the three most expensive stages of a pull, by
  time and by transferred volume, without reading code or logs.
- **SC-007**: The number of external provider requests consumed per repeat pull does
  not increase for any dataset, and the daily request budget lasts at least as long
  as it does today.
- **SC-008**: A first-ever pull of an unknown stock completes no slower than it does
  today.
- **SC-009**: Every failure mode above — provider unavailable, budget exhausted,
  dataset not covered by the plan — still results in a completed pull serving stored
  data, with **zero** pulls failing outright for reasons that today degrade
  gracefully.
- **SC-010**: A full refresh produces data **byte-for-byte equivalent** to a
  from-scratch download for any stock, verified explicitly against a stock that has
  split since its stored history was first captured — the case delta pulls
  deliberately do not handle.
- **SC-011**: The operator can trigger a full refresh for a stock, covering all of its
  delta-maintained datasets, in **one action**, without choosing which dataset to
  refresh.
- **SC-012**: **Zero** full re-downloads occur unattended — every full retrieval
  traces to a first-ever pull, an operator request, or the too-large-a-gap condition,
  and none to a schedule.
- **SC-013**: Interrupting a full refresh at any point leaves the stock's stored data
  at least as usable as before it started, across **100%** of interruption points
  tested.

### Measured Outcomes Addendum (2026-08-17)

Measured live against MSFT on the running stack, after US1 shipped. This is the
data US1 existed to produce, and it changed one target.

**Where a pull's time actually goes** — this is the headline finding:

| | Repeat pull |
|---|---|
| Total wall time | ~51 s |
| Data fetch (all 11 stages) | **4.6 s — 9%** |
| LLM agents (unaccounted) | **46.4 s — 91%** |

Delta fetching cannot make a pull 50% faster because fetching was never half the
pull. The original SC-001 was written before anything was measured; it is now
restated against the fetch portion, which the work does move.

**What the delta work did achieve**, cold stores → warm (same ticker, same day):

| Dataset | Requests | Bytes | Change |
|---|---|---|---|
| price | 1 → 1 | 288,513 → 236 | **−99.9%** |
| news | 4 → 1 | 667,430 → 15,068 | **−97.7%**, 3 fewer requests |
| insider | 2 → 2 | 8,759 → 1,117 | **−87%** |
| *delta-maintained total* | 7 → 4 | 964,702 → 16,421 | **−98.3%** |
| whole pull | 14 → 11 | 1,067,468 → 407,470 | −62% |
| fetch time | | 7.0 s → 4.6 s | **−34%** |

Also confirmed: `indicators` reports 0 requests (the duplicate full-history
download is gone — SC-003), and switching all four chart resolutions costs **0**
provider calls, down from 4 (SC-004).

**Implication for anyone continuing this work**: the remaining lever on pull
latency is the sequential LLM agent chain, not data retrieval. Seven structured
Ollama calls run one after another; that is where 91% of the time is. Delta
fetching was worth doing — it cut transfer by 98% and removed two whole classes
of redundant download — but it is finished as a speed lever.

## Assumptions

- **Scope is the per-stock pull.** Market-wide and admin datasets (market breadth,
  sector performance, economic calendar, macro indicators, market-wide news) are out
  of scope for this feature. They refresh on their own cadence and are not part of the
  per-stock pull latency the user is trying to reduce.
- **Both pull paths are in scope.** The optimization covers both the analysis-time
  refresh of a stock and the on-demand data a stock's page requests, because both are
  backed by the same underlying datasets and the user perceives both as "pulling data
  on a stock."
- **Speed is the primary objective; request budget is a constraint, not a target.**
  Where the two conflict, the faster option wins provided it does not increase
  provider requests per pull (FR-022). Reducing budget consumption is a welcome side
  effect, not the goal.
- **Providers support bounded range requests.** The datasets targeted here are
  assumed to accept a start date or equivalent bound. Any dataset that turns out not
  to support this is simply excluded from incremental treatment and continues to
  behave as it does today.
- **Not every dataset is a delta candidate.** Datasets that are already effectively
  incremental, are point-in-time snapshots with no natural "since" boundary, or are
  already served read-only from storage are excluded. Statement-level financial data
  changes only on a filing cadence and is already served from a long-lived cache; it
  is not a priority target.
- **Silent drift is an accepted risk.** With no automatic re-baselining and no drift
  detection (FR-010), a corporate action that retroactively rewrites stored history
  leaves that history wrong until the operator triggers a full refresh — and nothing
  signals that it happened. This was a deliberate choice to keep the default path as
  fast and as simple as possible, taken in full knowledge of the failure mode. The
  full-refresh control (US5) is the only remedy. It should be recorded as an accepted
  limitation when this ships, and revisited if it bites in practice.
- **The full-refresh control sits with the existing per-stock pull trigger.** Exact
  placement and wording are planning details; what the spec fixes is that it is one
  action, on a single stock, distinguishable from an ordinary pull.
- **Existing stored data is a valid baseline.** No migration that discards and
  re-fetches every stock's data is required; the system bootstraps coverage records
  from what it already holds.
- **Success criteria are measured on the existing local deployment** — a single-user,
  self-hosted stack — using the same stocks and the same data plan as today, so
  before/after comparisons are like-for-like.
- **"At least 50% faster" (SC-001) is a target derived from the observed cost
  profile**, where full history re-downloads and repeated identical downloads dominate
  a repeat pull. US1's measurement is expected to confirm or correct this figure
  before the later stories are built out.

## Dependencies

- The existing cache-first, budget-guarded data access layer and its daily request
  cap must remain the single path for all external data access (constitution
  Principle IV).
- The existing per-stock storage collections are the baseline that coverage records
  are derived from.
- Both services that fetch the same datasets must adopt the same coverage semantics,
  since they read and write the same stored data (constitution Principle VI).

## Out of Scope

- Market-wide and admin-job datasets.
- Changing what analysis is performed, which providers are used, or which datasets
  are collected.
- Automatic drift detection, and any scheduled or automatic full re-baselining — full
  retrieval is operator-initiated only (FR-010).
- Bulk or watchlist-wide full refresh — the control acts on one stock at a time.
- Real-time or streaming price updates.
- Parallelism and concurrency changes as a speed lever — this feature reduces the
  work done, not the way remaining work is scheduled.
- Any change to how results are presented to the user beyond the operator-facing
  timing breakdown in US1.
