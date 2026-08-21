# Phase 1 Data Model: Earnings Page Readability & Filters

**Feature**: `025-earnings-page-filters` | **Date**: 2026-08-17

Nothing here is persisted. These are wire shapes and in-memory structures; the only thing
that touches MongoDB is the raw provider response held in `earnings_cache` for 4h
(research.md D6). See spec FR-026.

---

## 1. Provider payload (input)

FMP `stable/earnings-calendar?from=&to=` returns a flat JSON array. Verified key set —
these seven and no others (research.md D1):

| Field | Type | Notes |
|---|---|---|
| `symbol` | string | Not unique within a window — duplicates observed |
| `date` | string `YYYY-MM-DD` | Report date |
| `epsActual` | number \| null | null when not yet reported or not published |
| `epsEstimated` | number \| null | null when no analyst coverage |
| `revenueActual` | number \| null | Absolute currency units |
| `revenueEstimated` | number \| null | Absolute currency units |
| `lastUpdated` | string `YYYY-MM-DD` | Provider's last touch — feeds FR-029 |

**No time-of-day field.** The bmo/amc marker is unavailable from this endpoint (D4).

---

## 2. `EarningsCalendarEntry` (output — the wire contract)

One row of the table. Produced by joining a provider row to the screener universe and
deriving the surprise fields.

| Field | Type | Source | Notes |
|---|---|---|---|
| `ticker` | string | `symbol`, uppercased | |
| `company` | string | universe | |
| `sector` | string \| null | universe | |
| `market_cap` | number | universe | Always present — absence excludes the row (§5) |
| `report_date` | string `YYYY-MM-DD` | `date` | |
| `eps_estimate` | number \| null | `epsEstimated` | |
| `eps_actual` | number \| null | `epsActual` | |
| `revenue_estimate` | number \| null | `revenueEstimated` | |
| `revenue_actual` | number \| null | `revenueActual` | |
| `eps_surprise_pct` | number \| null | derived (§4) | null means "cannot be computed" |
| `revenue_surprise_pct` | number \| null | derived (§4) | |
| `beat` | bool \| null | derived (§4) | Keyed off EPS; null when no surprise |
| `reporting_state` | enum (§3) | derived | |
| `last_updated` | string `YYYY-MM-DD` | `lastUpdated` | FR-029 |

**Removed from the previous shape**: `report_time`. This is a breaking change for
`api/types.ts` and every consumer — see contracts/earnings-calendar.md.

---

## 3. `reporting_state` enum

Drives FR-013's three-way row treatment. Derived, never sent by the provider.

| Value | Condition | UI treatment |
|---|---|---|
| `upcoming` | `report_date` is today or later, no actuals present | Show estimates; actual and surprise columns read "—" |
| `reported` | Any actual present (`eps_actual` or `revenue_actual` non-null) | Show actuals and whatever surprise is computable |
| `awaiting` | `report_date` is in the past but both actuals are null | Explicitly "awaiting results" — **must not render as a miss** (spec Edge Cases) |

The `awaiting` state is the one most likely to be skipped in implementation and the one the
spec calls out by name. A past date with no actuals is a real and common condition — 201 of
2,347 rows in the probed past window (D1) — not an error.

---

## 4. Surprise derivation

Pure function, backend, unit-tested (research.md D3):

```text
surprise_pct(actual, estimate):
    if actual is None:      return None
    if estimate is None:    return None
    if estimate == 0:       return None          # FR-011: never divide by zero
    return round((actual - estimate) / abs(estimate) * 100, 2)
```

`abs(estimate)` in the denominator is what makes negative EPS behave. Worked cases:

| actual | estimate | result | reading |
|---|---|---|---|
| 1.20 | 1.00 | `+20.0` | beat |
| 0.80 | 1.00 | `−20.0` | miss |
| −0.20 | −0.30 | `+33.33` | **beat** — lost less than feared |
| −0.40 | −0.30 | `−33.33` | miss — lost more |
| 0.06 | null | `null` | actual with no coverage (real: `BEBE`) |
| 0.06 | 0 | `null` | zero estimate |
| null | 1.00 | `null` | not yet reported |

