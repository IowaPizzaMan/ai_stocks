# Feature Specification: Deduplicate Analysis Feed & Storage

**Feature Branch**: `016-dedupe-analysis-feed`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "In the feed, I want to now show duplicates. In the database I don't want to save duplpcates either, I will always only want to see the lastest"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One feed card per ticker (Priority: P1)

As a user browsing the Feed, I want each ticker to appear at most once, showing its most recent analysis, so that re-analysis of the same stock doesn't clutter my feed with repeated cards for the same company.

**Why this priority**: This is the visible symptom the user is reacting to — it's the first thing they see, and it directly affects how usable the Feed is as a discovery tool.

**Independent Test**: Trigger two analyses for the same ticker (e.g. AAPL) at different times, then load the Feed. Only one AAPL card should appear, and it should reflect the second (more recent) analysis.

**Acceptance Scenarios**:

1. **Given** a ticker has been analyzed multiple times, **When** the user loads the Feed, **Then** exactly one card for that ticker appears, showing the most recent analysis's signal, conviction, and summary.
2. **Given** the user applies a filter (signal, sector, conviction, or ticker search), **When** the Feed re-queries, **Then** results are still deduplicated to one card per matching ticker.
3. **Given** the user scrolls to load more pages, **When** additional pages load, **Then** no ticker previously shown on an earlier page reappears on a later page.

---

### User Story 2 - Storage keeps only the latest analysis per ticker (Priority: P1)

As the system, when a new analysis finishes for a ticker, I want the ticker's stored analysis to be replaced by the new one rather than added alongside the old one, so the database never accumulates multiple analyses for the same ticker.

**Why this priority**: This is the root cause fix requested by the user ("in the database I don't want to save duplicates either") — without it, User Story 1 would require dedup logic on every read instead of being naturally true of the data.

**Independent Test**: Run analysis for a ticker twice in a row. After the second run completes, querying storage for that ticker returns exactly one record, matching the second run's output.

**Acceptance Scenarios**:

1. **Given** a ticker has no prior stored analysis, **When** its first analysis completes, **Then** one record is created for that ticker.
2. **Given** a ticker already has a stored analysis, **When** a new analysis for that ticker completes, **Then** the existing record is replaced with the new analysis (same ticker, new data), and no second record is created.
3. **Given** two analyses for the same ticker complete in close succession (e.g. a manual queue request and an automatic re-scan overlap), **When** both writes finish, **Then** the ticker ends up with exactly one stored record reflecting whichever analysis actually finished last.

---

### User Story 3 - Existing duplicates are cleaned up (Priority: P2)

As the system operator, I want the duplicate analysis records that already exist in the database (from before this change) collapsed down to one per ticker, so historical clutter doesn't linger and continue to show up anywhere records are still read directly (e.g. per-ticker analysis lookups).

**Why this priority**: Without this cleanup, the Feed and per-ticker views would still reflect old duplicate data until every ticker happens to be re-analyzed naturally, which could take a long time for less-active tickers.

**Independent Test**: Before the change, seed the database with a ticker that has 5 stored analyses at different timestamps. Run the cleanup. Afterward, exactly 1 record remains for that ticker, and it is the one with the latest timestamp.

**Acceptance Scenarios**:

1. **Given** a ticker has multiple stored analyses, **When** the cleanup runs, **Then** only the record with the most recent timestamp for that ticker remains (or, if two records tie on timestamp, any one of the tied records); all other records for that ticker are removed.
2. **Given** a ticker already has only one stored analysis, **When** the cleanup runs, **Then** that record is left unchanged.
3. **Given** the cleanup has already been run once, **When** it is run again, **Then** it makes no further changes (safe to re-run).

---

### Edge Cases

