# Data Integrity & Migration Safety Checklist: Deduplicate Analysis Feed & Storage

**Purpose**: Validate requirements quality for the highest-risk part of this spec — the upsert-on-write replacement behavior, the one-time cleanup of existing duplicates, and concurrency/re-run safety — before proceeding to `/speckit-plan`.
**Created**: 2026-08-14
**Reviewed**: 2026-08-15 (post-plan/tasks, before `/speckit-implement`)
**Feature**: [spec.md](../spec.md)

**Note**: This checklist tests whether the requirements are complete, clear, consistent, and measurable — not whether any implementation works. Depth: standard pre-plan review.

## Requirement Completeness

- [x] CHK001 Is the trigger mechanism for the one-time cleanup specified (e.g., automatic at startup vs. manual invocation)? [Completeness, Gap, Spec §FR-006] — Resolved: FR-006 now states it's a manually-triggered, one-time operator action, not automatic/unattended.
- [x] CHK002 Are requirements defined for what happens if the replace-on-write operation fails partway through (e.g., a DB error during the write)? [Completeness, Gap, Spec §FR-004] — Resolved: FR-004 now requires a failed write to leave the previous analysis unchanged (no partial/missing record).
- [x] CHK003 Is there a requirement for how "most recent" is determined when two stored analyses for the same ticker have identical timestamps (tie-breaking)? [Completeness, Gap, Spec §User Story 3] — Resolved: new Edge Case + US3 Acceptance Scenario 1 note — either tied record may be kept, no deterministic tie-break required.
- [x] CHK004 Are requirements defined for confirming or reporting the outcome of the one-time cleanup (e.g., how many records were removed, success/failure signal)? [Completeness, Gap, Spec §FR-006] — Resolved: FR-006 now requires reporting how many records were removed.
- [x] CHK005 Is it specified whether "one analysis per ticker" is enforced only at the application layer, or whether a data-level guarantee is also required? [Completeness, Spec §FR-004] — Resolved: FR-004 clarifies the application-layer write path is the requirement; a DB-level uniqueness guarantee is allowed but not separately mandated.

## Requirement Clarity

- [x] CHK006 Is "close succession" (used to describe overlapping analysis completions) given any bound, or is it intentionally left unbounded? [Clarity, Spec §User Story 2] — Already adequate: Edge Cases/Assumptions intentionally leave it unbounded — no locking/queueing is required regardless of how close.
- [x] CHK007 Is "most recent timestamp" tied to a specific, named field on the Analysis entity? [Clarity, Spec §Key Entities] — Intentionally left abstract; naming the concrete field is a data-model concern (see data-model.md), not a spec-level detail per this project's spec-writing conventions.
- [x] CHK008 Is "safe to run more than once" defined precisely enough to be objectively verified (e.g., no side effects, no errors, unchanged record count on a second run)? [Measurability, Spec §FR-007] — Already adequate: US3's Independent Test states this directly (re-run makes no further changes).

## Requirement Consistency

- [x] CHK009 Do FR-004 (replace on write) and FR-006 (one-time cleanup) agree on what counts as a "duplicate" for a ticker, so the same test data would satisfy both? [Consistency, Spec §FR-004, §FR-006] — Already adequate: the Assumptions section's single definition ("multiple stored analyses for the same ticker, regardless of time separation") applies to both.
- [x] CHK010 Is the "last write wins" resolution described in Edge Cases consistent with the replace-in-place mechanism implied by FR-004, or could the two be satisfied by contradictory implementations? [Consistency, Spec §Edge Cases, §FR-004] — Already adequate: both describe the same replace-in-place, last-writer-determines-final-state behavior.

## Acceptance Criteria Quality

- [x] CHK011 Can SC-002 ("verified immediately after the run completes") be objectively checked without assuming an implementation detail of how a caller knows the run has completed? [Measurability, Spec §SC-002] — Already adequate: measured as a storage query after the completion event, not tied to a specific implementation.
- [x] CHK012 Does SC-003 specify how "distinct tickers that have ever been analyzed" is determined, given that FR-005 removes the historical records that might otherwise establish that count? [Measurability, Spec §SC-003, §FR-005] — Resolved: SC-003 reworded to `count(*) == count(DISTINCT ticker)`, computed from the post-cleanup collection itself — no separate history needed since FR-006 (not FR-005) is what collapses duplicates.
- [x] CHK013 Are acceptance criteria defined for verifying the cleanup did not remove the wrong record when duplicate timestamps exist for a ticker? [Acceptance Criteria, Gap] — Resolved: US3 Acceptance Scenario 1 now explicitly allows either tied record as a valid outcome.

