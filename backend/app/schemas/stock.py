from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Any
from decimal import Decimal


class StockCreate(BaseModel):
    ticker: str


class StockResponse(BaseModel):
    id: int
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    added_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class StockListResponse(BaseModel):
    stocks: list[StockResponse]
    total: int


class PriceHistoryResponse(BaseModel):
    id: int
    stock_id: int
    date: date
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    adj_close: Optional[Decimal] = None
    volume: Optional[int] = None

    class Config:
        from_attributes = True


class FinancialStatementResponse(BaseModel):
    id: int
    stock_id: int
    period_end: date
    period_type: str
    statement_type: str
    data: dict[str, Any]
    fetched_at: datetime

    class Config:
        from_attributes = True


class NewsArticleResponse(BaseModel):
    id: int
    stock_id: int
    article_id: str
    title: str
    link: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[datetime] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[Decimal] = None
    fetched_at: datetime

    class Config:
        from_attributes = True


class StockAnalysisResponse(BaseModel):
    id: int
    stock_id: int
    analysis_date: date
    bull_case: Optional[str] = None
    bear_case: Optional[str] = None
    short_term_outlook: Optional[str] = None
    long_term_outlook: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    news_summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SyncResponse(BaseModel):
    ticker: str
    prices_synced: int
    financials_synced: int
    news_synced: int
    earnings_synced: int = 0
    status: str
    message: str


class MetricValue(BaseModel):
    period: date
    value: Optional[float] = None
    change_percent: Optional[float] = None


class MetricsResponse(BaseModel):
    ticker: str
    revenue: list[MetricValue]
    gross_margin: list[MetricValue]
    operating_margin: list[MetricValue]
    net_margin: list[MetricValue]
    eps: list[MetricValue]
    free_cash_flow: list[MetricValue]
    pe_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None


class EarningsDataResponse(BaseModel):
    id: int
    stock_id: int
    data_type: str
    data: dict[str, Any]
    fetched_at: datetime

    class Config:
        from_attributes = True


class EarningsResponse(BaseModel):
    """Aggregated earnings data for a stock."""
    ticker: str
    annual_earnings: Optional[dict[str, Any]] = None
    quarterly_earnings: Optional[dict[str, Any]] = None
    earnings_dates: Optional[dict[str, Any]] = None
    earnings_estimate: Optional[dict[str, Any]] = None
    revenue_estimate: Optional[dict[str, Any]] = None
    earnings_trend: Optional[dict[str, Any]] = None
    growth_estimates: Optional[dict[str, Any]] = None
    eps_revisions: Optional[dict[str, Any]] = None


# Watchlist schemas
class WatchlistCreate(BaseModel):
    name: str
    description: Optional[str] = None


class WatchlistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class WatchlistResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stock_count: int = 0

    class Config:
        from_attributes = True


class WatchlistDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stocks: list[StockResponse]

    class Config:
        from_attributes = True


class WatchlistListResponse(BaseModel):
    watchlists: list[WatchlistResponse]
    total: int


class AddStockToWatchlistRequest(BaseModel):
    ticker: str
