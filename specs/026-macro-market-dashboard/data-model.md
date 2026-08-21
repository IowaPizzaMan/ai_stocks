# Phase 1 Data Model: Macro Market Dashboard

**Feature**: `026-macro-market-dashboard` · **Date**: 2026-08-21

Four MongoDB collections, all already named as constants in `backend/db.py` and `agent-runner/tools/db.py` (reserved by `017-fmp-migration-admin`, never written to). Shapes below supersede 017's data-model where noted — see plan.md Complexity Tracking for the recorded amendment.

Written by `agent-runner/tools/economics.py`. Read by `backend/routers/market.py`. Nothing else touches them.

---

## 1. `treasury_rates` — maintained store, no TTL

One document per trading session. This is a **store, not a cache**: it accumulates via backfill + daily extension, and a TTL index would destroy the history FR-012 and FR-016 depend on. Same discipline as `price_history` from spec 024.

| Field | Type | Notes |
|---|---|---|
| `date` | string `YYYY-MM-DD` | **unique index**. Provider's session date |
| `m1`, `m2`, `m3`, `m6` | float \| null | 1/2/3/6-month yields, percent |
| `y1`, `y2`, `y3`, `y5`, `y7`, `y10`, `y20`, `y30` | float \| null | 1–30-year yields, percent |
| `source` | string | `"fmp"` |
| `collected_at` | datetime (UTC) | when this row was written |

**Provider field mapping** (`month1` → `m1`, `year10` → `y10`, etc.). A maturity absent from the response stores as `null`, never `0` — spec Edge Cases requires the curve to skip the point rather than plot a zero.

**Index**: `date` ascending, unique. Upsert on `date` so re-fetching an overlapping window is idempotent.

**Validation**:
- `date` must parse as a calendar date; rows failing this are skipped, not stored.
- A row with every maturity `null` is not stored.

---

## 2. `economic_calendar_events` — refreshed window

US high/medium-impact releases only, filtered at collect time (research D6).

| Field | Type | Notes |
|---|---|---|
| `date` | datetime (UTC) | **unique with `event`**. Provider returns naive UTC |
| `event` | string | release name, e.g. `"Core CPI YoY (Aug)"` |
| `country` | string | always `"US"` after filtering |
| `currency` | string \| null | |
| `impact` | string | `"High"` \| `"Medium"` |
| `previous` | float \| null | prior period's reading |
| `estimate` | float \| null | consensus; **null is meaningful** — FR-020 renders it as unavailable |
| `actual` | float \| null | null until reported |
| `unit` | string \| null | `"%"`, `"K"`, … |
| `source`, `collected_at` | — | envelope |

**No derived outcome is stored.** Above/below/in-line and surprise magnitude are computed at read time (§6) — FR-021b forbids a stored polarity, and keeping the classification in a pure function keeps it testable and correctable.

**Index**: compound `(date, event)` unique; `date` descending for range queries.

**Refresh semantics**: upsert over the `today − 7d … today + 14d` window each run, so an event's `actual` fills in as it reports and estimates get revised in place. Documents older than the window are pruned on each successful run — the page never looks further back than 7 days.

---

## 3. `economic_indicators` — accumulating readings

**Amended from 017**: that spec restricted this collection to *"only series NOT in `tools/macro.py` DEFAULT_INDICATORS"*. Spec 026 Q4 makes FMP the single source for the four backdrop tiles, which overlap FRED. The restriction is lifted (research D3).

| Field | Type | Notes |
|---|---|---|
| `indicator` | string | **unique with `date`**. Provider series name, e.g. `"inflationRate"` |
| `date` | string `YYYY-MM-DD` | the period the reading refers to, **not** when it was fetched |
| `value` | float | |
| `source`, `collected_at` | — | envelope |

**Retention is the point** (FR-024b). The provider returns 1–3 readings for most series, so direction-versus-prior is unavailable on first run for `GDP`. Every fetched reading is upserted and kept; over successive runs the collection accumulates the prior values that FR-024a needs. Nothing is pruned.

**Series pulled** (research D4):

| Tile | Series | Depth at probe |
|---|---|---|
| Growth | `GDP` | 1 reading — ships with no direction until retention supplies one |
| Inflation | `inflationRate` | 62 readings — direction and trend immediately |
| Employment | `unemploymentRate` | 2 readings |
| Policy rate | `federalFunds` | 3 readings |
| Consumer *(optional)* | `retailSales`, `consumerSentiment` | 3 readings each |

**Index**: compound `(indicator, date)` unique; `(indicator, date DESC)` for latest-two lookups.

