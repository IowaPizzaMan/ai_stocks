from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, timedelta
from ..database import get_db
from ..models import WatchedStock, PriceHistory, FinancialStatement, NewsArticle, EarningsData
from ..schemas import (
    PriceHistoryResponse,
    FinancialStatementResponse,
    NewsArticleResponse,
    SyncResponse,
    MetricsResponse,
    MetricValue,
    EarningsResponse,
)
from ..services import YahooFinanceService

router = APIRouter(prefix="/api/stocks", tags=["data"])


def get_stock_or_404(ticker: str, db: Session) -> WatchedStock:
    stock = db.query(WatchedStock).filter(
        WatchedStock.ticker == ticker.upper(),
        WatchedStock.is_active == True
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")
    return stock


@router.get("/{ticker}/prices", response_model=list[PriceHistoryResponse])
def get_prices(
    ticker: str,
    period: str = Query("1y", description="Time period: 1w, 1m, 3m, 1y, 5y, max"),
    db: Session = Depends(get_db)
):
    """Get price history for a stock."""
    stock = get_stock_or_404(ticker, db)

    period_map = {
        "1w": 7,
        "1m": 30,
        "3m": 90,
        "1y": 365,
        "5y": 1825,
        "max": None,
    }

    days = period_map.get(period)
    query = db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id)

    if days:
        start_date = date.today() - timedelta(days=days)
        query = query.filter(PriceHistory.date >= start_date)

    prices = query.order_by(PriceHistory.date).all()
    return prices


@router.get("/{ticker}/financials", response_model=list[FinancialStatementResponse])
def get_financials(
    ticker: str,
    statement_type: str = Query("income", description="Statement type: income, balance, cashflow"),
    period_type: str = Query("quarterly", description="Period type: quarterly, annual"),
    db: Session = Depends(get_db)
):
    """Get financial statements for a stock."""
    stock = get_stock_or_404(ticker, db)

    statements = (
        db.query(FinancialStatement)
        .filter(
            FinancialStatement.stock_id == stock.id,
            FinancialStatement.statement_type == statement_type,
            FinancialStatement.period_type == period_type,
        )
        .order_by(desc(FinancialStatement.period_end))
        .all()
    )
    return statements


