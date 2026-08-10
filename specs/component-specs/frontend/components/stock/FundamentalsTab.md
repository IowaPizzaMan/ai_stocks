# frontend/src/components/stock/FundamentalsTab.tsx

## Purpose
Renders financial charts and key ratio cards for the Fundamentals tab. Data comes from `useStockFinancials()` (backend model: `backend/models/stock.md`) and the fundamental sub-report. Field names below are the **real FMP field names** (reconciled against the raw FMP payload — see "Field Reconciliation" at the bottom), not placeholders — bind directly to these.

Every chart is **trend-first**: N years on the x-axis, not a single latest value. FMP's annual arrays come back newest-first, so reverse to chronological order before charting. The two highest-value trend charts (valuation bands in §6, margin trend in §2) improve the most with 8–10yr history vs. a 4yr window — prioritize backfilling those two first if FMP's 250 calls/day free-tier budget is a constraint (see `DATA_SOURCES.md`). `income_quarterly` also supports the seasonality view in §1 that annual data can't — keep pulling quarterly even once deep annual history exists.

## Sections

### 1. Growth & Scale
Source: `income_annual` / `income_quarterly` + `growth`

- **Revenue & Net Income** (`revenue`, `netIncome`) — grouped bar chart (Recharts `BarChart`), 4yr by default, extend to 5–10yr as history backfills.
- **YoY growth overlay** (`growthRevenue`, `growthNetIncome`, `growthEPS`) — line chart on a secondary axis over the bar chart above, so growth *deceleration* is visible even while absolute $ climbs.
- **EPS** (`eps`, `epsDiluted`) — line chart. Diluted is the conservative figure — plot it as the primary line, basic EPS as a thin secondary line.
- **Quarterly seasonality** (`income_quarterly.revenue` grouped by `period` Q1–Q4, one bar per quarter across years) — reveals seasonal patterns (e.g. holiday-quarter strength) that the annual chart can't show.

```tsx
<BarChart data={annualIncome}>
  <Bar dataKey="revenue" fill="#6366f1" name="Revenue" />
  <Bar dataKey="netIncome" fill="#475569" name="Net Income" />
  <Line dataKey="growthRevenue" yAxisId="growth" stroke="#facc15" name="Revenue YoY %" />
  <XAxis dataKey="period" />
  <YAxis yAxisId="amount" tickFormatter={v => `$${(v/1e9).toFixed(1)}B`} />
  <YAxis yAxisId="growth" orientation="right" tickFormatter={v => `${v}%`} />
  <Tooltip formatter={(v: number) => `$${(v/1e9).toFixed(2)}B`} />
  <Legend />
</BarChart>
```

### 2. Profitability / Margins
Source: `income_annual` + `ratios`

- **Margin trend** (`grossProfitMargin`, `operatingProfitMargin`, `ebitdaMargin`, `netProfitMargin`) — multi-line trend, % y-axis. Four lines, one chart.
- **Margin waterfall** (revenue → grossProfit → operatingIncome → netIncome, one year at a time) — complements the trend line by showing *where* margin is lost within a single year.

### 3. Returns & Capital Efficiency
Source: `key_metrics`

- **Returns trend** (`returnOnEquity`, `returnOnInvestedCapital`, `returnOnAssets`, `returnOnCapitalEmployed`) — multi-line trend or small-multiple bars. Keep ROIC and ROCE both (redundant for most companies, diverges for heavily-levered ones).
- ⚠️ **ROE distortion guard**: buyback-heavy companies (shrinking `totalStockholdersEquity`) can show ROE well over 100% — not a data error, just equity math. Any ROE display (`MetricCard` or trend line) needs a tooltip/caption for low-equity companies, or it reads as broken.

### 4. Balance Sheet Health / Liquidity
Source: `balance_annual` + `ratios`

- **Assets vs. liabilities** (`totalCurrentAssets` vs `totalCurrentLiabilities`) — stacked/mirrored bar, a visual gut-check before showing the ratio below.
- **Liquidity gauge** (`currentRatio`, `quickRatio`) — gauge or banded bar: red <1.0, amber 1.0–1.5, green >1.5. Pair with `operatingCashFlowRatio` — a sub-1.0 current ratio can be normal for a fast cash-generating company, and OCF ratio is the more honest liquidity signal in that case. Don't show the gauge without that pairing/caption — a bare red gauge reads as "in trouble" when it may not be.
- **Debt vs. cash** (`totalDebt`, `cashAndCashEquivalents`, `netDebt` as the delta) — bar chart, always reads correctly as-is.
- **Debt/Equity trend** (`debtToEquityRatio`) — line chart. ⚠️ Same equity-shrinkage distortion as ROE above: a falling ratio can look like de-leveraging when it's mostly the denominator shrinking from buybacks, not less debt. Pair with a `totalDebt` trend line alongside it so the real story (debt flat/up, equity down) is visible.

### 5. Cash Flow Quality
Source: `cashflow_annual` + `key_metrics`

- **Accounting quality check** (`netIncome` vs `operatingCashFlow` vs `freeCashFlow`, 3-line trend on one chart) — the single most important chart in this tab: OCF should track or exceed net income. When it doesn't, that's a real quality flag.
- **FCF waterfall** (`operatingCashFlow` → `capitalExpenditure` → `freeCashFlow`, per year) — shows capital intensity directly.
- **Shareholder returns vs. FCF** (`commonStockRepurchased` + `commonDividendsPaid` as a stacked bar, `freeCashFlow` as a line overlay) — answers "is the company returning more cash than it generates?" Flag/annotate any year where payout (buybacks + dividends) exceeds FCF — it means cash reserves or debt are funding the payout.
- **FCF Yield / Capex-to-Revenue** (`freeCashFlowYield`, `capexToRevenue`) — `MetricCard`s.

