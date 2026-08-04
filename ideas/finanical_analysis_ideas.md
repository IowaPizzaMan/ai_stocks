
## Financial data breakdown — for FundamentalsTab / DATA_SOURCES spec integration

Reviewed the AAPL record above as a financial analyst would: which of these ~150 raw FMP fields actually drive a decision, and how each should be charted once multi-year history is loaded. The existing `FundamentalsTab.md` spec already sketches 4 chart sections + 6 ratio cards, but its field names (`pe_ttm`, `ev_ebitda`, `roe_roic`...) are placeholders that don't match the real FMP field names below — table at the bottom reconciles that.

### 1. Growth & Scale — `income_annual` / `income_quarterly` + `growth`
| Field | Chart | Notes |
|---|---|---|
| `revenue`, `netIncome` | Grouped bar, multi-year | Already in spec §1. With more history, extend to 5–10yr. |
| `growthRevenue`, `growthNetIncome`, `growthEPS` | Line, secondary axis over the bar chart | YoY % — lets you see growth *decelerating* even while absolute $ climbs (AAPL: revenue +6.4% FY25 vs +2.0% FY24). |
| `eps`, `epsDiluted` | Line | Diluted is the conservative one — use it as primary, basic as a thin secondary line. |
| `income_quarterly.revenue` by `period` (Q1–Q4) | Seasonality bar chart, one bar per quarter across years | Apple's Q1 (holiday) is consistently ~40% higher than Q2/Q3 — a seasonality chart is genuinely useful for AAPL specifically, not just decorative. |

### 2. Profitability / Margins — `income_annual` + `ratios`
| Field | Chart | Notes |
|---|---|---|
| `grossProfitMargin`, `operatingProfitMargin`, `ebitdaMargin`, `netProfitMargin` | Multi-line trend, % y-axis | Matches spec §2 exactly — these 4 field names are the real ones to bind. |
| revenue → grossProfit → operatingIncome → netIncome | Waterfall, one year at a time | Nice complement to the trend line: shows *where* margin is lost within a single year. |

### 3. Returns & Capital Efficiency — `key_metrics`
| Field | Chart | Notes |
|---|---|---|
| `returnOnEquity`, `returnOnInvestedCapital`, `returnOnAssets` | Multi-line trend or small-multiple bars | ⚠️ AAPL's `returnOnEquity` is **151%** — not a bug, it's buybacks driving equity toward zero (`totalStockholdersEquity` fell from $50.7B in FY22 to $73.7B in FY25 while paying out $90B+/yr in repurchases). Any ROE display needs a tooltip/caveat for low-equity companies, or it reads as a data error. |
| `returnOnCapitalEmployed` | Same panel as ROIC | Redundant with ROIC for most companies but diverges when there's a lot of debt — keep both, drop neither. |

### 4. Balance Sheet Health / Liquidity — `balance_annual` + `ratios`
| Field | Chart | Notes |
|---|---|---|
| `totalCurrentAssets` vs `totalCurrentLiabilities` | Stacked/mirrored bar | Visual gut-check before showing the ratio. |
| `currentRatio`, `quickRatio` | Gauge or banded bar (red <1.0, amber 1.0–1.5, green >1.5) | AAPL sits at 0.89 — below 1.0, which looks alarming out of context but is normal for AAPL given its cash-generation speed. A gauge without a "why" caption will scare users; consider pairing with `operatingCashFlowRatio` (0.67) which is the more honest liquidity signal for a company like this. |
| `totalDebt`, `cashAndCashEquivalents`, `netDebt` | Bar (debt vs cash, net debt as the delta) | Straightforward and always reads correctly. |
| `debtToEquityRatio` | Trend line | ⚠️ Same equity-shrinkage distortion as ROE above (2.6x → 1.5x looks like *de-leveraging* but is mostly equity math, not less debt). Pair with `totalDebt` trend line to show the real story. |

### 5. Cash Flow Quality — `cashflow_annual` + `key_metrics`
| Field | Chart | Notes |
|---|---|---|
| `netIncome` vs `operatingCashFlow` vs `freeCashFlow` | 3-line trend, same chart | This is the single most important "is the accounting real" chart — OCF should track or exceed net income (AAPL: OCF $111B > NI $112B, healthy). |
| `operatingCashFlow` → `capitalExpenditure` → `freeCashFlow` | Waterfall per year | Shows capital intensity directly. |
| `commonStockRepurchased`, `commonDividendsPaid` vs `freeCashFlow` | Stacked bar (buybacks + dividends) with FCF as a line overlay | "Is the company returning more than it generates?" — AAPL returned ~$106B (buybacks+divs) against $99B FCF in FY25, i.e. drawing down cash/issuing debt to fund it. Worth flagging when payout > FCF. |
| `freeCashFlowYield`, `capexToRevenue` | MetricCard | Already effectively covered by spec's FCF Yield card. |

