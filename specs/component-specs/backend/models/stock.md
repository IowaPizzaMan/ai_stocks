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
```python
class FinancialStatement(BaseModel):
    period: str         # "2024-Q3", "2023-FY"
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    eps_diluted: float | None = None
    free_cash_flow: float | None = None
```

### `KeyRatios`
```python
class KeyRatios(BaseModel):
    pe_ttm: float | None = None
    ev_ebitda: float | None = None
    price_to_sales: float | None = None
    price_to_book: float | None = None
    fcf_yield_pct: float | None = None
    debt_to_equity: float | None = None
    gross_margin_pct: float | None = None
    net_margin_pct: float | None = None
    roe: float | None = None
    roic: float | None = None
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
