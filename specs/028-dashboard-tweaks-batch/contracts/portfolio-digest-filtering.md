# Contract: Portfolio Digest — link fix and filter-aware highlights

**Stories**: US1 (FR-001), US2 (FR-002, FR-003, FR-004, FR-004a, FR-004b)
**Research**: R1, R2, R3

No API shape changes beyond one added field. This is predominantly a frontend contract.

---

## 1. Route link fix (FR-001)

| | Before | After |
|---|---|---|
| `PortfolioDigestPanel.tsx:101` | `to={`/stocks/${h.ticker}`}` | `to={`/stock/${h.ticker}`}` |

`App.tsx` registers `/stock/:ticker` (singular). No route matches the plural form and
there is no catch-all, so React Router renders an empty `<main>` — the reported blank
page (R1).

**Also added** (`App.tsx`): a terminal catch-all so this failure class is never silent
again.

```tsx
<Route path="*" element={<NotFound />} />
```

`NotFound` renders a short "page not found" message and a link to `/`. It must be the
last route.

**Assertions**
- Clicking a highlight navigates to `/stock/<TICKER>` and the detail page renders its
  header.
- Navigating to an unregistered path renders the NotFound message, not an empty main.

---

## 2. `GET /portfolio/digest` — one added field

Response shape is unchanged except that each highlight gains `sector`:

```jsonc
{
  "as_of": "2026-08-22T14:02:11Z",
  "overview": "…",
  "highlights": [
    {
      "ticker": "NVDA",
      "signal": "bullish",
      "conviction": "high",
      "note": "…",
      "sector": "Technology"      // NEW — nullable
    }
  ],
  "stock_count": 12,
  "total_tracked_count": 40,
  "capped": false,
  "stale": false
}
```

`sector` is `null` on documents generated before this change. The router passes through
whatever is stored; it performs no join itself.

---

## 3. Sector join in the digest job (R3)

In `agent-runner/tools/portfolio.py`:

1. Add `"sector": 1` to `_PROJECTION`.
2. Carry `sector` through `_condense` into an in-memory `{ticker: sector}` map.
3. **After** `portfolio_digest_agent.run(...)` returns, enrich each highlight:
   `highlight["sector"] = sector_by_ticker.get(highlight["ticker"])`.
4. Persist enriched highlights.

**`sector` MUST NOT be added to the agent's `SCHEMA`.** It is a known stored fact; letting
the model emit it invites a hallucinated or mistyped value (Principle III).

**Assertions**
- A highlight for a ticker whose analysis has a sector gets that exact sector.
- A highlight for a ticker absent from the gathered set gets `None`, not a crash.
- The agent's request schema contains no `sector` key.

---

## 4. Highlight filtering predicate (FR-002, FR-003)

New pure module `frontend/src/lib/filterHighlights.ts`:

```ts
export type HighlightFilters = {
  ticker?: string;
  signal?: string;
  conviction?: string;
  sector?: string;
};

export function filterHighlights<T extends {
  ticker: string; signal?: string; conviction?: string; sector?: string | null;
}>(highlights: T[], filters: HighlightFilters): T[];
```

**Rules**
- No filters set → returns the input unchanged (FR-003).
- `ticker` → case-insensitive **substring** match, mirroring the feed's own regex
  behavior (`analysis.py` uses `$regex` so partial typing narrows as-you-go). An exact
  match would make the panel disagree with the grid beside it.
- `signal`, `conviction`, `sector` → exact match, case-insensitive.
- A highlight with `sector: null` matches **no** sector filter.
- Multiple filters combine with AND.
- Never mutates the input array.

**Assertions**: one case per dimension; combinations; null sector against a sector filter;
substring vs exact ticker; empty result; empty input.

---

## 5. Panel behavior (FR-004, FR-004a, FR-004b)

`PortfolioDigestPanel` reads filters itself via `useSearchParams` — the same source
`Stocks.tsx:50-55` reads (R2). No props are added.

| Condition | Rendering |
|---|---|
| Any filter active | Overview paragraph rendered **unchanged**, preceded by a scope label: `across all N tracked stocks` (FR-004b) |
| No filter active | Overview rendered as today; no scope label |
| Filters active, ≥1 highlight matches | Only matching highlights listed |
| Filters active, 0 highlights match | `No highlighted stocks match the current filter.` in the highlights area — overview still shown (FR-004) |
| No highlights at all (empty digest) | Existing "No summary yet" empty state, **unaffected by filter state** (spec Edge Cases) |

**Explicitly unchanged**: no refetch, no regeneration, and no request of any kind fires on
a filter change (clarification Q1). The Regenerate button's behavior is untouched.

**Assertions**
- Setting `?signal=bearish` narrows the rendered highlight list without a new network call.
- The overview text is byte-identical with and without a filter; only the label appears.
- A filter matching nothing shows the no-match message *and* still shows the overview.
- The genuinely-empty digest state renders identically with and without filters.
