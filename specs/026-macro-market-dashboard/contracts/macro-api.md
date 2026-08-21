# Contract: Macro Dashboard API

**Feature**: `026-macro-market-dashboard` · Phase 1 output
**Consumers**: `frontend/src/hooks/useEconomics.ts` → `pages/Macro.tsx` · **Producer**: `backend/routers/market.py`

Four new read-only endpoints under the existing `/market` prefix. They follow the seam that router already documents: **the agent-runner computes and caches, the router shapes and serves.** No endpoint here calls an external provider (FR-030).

Derived-field semantics (spread math, comparison classification, direction) are pinned in [../data-model.md §6](../data-model.md) and are not repeated here.

---

## Universal rules

**Always 200.** Every endpoint backs a panel on a dashboard where a red error state is worse than an empty, labeled one — the same rule `GET /market/news` already follows. An empty collection returns an empty payload with `as_of: null`, never a 4xx/5xx.

**Freshness envelope on every response:**

```jsonc
{ "as_of": "2026-08-20T21:04:11Z" | null,   // dataset_meta.last_success_at
  "stale": false }                           // true when last_run_status == "failed"
```

`stale: true` means the newest refresh failed and what follows is the previous good data (FR-028). The panel renders it with a visible age rather than an error.

---

## `GET /market/treasury-curve`

Query: `lookback_days` (int, default 180, 30–750) — bounds the spread trend series only; the curve comparison always reaches back a full year.

```jsonc
{
  "as_of": "2026-08-20T21:04:11Z",
  "stale": false,
  "session": "2026-08-19",              // latest stored session; null when empty
  "curve": [
    { "maturity": "1M",  "months": 1,   "current": 3.77, "month_ago": 3.81, "year_ago": 4.92 },
    { "maturity": "10Y", "months": 120, "current": 4.65, "month_ago": 4.58, "year_ago": 3.91 },
    { "maturity": "30Y", "months": 360, "current": 5.19, "month_ago": 5.11, "year_ago": 4.22 }
  ],
  "comparison_sessions": {              // the sessions the overlays actually resolved to
    "month_ago": "2026-07-18",
    "year_ago": null                    // null ⇒ history doesn't reach; overlay omitted
  },
  "spreads": [
    { "key": "10y-2y",  "label": "10y – 2y",  "current_bps": 46.0,
      "change_bps": -6.0, "inverted": false,
      "series": [ { "date": "2026-08-18", "bps": 52.0 }, { "date": "2026-08-19", "bps": 46.0 } ] }
  ]
}
```

**Rules**
- `curve[]` covers every maturity present in the latest session, ordered by `months` ascending. A maturity missing from a session is `null` in that column — clients draw a gap, never a zero (FR-011, spec Edge Cases).
- `months` is the numeric X value. Maturities are **not** evenly spaced; a category axis would misrepresent curve shape.
- `comparison_sessions` reports the session each overlay actually snapped to (nearest at or before target). A `null` means the overlay is unavailable and the client omits that line rather than approximating it.
- `spreads[]` always contains exactly the three keys `10y-2y`, `30y-10y`, `10y-3m`, in that order, even when a maturity is missing — an unavailable spread carries `current_bps: null` so the tile can say so.
- `change_bps` compares against the **previous stored session**, not calendar yesterday (FR-014).
- Empty collection → `session: null`, `curve: []`, `spreads: []` with all three keys still present but null-valued.

---

## `GET /market/economic-calendar`

Query: `forward_days` (default 14, 1–30), `back_days` (default 7, 1–30).

```jsonc
{
  "as_of": "2026-08-20T21:04:11Z",
  "stale": false,
  "timezone": "America/New_York",       // explicit label; FR-022
  "upcoming": [
    { "date": "2026-09-04T12:30:00Z", "event": "Average Hourly Earnings YoY (Aug)",
      "impact": "High", "previous": 3.2, "estimate": 3.3, "unit": "%" }
  ],
  "reported": [
    { "date": "2026-08-19T12:30:00Z", "event": "Retail Sales MoM (Jul)",
      "impact": "High", "previous": 0.4, "estimate": 0.3, "actual": 0.6, "unit": "%",
      "comparison": "above", "surprise": 0.3 }
  ]
}
```

