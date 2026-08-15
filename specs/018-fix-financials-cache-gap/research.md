# Research: Fix Stale Empty Financials Cache

**Feature**: 018-fix-financials-cache-gap | **Date**: 2026-08-15

No NEEDS CLARIFICATION markers remained in the Technical Context — the root cause was
confirmed against the running system during `/speckit-clarify` (live Mongo inspection +
recovered 2026-08-09 agent-runner log). The decisions below resolve the design unknowns.

## D1: How to mark retry-eligible results — per-key `outcomes` map on the cache doc

**Decision**: Add one additive field to each `financials_cache` document:
`outcomes: {<statement_key>: "confirmed" | "unavailable"}`, written at fetch time.
`confirmed` = FMP returned HTTP 200 (whether the payload had records or was affirmatively
empty). `unavailable` = the key degraded to `[]` because of a 402/403 or
`FmpBudgetExceededError`.

**Rationale**: The ambiguity that caused this bug is that `[]` in `data` has two meanings.
An explicit per-key marker removes the ambiguity without changing the shape of `data`
itself, so every existing consumer (`agents/fundamental_analyst.py`, backend
`/stocks/{ticker}/financials`) keeps working unmodified. Two states are enough: the
`data` value already distinguishes "confirmed with records" from "confirmed empty".

**Alternatives considered**:
- *Don't cache failed fetches at all*: rejected — a single 402'd key would force re-fetching
  all seven keys every run (wasting calls on the six that succeeded), and callers expect all
  seven keys present in the returned dict.
- *Shorter TTL for empty results (e.g., 24h)*: rejected — still conflates "confirmed no
  data" with "temporarily unavailable", violating FR-002/FR-003, and adds a second TTL
  constant to reason about.
- *Three-state map (`ok` / `empty_confirmed` / `unavailable`)*: rejected — the third state
  duplicates information already present in `data[key]`; two states keep the invariant
  minimal.

## D2: Retry cadence — every analysis run, no extra cooldown

**Decision**: On a warm cache hit, re-fetch every `unavailable` key on that run; no
per-ticker or per-key cooldown beyond the existing `fmp_client` throttle and daily soft cap.

**Rationale**: User decision from the 2026-08-15 clarification session. Analysis is only
triggered manually per ticker (constitution Principle V: all triggering flows through
`work_queue`, never cron), so retry volume is bounded by the user's own trigger frequency —
at most 7 extra FMP calls per run. Live evidence showed FMP coverage for BSX flipped within
~6 days, so long cooldowns directly delay recovery.

**Alternatives considered**: cause-specific cooldowns (budget=next-day, 402=weekly) and a
fixed 24h cooldown — both rejected by the user after the budget guard was confirmed
disabled in this deployment and coverage was shown to change within days.

## D3: Legacy documents — treat outcome-less empty keys as unavailable

**Decision**: A cached doc with no `outcomes` field (written before this fix) treats any
key whose `data` value is empty as `unavailable` (retry-eligible) and any non-empty key as
`confirmed`.

**Rationale**: This makes the fix self-correcting for the reported BSX case — the next
analysis run retries all seven empty keys, and FMP now returns data. No manual cache
clearing, no migration script (spec FR-005 and the third edge case). The cost is bounded:
a legacy ticker whose statement type is *genuinely* empty gets retried once, comes back
200-empty, and is recorded `confirmed` — one extra call per such key, once ever.

**Alternatives considered**: one-off migration script to stamp `outcomes` onto existing
docs — rejected as unneeded infra (Principle V); the lazy interpretation achieves the same
end state through the code path that must exist anyway.

## D4: `fetched_at` semantics on partial retry — preserve the full-fetch timestamp

**Decision**: A partial retry (re-fetching only `unavailable` keys) updates `data` and
`outcomes` but does NOT bump `fetched_at`. Only a full fetch (cache miss / 90-day expiry)
sets a new `fetched_at`.

**Rationale**: If retries bumped `fetched_at`, a ticker with a persistently-unavailable key
would slide its window forward on every run and its *confirmed* keys would never hit the
90-day refresh. Preserving the original timestamp keeps the spec's "existing 90-day window
for confirmed results is out of scope to change" assumption literally true. Side effect:
data recovered by a day-6 retry expires on day 90 rather than day 96 — an earlier refresh,
harmless.

**Alternatives considered**: per-key `fetched_at` — rejected as complexity with no user
value at this scale (Principle V).

## D5: Error classification — unchanged raise/degrade boundaries

**Decision**: Keep the existing classification in `get_financials`: HTTP 402/403 and
`FmpBudgetExceededError` degrade to `[]` (now recorded `unavailable`); any other
`requests.HTTPError` continues to raise (nothing cached for that run). HTTP 200 with an
empty body is `confirmed`.

**Rationale**: The spec's Assumptions section directs unfamiliar errors into one of the two
buckets rather than inventing new ones; a raise means "no result at all", which is already
correctly not cached. Matches the current tested behavior
(`test_restricted_symbol_402_degrades_to_empty`, `test_budget_exceeded_degrades_to_empty`).

**Alternatives considered**: treating 5xx/timeouts as `unavailable` too — deferred; today
they abort the fetch before the cache write, which already produces a retry on the next run
(no doc within the window), so behavior is equivalent without new code.
