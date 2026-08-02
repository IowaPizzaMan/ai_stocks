"""Pre-populate the watchlist in MongoDB. Run outside Docker: python scripts/seed_watchlist.py AAPL MSFT ..."""
import sys

# TODO(Phase 1): upsert tickers into `watchlist` and register in `ticker_index`.

if __name__ == "__main__":
    tickers = [t.upper() for t in sys.argv[1:]]
    if not tickers:
        sys.exit("usage: python seed_watchlist.py TICKER [TICKER ...]")
    raise NotImplementedError("Phase 1")
