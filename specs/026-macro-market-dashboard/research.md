# Phase 0 Research: Macro Market Dashboard

**Feature**: `026-macro-market-dashboard` · **Date**: 2026-08-21

All provider behavior below was verified live against the stable API on 2026-08-21, not assumed from documentation. Three of the findings contradict what the endpoints appear to promise, and each one changed a design decision.

---

## D1: Who refreshes the data — agent-runner worker, not backend-on-request

**Decision**: A new `agent-runner/economics_worker.py` runs once daily on the existing `main.py` timer loop, and the same logic registers as the `economics_pull` handler in `tools/admin_jobs.py` so it can also be triggered on demand through `work_queue`.

**Rationale**: This was the question deferred out of `/speckit-clarify`, and the codebase had already answered it. Spec `017-fmp-migration-admin` reserved `economics_pull` in its job registry with a dataset name (`economics`) and `stale_minutes` (15), and reserved all four collections in both services' `db.py`. The handler was simply never written. Implementing it satisfies 017's contract instead of building a second, competing path.

The daily-timer half is needed because `backend/routers/admin.py` does not exist yet — 017's REST surface was never built either, so nothing can enqueue an admin job today. `breadth_worker.run_daily_breadth_if_due` is the established pattern for exactly this: a market-wide pull that must happen whether or not anyone triggers it. Registering *both* means the timer guarantees freshness now, and the job becomes manually runnable for free once 017's admin router lands.

**Alternatives considered**:
- *Backend cache-first on request*, as `GET /market/news` does. Rejected: a first-run 2-year Treasury backfill is ~8 sequential provider calls; putting that on a user's page load violates SC-007 and would duplicate the budget-guard logic that already lives in `agent-runner/tools/fmp_client.py`. `routers/market.py`'s own docstring states the seam — the router serves what the agent-runner cached.
- *A cron container or scheduler*. Rejected outright by constitution V.

---

## D2: Treasury history — the row cap is per-request, not per-range

**Decision**: One-time backfill of ~2 years in eight ~90-day windows, guarded by a meta flag; thereafter one incremental call per day.

**Rationale**: The endpoint caps every response at roughly 62 rows regardless of the range requested:

| Request | Rows returned | Span |
|---|---|---|
| `treasury-rates` (no params) | 62 | 2026-05-21 → 2026-08-19 |
| `from=2023-08-01&to=2026-08-21` (3 years) | 61 | 2026-05-26 → 2026-08-20 |
| `from=2025-08-01&to=2025-08-31` | 21 | full month |
| `from=2024-08-01&to=2024-08-31` | 22 | full month |

The critical finding is the contrast between rows 2 and 3: a wide range is silently truncated to the most recent ~3 months, but a *narrow historical* range returns that window faithfully. Deep history is therefore reachable — it just has to be requested in chunks. Without this, FR-012's one-year-ago overlay and FR-016's spread trends would be unsatisfiable for a year, which is precisely why the user chose backfill in Q3.

**Gap healing**: the daily incremental requests from the last stored session forward rather than assuming yesterday (FR-017b). Because a no-parameter call returns ~3 months, any outage shorter than a quarter self-heals in a single call — no special recovery path needed.

**Alternatives considered**: forward-accumulation only (Q3 option B) — rejected by the user; on-demand year-ago fetch (option C) — rejected, it puts a provider call on the read path, violating FR-030.

---

## D3: `economic-indicators` conflicts with spec 017's design — amend, don't bypass

**Decision**: Widen `017-fmp-migration-admin/data-model.md`'s `economic_indicators` constraint to permit series that overlap FRED, and record the amendment in both that file and this plan's Complexity Tracking.

**Rationale**: 017 specified that collection as holding *"only series NOT in `tools/macro.py` DEFAULT_INDICATORS (FR-016)"* — an explicit anti-duplication rule, since FRED already carries `CPIAUCSL`, `FEDFUNDS`, `UNRATE`, `GDP`. Spec 026's Q4 answer selects FMP as the **single** source for exactly those four tiles. The two cannot both hold.

Constitution II forbids silently bypassing a spec that implementation proves wrong, so the resolution is an explicit amendment rather than a quiet write. The amendment is cheap: nothing writes or reads `economic_indicators` today, so there is no migration and no affected consumer. FRED's `tools/macro.py` is left untouched and keeps serving the sector macro worker.

The residual cost — the same four series existing in two collections with different freshness — is documented in plan.md as an accepted seam, bounded by the rule that no code blends the two.

**Alternatives considered**: sourcing the tiles from FRED (would have avoided the conflict entirely and carries fresher data) — rejected, the user was shown the staleness evidence and reaffirmed FMP.

---

## D4: Indicator series selection — prefer the series with usable history

**Decision**: Inflation uses `inflationRate`; growth uses `GDP`; employment uses `unemploymentRate`; policy rate uses `federalFunds`. Consumer strength (`retailSales`, `consumerSentiment`) is available at zero extra design cost and is included as an optional fifth tile.

**Rationale**: Probed depth and freshness per series:

| Series | Rows returned | Latest date |
|---|---|---|
| `GDP` | 1 | 2025-10-01 |
| `CPI` | 2 | 2025-11-01 |
| `unemploymentRate` | 2 | 2025-11-01 |
| `federalFunds` | 3 | 2025-11-01 |
| `inflationRate` | **62** | 2025-11-19 |
| `retailSales` | 3 | 2025-11-01 |
| `consumerSentiment` | 3 | 2025-11-01 |

