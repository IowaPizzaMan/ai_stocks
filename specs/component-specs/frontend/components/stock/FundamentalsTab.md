# frontend/src/components/stock/FundamentalsTab.tsx

## Purpose
Renders financial charts and key ratio cards for the Fundamentals tab. Data comes from `useStockFinancials()` and the fundamental sub-report.

## Sections

### 1. Revenue & Earnings Bar Chart
Grouped bar chart (Recharts `BarChart`) showing last 4 years:
- Revenue (in billions, indigo bars)
- Net income (slate bars)
- YoY % growth annotations above each bar

```tsx
<BarChart data={annualIncome}>
  <Bar dataKey="revenue" fill="#6366f1" name="Revenue" />
  <Bar dataKey="netIncome" fill="#475569" name="Net Income" />
  <XAxis dataKey="period" />
  <YAxis tickFormatter={v => `$${(v/1e9).toFixed(1)}B`} />
  <Tooltip formatter={(v: number) => `$${(v/1e9).toFixed(2)}B`} />
  <Legend />
</BarChart>
```

### 2. Margin Trends (Line Chart)
Three lines over time: gross margin %, operating margin %, net margin %

### 3. Key Ratio Cards (Grid)
2×3 grid of `MetricCard` (see `shared/MetricCard.md`):
- P/E TTM (`pe_ttm`)
- EV/EBITDA (`ev_ebitda`)
- FCF Yield (`fcf_yield`)
- Debt/Equity (`debt_equity`)
- Gross Margin (`gross_margin`)
- ROE / ROIC (`roe_roic`)

Each card is colored by `MetricCard`'s heat scale — ice blue where the value sits at the low end of its typical range, red at the high end, so a high P/E card runs red and a low P/E card runs ice blue, and the whole grid shows at a glance where the company sits on each ratio. Trend arrow (up/down vs. prior year) still shown alongside the value.

```tsx
<div className="grid grid-cols-3 gap-3">
  <MetricCard metricKey="pe_ttm"       label="P/E (TTM)"     value={ratios.pe_ttm}       trend={trends.pe_ttm} />
  <MetricCard metricKey="ev_ebitda"    label="EV/EBITDA"     value={ratios.ev_ebitda}    trend={trends.ev_ebitda} />
  <MetricCard metricKey="fcf_yield"    label="FCF Yield"     value={ratios.fcf_yield}    trend={trends.fcf_yield} />
  <MetricCard metricKey="debt_equity"  label="Debt/Equity"   value={ratios.debt_equity}  trend={trends.debt_equity} />
  <MetricCard metricKey="gross_margin" label="Gross Margin"  value={ratios.gross_margin} trend={trends.gross_margin} />
  <MetricCard metricKey="roe_roic"     label="ROE / ROIC"    value={ratios.roe_roic}     trend={trends.roe_roic} />
</div>
```

### 4. Earnings Track Record
Table of last 8 quarters: EPS estimate, EPS actual, surprise %, beat/miss badge

## Dependencies
- `recharts`
- `useStockFinancials`
- `MetricCard` (`shared/MetricCard.md`)