### 6. Valuation
Source: `ratios` + `key_metrics` (heavy field overlap between the two — see dedup note below)

- **Valuation band chart** — `priceToEarningsRatio`, `priceToSalesRatio`, `priceToBookRatio` as trend lines, each with a shaded band for that ticker's own trailing 4–10yr min/max/avg. This is the highest-value chart in the whole tab: "is this expensive relative to its own history," not relative to an arbitrary market-wide threshold. Gets meaningfully better as more history backfills (prioritize per the note in "Purpose" above).
- **Dividend yield** (`dividendYield`) — `MetricCard`.
- **Duplicate-field dedup** — FMP returns the same values from two endpoints; pick one canonical source per metric and don't chart both:
  - `enterpriseValueMultiple` (`ratios`) and `evToEBITDA` (`key_metrics`) are literally identical — canonical source: `ratios.enterpriseValueMultiple`.
  - `priceToFreeCashFlowRatio` (`ratios`) and `1 / freeCashFlowYield` (`key_metrics`) are the same metric, inverse form — canonical source: `ratios.priceToFreeCashFlowRatio`.
  - `currentRatio` appears identically in both `ratios` and `key_metrics` — canonical source: `ratios.currentRatio`.

### 7. Efficiency / Working Capital Cycle
Source: `key_metrics`

- **DSO / DIO / DPO** (`daysOfSalesOutstanding`, `daysOfInventoryOutstanding`, `daysOfPayablesOutstanding`) — grouped bar per year, standard trio.
- **Cash conversion cycle** (`cashConversionCycle`) — bold single-number/trend callout card, can go negative. A negative CCC (suppliers effectively financing operations) is a genuinely rare, impressive signal — surface it prominently rather than burying it in a table.

### Key Ratio Cards (Grid)
2×3 grid of `MetricCard` (see `shared/MetricCard.md`), colored by its heat scale (ice blue = low end of typical range, red = high end) with a trend arrow vs. prior year:

```tsx
<div className="grid grid-cols-3 gap-3">
  <MetricCard metricKey="priceToEarningsRatio" label="P/E (TTM)"    value={ratios.priceToEarningsRatio}    trend={trends.priceToEarningsRatio} />
  <MetricCard metricKey="enterpriseValueMultiple" label="EV/EBITDA" value={ratios.enterpriseValueMultiple} trend={trends.enterpriseValueMultiple} />
  <MetricCard metricKey="freeCashFlowYield" label="FCF Yield"       value={keyMetrics.freeCashFlowYield}    trend={trends.freeCashFlowYield} />
  <MetricCard metricKey="debtToEquityRatio" label="Debt/Equity"     value={ratios.debtToEquityRatio}        trend={trends.debtToEquityRatio} />
  <MetricCard metricKey="grossProfitMargin" label="Gross Margin"    value={ratios.grossProfitMargin}        trend={trends.grossProfitMargin} />
  <MetricCard metricKey="returnOnEquity" label="ROE"                value={keyMetrics.returnOnEquity}       trend={trends.returnOnEquity} />
  <MetricCard metricKey="returnOnInvestedCapital" label="ROIC"      value={keyMetrics.returnOnInvestedCapital} trend={trends.returnOnInvestedCapital} />
</div>
```

ROE and ROIC are separate cards, not one combined "ROE / ROIC" tile — they can diverge meaningfully (see §3), and collapsing them into one value hides that.

### Earnings Track Record
Table of last 8 quarters: EPS estimate, EPS actual, surprise %, beat/miss badge.

## Data Quality Caveats (guard before charting)
- **SG&A sub-line inconsistency** — `generalAndAdministrativeExpenses` and `sellingAndMarketingExpenses` flip between `0` and populated across years within the *same* company's records; it's an FMP filing-categorization change, not a real business swing. Always chart the combined `sellingGeneralAndAdministrativeExpenses` line for trend views. Don't build a stacked S&M-vs-G&A breakdown off the sub-fields — it will show fake zero-drops.
- **Same pattern on the balance sheet** — `accruedExpenses` and `taxPayables` can flip between `$0` and populated year to year. Treat as filing-categorization noise, not signal; don't trend-chart these two directly.
- **`interestCoverageRatio` reports as `0`** in years where a company carries near-zero net interest expense — that's "not applicable," not literally zero coverage. Render as "N/A" below some threshold rather than `0x`.
- **`priceToEarningsGrowthRatio` (PEG) is unstable** for low/negative-growth years (can swing from +170 to -46 year over year when dividing by a near-zero growth rate) — don't trend-chart PEG without a sanity clamp on the denominator.

## Field Reconciliation
`FundamentalsTab` previously used placeholder field names that didn't match FMP's real payload. Mapping, for anything still referencing the old names elsewhere:

| Old placeholder | Real field | Source array |
|---|---|---|
| `pe_ttm` | `priceToEarningsRatio` | `ratios` |
| `ev_ebitda` | `enterpriseValueMultiple` | `ratios` (not `key_metrics.evToEBITDA` — duplicate, see §6) |
| `fcf_yield` | `freeCashFlowYield` | `key_metrics` |
| `debt_equity` | `debtToEquityRatio` | `ratios` |
| `gross_margin` | `grossProfitMargin` | `ratios` |
| `roe_roic` | `returnOnEquity` + `returnOnInvestedCapital` | `key_metrics` — two separate cards, not one combined metric |

See `backend/models/stock.md` for the corresponding `KeyRatios`/`StockFinancials` Pydantic model, which uses these same real field names.

## Dependencies
- `recharts`
- `useStockFinancials`
- `MetricCard` (`shared/MetricCard.md`)
