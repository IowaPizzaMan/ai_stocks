from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from ..config import get_settings

settings = get_settings()


class SentimentAnalyzer:
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.labels = ["negative", "neutral", "positive"]
        self._loaded = False

    def load(self):
        if self._loaded:
            return

        self.tokenizer = AutoTokenizer.from_pretrained(settings.sentiment_model)
        self.model = AutoModelForSequenceClassification.from_pretrained(settings.sentiment_model)
        self.model.eval()
        self._loaded = True

    def analyze(self, text: str) -> dict:
        """Analyze sentiment of a text."""
        self.load()

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=1)

        scores = probabilities[0].tolist()
        max_idx = scores.index(max(scores))

        return {
            "sentiment": self.labels[max_idx],
            "score": scores[max_idx],
            "scores": {
                "negative": scores[0],
                "neutral": scores[1],
                "positive": scores[2],
            },
        }

    def analyze_batch(self, texts: list[str]) -> list[dict]:
        """Analyze sentiment of multiple texts."""
        self.load()

        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=1)

        results = []
        for probs in probabilities:
            scores = probs.tolist()
            max_idx = scores.index(max(scores))
            results.append({
                "sentiment": self.labels[max_idx],
                "score": scores[max_idx],
                "scores": {
                    "negative": scores[0],
                    "neutral": scores[1],
                    "positive": scores[2],
                },
            })

        return results
