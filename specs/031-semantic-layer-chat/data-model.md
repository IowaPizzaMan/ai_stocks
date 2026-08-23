# Phase 1 Data Model: Semantic Layer Chat Assistant

**Feature**: `031-semantic-layer-chat` | **Date**: 2026-08-23

Field names and source paths below were verified against live documents (research.md R3/R4).

---

## New collection: `screener`

One flat document per ticker. **Every queryable field is top-level** — this is the design
constraint that makes model-generated queries work (research.md R1), not a stylistic choice.

Registered as `SCREENER = "screener"` in **both** `backend/db.py` and
`agent-runner/tools/db.py`, per the hand-sync convention (Principle VI).

### Document shape

| Field | Type | Nullable | Source / derivation |
|---|---|---|---|
| `ticker` | string | no | `price_history.ticker`, uppercase |
| `name` | string | yes | `company_info.profile.name` |
| `sector` | string | yes | `company_info.profile.sector` |
| `industry` | string | yes | `company_info.profile.industry` |
| `market_cap` | number | yes | `company_info.profile.market_cap` (coerce `$numberLong`) |
| `is_tracked` | boolean | no | `true` if present in `ticker_index`; `false` for universe-only symbols |
| `last_close` | number | yes | last `bars[].close` |
| `last_bar_date` | string | yes | last `bars[].date` (`YYYY-MM-DD`) |
| `range_pct_20d` | number | yes | `(last_close − min(low,20)) / (max(high,20) − min(low,20))`; `null` if range is zero-width |
| `zscore_20d` | number | yes | `(last_close − mean(close,20)) / stdDevPop(close,20)`; `null` if stdev is 0 |
| `weekly_change_pct` | number | yes | `(last_close − close[−6]) / close[−6] × 100` |
| `monthly_change_pct` | number | yes | `(last_close − close[−21]) / close[−21] × 100` |
| `weekly_trend` | string | yes | `"up"` if `weekly_change_pct > 0`, `"down"` if `< 0`, else `"flat"` |
| `revenue_growth_yoy` | number | yes | `financials_cache.data.growth[0].growthRevenue` |
| `net_income_growth_yoy` | number | yes | `financials_cache.data.growth[0].growthNetIncome` |
| `net_profit_margin` | number | yes | `financials_cache.data.ratios[0].netProfitMargin` |
| `margin_trend` | string | yes | `"improving"` / `"flat"` / `"deteriorating"` — compares `ratios[0]` vs `ratios[1]` net margin |
| `financials_trend` | string | yes | composite: `"improving"` when ≥2 of {revenue growth > 0, net-income growth > 0, margin improving} hold; `"deteriorating"` when ≥2 are negative; else `"flat"` |
| `free_cash_flow` | number | yes | `financials_cache.data.cashflow_annual[0].freeCashFlow` (coerce `$numberLong`) |
| `total_debt` | number | yes | `financials_cache.data.balance_annual[0].totalDebt` (coerce `$numberLong`) |
| `fcf_exceeds_debt` | boolean | yes | `free_cash_flow > total_debt`; `null` when either input is missing |
| `signals_as_of` | Date | no | when this document was computed |
| `price_data_through` | string | yes | `price_history.coverage.last_date` — lets a stale price feed be spotted |
| `financials_as_of` | string | yes | `financials_cache.data.income_annual[0].date` |
| `insufficient_history` | boolean | no | `true` when fewer than 25 bars exist; all price signals are then `null` |

### Validation rules

- `ticker` unique; the natural key for upsert.
- Price signals require **≥25 bars**; otherwise every price signal is `null` and
  `insufficient_history` is `true`. Never emit a computed-looking zero.
- Financial signals require ≥1 annual period; trend fields additionally require ≥2. Missing →
  `null`, never a default.
- `$numberLong` values **must** be coerced to plain numbers before writing, or numeric
  comparisons in generated queries misbehave (research.md R3).
- `null` means "unknown", never "does not match". SC-008 requires absence to be reported
  rather than silently filtered — the API surfaces counts of null-signal tickers.

### Indexes

```
{ticker: 1}              unique
{range_pct_20d: 1}
{zscore_20d: 1}
{weekly_change_pct: 1}
{financials_trend: 1}
{fcf_exceeds_debt: 1}
{sector: 1}
{is_tracked: 1}
```

Single-field by design. Generated queries combine predicates in unpredictable orders, so a
compound index would serve one ordering and be ignored by the rest; at ~8,340 documents / ~17 MB
even at 15x, the collection is cache-resident and index intersection is ample (research.md R8).

### Lifecycle

Rebuilt per ticker on each refresh cycle via `replace_one(..., upsert=True)`. **No TTL** — a
stale signal document is more useful than a missing one, and `signals_as_of` makes staleness
visible. Removed when a ticker is removed (alongside the existing per-ticker cleanup in
`backend/routers/stocks.py`).

---

## Existing collections (read-only inputs, unchanged)

| Collection | Used for | Notes |
|---|---|---|
| `price_history` | all price signals | **Do not add fields** — both services `replace_one` the whole document and would erase them (research.md R11) |
| `financials_cache` | all financial signals | nested 3 deep, `$numberLong` values |
| `company_info` | name, sector, industry, market cap | |
| `ticker_index` | `is_tracked` | 65 tracked vs 556 in price universe |

---

## Transient entities (not persisted — FR-004)

### ChatTurn
`{ role: "user" | "assistant", content: string }` — held in browser state only, replayed to the
backend each request, capped at the last ~6 turns (research.md R9).

### GeneratedQuery
`{ collection: string, pipeline: object[] }` — the model's output. Validated before execution;
never stored.

### ChatAnswer
`{ answer, criteria[], match_count, rows[], generated_query, degraded }` — assembled per request,
returned, discarded.

---

## Cleanup (FR-006)

| Action | Target | Rationale |
|---|---|---|
| **Drop collection** | `portfolio_digest_cache` | 1 doc, **zero** code references; orphaned when the portfolio-digest feature was removed (research.md R7) |
| **Remove dead constants** | `FUND_HOLDINGS`, `SECTOR_PERFORMANCE`, `STOCK_NEWS`, `MARKET_NEWS` from both `db.py` files | Declared but unused; **no collections exist** for them. Do **not** touch the `"sector_performance"` / `"fund_holdings"` literals in `agent-runner/tools/fmp_client.py:148,153` — those are FMP probe family keys |
| **Keep** | `transcripts_cache` | Reserved for `specs/007-earnings-transcripts/`; referenced by index bootstrap, cleanup-on-delete, and an asserting test — pending user confirmation |
| **Keep** | `fmp_entitlements` | Actively written (`fmp_client.py:191`), merely not yet created in the DB |
