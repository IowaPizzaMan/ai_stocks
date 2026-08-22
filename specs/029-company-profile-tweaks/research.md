# Phase 0 Research: Company Profile, Peers & Navigation Tweaks

**Feature**: `029-company-profile-tweaks` | **Date**: 2026-08-22

All Technical Context unknowns are resolved below. No NEEDS CLARIFICATION markers remain.

---

## R1 — Storage: reuse `company_info`, do not add a collection

**Decision**: Store the profile, peers list, and employee-count history in the existing
`company_info` collection, one document per ticker, unique index on `ticker`. No TTL.

**Rationale**: `COMPANY_INFO = "company_info"` is already declared in **both**
`backend/db.py:46` and `agent-runner/tools/db.py:51`, has been since spec 017, and
**nothing anywhere reads or writes it** — the only other occurrence in the codebase is
`fmp_client.PROBE_ENDPOINTS["company_info"] = "profile?symbol=AAPL"`, which probes the
exact endpoint this feature consumes. The name was reserved for this payload. Reusing it
satisfies Principle VI (the constant is already hand-synced across services) and
Principle V (no new infrastructure).

No TTL, matching `price_history`/`stock_news_cache`: freshness is enforced by explicit
`fetched_at` comparison at read time, not by document expiry. A TTL would silently delete
a ticker's sector and industry, which would drop it out of the Sectors rollup with no
error anywhere — the same failure mode 024 documented for `stock_news_cache`.

**Alternatives considered**:
- Three collections (`company_profile`, `company_peers`, `employee_counts`) — rejected:
  three indexes and three round trips to render one tab, for data that is always fetched
  and always read together, keyed identically.
- Embed in `ticker_index` — rejected: `ticker_index` is the ticker *registry* read on
  nearly every request; loading it with a multi-KB description blob and a peers array
  would bloat every listing. (Two scalars are a different matter — see R3.)

---

## R2 — Three independent freshness markers in one document

**Decision**: One `company_info` document per ticker carrying `profile`, `peers`, and
`employee_counts` payloads, each with its own `*_fetched_at` timestamp and `*_outcome`
marker (`confirmed` | `unavailable`).

**Rationale**: The clarifications set different cadences — the profile refreshes every
pull, peers and employee counts sit behind a ~90-day window (FR-008a). Separate markers
let one dataset refresh while the others are served from cache, and let a 402-degraded
dataset be retried on the next pull without resetting the others' windows. This mirrors
`financials.get_financials`'s per-key `outcomes` mechanism, which exists precisely because
spec 018 found that a blanket "fetched" flag froze a 402-degraded payload for the whole
90-day window (the BSX bug).

**Alternatives considered**: a single `fetched_at` for the document — rejected, it
reintroduces the exact 018 bug class.

---

## R3 — Denormalize `sector` + `industry` onto `ticker_index`

**Decision**: When a profile is fetched, write `sector`, `industry`, `name`, and
`logo_url` onto the ticker's `ticker_index` document, in addition to storing the full
profile in `company_info`. All filtering and rollup reads use `ticker_index`.

**Rationale**: This is the decision that makes everything else cheap.

1. `ticker_index.sector` **already exists** — `register_ticker()`
   (`agent-runner/tools/db.py:183`) accepts and writes it, and `macro_worker.py:26`
   already derives its per-sector work from `db[TICKER_INDEX].distinct("sector", …)`.
   Writing the profile's sector there means the macro worker starts receiving real,
   consistent sectors with **zero code change** (spec Assumptions).
2. The feed's `sentiment` filter (028, `analysis.py:36-41`) already resolves tickers from
   `ticker_index` and constrains `analyses` with `$in`. Sector and industry filters reuse
   that identical two-step shape — a proven pattern, no `$lookup`, no aggregation change.
3. `ticker_index` already has a unique index on `ticker` and an index on `status`.

Denormalization is safe here because there is exactly one writer (the profile fetch) and
the value is re-asserted on every pull.

**Alternatives considered**:
- `$lookup` from `analyses` to `company_info` in the sectors aggregation — rejected:
  `backend/routers/sectors.py` deliberately does its rollup in Python (its module
  docstring says so); adding a lookup stage cuts against that and against Principle V.
- Read `company_info` for every filter query — rejected: an extra full-collection read on
  every feed page load to fetch two scalars already available on a collection being read
  anyway.

---

## R4 — FMP endpoints and entitlement

**Decision**: Three stable-API paths, called through `tools/fmp_client.fmp_get`:

| Dataset | Path | Cadence |
|---|---|---|
| Profile | `profile?symbol={t}` | every pull |
| Peers | `stock-peers?symbol={t}` | 90-day window |
| Employees | `historical-employee-count?symbol={t}` | 90-day window |

Add `stock_peers` and `employee_count` families to `fmp_client.PROBE_ENDPOINTS` so
`fmp_entitlement_probe` covers them like every other family.

