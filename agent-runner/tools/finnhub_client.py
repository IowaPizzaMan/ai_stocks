"""Shared Finnhub REST helper (free tier: 60 calls/min — no caching needed)."""
import requests

from settings import settings

FINNHUB_BASE = "https://finnhub.io/api/v1/"


def finnhub_get(path: str, **params) -> dict | list:
    params["token"] = settings.finnhub_api_key
    r = requests.get(f"{FINNHUB_BASE}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()