## Scenario Coverage

- [x] CHK014 Is there a requirement covering what happens if the cleanup is interrupted partway through (e.g., a process restart mid-run)? [Coverage, Exception Flow, Gap, Spec §FR-007] — Resolved: new Edge Case + FR-007 addition — per-ticker independence means an interrupted run is safely resumable by re-running.
- [x] CHK015 Are requirements defined for a ticker that has zero stored analyses (never analyzed) when its per-ticker lookup is queried? [Coverage, Edge Case, Gap, Spec §FR-005] — Resolved: FR-005 + new Edge Case — returns empty/no-result, not an error.
- [x] CHK016 Is there a requirement covering how the cleanup should behave if it encounters duplicate records with missing or malformed timestamp data? [Coverage, Exception Flow, Gap] — Resolved: FR-006 now requires deterministic handling (treat as oldest) rather than erroring or skipping.

## Edge Case Coverage

- [x] CHK017 Is the "last write wins" tie-breaking rule specific enough to be tested deterministically, or does it rely on ordering guarantees not described in the spec? [Edge Case, Ambiguity, Spec §Edge Cases] — Resolved: new Edge Case text clarifies "last" means actual write order, not a timestamp comparison — testable by controlling which write happens last.
- [x] CHK018 Are requirements defined for what should happen if the one-time cleanup runs while new analyses are actively completing for other tickers? [Edge Case, Gap, Spec §FR-006] — Resolved: new Edge Case — safe by construction since cleanup considers each ticker independently.

## Non-Functional Requirements

- [x] CHK019 Is there a requirement bounding how long the one-time cleanup is allowed to take, given it may need to scan the full analyses collection? [Non-Functional, Gap] — Resolved: new Assumptions bullet — intentionally unbounded; a hard SLA would be premature optimization at this project's scale.
- [x] CHK020 Does the spec establish whether the cleanup runs synchronously (blocking startup or other operations) or independently of them? [Non-Functional, Gap] — Resolved by the same FR-006 change as CHK001: it's a standalone manual operator action, not coupled to service startup.

## Dependencies & Assumptions

- [x] CHK021 Is the assumption that "concurrent analyses for the same ticker are rare" validated against actual system behavior (e.g., queue/worker concurrency limits), or asserted without supporting basis? [Assumption, Spec §Assumptions] — Resolved: Assumptions now grounds this in the current single-queue-worker architecture rather than asserting it bare.
- [x] CHK022 Is the dependency between FR-005 (per-ticker lookups return only the latest) and any other feature that may still expect historical analysis data documented? [Dependency, Gap] — Already adequate: Edge Cases already documents the Analysis History Timeline's removal as the consequence of this dependency.

## Ambiguities & Conflicts

- [x] CHK023 Is it unambiguous whether "replace" (FR-004) means the prior record's identity is reused, or that a new record entirely replaces it — and does that distinction matter elsewhere in the spec? [Ambiguity, Spec §FR-004] — Resolved: FR-004 now states identity reuse vs. full replacement is unspecified/immaterial, provided the one-record-per-ticker invariant holds continuously.
- [x] CHK024 Is there a documented way to verify SC-003's target ("zero duplicate tickers remain") post-cleanup, or does the spec assert the outcome without a corresponding verification requirement? [Conflict, Gap, Spec §SC-003, §FR-006] — Resolved by the same SC-003 reword as CHK012 — the `count(*) == count(DISTINCT ticker)` form is directly verifiable.

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline
- Link to relevant resources or documentation
- Items are numbered sequentially for easy reference
- All 24 items resolved on 2026-08-15: 17 via direct spec.md edits (FR-004, FR-005, FR-006, FR-007, SC-003, Edge Cases, Assumptions, US3 Acceptance Scenario 1); 7 already adequate as originally written (CHK006, CHK007, CHK008, CHK009, CHK010, CHK011, CHK022). Spec is ready to proceed to `/speckit-implement`.