- What happens to the existing "Analysis History Timeline" (previously shown on the stock detail page, listing how a ticker's AI verdict evolved over past analyses)? It is removed as part of this change — once only the latest analysis per ticker is retained, there is no history left to show. Per-ticker analysis views show only the current (latest) analysis.
- What happens if a ticker's analysis is currently mid-run when a second analysis for the same ticker is also triggered? Whichever analysis completes and writes last determines the final stored record; there is no requirement to block or queue concurrent runs for the same ticker (that is out of scope for this feature). "Writes last" means actual write order, not a comparison of the two analyses' timestamp values — the system is not required to detect or resolve a case where the later write happens to carry an earlier timestamp.
- What happens to the Feed's reported total count? It reflects the number of distinct tickers with a stored analysis, not the number of analysis runs ever performed.
- What happens on the Sectors view, which already shows one card per ticker (most recent per sector)? No behavior change — it already reflects latest-per-ticker; this feature just makes that guarantee true everywhere, not only in that view.
- What happens if the one-time cleanup (FR-006) runs while new analyses are actively completing for other tickers? This is safe: the cleanup considers each ticker independently, so tickers not currently being written are unaffected, and a ticker that is both cleaned up and re-analyzed around the same time simply resolves via the same last-write-wins behavior described above.
- What happens if the cleanup is interrupted partway through (e.g. a process restart)? Since it processes each ticker independently and is safe to re-run (FR-007), an interrupted run leaves already-processed tickers deduplicated and unprocessed tickers untouched; simply re-running it converges to the correct end state with no manual repair needed.
- What happens if two stored analyses for the same ticker have identical timestamps? Either MAY be treated as the "latest" — exact tie-breaking is not required, only that exactly one record for that ticker remains afterward.
- What happens to a per-ticker analysis lookup for a ticker that has never been analyzed? It returns an empty/no-result response, not an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Feed MUST show at most one entry per ticker, representing that ticker's most recent completed analysis.
- **FR-002**: The Feed's total/pagination counts MUST reflect the number of distinct tickers represented, not the number of analysis runs.
- **FR-003**: Feed filtering (by signal, sector, conviction, and ticker search) MUST apply to the latest analysis per ticker — a ticker matches a filter based on its current (latest) values, not any past analysis.
- **FR-004**: When a new analysis for a ticker completes, the system MUST store it in place of that ticker's previous analysis rather than as an additional record, so each ticker has exactly one stored analysis at any time. A failed write MUST leave the ticker's previous analysis unchanged — it must never result in a partial or missing record. Whether "in place" reuses the previous record's identity or fully replaces it is not prescribed, as long as the one-record-per-ticker invariant holds continuously from the application's write path; an additional database-level uniqueness guarantee is allowed but not separately required by this spec.
- **FR-005**: Per-ticker analysis lookups (e.g. the stock detail page) MUST return only the ticker's current (latest) analysis; multi-analysis history views are removed. For a ticker with no stored analysis, the lookup MUST return an empty/no-result response rather than an error.
- **FR-006**: The system MUST perform a one-time cleanup of pre-existing duplicate analysis records, retaining only the most recent record per ticker and removing older ones. This cleanup is a manually-triggered, one-time operator action delivered alongside this feature — it MUST NOT run automatically and unattended (e.g. every service startup) as ongoing behavior. It MUST report how many records it removed, so the operator can confirm what it did (including "nothing," on an already-clean database). If a duplicate record has missing or malformed timestamp data, the cleanup MUST still resolve deterministically (treating it as older than any record with a valid timestamp) rather than error out or skip that ticker.
- **FR-007**: The cleanup in FR-006 MUST be safe to run more than once without further changes after the first successful run — including after an interrupted prior run (e.g. a process restart partway through); re-running MUST converge to the correct end state without manual repair.
- **FR-008**: Replacing a ticker's stored analysis MUST NOT affect other tickers' stored analyses or feed entries.

### Key Entities *(include if feature involves data)*

- **Analysis**: The AI-generated evaluation of a single ticker (signal, conviction, summary, key trends, flags, sub-reports, position management guidance). After this change, at most one Analysis exists per ticker at any given time; a new completed analysis for a ticker takes the place of the previous one.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the Feed, each ticker appears exactly once no matter how many times it has been analyzed historically.
- **SC-002**: After any ticker is re-analyzed, the number of stored analyses for that ticker is exactly one, verified immediately after the run completes.
- **SC-003**: After the one-time cleanup runs, the total count of stored analyses in the database equals the number of distinct tickers present in that database (`count(*) == count(DISTINCT ticker)`) — zero duplicate tickers remain. FR-006's cleanup has already collapsed each ticker to its one most-recent record by the time this count is taken, so no separate history is needed to compute or verify it.
- **SC-004**: Feed page-load and filtering performance is not noticeably degraded (perceived load time stays under 1 second for a page of results) as a result of deduplication.

## Assumptions

- "Duplicates" refers to multiple stored analyses for the same ticker, regardless of how much time separates them — not just accidental back-to-back re-runs.
- The existing "Analysis History Timeline" feature on the stock detail page (previously spec'd to show how a ticker's verdict evolved over time) is intentionally removed as a consequence of this change, per explicit direction: only the latest analysis per ticker is retained anywhere in the system.
- The one-time cleanup of existing duplicate records is in scope for this feature and should run as part of delivering it, not as a separately scheduled follow-up.
- Concurrent analyses for the same ticker are rare enough that a "last write wins" outcome is acceptable; building a locking/queueing mechanism to prevent concurrent analysis of the same ticker is out of scope. This is grounded in the current architecture, not just asserted: analysis runs are claimed and processed one at a time by a single queue worker, so a genuine concurrent write for one ticker requires two separately-triggered runs to overlap in wall-clock time — not routine operation.
- Other views that already aggregate to one-card-per-ticker (e.g. the Sectors view) are unaffected in behavior, since latest-per-ticker becomes true of the underlying data itself rather than something each view has to compute separately.
- The one-time cleanup (FR-006/FR-007) has no specified time bound or performance target. At this project's single-user, local-first scale, scanning the full analyses collection once is not expected to be a practical concern, and imposing a bound now would be premature optimization.
