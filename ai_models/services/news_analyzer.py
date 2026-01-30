from ..models import SentimentAnalyzer


class NewsAnalyzerService:
    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()

    def analyze_news(self, articles: list[dict]) -> list[dict]:
        """Analyze sentiment of news articles."""
        if not articles:
            return []

        titles = [a.get("title", "") for a in articles]
        sentiments = self.sentiment_analyzer.analyze_batch(titles)

        results = []
        for article, sentiment in zip(articles, sentiments):
            results.append({
                "article_id": article.get("article_id"),
                "title": article.get("title"),
                "sentiment": sentiment["sentiment"],
                "sentiment_score": sentiment["score"],
            })

        return results

    def get_sentiment_summary(self, articles: list[dict]) -> dict:
        """Get aggregate sentiment statistics."""
        if not articles:
            return {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "overall_sentiment": "neutral",
            }

        analyzed = self.analyze_news(articles)

        positive = sum(1 for a in analyzed if a["sentiment"] == "positive")
        negative = sum(1 for a in analyzed if a["sentiment"] == "negative")
        neutral = sum(1 for a in analyzed if a["sentiment"] == "neutral")
        total = len(analyzed)

        if positive > negative and positive > neutral:
            overall = "positive"
        elif negative > positive and negative > neutral:
            overall = "negative"
        else:
            overall = "neutral"

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "overall_sentiment": overall,
        }