**Rationale**: `profile` is already a probed family (`company_info`) and the user supplied
live sample responses for all three, so entitlement is confirmed empirically. The two new
families are unprobed today; adding them costs 2 calls per probe run and makes a future
plan downgrade visible in `fmp_entitlements` rather than as a mystery empty section.
`fmp_get` supplies the throttle, the soft-cap guard, and pull-cost metric attribution
(Principle IV) — no new HTTP path is introduced.

**Alternatives considered**: bypassing `fmp_client` for the "cheap" profile call —
rejected outright; Principle IV admits no exceptions, and it would break pull-cost
attribution.

---

## R5 — The sector switch carries no migration risk (and fixes a logged bug)

**Decision**: Re-source sector from the profile with no data migration, and close the
corresponding KNOWN_ISSUES entry.

**Rationale**: Verified during research — **nothing writes `analyses.sector` today**.
`Crew.run()` composes the analyses document from `**synthesis`
(`agent-runner/crew.py:310-323`), and `portfolio_strategist.SCHEMA` has no `sector`
property; no other agent supplies one. `GET /sectors` matches
`{"sector": {"$nin": [None, ""]}}`, so the rollup returns `[]` for every real analysis
document.

This is already the **first open bug in `KNOWN_ISSUES.md`**, which diagnoses it exactly
and proposes this fix: *"have `Crew.run()` fetch/attach the ticker's sector (e.g. from an
FMP profile call …)"*. Consequences:

- There is no legacy `analyses.sector` data to migrate, reconcile, or fall back to.
- The spec's "unclassified bucket" (FR-027) is a **strict improvement** over today's
  permanently-empty page, not a regression.
- Only `backend/tests/test_sectors.py` exercised the rollup, by inserting `sector=`
  directly — which is why the bug survived. New tests must build state through the
  profile write path, not by hand-inserting sectors.
- The implement phase moves that KNOWN_ISSUES entry to the Fixed section.

---

## R6 — Logos: remote `<img>` with an `onError` fallback, in one shared component

**Decision**: A single `components/shared/CompanyLogo.tsx` renders
`https://images.financialmodelingprep.com/symbol/{TICKER}.png` (as supplied in the
profile's `image` field) with a size prop, `loading="lazy"`, and an `onError` handler that
swaps to a neutral monogram tile. Treat FMP's `defaultImage: true` as "no logo" without
even attempting the request.

**Rationale**: Three surfaces need identical fallback behavior (tile, hover card, stock
header) across FR-013/FR-021/FR-021a; one component means one code path and one test.
`defaultImage` is FMP's own "this is a placeholder" flag, so honoring it avoids rendering
a generic grey square as if it were a brand. `onError` covers the residual case of a URL
that 404s or is blocked. No proxying through the backend — this is a local-first
single-user app with no CSP constraint, and proxying would add a backend route whose only
job is to forward bytes (Principle V).

**Alternatives considered**: caching logo bytes in Mongo — rejected as premature; the
provider CDN is already a cache and the browser caches on top of it.

---

## R7 — Price/change/volume from existing bars, not from the profile

**Decision**: The profile section computes current price, change, change %, and volume
from the daily bars `StockDetail` already loads via `useStockPriceHistory`. The profile
supplies only market cap, beta, last dividend, 52-week range, and average volume.

**Rationale**: FR-011a/FR-011b, from clarification 5. `StockDetail` already calls
`useStockPriceHistory(symbol, PANEL_TIMEFRAMES)` for the Charts tab, so the daily series
is in the TanStack Query cache before Overview renders — deriving from it costs one array
read, needs no new endpoint, and makes the two tabs structurally incapable of disagreeing.
Change is `last close − previous close`; volume is the last bar's volume.

**Alternatives considered**:
- Display the profile's own price with an "as of" label — rejected by clarification.
- A new backend quote endpoint — rejected: a provider call per page view violates
  Principle IV and SC-010.

---

## R8 — Peers ordering and untracked peer navigation

**Decision**: Sort peers by market cap descending, nulls last, ties broken by symbol.
Peer links go to `/stock/{symbol}` unconditionally.

**Rationale**: FR-014/edge cases. `stock-peers` returns no explicit ordering guarantee, so
an explicit sort is required for a stable, testable list. `StockDetail` already handles
untracked tickers — `useTickerRecord` returning undefined renders the "No analysis yet …
charts below still render" state and hides the sentiment buttons (028 FR, verified at
`StockDetail.tsx:77` and `:137-152`) — so an untracked peer needs no new handling.

---

## R9 — News page: a route, not a tab; the tab bar disappears entirely

**Decision**: Add `/news` to `App.tsx` and a `News` entry to `Navbar.tsx`'s `links` array.
`pages/News.tsx` renders the existing `MarketNewsPanel` unchanged. `Stocks.tsx` drops its
`TabBar`, its `TABS`/`DEFAULT_TAB` constants, and its hash-tab logic.

**Rationale**: With news gone, the Stocks page has exactly one tab — a tab bar with one
tab is noise. Removing it also satisfies FR-004 for free: an old `#news` bookmark becomes
an ignored URL fragment on a page that no longer reads the hash, so it renders the grid
normally rather than erroring. `MarketNewsPanel` is already self-contained (its own hook,
its own loading/error/empty states, capped at 20 with no infinite scroll), so the new page
is a thin wrapper — the "same content and behavior" of FR-002 is guaranteed by literally
reusing the component.

