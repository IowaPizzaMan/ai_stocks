# Phase 0 Research: Earnings Page Readability & Filters

**Feature**: `025-earnings-page-filters` | **Date**: 2026-08-17

All Technical Context unknowns are resolved below. Probes were run live against the
project's configured FMP key on 2026-08-17.

---

## D1 — Source of actuals and estimates

**Decision**: Fetch the calendar from FMP `stable/earnings-calendar?from=&to=`, replacing
Finnhub `calendar/earnings` in `backend/earnings_data.py::get_earnings_calendar`.

**Rationale**: The feature is impossible on Finnhub. Finnhub's calendar returns
`epsEstimate`/`revenueEstimate` only — no actuals — so User Story 2 (surprise for
already-reported companies) has no data source there. FMP's endpoint returns both, plus a
`lastUpdated` field that satisfies FR-029.

**This contradicts a documented project constraint, and the constraint is stale.**
`KNOWN_ISSUES.md` records under upstream API-tier constraints:

> `earnings-calendar` truncates to ~15 rows → calendar comes from Finnhub

That no longer reproduces. Live probes on 2026-08-17:

| Window | Rows returned |
|---|---|
| `from=2026-08-15&to=2026-08-19` (5 days, forward) | **789** |
| `from=2026-08-10&to=2026-08-15` (6 days, past) | **2,347** |

Field coverage on the past window: 2,146 rows carry `epsActual`, 1,697 carry
`revenueActual`, and 1,496 have both an actual and a non-zero estimate — i.e. a computable
EPS surprise. Every row exposes exactly these keys:

```text
symbol, date, epsActual, epsEstimated, revenueActual, revenueEstimated, lastUpdated
```

Either the key's entitlement changed or FMP lifted the limit. Because the whole feature
rests on this, the quickstart asserts row counts as a standing check rather than trusting
it silently, and `KNOWN_ISSUES.md` must be corrected — leaving a false constraint in place
would send the next reader back to Finnhub.

**Alternatives considered**:
- *Keep Finnhub for the calendar, fetch actuals per-symbol via FMP `earnings?symbol=`* —
  rejected: one call per company against a 250/day cap makes a 300-row window unaffordable.
- *Finnhub for future dates, FMP for past dates* — rejected: two sources for one table
  means two shapes, two failure modes, and reconciliation at the seam, for no gain now that
  FMP covers both directions.

---

## D2 — Endpoint signature

**Decision**: Change `GET /earnings/calendar?days=N` to
`GET /earnings/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD`. Do not keep `days` as an alias.

**Rationale**: `days` cannot express a backward-looking window, which is the point of the
feature. The frontend is the only consumer — `useEarningsCalendar` in
`hooks/useEarningsScan.ts` is the sole call site, and the agent-runner has its own
independent copy of the fetch layer (see D7). A compatibility alias would be dead code from
the day it shipped, which Principle V rules out.

**Alternatives considered**: a parallel `/earnings/calendar/range` endpoint — rejected, two
endpoints doing one job; `days_back`/`days_ahead` pair — rejected, still relative, so
caching and preset-resolution both have to re-derive absolute dates anyway.

---

## D3 — Where surprise is computed

**Decision**: Compute EPS and revenue surprise server-side in `earnings_data.py` as a pure
function over one entry. Return the derived values on the wire. Never store them.

**Rationale**: Constitution Principle III wants deterministic computation isolated and
exhaustively testable; Principle I calls pure functions the highest-value test surface.
A `_surprise_pct(actual, estimate)` helper covers every case the spec calls out — negative
EPS beating a negative estimate, zero estimate, missing actual, missing estimate — in fast
unit tests with no HTTP and no React. Computing it in the browser would scatter the same
logic into component tests and risk drift with the existing
`earnings_data.py::get_earnings_history`, which already computes surprise the same way.

This satisfies FR-026a: derived on read, not persisted. The 4h response cache (D6) stores
the raw provider payload, not derived values.

**Alternatives considered**: compute in the frontend — rejected per above; store computed
surprises in Mongo — rejected outright by FR-026.

---

## D4 — The bmo/amc report-time column

**Decision**: **Drop the before-open / after-close marker from the earnings table.**

**Rationale**: FMP's `stable/earnings-calendar` has no time-of-day field. The seven keys in
D1 are the complete set — there is no `time`, and no variant appeared across 3,136 probed
rows. The current UI shows this marker from Finnhub's `hour` field, so switching sources
loses it.

Recovering it would mean either keeping a parallel Finnhub call purely for one badge, or
one FMP `earnings?symbol=` call per row (that endpoint does carry `time`, which is why
`get_earnings_history` can classify bmo). Both cost real complexity or real budget for a
decorative column that no functional requirement depends on.

**This is a genuine loss, not a neutral simplification** — bmo/amc tells an earnings trader
whether today's print lands before the open or tonight — so it is surfaced here, in the
plan's Risks table, and reflected back into the spec's Key Entities rather than quietly
dropped. If it turns out to matter, the cheap path is a follow-up feature that enriches
only the rows currently on screen.