@router.get("/{ticker}/news", response_model=list[NewsArticleResponse])
def get_news(
    ticker: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get news articles for a stock."""
    stock = get_stock_or_404(ticker, db)

    articles = (
        db.query(NewsArticle)
        .filter(NewsArticle.stock_id == stock.id)
        .order_by(desc(NewsArticle.published_at))
        .limit(limit)
        .all()
    )
    return articles


@router.get("/{ticker}/earnings", response_model=EarningsResponse)
def get_earnings(ticker: str, db: Session = Depends(get_db)):
    """Get all earnings data for a stock."""
    stock = get_stock_or_404(ticker, db)

    earnings_records = (
        db.query(EarningsData)
        .filter(EarningsData.stock_id == stock.id)
        .all()
    )

    # Build response with all earnings data types
    response_data = {"ticker": stock.ticker}
    for record in earnings_records:
        response_data[record.data_type] = record.data

    return EarningsResponse(**response_data)


@router.post("/{ticker}/sync", response_model=SyncResponse)
def sync_stock(ticker: str, db: Session = Depends(get_db)):
    """Trigger data sync for a stock (delta fetch)."""
    import traceback
    import logging
    logger = logging.getLogger(__name__)

    stock = get_stock_or_404(ticker, db)
    yf_service = YahooFinanceService(db)

    try:
        prices_count = yf_service.sync_prices(stock)
        financials_count = yf_service.sync_financials(stock)
        new_articles = yf_service.sync_news(stock)
        earnings_count = yf_service.sync_earnings(stock)

        return SyncResponse(
            ticker=stock.ticker,
            prices_synced=prices_count,
            financials_synced=financials_count,
            news_synced=len(new_articles),
            earnings_synced=earnings_count,
            status="success",
            message=f"Synced {prices_count} prices, {financials_count} financial records, {len(new_articles)} news articles, {earnings_count} earnings data types",
        )
    except Exception as e:
        logger.error(f"Sync failed for {ticker}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/{ticker}/metrics", response_model=MetricsResponse)
def get_metrics(ticker: str, db: Session = Depends(get_db)):
    """Get calculated financial metrics with QoQ growth."""
    stock = get_stock_or_404(ticker, db)
    yf_service = YahooFinanceService(db)

    income_stmts = (
        db.query(FinancialStatement)
        .filter(
            FinancialStatement.stock_id == stock.id,
            FinancialStatement.statement_type == "income",
            FinancialStatement.period_type == "quarterly",
        )
        .order_by(desc(FinancialStatement.period_end))
        .limit(8)
        .all()
    )

    cashflow_stmts = (
        db.query(FinancialStatement)
        .filter(
            FinancialStatement.stock_id == stock.id,
            FinancialStatement.statement_type == "cashflow",
            FinancialStatement.period_type == "quarterly",
        )
        .order_by(desc(FinancialStatement.period_end))
        .limit(8)
        .all()
    )

    def extract_metrics(stmts, key_names):
        values = []
        for stmt in reversed(stmts):
            data = stmt.data
            value = None
            for key in key_names:
                if key in data:
                    value = data[key]
                    break
            values.append(MetricValue(period=stmt.period_end, value=value))

        for i in range(1, len(values)):
            if values[i].value and values[i - 1].value and values[i - 1].value != 0:
                change = ((values[i].value - values[i - 1].value) / abs(values[i - 1].value)) * 100
                values[i].change_percent = round(change, 2)

        return values

    revenue = extract_metrics(income_stmts, ["Total Revenue", "Revenue"])
    gross_profit = extract_metrics(income_stmts, ["Gross Profit"])
    operating_income = extract_metrics(income_stmts, ["Operating Income", "Operating Revenue"])
    net_income = extract_metrics(income_stmts, ["Net Income", "Net Income Common Stockholders"])
    eps = extract_metrics(income_stmts, ["Basic EPS", "Diluted EPS"])
    fcf = extract_metrics(cashflow_stmts, ["Free Cash Flow"])

    def calc_margin(numerator_list, denominator_list):
        margins = []
        for i, num in enumerate(numerator_list):
            if i < len(denominator_list) and num.value and denominator_list[i].value:
                margin = (num.value / denominator_list[i].value) * 100
                margins.append(MetricValue(period=num.period, value=round(margin, 2)))
            else:
                margins.append(MetricValue(period=num.period, value=None))
        return margins

    gross_margin = calc_margin(gross_profit, revenue)
    operating_margin = calc_margin(operating_income, revenue)
    net_margin = calc_margin(net_income, revenue)

    valuation = yf_service.get_valuation_metrics(stock.ticker)

    return MetricsResponse(
        ticker=stock.ticker,
        revenue=revenue,
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        net_margin=net_margin,
        eps=eps,
        free_cash_flow=fcf,
        pe_ratio=valuation.get("pe_ratio"),
        ps_ratio=valuation.get("ps_ratio"),
        pb_ratio=valuation.get("pb_ratio"),
        peg_ratio=valuation.get("peg_ratio"),
        ev_ebitda=valuation.get("ev_ebitda"),
        current_ratio=valuation.get("current_ratio"),
        debt_to_equity=valuation.get("debt_to_equity"),
        roe=valuation.get("roe"),
        roa=valuation.get("roa"),
    )


@router.post("/sync/all")
def sync_all_stocks(db: Session = Depends(get_db)):
    """Sync all watched stocks."""
    stocks = db.query(WatchedStock).filter(WatchedStock.is_active == True).all()
    yf_service = YahooFinanceService(db)

    results = []
    for stock in stocks:
        try:
            prices = yf_service.sync_prices(stock)
            financials = yf_service.sync_financials(stock)
            news = yf_service.sync_news(stock)
            earnings = yf_service.sync_earnings(stock)
            results.append({
                "ticker": stock.ticker,
                "status": "success",
                "prices": prices,
                "financials": financials,
                "news": len(news),
                "earnings": earnings,
            })
        except Exception as e:
            results.append({
                "ticker": stock.ticker,
                "status": "failed",
                "error": str(e),
            })

    return {"results": results}