### 6. Valuation — `ratios` + `key_metrics` (heavy overlap, needs de-duplication)
| Field | Chart | Notes |
|---|---|---|
| `priceToEarningsRatio`, `priceToSalesRatio`, `priceToBookRatio` | Trend line **with a shaded band** for that ticker's own 4–10yr min/max/avg | The single highest-value chart in this whole dataset — "is this expensive relative to its own history," not relative to an arbitrary threshold. Needs the longer history you mentioned is coming. |
| `enterpriseValueMultiple` (in `ratios`) vs `evToEBITDA` (in `key_metrics`) | — | **Duplicate value** (literally identical: 26.9699... in both). Pick one canonical source. |
| `priceToFreeCashFlowRatio` (`ratios`) vs `1 / freeCashFlowYield` (`key_metrics`) | — | Same metric, inverse form, two sources. Same for `currentRatio` (present in both objects, identical value). |
| `dividendYield` | MetricCard | Fine as-is. |

### 7. Efficiency / Working Capital Cycle — `key_metrics`
| Field | Chart | Notes |
|---|---|---|
| `daysOfSalesOutstanding`, `daysOfInventoryOutstanding`, `daysOfPayablesOutstanding` | Grouped bar per year | Standard DSO/DIO/DPO trio. |
| `cashConversionCycle` | Single bold number/trend, can go negative | AAPL: **-42 days**. This is a great "explain it" callout card — negative CCC means suppliers are financing Apple's operations, a genuinely impressive/rare signal worth surfacing prominently rather than burying in a table. |

### Data quality caveats (don't chart these directly without guards)
- **SG&A sub-line inconsistency**: `generalAndAdministrativeExpenses` and `sellingAndMarketingExpenses` flip between `0` and populated across years in the *same* AAPL record (e.g. FY24 has real S&M of $18.6B, FY23/FY22/FY25 show `$0`) — FMP's categorization changes by filing, not a real business change. **Always chart `sellingGeneralAndAdministrativeExpenses` (the combined line)** for trend views; don't build a stacked S&M-vs-G&A chart off these sub-fields, it'll show fake zero-drops.
- Same pattern on the balance sheet: `accruedExpenses`, `taxPayables` go from `$0` one year to billions the next (FY25 `accruedExpenses` populated, `taxPayables: 0`; FY24 reversed). Treat as filing-categorization noise, not signal.
- `interestCoverageRatio` reports as `NumberInt(0)` in years AAPL carries near-zero net interest expense — that's "not applicable," not literally zero coverage. Render as "N/A" below some threshold rather than `0x`.
- `priceToEarningsGrowthRatio` (PEG) swings wildly (`170.9` in FY23, `-45.9` in FY24) because it's dividing by a near-zero growth rate — PEG is unstable for low/negative-growth years and shouldn't be trend-charted without a sanity clamp.

### Reconciling `FundamentalsTab.md` placeholder names → real FMP fields
| Spec placeholder | Real field | Source array |
|---|---|---|
| `pe_ttm` | `priceToEarningsRatio` | `ratios` |
| `ev_ebitda` | `enterpriseValueMultiple` | `ratios` (not `key_metrics.evToEBITDA` — duplicate, pick one) |
| `fcf_yield` | `freeCashFlowYield` | `key_metrics` |
| `debt_equity` | `debtToEquityRatio` | `ratios` |
| `gross_margin` | `grossProfitMargin` | `ratios` |
| `roe_roic` | `returnOnEquity` + `returnOnInvestedCapital` | `key_metrics` (two separate cards, not one combined metric) |

### Since more historical data is coming
- Every chart above should be built trend-first (N years on the x-axis), not single-latest-value — the annual arrays are already ordered newest-first, so reverse for chronological x-axes.
- The valuation-band chart (§6) and margin trend (§2) get meaningfully better with 8–10yr history vs the 4yr in this sample; worth prioritizing backfill for those two over the others if fetch budget (FMP free tier: 250 calls/day, see `DATA_SOURCES.md`) is a constraint.
- `income_quarterly` supports a seasonality view that `income_annual` can't — keep pulling quarterly even once you have deep annual history.