Navbar order: insert **News** after **Stocks**, matching the user's mental model of it as
the second market-wide surface.

**Alternatives considered**: keeping a single-tab TabBar for symmetry with StockDetail —
rejected as pure ceremony.

---

## R10 — Sector chart height

**Decision**: Raise `ResponsiveContainer height` from `280` to `440`.

**Rationale**: FR-028. Eleven series over a ~30% percentage range at 280px gives roughly
8px of vertical separation between adjacent lines — below the threshold where a line can
be followed across crossings. 440px is a ~57% increase, keeps the chart plus its window
selector inside a 900px viewport without scrolling, and stays a fixed pixel height
consistent with every other chart in the app.

---

## R11 — Legend toggling via Recharts `hide`, with state above the chart

**Decision**: Hold `hidden: Set<string>` in `SectorEtfChart` component state. Pass
`hide={hidden.has(s.ticker)}` to each `<Line>` and toggle from `<Legend onClick>`. Style
hidden legend entries at reduced opacity with a line-through, and set
`aria-pressed`/`role="button"` on the legend content for keyboard activation.

**Rationale**: FR-029/FR-030/FR-031/FR-032.
- A `<Line hide>` is excluded from Recharts' Y-domain computation, so `domain={["auto",
  "auto"]}` re-fits to the visible series automatically — FR-030 needs no manual math.
- Component state (not URL state) satisfies FR-031 for free: changing the window updates a
  search param, which re-renders `SectorEtfChart` without unmounting it, so `hidden`
  survives. It also satisfies the spec's assumption that toggles are within-visit only and
  not encoded in the shareable URL.
- Recharts' default legend renders `<li>`s, which are not keyboard-focusable; FR-029's
  keyboard clause requires a custom `content` renderer using real `<button>` elements.
- FR-032's all-hidden state is a length check on `hidden` against the series list,
  rendering a distinct "all series hidden" message rather than the existing "no data" one.

**Alternatives considered**: filtering the `data` array instead of using `hide` — rejected:
it would recompute the merged dataset on every toggle and lose Recharts' animation
continuity.

---

## R12 — Employee count chart shape

**Decision**: Recharts `LineChart` over `periodOfReport` ascending, `employeeCount` on Y,
abbreviated tick formatter (`166000 → 166k`), tooltip showing period, headcount, and
`formType`. Single-point series renders with `dot` visible so it is not an invisible line.

**Rationale**: FR-015/FR-017 and the single-period edge case. The endpoint returns one row
per filing (annual 10-K cadence), so the full history is a handful of points — no window
selector, no downsampling, per the spec's assumption. `formType` is in the tooltip because
a 10-K figure and a 10-Q figure are not the same measurement and the user should see which
they are reading.

---

## R13 — Industry filter as a `<select>`, backed by a distinct-values endpoint

**Decision**: `GET /stocks/industries` returns the sorted distinct industries present
among tracked tickers. `FilterBar` renders a `<select>` bound to an `industry` search
param.

**Rationale**: FR-024/FR-025. The existing filters (signal, conviction, sentiment) are
pill rows because each has 2–3 fixed values; industry is open-ended and FMP's taxonomy runs
to ~150 values, of which a user's tracked set might cover 20+. A pill row would wrap into
several lines and dominate the bar. Sourcing choices from a distinct query over
`ticker_index` guarantees FR-024's "no offered choice yields an empty grid".

The backend filter mirrors 028's `sentiment` two-step exactly, including its critical
detail: an empty resolved ticker list must produce `$in: []` (matches nothing), never be
skipped — skipping silently falls back to the unfiltered feed (`analysis.py:38-41`).

**Alternatives considered**: a free-text industry search — rejected: invites typos and
zero-result states the dropdown makes impossible.

---

## R14 — Portfolio digest teardown: code first, then a documented one-time drop

**Decision**: Delete all source and test files, remove the router registration and the job
handler, remove the collection constant from both `db.py` files, and document the
`db.portfolio_digest_cache.drop()` mongosh step in `quickstart.md`.

**Rationale**: FR-019 requires the stored records and the collection to go, but the
services do not drop collections at runtime — `ensure_indexes` only creates. The
established precedent is 024's one-time mongosh index-drop documented in that spec's
quickstart. Order matters: ship the code that stops writing first, then drop, so nothing
recreates the collection between the two steps.

Full inventory in [contracts/portfolio-digest-removal.md](./contracts/portfolio-digest-removal.md).
Two footguns for the teardown, both found by grepping rather than by reading the obvious
files:

- `tools/market_movers.py:17` mentions `run_portfolio_digest` in a **docstring** (citing
  its fetch-before-write pattern), not in code. Reword the comment; do not "fix" it by
  deleting logic.
- `api/types.ts:519` has `pct_of_portfolio`, which belongs to institutional holdings and
  is **unrelated** to the digest. A careless grep-and-delete on "portfolio" breaks the
  Institutional tab.

**Alternatives considered**: leaving the collection to rot — rejected by clarification 1
("dropped outright").