**Rules**
- `upcoming[]` is chronological ascending; `reported[]` is reverse-chronological.
- An event scheduled **later today** belongs in `upcoming`, not `reported` (FR-023). The split is on `date > now`, not on calendar day.
- An event is `reported` only when `actual != null`. A past-dated event still awaiting its print stays in neither list rather than appearing as a null-valued result.
- `comparison` is `null` when `estimate` is null — FR-021c. It is never defaulted to `in_line`.
- `comparison` carries **no polarity**. `"above"` means numerically above the estimate and nothing more; the response deliberately contains no good/bad field (FR-021b).
- `timezone` is returned so the client labels times without hardcoding the assumption.
- Empty window → both arrays empty; the client renders "no major releases scheduled" (FR-018 edge case), not an error.

---

## `GET /market/economic-indicators`

```jsonc
{
  "as_of": "2026-08-20T21:04:11Z",
  "stale": false,
  "indicators": [
    { "key": "growth",     "label": "GDP",           "series": "GDP",
      "value": 31422.526, "unit": "USD bn", "as_of": "2025-10-01",
      "direction": null,  "change": null,  "lagging": true },
    { "key": "inflation",  "label": "Inflation rate", "series": "inflationRate",
      "value": 2.27, "unit": "%", "as_of": "2025-11-19",
      "direction": "down", "change": -0.11, "lagging": true }
  ]
}
```

**Rules**
- `indicators[]` is ordered `growth`, `inflation`, `employment`, `policy_rate`, then any optional consumer tiles — a fixed order so the row does not reshuffle between loads.
- `direction` and `change` are `null` when no prior reading has been retained. The client omits the direction glyph entirely; it must **not** render null as flat or unchanged (FR-024a).
- `as_of` is the **period the reading refers to**, not when it was fetched. These differ by months for this source.
- `lagging: true` when `as_of` is older than 90 days (FR-026a). Expect this to be true for most series — it is a normal state, not an error.
- A series that has never been fetched is omitted from the array rather than included with a null value, so a partial pull degrades to fewer tiles rather than broken ones (FR-024's per-indicator independence).

---

## `GET /market/risk-premium`

```jsonc
{
  "as_of": "2026-08-20T21:04:11Z",
  "stale": false,
  "country": "United States",
  "total_equity_risk_premium": 4.46,
  "country_risk_premium": 0.23,
  "collected_at": "2026-08-20T21:04:11Z"
}
```

**Rules**
- Single US row. Never an array — the page renders one tile (FR-025).
- `collected_at` is the as-of proxy; the provider supplies no revision date (research D5). The client labels the tile as a slow-moving valuation input, which is also why no history is served.
- Nothing stored → all value fields `null`, `as_of: null`. The tile shows unavailable.

---

## Frontend consumption contract

`frontend/src/hooks/useEconomics.ts` exposes one query per endpoint.

- **`staleTime: 24h`, `refetchInterval: false`** on all four — the underlying data refreshes once daily and the constitution forbids polling.
- **Four independent queries, not one composite.** FR-027 requires each section to render and fail on its own; a single combined query would couple their loading and error states.
- Each panel renders its own loading skeleton, its own empty state, and its own `stale` badge. No panel's failure is allowed to unmount another.
- The page-level empty state (FR-031) appears only when **all four** queries plus breadth have resolved with nothing — it is a composition of the section states, not a fifth query.

### Breadth panel (no new endpoint)

`GET /market/breadth` and `GET /market/flow-events` are unchanged. Two behavioral changes are client-side only:

- `MarketFlowCard`'s `event` prop becomes optional. With no event: neutral `border-zinc-800`, no headline row, chart and divergence text still rendered (FR-002a).
- `BreadthDivergenceChart` renders `namo` as a second line on the existing oscillator pane and drops its `oscillator` prop and toggle. The divergence overlay stays bound to NYMO (FR-008).

The `MarketBreadth` response already carries both `nymo` and `namo` arrays, so no API or type change is required.