**Alternatives considered**: keep a Finnhub call solely for `hour` — rejected (second
source, second failure mode, Principle V); per-symbol FMP enrichment — rejected (budget).

---

## D5 — Market-cap screen and payload size

**Decision**: Join FMP rows against the cached Nasdaq screener universe
(`get_screener_universe`, 24h TTL) and drop any symbol absent from it, before serializing
the response.

**Rationale**: This one join does four jobs at once: supplies `market_cap` for the required
ordering (FR-019), supplies company name and sector for display, enforces the ≥$500M screen
(FR-020), and bounds the payload. It is exactly what makes the user's own noise examples
disappear — `CGXEF` and `CMCAW` are not in a ≥$500M US-listed universe, so they never reach
the client regardless of slider positions.

Sizing: a 6-day peak window returns ~2,300 raw rows; the universe holds roughly 5–6k
symbols ≥$500M, so expect ~10–15% to survive. A ±30-day in-season window should land near
1–3k rows on the wire (~10 fields each, a few hundred KB) — acceptable for a local-network
SPA, and measured in quickstart step 6 rather than assumed.

**Alternatives considered**: send everything and screen in the browser — rejected: 20k rows
over the wire, and the client has no market cap to screen or sort by; paginate — rejected as
premature, and it would break the "always ordered by market cap" guarantee across pages.

---

## D6 — Caching and budget

**Decision**: Cache each exact window as an `earnings_cache` doc keyed
`{type: "calendar_range", from, to}` with a 4h TTL, and route the fetch through
`backend/fmp.py::fmp_get`.

**Rationale**: `fmp_get` increments `fmp_usage` and raises `FmpBudgetExceededError` before
spending the call that would breach the cap, which is what Principle IV requires. Keying by
exact window makes FR-027d's cache reuse work: the six presets resolve to six stable
windows, so ordinary browsing replays cache hits rather than spending budget. The 4h TTL
matches the existing `CALENDAR_CACHE_HOURS`.

On `FmpBudgetExceededError`, serve the newest cached doc for that window regardless of age
and flag it stale in the response (FR-028); only raise if no cached doc exists at all.

**Side effect worth stating**: `earnings_data.py::_fmp_get` currently calls FMP with a bare
`requests.get` and never increments `fmp_usage` — an open KNOWN_ISSUES item whose remaining
fix is described there as "mechanical: route `earnings_data.py::_fmp_get` through
`backend.fmp.fmp_get`". This feature does exactly that, closing the item.

**Alternatives considered**: cache one wide span and slice it — rejected, contradicts the
refetch-per-window decision the user made in clarification; no cache — rejected, violates
Principle IV and would spend the daily cap on page refreshes.

---

## D7 — The agent-runner seam

**Decision**: Change only `backend/earnings_data.py`. Leave
`agent-runner/tools/earnings_calendar.py` on Finnhub.

**Rationale**: The two modules are hand-mirrored by design (the services share only MongoDB,
per Principle V) and both write `earnings_cache`. The agent-runner's copy serves the scoring
scanner, which needs a forward-looking screen and no actuals — it has no reason to change,
and changing it would widen this feature into the scan the spec just removed from the page.

**But the mirror genuinely breaks here**, and Principle VI treats silent divergence between
the layers as a bug. Two concrete consequences to record in KNOWN_ISSUES:

1. The two services now use different providers for the same concept, so their cached
   calendar docs are no longer interchangeable.
2. Cache-key collision must be avoided: the new backend docs use
   `{type: "calendar_range", ...}`, distinct from the agent-runner's existing
   `{type: "calendar", days: N}`. Reusing `type: "calendar"` would have the two services
   silently overwrite each other with different shapes — the exact failure Principle VI
   exists to prevent.

**Alternatives considered**: migrate both — rejected, scope creep into the dormant scanner;
extract a shared package — rejected explicitly by Principle V.

---

## D8 — Frontend filter state and fetching

**Decision**: Hold all filter state in URL search params via `useSearchParams`. Only
`from`/`to` reach the server; revenue floor, EPS floor, and the big-movers toggle filter
in-memory with `useMemo`.

**Rationale**: The constitution's stack constraints name "filter state in URL search params"
directly, and `InstitutionalFlowFilterBar.tsx` and `Stocks.tsx` already establish the
pattern — including the `setSearchParams(next, { replace: true })` idiom that avoids
polluting browser history. URL params also satisfy FR's session-persistence requirement
more strongly than component state, since the view survives a reload and is shareable.

TanStack Query keyed `["earnings-calendar", from, to]` gives FR-027d's cache reuse and
FR-027e's out-of-order protection for free — Query discards responses for non-current keys,
so a slow abandoned window cannot overwrite a newer one. `staleTime` of 4h mirrors the
backend cache. `refetchInterval` stays `false` per Principle V.

Custom date inputs debounce into URL params on a ~400ms timer, matching the existing
`InstitutionalFlowFilterBar` pattern, which satisfies FR-027a's "commit, not keystroke"
requirement. Preset clicks write params immediately — no debounce needed, since each click
is already exactly one window.

**Alternatives considered**: `useState` — rejected, contradicts the constitution and loses
state on reload; a reducer or state library — rejected, four scalar values do not need one.