---

## 4. `market_risk_premium` — single US row

**Amended from 017**: that spec keyed this on a provider `date` field. The endpoint returns no date (research D5) — its only keys are `country`, `continent`, `countryRiskPremium`, `totalEquityRiskPremium`.

| Field | Type | Notes |
|---|---|---|
| `country` | string | **unique index**. Always `"United States"` — filtered at collect time |
| `total_equity_risk_premium` | float | e.g. `4.46` |
| `country_risk_premium` | float | e.g. `0.23` |
| `source` | string | `"fmp"` |
| `collected_at` | datetime (UTC) | serves as the as-of date, since the provider supplies none |

Replaced in place each run. One document, always.

---

## 5. Freshness envelope

`economics_pull` reports as a **single dataset** for freshness purposes, per 017's contract (*"writes four collections but reports as one job/dataset"*):

```
dataset_meta: { dataset: "economics", last_success_at, record_count, last_run_status, source: "fmp" }
```

Written via the existing `agent-runner/tools/db.write_dataset_meta`. `record_count` is the sum of rows written across all four collections. A failed run writes `last_run_status: "failed"` **without** advancing `last_success_at` — the helper already enforces this, so a partial failure can never claim fresher data than it wrote (FR-028's fail-soft contract depends on it).

**Backfill guard**: a `dataset_meta`-style marker `{ dataset: "economics_backfill", last_success_at }` records that the one-time 2-year Treasury backfill completed. Its presence is what makes the backfill run once (FR-017a). If absent or failed, the next run retries it.

---

## 6. Derived read shapes (computed, never stored)

These exist only in the response bodies defined in [contracts/macro-api.md](contracts/macro-api.md). Each is produced by a pure function — the deterministic-core surface constitution I wants exhaustively tested.

### Yield spreads

```
Spread { key: "10y-2y" | "30y-10y" | "10y-3m",
         label, current_bps, change_bps, inverted, series: [{date, bps}] }
```

Pure functions, split so each is independently testable:

| Function | Contract |
|---|---|
| `spread_bps(row, long_key, short_key)` | `(row[long] - row[short]) * 100`, rounded to 1dp. Returns `null` if either maturity is `null` |
| `spread_series(rows, long, short)` | maps `spread_bps` over sessions, dropping nulls |
| `session_change(series)` | last minus **previous stored session** — never calendar yesterday (spec Edge Cases: weekends/holidays have no row) |
| `is_inverted(bps)` | `bps < 0`. Exactly zero is not inverted |

### Curve comparison

```
CurvePoint { maturity: "1M".."30Y", months: 1..360, current, month_ago, year_ago }
```

| Function | Contract |
|---|---|
| `nearest_session(dates, target)` | latest stored session **at or before** `target`. Returns `null` when history does not reach back that far — the overlay is then omitted, never approximated (spec Assumptions) |
| `align_curve(current_row, m1_row, y1_row)` | one point per maturity; `months` supplies the numeric X so the axis is proportional, not evenly spaced. A `null` maturity yields a gap, not a zero |

The `months` field matters: plotting maturities as equal-width categories would misrepresent curve shape — the gap between 20Y and 30Y is not the gap between 1M and 2M.

### Calendar outcome

```
ReportedEvent { …event fields, comparison: "above" | "below" | "in_line" | null, surprise: float | null }
```

| Function | Contract |
|---|---|
| `classify(actual, estimate)` | `null` when either is `null` (FR-021c — no estimate means no comparison, **not** `in_line`); `in_line` on exact equality; otherwise `above`/`below` |
| `surprise(actual, estimate)` | `actual - estimate`, or `null` |

`classify` asserts **no market-direction polarity** (FR-021b). There is no good/bad mapping anywhere in the codebase for this feature, by design.

### Indicator direction

```
IndicatorTile { key, label, value, as_of, direction: "up" | "down" | "flat" | null,
                change, lagging: bool }
```

| Function | Contract |
|---|---|
| `direction(latest, prior)` | `null` when `prior` is absent — FR-024a forbids rendering a missing prior as `flat` or `0` |
| `is_lagging(as_of, now)` | `as_of` older than 90 days (FR-026a). Expected `true` for most series from this source, so it is a normal state, not an error |

---

## 7. Entity relationships

No cross-collection references. Each of the four is independently readable and independently failable — a design property FR-027 requires, since one section going dark must not take the others with it. The page composes them; the database does not join them.

`treasury_rates` is the only collection with meaningful internal ordering (session sequence), and it is the only one that grows without bound — ~250 rows/year, ~500 at steady state after backfill.
