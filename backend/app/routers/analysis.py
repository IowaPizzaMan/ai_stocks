from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date
import httpx
from ..database import get_db
from ..models import WatchedStock, NewsArticle, FinancialStatement, StockAnalysis
from ..schemas import StockAnalysisResponse
from ..config import get_settings

router = APIRouter(prefix="/api/stocks", tags=["analysis"])

settings = get_settings()


def get_stock_or_404(ticker: str, db: Session) -> WatchedStock:
    stock = db.query(WatchedStock).filter(
        WatchedStock.ticker == ticker.upper(),
        WatchedStock.is_active == True
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")
    return stock


@router.get("/{ticker}/analysis", response_model=StockAnalysisResponse | None)
def get_analysis(ticker: str, db: Session = Depends(get_db)):
    """Get the latest AI analysis for a stock."""
    stock = get_stock_or_404(ticker, db)

    analysis = (
        db.query(StockAnalysis)
        .filter(StockAnalysis.stock_id == stock.id)
        .order_by(desc(StockAnalysis.analysis_date))
        .first()
    )

    if not analysis:
        return None
    return analysis


@router.post("/{ticker}/analyze", response_model=StockAnalysisResponse)
async def trigger_analysis(ticker: str, db: Session = Depends(get_db)):
    """Trigger analysis for a stock. Uses AI if enabled, otherwise generates basic analysis."""
    stock = get_stock_or_404(ticker, db)

    recent_news = (
        db.query(NewsArticle)
        .filter(NewsArticle.stock_id == stock.id)
        .order_by(desc(NewsArticle.published_at))
        .limit(20)
        .all()
    )

    income_stmts = (
        db.query(FinancialStatement)
        .filter(
            FinancialStatement.stock_id == stock.id,
            FinancialStatement.statement_type == "income",
            FinancialStatement.period_type == "quarterly",
        )
        .order_by(desc(FinancialStatement.period_end))
        .limit(4)
        .all()
    )

    positive_news = [n for n in recent_news if n.sentiment == "positive"]
    negative_news = [n for n in recent_news if n.sentiment == "negative"]

    revenue_trend = "N/A"
    revenue_growth = None
    if income_stmts and len(income_stmts) >= 2:
        latest = income_stmts[0].data.get("Total Revenue") or income_stmts[0].data.get("Revenue")
        previous = income_stmts[1].data.get("Total Revenue") or income_stmts[1].data.get("Revenue")
        if latest and previous and previous != 0:
            revenue_growth = ((latest - previous) / abs(previous)) * 100
            revenue_trend = f"{revenue_growth:.1f}% QoQ growth"

    if settings.ai_models_enabled:
        positive_headlines = "\n".join([f"- {n.title}" for n in positive_news[:5]]) or "No recent positive news"
        negative_headlines = "\n".join([f"- {n.title}" for n in negative_news[:5]]) or "No recent negative news"

        bull_prompt = f"""You are a stock analyst. Write a concise bull case (2-3 paragraphs) for {stock.company_name} ({stock.ticker}).

Company: {stock.company_name}
Sector: {stock.sector}
Industry: {stock.industry}

Recent positive news:
{positive_headlines}

Financial highlights:
- Revenue trend: {revenue_trend}

Write a compelling bull case focusing on growth opportunities, competitive advantages, and positive catalysts. Be specific and data-driven."""

        bear_prompt = f"""You are a stock analyst. Write a concise bear case (2-3 paragraphs) for {stock.company_name} ({stock.ticker}).

Company: {stock.company_name}
Sector: {stock.sector}
Industry: {stock.industry}

Recent concerning news:
{negative_headlines}

Financial highlights:
- Revenue trend: {revenue_trend}

Write a realistic bear case focusing on risks, challenges, and potential negative catalysts. Be specific and data-driven."""

        try:
            async with httpx.AsyncClient() as client:
                bull_response = await client.post(
                    f"{settings.ollama_url}/api/generate",
                    json={
                        "model": "mistral",
                        "prompt": bull_prompt,
                        "stream": False,
                    },
                    timeout=120.0,
                )
                bull_case = bull_response.json().get("response", "Analysis unavailable")

                bear_response = await client.post(
                    f"{settings.ollama_url}/api/generate",
                    json={
                        "model": "mistral",
                        "prompt": bear_prompt,
                        "stream": False,
                    },
                    timeout=120.0,
                )
                bear_case = bear_response.json().get("response", "Analysis unavailable")
        except Exception as e:
            bull_case = f"Unable to generate AI analysis: {str(e)}"
            bear_case = f"Unable to generate AI analysis: {str(e)}"
    else:
        # Generate basic analysis without AI
        bull_points = []
        bear_points = []

        if revenue_growth is not None:
            if revenue_growth > 10:
                bull_points.append(f"Strong revenue growth of {revenue_growth:.1f}% QoQ")
            elif revenue_growth > 0:
                bull_points.append(f"Positive revenue growth of {revenue_growth:.1f}% QoQ")
            elif revenue_growth < -10:
                bear_points.append(f"Significant revenue decline of {revenue_growth:.1f}% QoQ")
            else:
                bear_points.append(f"Slight revenue decline of {revenue_growth:.1f}% QoQ")

        if len(positive_news) > 0:
            bull_points.append(f"{len(positive_news)} positive news articles in recent coverage")
            bull_points.append(f"Recent positive headlines include: {positive_news[0].title[:100]}...")

        if len(negative_news) > 0:
            bear_points.append(f"{len(negative_news)} negative news articles in recent coverage")
            bear_points.append(f"Recent concerns include: {negative_news[0].title[:100]}...")

        if stock.sector:
            bull_points.append(f"Operates in {stock.sector} sector ({stock.industry or 'various industries'})")

        if not bull_points:
            bull_points.append("Insufficient data to generate bull case. Sync more data for better analysis.")
        if not bear_points:
            bear_points.append("Insufficient data to generate bear case. Sync more data for better analysis.")

        bull_case = "BULL CASE (Basic Analysis - AI Disabled)\n\n" + "\n".join(f"- {p}" for p in bull_points)
        bear_case = "BEAR CASE (Basic Analysis - AI Disabled)\n\n" + "\n".join(f"- {p}" for p in bear_points)

    total_news = len(recent_news)
    positive_count = len(positive_news)
    negative_count = len(negative_news)
    neutral_count = total_news - positive_count - negative_count

    if total_news > 0:
        sentiment_ratio = positive_count / total_news
        if sentiment_ratio > 0.6:
            short_term = "Bullish - Predominantly positive news sentiment"
        elif sentiment_ratio < 0.3:
            short_term = "Bearish - Predominantly negative news sentiment"
        else:
            short_term = "Neutral - Mixed news sentiment"
    else:
        short_term = "Insufficient news data for short-term outlook"

    long_term = f"Based on {len(income_stmts)} quarters of financial data. {revenue_trend}."

    news_summary = f"Analyzed {total_news} recent articles: {positive_count} positive, {negative_count} negative, {neutral_count} neutral."

    confidence = min(0.9, 0.3 + (total_news * 0.02) + (len(income_stmts) * 0.1))
    if not settings.ai_models_enabled:
        confidence = confidence * 0.5  # Lower confidence for non-AI analysis

    existing = (
        db.query(StockAnalysis)
        .filter(
            StockAnalysis.stock_id == stock.id,
            StockAnalysis.analysis_date == date.today(),
        )
        .first()
    )

    if existing:
        existing.bull_case = bull_case
        existing.bear_case = bear_case
        existing.short_term_outlook = short_term
        existing.long_term_outlook = long_term
        existing.confidence_score = confidence
        existing.news_summary = news_summary
        analysis = existing
    else:
        analysis = StockAnalysis(
            stock_id=stock.id,
            analysis_date=date.today(),
            bull_case=bull_case,
            bear_case=bear_case,
            short_term_outlook=short_term,
            long_term_outlook=long_term,
            confidence_score=confidence,
            news_summary=news_summary,
        )
        db.add(analysis)

    db.commit()
    db.refresh(analysis)
    return analysis


@router.post("/analyze/all")
async def analyze_all_stocks(db: Session = Depends(get_db)):
    """Run analysis on all watched stocks."""
    stocks = db.query(WatchedStock).filter(WatchedStock.is_active == True).all()

    results = []
    for stock in stocks:
        try:
            analysis = await trigger_analysis(stock.ticker, db)
            results.append({
                "ticker": stock.ticker,
                "status": "success",
                "analysis_date": str(analysis.analysis_date),
            })
        except Exception as e:
            results.append({
                "ticker": stock.ticker,
                "status": "failed",
                "error": str(e),
            })

    return {"results": results}
