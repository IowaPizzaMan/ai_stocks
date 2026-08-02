"""Pre-populate the watchlist in MongoDB.

Run outside Docker, from the repo root (so agent-runner's .env resolution works):
    python scripts/seed_watchlist.py AAPL MSFT NVDA
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-runner"))

from tools.db import WATCHLIST, get_db, register_ticker  # noqa: E402
from tools.price import is_ticker_valid  # noqa: E402


def seed(tickers: list[str]) -> None:
    db = get_db()
    for ticker in tickers:
        ticker = ticker.upper()
        if db[WATCHLIST].find_one({"ticker": ticker}):
            print(f"{ticker}: already in watchlist, skipping")
            continue
        if not is_ticker_valid(ticker):
            print(f"{ticker}: no price data on Yahoo — not adding (typo or delisted?)")
            continue

        register_ticker(ticker, source="watchlist", db=db)
        db[WATCHLIST].insert_one(
            {"ticker": ticker, "name": None, "sector": None, "status": "active",
             "added_at": datetime.now(timezone.utc)}
        )
        print(f"{ticker}: added")

    total = db[WATCHLIST].count_documents({})
    print(f"watchlist now has {total} ticker(s)")


if __name__ == "__main__":
    args = [t.upper() for t in sys.argv[1:]]
    if not args:
        sys.exit("usage: python scripts/seed_watchlist.py TICKER [TICKER ...]")
    seed(args)
