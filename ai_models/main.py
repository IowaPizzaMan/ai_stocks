from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .models import SentimentAnalyzer
from .services import NewsAnalyzerService, CaseBuilderService
from .config import get_settings

settings = get_settings()

app = FastAPI(
    title="AI Models Service",
    description="AI/ML service for stock sentiment analysis and case generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sentiment_analyzer = SentimentAnalyzer()
news_analyzer = NewsAnalyzerService()
case_builder = CaseBuilderService()


class SentimentRequest(BaseModel):
    text: str


class BatchSentimentRequest(BaseModel):
    texts: list[str]


class NewsArticle(BaseModel):
    article_id: str
    title: str


class AnalyzeNewsRequest(BaseModel):
    articles: list[NewsArticle]


class BuildCasesRequest(BaseModel):
    company_name: str
    ticker: str
    sector: str | None = None
    industry: str | None = None
    news_articles: list[dict]
    financial_data: dict | None = None


@app.get("/")
def root():
    return {"message": "AI Models Service", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/sentiment")
def analyze_sentiment(request: SentimentRequest):
    """Analyze sentiment of a single text."""
    try:
        result = sentiment_analyzer.analyze(request.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sentiment/batch")
def analyze_sentiment_batch(request: BatchSentimentRequest):
    """Analyze sentiment of multiple texts."""
    try:
        results = sentiment_analyzer.analyze_batch(request.texts)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/news")
def analyze_news(request: AnalyzeNewsRequest):
    """Analyze sentiment of news articles."""
    try:
        articles = [{"article_id": a.article_id, "title": a.title} for a in request.articles]
        results = news_analyzer.analyze_news(articles)
        summary = news_analyzer.get_sentiment_summary(articles)
        return {
            "articles": results,
            "summary": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/cases")
async def build_cases(request: BuildCasesRequest):
    """Build bull and bear cases for a stock."""
    try:
        result = await case_builder.build_cases(
            company_name=request.company_name,
            ticker=request.ticker,
            sector=request.sector,
            industry=request.industry,
            news_articles=request.news_articles,
            financial_data=request.financial_data or {},
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
