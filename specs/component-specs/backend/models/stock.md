# api/models/stock.py

## Purpose
Pydantic models for stock search results and cached financial data endpoints.

## Models

### `StockSearchResult`
```python
class StockSearchResult(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    status: Literal["active", "removed_from_market"] = "active"
    last_signal: Literal["bullish", "bearish", "neutral"] | None = None
    last_conviction: Literal["high", "medium", "low"] | None = None
    last_analyzed: datetime | None = None
```

### `FinancialStatement`
Field names match FMP's real `income-statement`/`cash-flow-statement` payload directly (see `DATA_SOURCES.md` → FMP) — no renaming/aliasing, so the frontend (`FundamentalsTab.md`) can bind straight through without a translation layer.
```python
class FinancialStatement(BaseModel):
    period: str         # "2024-Q3", "2023-FY"
    revenue: float | None = None
    grossProfit: float | None = None
    operatingIncome: float | None = None
    netIncome: float | None = None
    eps: float | None = None
    epsDiluted: float | None = None
    operatingCashFlow: float | None = None
    capitalExpenditure: float | None = None
    freeCashFlow: float | None = None
    commonStockRepurchased: float | None = None
    commonDividendsPaid: float | None = None
    # YoY growth, from FMP's income-statement-growth/cash-flow-statement-growth
    growthRevenue: float | None = None
    growthNetIncome: float | None = None
    growthEPS: float | None = None
```

### `KeyRatios`
Sourced from FMP `v3/ratios` + `v3/key-metrics`, real field names throughout (see "Field Reconciliation" in `FundamentalsTab.md` for the old placeholder → real-field mapping this replaced). Where FMP duplicates a value across both endpoints (`enterpriseValueMultiple`/`evToEBITDA`, `priceToFreeCashFlowRatio`/inverse `freeCashFlowYield`, `currentRatio`), only the canonical `ratios`-sourced field is kept here.
```python
class KeyRatios(BaseModel):
    # Valuation — ratios
    priceToEarningsRatio: float | None = None
    priceToSalesRatio: float | None = None
    priceToBookRatio: float | None = None
    enterpriseValueMultiple: float | None = None       # canonical EV/EBITDA
    priceToFreeCashFlowRatio: float | None = None
    priceToEarningsGrowthRatio: float | None = None    # PEG — unstable near-zero growth, see caveat
    dividendYield: float | None = None
    # Margins — ratios
    grossProfitMargin: float | None = None
    operatingProfitMargin: float | None = None
    ebitdaMargin: float | None = None
    netProfitMargin: float | None = None
    # Leverage / liquidity — ratios
    debtToEquityRatio: float | None = None
    currentRatio: float | None = None
    quickRatio: float | None = None
    operatingCashFlowRatio: float | None = None
    interestCoverageRatio: float | None = None         # render "N/A" near-zero, not "0x" — see caveat
    # Returns / capital efficiency — key_metrics
    returnOnEquity: float | None = None
    returnOnInvestedCapital: float | None = None
    returnOnAssets: float | None = None
    returnOnCapitalEmployed: float | None = None
    # Cash flow quality — key_metrics
    freeCashFlowYield: float | None = None
    capexToRevenue: float | None = None
    # Efficiency / working capital cycle — key_metrics
    daysOfSalesOutstanding: float | None = None
    daysOfInventoryOutstanding: float | None = None
    daysOfPayablesOutstanding: float | None = None
    cashConversionCycle: float | None = None
    # Balance sheet — balance_annual
    totalDebt: float | None = None
    cashAndCashEquivalents: float | None = None
    netDebt: float | None = None
```

### `StockFinancials`
```python
class StockFinancials(BaseModel):
    ticker: str
    income_statements: list[FinancialStatement]
    key_ratios: KeyRatios
    last_updated: datetime
```

### `AgentSignals`
```python
class AgentSignals(BaseModel):
    ticker: str
    timestamp: datetime
    technical: dict | None = None
    fundamental: dict | None = None
    insider: dict | None = None
    institutional: dict | None = None
    recommendation: dict | None = None
```