`inflationRate` returns 62 readings where `CPI` returns 2 — a direction indicator and a trend are available from it immediately, satisfying FR-024c's "prefer the deeper series" rule. `GDP` returning a single row is exactly the case FR-024a exists for: its tile ships with no direction indicator until FR-024b's retention supplies a second reading.

Note the dates: every series is dated 2025-10/2025-11 against a current date of 2026-08-21 — roughly nine months stale. This is a property of the source, surfaced by FR-026a's lagging marker rather than hidden. `from`/`to` parameters return an empty array on this endpoint, so there is no way to request fresher or deeper data.

---

## D5: `market-risk-premium` has no date field

**Decision**: Store the US row keyed by `collected_at`, not by a provider-supplied date. Filter to `country == "United States"` at collect time.

**Rationale**: 017's data-model specified `date` as part of this collection's unique key. The endpoint does not return one — the response keys are exactly `country`, `continent`, `countryRiskPremium`, `totalEquityRiskPremium`. The US row currently reads `totalEquityRiskPremium: 4.46`, `countryRiskPremium: 0.23`. Full response is 192 country rows; storing only the US row keeps the collection a single document, matching how the page uses it (one labeled tile, FR-025).

This is a second small correction to 017's shape, folded into the same amendment as D3.

---

## D6: Economic calendar — filter at collect time

**Decision**: Fetch a window spanning `today − 7d` to `today + 14d`, filter to `country == "US"` and `impact in {High, Medium}` before storing, and upsert on `(date, event)`.

**Rationale**: The raw feed is overwhelmingly noise for this purpose. A two-week forward window returned **1,017 rows, of which 142 were US** — and the US rows are dominated by `Baker Hughes Oil Rig Count`, `52-Week Bill Auction`, and similar `impact: "Low"` entries. Filtering at collect time rather than read time keeps the collection small and means the router does no work the worker could have done once.

The single fetch covers both FR-018 (next 14 days) and FR-021 (trailing 7 days reported), so the calendar costs one provider call per refresh.

**Timezone**: the provider returns naive timestamps in UTC (`"2026-09-04 12:30:00"` for an 8:30 ET release). Stored as UTC, rendered in US/Eastern with an explicit label, satisfying FR-022 — Eastern is what release schedules are quoted in.

---

## D7: Spreads computed at read time, from raw stored curves

**Decision**: `treasury_rates` stores raw provider snapshots. The 10y–2y, 30y–10y and 10y–3m spreads, their session-over-session change, inversion flags, and trend series are all derived in `backend/routers/market.py` via pure functions in a testable module.

**Rationale**: Mirrors how `GET /market/breadth` already works — the collection holds what was fetched, the router shapes it. Storing derived spreads would mean a schema migration every time a new spread is wanted, and would make the stored data lie if the derivation were ever corrected. Derivation over ~500 documents is trivially fast and, being pure, is exhaustively unit-testable per constitution I.

**Prior-session change** compares against the previous stored *session*, not calendar yesterday — weekends and holidays have no row (spec Edge Cases).

---

## D8: Breadth chart — one oscillator pane, two lines

**Decision**: `BreadthDivergenceChart` keeps its two-pane structure (SPY above, oscillator below) and gains a second `Line` on the oscillator pane for NAMO. The `oscillator` prop and its toggle are removed; the `compact` prop is retained for density but no longer suppresses the second series.

**Rationale**: Q2 selected the shared-pane layout. Both oscillators use the same ±60 scale, so they share a Y axis honestly. The existing divergence overlay already renders as a dashed line with anchor dots — visually distinct from either solid oscillator line, so drawing it against NYMO only (FR-008) stays unambiguous without extra treatment.

The auto-fitting Y domain already in the component must now fit *both* series; the existing `min - 5 / max + 5` callbacks handle this once the merge includes both, since Recharts computes the domain across every series on the axis.

**Color assignment**: NYMO keeps `bfActiveColor` (violet). NAMO takes `accentColor`... rejected — SPY already owns sky in the pane above, and reusing it across panes would read as the same series. NAMO takes `bfPriorColor` (zinc-600) — deliberately recessive, since NYMO is the primary signal per `market_flow_rules.md` §4 and the one divergences are measured against.

---

## D9: Making the breadth panel unconditional (FR-002a)

**Decision**: `MarketFlowCard`'s `event` prop becomes optional. With no event it renders a neutral `border-zinc-800` panel titled "Market breadth" with no headline row; with an event it renders exactly as today, tinted by `divergence_type`.

**Rationale**: Q1's answer requires breadth to survive quiet markets. The current `Macro.tsx` gates the card on `pinnedEvents.length > 0` after a 14-day age filter, so a calm fortnight erases the page's headline signal. Making the event decorative rather than structural is a smaller change than extracting a separate panel component, and it preserves the outlined card the user explicitly asked to keep.

The `TONE` map gains a `neutral` entry; `divergence_type` remains `"bullish" | "bearish"` on the event type itself, so no API type changes.

---

## Summary of provider limits discovered

Three findings materially constrained the design and are worth carrying into implementation:

1. **`treasury-rates` truncates wide ranges to ~62 rows** but honors narrow historical windows — backfill must chunk (D2).
2. **`economic-indicators` ignores `from`/`to`** (returns `[]`) and its data lags ~9 months — depth and freshness cannot be improved by asking differently (D4).
3. **`market-risk-premium` returns no date field** — 017's assumed shape is wrong (D5).

Steady-state cost is **7–9 provider calls per day**: 1 rates + 1 calendar + 1 risk premium + one call per indicator series (4 required, up to 6 with the optional consumer tiles — the endpoint takes a single `name` per request, so they cannot be batched). The one-time Treasury backfill adds ~8 calls once. All of it runs through `fmp_client` under the shared daily soft cap.
