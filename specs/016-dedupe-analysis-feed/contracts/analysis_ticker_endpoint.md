# Contract: `GET /analysis/{ticker}`

File: `backend/routers/analysis.py:67-73`. Consumed by `useTickerAnalysis`
(`frontend/src/hooks/useAnalysis.ts:28-37`) and rendered in `StockDetail.tsx` (AI Summary tab).

## Before (current behavior)

```text
GET /analysis/{ticker}?limit=10

200 -> Analysis[]   # 0..limit most recent docs for ticker, newest first
```

## After (this feature)

```text
GET /analysis/{ticker}

200 -> Analysis | null   # the ticker's current (only) stored analysis, or null if none exists
```

- `limit` query param is removed — no longer meaningful once at most one document per
  ticker can exist (see `data-model.md` Invariant change).
- Implementation: `db[ANALYSES].find_one({"ticker": ticker.upper()}, {"_id": 0})` (drop
  `.sort()`/`.limit()`, `find` → `find_one`). Returns `None` when no analysis exists for the
  ticker (FastAPI serializes to JSON `null`, HTTP 200 — matches existing convention of this
  router, which does not 404 on empty results elsewhere, e.g. `GET /analysis/feed` with no
  matches returns an empty list rather than 404).

**Backward compatibility**: this is a breaking shape change (array → nullable object). The
one and only consumer, `useTickerAnalysis`, is updated in the same change (see
`research.md` D4) — no dual-shape/versioning support is needed since this is a local-first
single-deployment app with no external API consumers (Constitution Principle V).

## Consumers to update (tracked for /speckit-tasks, not this plan)

- `frontend/src/hooks/useAnalysis.ts:28-37` — `useTickerAnalysis` return type
  `Analysis[]` → `Analysis | null`.
- `frontend/src/pages/StockDetail.tsx:43,54` — replace `const { data: analyses } = useTickerAnalysis(symbol)` /
  `const latest = analyses?.[0]` with the analysis object used directly.
- `backend/tests/test_routers.py:56-63` (`test_ticker_history`) — rewrite to assert a single
  object matching the latest doc, not a 2-element list.
- `specs/component-specs/frontend/components/stock/AISummaryTab.md:75-77` — remove the
  "Analysis History Timeline" spec section (never implemented; no longer planned per FR-005).
