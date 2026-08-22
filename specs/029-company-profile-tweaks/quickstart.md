# Quickstart: Company Profile, Peers & Navigation Tweaks

**Feature**: `029-company-profile-tweaks` | **Date**: 2026-08-22

How to validate this feature end to end. Assumes the standard local stack.

---

## Prerequisites

```bash
docker compose up -d mongodb ollama
# backend + agent-runner + frontend per your usual dev loop
```

`FMP_API_KEY` must be set — this feature adds three provider endpoints. Confirm
entitlement for the two new families before anything else:

```bash
cd agent-runner
python -c "from tools.fmp_client import fmp_entitlement_probe; \
           print({r['family']: r['result'] for r in fmp_entitlement_probe()})"
```

Expect `company_info`, `stock_peers`, and `employee_count` to read `entitled`. A
`payment_required` on either new family means the sections will render their empty states
— that is correct fail-soft behavior, not a bug, but it makes US6/US7 unverifiable.

---

## One-time migration steps

Run **after** deploying the code, never before (R14 — a running worker would recreate the
collection).

```bash
mongosh stockai --eval '
  db.portfolio_digest_cache.drop();
  db.work_queue.deleteMany({ job_type: "portfolio_digest" });
'
```

No index migration is needed for `company_info` — `ensure_indexes` creates its unique
`ticker` index at agent-runner startup.

---

## Test gates

All three must pass before this is considered done (constitution Principle I + the
Development Workflow gates).

```bash
cd backend      && pytest && ruff check .
cd agent-runner && pytest && ruff check .
cd frontend     && npm test
```

Also run the removal verification block in
[contracts/portfolio-digest-removal.md](./contracts/portfolio-digest-removal.md#verification-fr-019-sc-009).

---

## Validation walkthrough

### 0. Day-one state — everything unclassified (edge case, FR-027)

Before pulling anything, with no profiles stored:

- `/sectors` → every tracked stock in the **Unclassified** bucket, with copy saying they
  await their next pull. Not an error, not an empty page.
- Stocks page → industry dropdown hidden (empty list).
- Tiles and headers → monogram logo fallbacks, no broken images.

This is the state a fresh deploy lands in, so check it deliberately rather than pulling
first and never seeing it.

### 1. Pull one ticker (US2, FR-005 – FR-013)

Pull `AAPL` from the Stocks page.

```bash
mongosh stockai --eval 'db.company_info.findOne({ticker:"AAPL"}, {profile:1, peers_outcome:1, employee_counts_outcome:1})'
mongosh stockai --eval 'db.ticker_index.findOne({ticker:"AAPL"}, {sector:1, industry:1, logo_url:1})'
```

Expect a populated `profile`, all three `*_outcome: "confirmed"`, and
`sector: "Technology"` / `industry: "Consumer Electronics"` denormalized onto
`ticker_index`.

Then on `/stock/AAPL`:

- Logo renders next to the ticker in the header (FR-012).
- **Overview tab** → company profile is the **topmost** section, above Verdict (FR-010),
  showing identity, classification, description, and the stats grid (FR-011).
- The price in that section **matches** the Charts tab's latest close (FR-011a/R7) — this
  is the one to check carefully; a mismatch means the section read the profile's stored
  price instead of the bars.
- "profile as of …" timestamp is present (FR-007).

### 2. Peers and employees (US6, US7)

Still on the Overview tab:

- **Peers** — symbol/name/price/market cap, largest cap first, caps abbreviated (`4.04T`).
  Click a peer → lands on `/stock/{symbol}`, rendering even if untracked (FR-014, R8).
- **Employee count** — chronological line chart, `166k`-style ticks, tooltip showing
  period, headcount, and form type (FR-015, FR-017).

Cost check — pull `AAPL` a second time and confirm only the profile refetched:

```bash
mongosh stockai --eval 'db.company_info.findOne({ticker:"AAPL"}, {profile_fetched_at:1, peers_fetched_at:1, employee_counts_fetched_at:1})'
```

`profile_fetched_at` advances; the other two do not (FR-008a, SC-010). A full refresh
(`mode="full"`) advances all three (FR-008b).

### 3. Sector rollup and industry filter (US5)

Pull two or three more tickers in different industries, then:

- `/sectors` → real buckets, no longer permanently empty. **This is the KNOWN_ISSUES fix**
  — verify explicitly, since the page has never populated before.
- Click a sector → the filtered grid contains exactly the count the rollup showed
  (FR-026a). Compare the numbers; do not eyeball it.
- Stocks page → industry dropdown lists only industries present among tracked stocks
  (FR-024). Select one → grid narrows, URL carries `?industry=…`, and the view is
  shareable (FR-025, SC-007).
- Combine industry with a signal or sentiment filter → AND semantics (FR-025).
- **Empty-match check**: hit `/analysis/feed?industry=Nonexistent` directly and confirm an
  **empty** result, not the full feed. This is the 028 `$in: []` invariant and the most
  likely regression in the whole feature.

### 4. Stocks page and hover card (US3)

- No Portfolio Summary panel anywhere; grid spans full width (FR-018).
- Each tile shows a small logo beside its ticker, with ticker and conviction dots still
  legible (FR-021a).
- Hover (and keyboard-focus) a tile → card shows the **full** AI summary, not a 3-line
  clamp, plus logo and company name (FR-020, FR-021).
- Hover a tile with no completed analysis → "no summary available" (FR-023).
- Hover a tile near the viewport's right/bottom edge with a long summary → card stays on
  screen and the summary stays readable (FR-022). The existing flip logic in
  `AnalysisTile` handles placement; a taller card makes the bottom edge the risky one.

### 5. News tab (US1)

- **News** appears in the top nav; one click from any page (SC-001, FR-001).
- Content and behavior identical to the old in-page tab — 20 most recent, newest first,
  ticker links, article links, no infinite scroll (FR-002).
- Stocks page has **no** tab bar at all (FR-003, R9).
- Open a stale `/#news` bookmark → renders the Stocks grid normally, no blank page
  (FR-004).

### 6. Sector chart (US4)

On `/sectors`:

- Chart is visibly taller — 440px vs the previous 280 (FR-028, R10).
- Click a ticker in the legend → that line hides, its legend entry shows as hidden
  (FR-029), and the Y-axis **re-fits** to the remaining series (FR-030).
- Click again → returns.
- Hide a few, then switch window 6M → 1Y → hidden set is **preserved** (FR-031).
- Hide all eleven → "all series hidden" state, distinct from "no data" (FR-032).
- Tab to a legend entry and press Enter/Space → same toggle as a click (FR-029).

---

## Closing the known issue

This feature fixes the first open bug in [KNOWN_ISSUES.md](../../KNOWN_ISSUES.md)
("Analysis documents never get a `sector`, so `/sectors` stays empty forever"). Once
step 3 passes, move that entry to the file's **Fixed** section with a pointer to this
spec — per the file's own convention, fixed items move rather than being deleted.

---

## Rollback notes

- Dropping `company_info` returns the app to its pre-feature state: sectors go empty, the
  industry dropdown hides, logos fall back. Nothing else breaks — no other collection
  depends on it.
- `ticker_index.sector`/`.industry`/`.logo_url` are additive; leaving them populated is
  harmless if the feature is reverted.
- The portfolio digest is **not** recoverable — its records are dropped by design
  (clarification 1). Reviving it means rebuilding from spec 027.
