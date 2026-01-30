import yfinance as yf
import json

ticker = yf.Ticker("AAPL")
news = ticker.news

print(f"News type: {type(news)}")
print(f"News count: {len(news) if news else 0}")

if news and len(news) > 0:
    print("\n--- First article ---")
    first = news[0]
    print(f"Type: {type(first)}")

    if isinstance(first, dict):
        print(f"Keys: {first.keys()}")
        print(f"\nFull structure:\n{json.dumps(first, indent=2, default=str)}")
    else:
        print(f"Value: {first}")
