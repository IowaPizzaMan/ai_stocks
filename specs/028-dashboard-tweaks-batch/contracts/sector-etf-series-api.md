# Contract: Sector ETF comparison chart

**Story**: US5 (FR-019, FR-020, FR-020a, FR-020b, FR-021)
**Research**: R5, R6, R13

---

## Tracked ETFs

A fixed constant list, declared once per service and hand-synced (Principle VI):

```text
XLC XLY XLP XLE XLF XLI XLV XLB XLRE XLK XLU
```

Each carries a display label (e.g. `XLK → Technology`) for the chart legend.

---

## Pull job: `sector_etf_pull`

New entry in `agent-runner/tools/admin_jobs.py::JOB_HANDLERS`; handler in
`agent-runner/tools/sector_etfs.py`. This is the one job name not already in 017's
registry — 017's `sector_performance_pull` is a *different* dataset (today's snapshot
percentages), so overloading it would make one job write two unrelated shapes (R5).

**Behavior**: loop the 11 tickers calling
`price_store.get_series(ticker, refresh="delta", db=db)`. Return the count that returned
usable bars.

`price_store` is used **unchanged** — sector ETFs are ordinary tickers to it, and it
already provides delta refresh, budget guarding, and fail-soft degradation (R5).

**Fail-soft per ticker** (FR-021 at the data layer): each ticker is wrapped
individually; one failing must not abort the other ten. `price_store.get_series` already
returns stored bars with `outcome: "degraded"` rather than raising on a provider error,
so the wrapper only needs to catch genuinely unexpected exceptions and continue.

**Cost**: 11 FMP calls per run, delta-bounded after the first (R13).

## `POST /sectors/etf-series/refresh`

Enqueues `sector_etf_pull`. Same dedupe contract as every other refresh endpoint (R4).

- **200** `{ "status": "enqueued", "job_id": "…" }`
- **200** `{ "status": "already_queued", "job_id": "<existing>" }`

---

## `GET /sectors/etf-series?window=6m`

Cache read only. Slices `price_history` server-side so the payload matches what is
displayed (R6).

**Query params**

| Param | Values | Default |
|---|---|---|
| `window` | `1m` \| `3m` \| `6m` \| `1y` | `6m` |

Any other value → **422**. The four values are the contract; a silent fallback would hide
a frontend bug.

**Response** — always 200; empty is a valid pre-refresh state:

```jsonc
{
  "window": "6m",
  "series": [
    {
      "ticker": "XLK",
      "label": "Technology",
      "bars": [
        { "date": "2026-02-24", "close": 248.11 },
        { "date": "2026-02-25", "close": 249.80 }
      ],
      "partial": false
    },
    { "ticker": "XLRE", "label": "Real Estate", "bars": [], "partial": true }
  ],
  "as_of": "2026-08-22T09:00:00Z"
}
```

**Rules**
- One entry per tracked ETF **always present**, even with zero bars — the chart must be
  able to name what is missing rather than silently omitting it (FR-021).
- `partial: true` when the entry has no bars, or its first bar starts materially after the
  window's start (i.e. history does not cover the full window).
- Only `date` and `close` are projected; the rest of each OHLCV bar is not sent.
- Bars ascending by date.
- No provider call — a ticker never pulled simply has no bars.

---

## Frontend

### `rebaseToPercent(bars) -> {date, pct}[]` (R6, FR-020)

New pure module `frontend/src/lib/rebaseToPercent.ts`.

- Divides each close by the **first close in the given array**, expressed as percent
  change: `(close / first - 1) * 100`.
- First point is always exactly `0`.
- Empty input → empty output.
- Single bar → one point at `0`.
- A first close of `0` → returns empty rather than dividing by zero.

Rebasing against the first bar *within the returned window* means each line starts at 0%
for the selected window, which is what makes 11 differently-priced ETFs comparable on one
axis — the entire reason for clarification Q2's answer.

A `partial` series rebases from its own first available bar and is labeled as partial, so
its shape stays readable without implying it covers the full window.

### `SectorEtfChart.tsx` (FR-019, FR-020a, FR-020b, FR-021)

- Recharts `LineChart` in a `ResponsiveContainer`, following the existing
  `macro/YieldCurveChart.tsx` pattern (already the project's multi-series chart precedent).
- 11 `<Line>` series, each with a distinct color plus a legend label (FR-020a). Color is
  never the only differentiator — the legend pairs each color with its ticker and sector
  name, consistent with the existing signal-legend practice in `Sectors.tsx`.
- Y axis formatted as percent; a zero reference line makes above/below-baseline readable
  at a glance.
- Window selector rendering the four options; selection stored in URL search params
  (`?window=`) per the constitution's filter-state rule, so a reload keeps the view.
- Series with `partial: true` are listed in a short note beneath the chart
  (e.g. `Limited history: XLRE`) rather than dropped (FR-021).
- Empty response → empty state naming the Refresh control.

**Assertions**
- All 11 tickers appear in the legend.
- Switching window refetches with the new `window` param and every line re-rebases to 0.
- A series with no bars does not prevent the others rendering, and is named in the note.
- `?window=` round-trips through the URL.
- `rebaseToPercent` unit cases: normal, empty, single bar, zero first close.
