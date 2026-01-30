import httpx
from ..config import get_settings

settings = get_settings()


class CaseGenerator:
    def __init__(self):
        self.ollama_url = settings.ollama_url
        self.model = settings.ollama_model

    async def generate_bull_case(
        self,
        company_name: str,
        ticker: str,
        sector: str,
        industry: str,
        positive_news: list[str],
        financial_highlights: dict,
    ) -> str:
        """Generate a bull case for a stock."""
        news_section = "\n".join([f"- {n}" for n in positive_news[:5]]) if positive_news else "No recent positive news"

        prompt = f"""You are a stock analyst. Write a concise bull case (2-3 paragraphs) for {company_name} ({ticker}).

Company: {company_name}
Sector: {sector}
Industry: {industry}

Recent positive news:
{news_section}

Financial highlights:
- Revenue growth: {financial_highlights.get('revenue_growth', 'N/A')}
- Profit margin: {financial_highlights.get('profit_margin', 'N/A')}
- FCF: {financial_highlights.get('fcf', 'N/A')}

Write a compelling bull case focusing on growth opportunities, competitive advantages, and positive catalysts. Be specific and data-driven."""

        return await self._generate(prompt)

    async def generate_bear_case(
        self,
        company_name: str,
        ticker: str,
        sector: str,
        industry: str,
        negative_news: list[str],
        financial_highlights: dict,
    ) -> str:
        """Generate a bear case for a stock."""
        news_section = "\n".join([f"- {n}" for n in negative_news[:5]]) if negative_news else "No recent negative news"

        prompt = f"""You are a stock analyst. Write a concise bear case (2-3 paragraphs) for {company_name} ({ticker}).

Company: {company_name}
Sector: {sector}
Industry: {industry}

Recent concerning news:
{news_section}

Financial highlights:
- Revenue growth: {financial_highlights.get('revenue_growth', 'N/A')}
- Debt to equity: {financial_highlights.get('debt_to_equity', 'N/A')}
- Competition risk: {financial_highlights.get('competition_risk', 'N/A')}

Write a realistic bear case focusing on risks, challenges, and potential negative catalysts. Be specific and data-driven."""

        return await self._generate(prompt)

    async def generate_summary(self, news_titles: list[str]) -> str:
        """Generate a summary of news articles."""
        if not news_titles:
            return "No recent news to summarize."

        titles = "\n".join([f"- {t}" for t in news_titles[:10]])

        prompt = f"""Summarize the following news headlines about a company in 2-3 sentences. Focus on the key themes and overall sentiment.

Headlines:
{titles}

Summary:"""

        return await self._generate(prompt)

    async def _generate(self, prompt: str) -> str:
        """Generate text using Ollama."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                return response.json().get("response", "Generation failed")
        except Exception as e:
            return f"Unable to generate: {str(e)}"
