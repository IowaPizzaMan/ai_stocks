# agent-runner/tools/sentiment.py

## Purpose
Fetches earnings call transcripts from Finnhub and prepares them for the SentimentAnalyst. Handles transcript discovery (listing available quarters) and retrieval.

## Functions

### `get_earnings_sentiment(ticker: str, num_quarters: int = 4) -> dict`

```python
def get_earnings_sentiment(ticker: str, num_quarters: int = 4) -> dict:
    # Get list of available transcripts
    transcript_list = finnhub_get(f"transcript/list?symbol={ticker}")
    available = transcript_list.get("transcript", [])  # list of { id, title, year, quarter }
    
    # Fetch the most recent N quarters
    transcripts = []
    for entry in available[:num_quarters]:
        text = finnhub_get(f"transcript?symbol={ticker}&year={entry['year']}&quarter={entry['quarter']}")
        transcripts.append({
            "year": entry["year"],
            "quarter": entry["quarter"],
            "text": text.get("transcript", [])  # list of { name, speech } segments
        })
    
    # Also fetch Finnhub's pre-computed SEC sentiment
    sec_sentiment = finnhub_get(f"stock/sec-sentiment?symbol={ticker}")
    
    return {
        "transcripts": transcripts,
        "sec_sentiment": sec_sentiment
    }
```

## Note on Transcript Format
Finnhub returns transcripts as a list of speech segments: `[{ "name": "Tim Cook", "speech": "..." }, ...]`. The chunker/summarizer will collapse and compress these before passing to the SentimentAnalyst — raw transcripts can be 30,000+ tokens.

## Caching
Cache transcripts in MongoDB `transcripts_cache` with `{ ticker, year, quarter }` as compound key. Transcripts never change after they're filed — no TTL needed. Only fetch quarters not already in cache.

```python
def get_transcript_cached(ticker, year, quarter):
    cached = db.transcripts_cache.find_one({ "ticker": ticker, "year": year, "quarter": quarter })
    if cached:
        return cached["text"]
    text = finnhub_get(f"transcript?symbol={ticker}&year={year}&quarter={quarter}")
    db.transcripts_cache.insert_one({ "ticker": ticker, "year": year, "quarter": quarter, "text": text, "fetched_at": now() })
    return text
```

## Dependencies
- `httpx` (Finnhub calls via shared `finnhub_get` helper)
- `pymongo`
