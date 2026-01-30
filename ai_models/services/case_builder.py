from ..models import CaseGenerator
from .news_analyzer import NewsAnalyzerService


class CaseBuilderService:
    def __init__(self):
        self.case_generator = CaseGenerator()
        self.news_analyzer = NewsAnalyzerService()

    async def build_cases(
        self,
        company_name: str,
        ticker: str,
        sector: str,
        industry: str,
        news_articles: list[dict],
        financial_data: dict,
    ) -> dict:
        """Build comprehensive bull and bear cases."""
        analyzed_news = self.news_analyzer.analyze_news(news_articles)

        positive_news = [a["title"] for a in analyzed_news if a["sentiment"] == "positive"]
        negative_news = [a["title"] for a in analyzed_news if a["sentiment"] == "negative"]

        financial_highlights = self._extract_highlights(financial_data)

        bull_case = await self.case_generator.generate_bull_case(
            company_name=company_name,
            ticker=ticker,
            sector=sector or "Unknown",
            industry=industry or "Unknown",
            positive_news=positive_news,
            financial_highlights=financial_highlights,
        )

        bear_case = await self.case_generator.generate_bear_case(
            company_name=company_name,
            ticker=ticker,
            sector=sector or "Unknown",
            industry=industry or "Unknown",
            negative_news=negative_news,
            financial_highlights=financial_highlights,
        )

        all_titles = [a.get("title", "") for a in news_articles]
        news_summary = await self.case_generator.generate_summary(all_titles)

        sentiment_summary = self.news_analyzer.get_sentiment_summary(news_articles)

        return {
            "bull_case": bull_case,
            "bear_case": bear_case,
            "news_summary": news_summary,
            "sentiment_summary": sentiment_summary,
            "analyzed_articles": analyzed_news,
        }

    def _extract_highlights(self, financial_data: dict) -> dict:
        """Extract key financial highlights for case generation."""
        if not financial_data:
            return {}

        income = financial_data.get("income", [])
        if income and len(income) >= 2:
            latest = income[0].get("data", {})
            previous = income[1].get("data", {})

            latest_revenue = latest.get("Total Revenue") or latest.get("Revenue")
            previous_revenue = previous.get("Total Revenue") or previous.get("Revenue")

            if latest_revenue and previous_revenue and previous_revenue != 0:
                growth = ((latest_revenue - previous_revenue) / abs(previous_revenue)) * 100
                revenue_growth = f"{growth:.1f}%"
            else:
                revenue_growth = "N/A"

            latest_net = latest.get("Net Income")
            if latest_revenue and latest_net:
                margin = (latest_net / latest_revenue) * 100
                profit_margin = f"{margin:.1f}%"
            else:
                profit_margin = "N/A"
        else:
            revenue_growth = "N/A"
            profit_margin = "N/A"

        cashflow = financial_data.get("cashflow", [])
        if cashflow:
            fcf = cashflow[0].get("data", {}).get("Free Cash Flow")
            fcf_str = f"${fcf:,.0f}" if fcf else "N/A"
        else:
            fcf_str = "N/A"

        return {
            "revenue_growth": revenue_growth,
            "profit_margin": profit_margin,
            "fcf": fcf_str,
            "debt_to_equity": financial_data.get("debt_to_equity", "N/A"),
            "competition_risk": "Industry competitive pressure",
        }