Without `abs()`, the third row inverts to `−33.33` and a company that beat is painted as a
miss. This is the single highest-value assertion in the suite.

`beat` is `eps_surprise_pct > 0` when that value exists, otherwise `null`. A null `beat`
must render as unavailable, never as `false` — FR-011 forbids showing an uncomputable
surprise as a miss.

---

## 5. Screening, dedupe, and ordering

Applied in this order, server-side:

1. **Screen** — drop any row whose `symbol` is absent from the screener universe. This
   enforces the ≥$500M floor (FR-020) and guarantees `market_cap` is non-null downstream
   (spec Edge Cases: a row with no market cap has no defined sort position, so it is
   excluded rather than sorted arbitrarily).
2. **Dedupe** — duplicate symbols occur in real payloads (`NVVE`, `ZCAR`, `SDOT`, `UGP` and
   others observed in a single 6-day window). Collapse on `ticker` keeping the row with the
   latest `last_updated`; tie-break on the later `report_date` so a stale duplicate cannot
   displace a fresh one. Per spec Edge Cases.
3. **Order** — sort by `market_cap` descending, tie-break `ticker` ascending for stability.
   FR-019 makes this fixed and non-overridable, so the backend emits sorted rows and the
   frontend preserves that order rather than re-sorting.

Client-side filtering (§6) only ever removes rows, so the ordering guarantee survives it.

---

## 6. `FilterState` (frontend, URL search params)

| Param | Type | Default | Reaches server? |
|---|---|---|---|
| `from` | `YYYY-MM-DD` | today − 2 | **Yes** |
| `to` | `YYYY-MM-DD` | today + 2 | **Yes** |
| `min_rev` | number | `10000000` ($10M) | No — client-side |
| `min_eps` | number | `0.01` | No — client-side |
| `movers` | `"1"` \| absent | absent (off) | No — client-side |

Defaults are omitted from the URL rather than written to it, so a bare `/earnings` is the
default view and the URL stays readable.

**Client-side predicate** (FR-017, FR-016b), applied to fetched rows:

```text
keep(row):
    rev = row.revenue_actual ?? row.revenue_estimate
    eps = row.eps_actual     ?? row.eps_estimate

    if min_rev > 0 and (rev is None or rev < min_rev):        drop
    if min_eps > 0 and (eps is None or abs(eps) < min_eps):   drop
    if movers:
        s_eps = row.eps_surprise_pct
        s_rev = row.revenue_surprise_pct
        if s_eps is None and s_rev is None:                   drop
        if max(abs(s_eps or 0), abs(s_rev or 0)) < 10:        drop
    keep
```

Two details the spec pins down and this predicate honors:

- **A floor at zero filters nothing.** `min_rev > 0` guards the null check, so a slider at
  its minimum keeps rows with no figure at all (FR-017). Above zero, missing figures are
  excluded — which is precisely what removes the all-dashes noise rows.
- **`abs(eps)`** means a large loss counts as significant. A company printing −2.50 is
  material news and must not be filtered out by a magnitude floor (FR-016).

---

## 7. Date preset resolution

Presets are pure functions of "today", resolved at click time (spec Assumptions):

| Preset | `from` | `to` |
|---|---|---|
| Today | today | today |
| ±2 days *(default)* | today − 2 | today + 2 |
| Last 7 days | today − 7 | today |
| Next 7 days | today | today + 7 |
| ±2 weeks | today − 14 | today + 14 |
| ±1 month | today − 30 | today + 30 |

A preset is shown active when both resolved dates equal the current `from`/`to` params
(FR-001b); otherwise no preset is highlighted. Selecting one writes both params, which also
populates the custom inputs (FR-001c).
