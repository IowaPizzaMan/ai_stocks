"""One-time cache warm-up: financials for every watchlist ticker, plus macro
and market-breadth data. All fetching goes through the cache-aware tools, so
re-running is safe and FMP quota guards apply (~7 FMP calls per cold ticker).

Run outside Docker, from the repo root:
    python scripts/backfill_financials.py            # whole watchlist
    python scripts/backfill_financials.py AAPL MSFT  # specific tickers
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-runner"))

from tools.breadth import get_market_breadth  # noqa: E402
from tools.db import FMP_USAGE, WATCHLIST, ensure_indexes, get_db  # noqa: E402
from tools.financials import get_financials  # noqa: E402
from tools.macro import get_macro_data  # noqa: E402


def backfill(tickers: list[str]) -> None:
    db = get_db()
    ensure_indexes(db)

    if not tickers:
        tickers = [w["ticker"] for w in db[WATCHLIST].find({}, {"ticker": 1})]
    if not tickers:
        sys.exit("watchlist is empty — seed it first: python scripts/seed_watchlist.py TICKER ...")

    print(f"backfilling {len(tickers)} ticker(s): {', '.join(tickers)}")
    for ticker in tickers:
        try:
            data = get_financials(ticker, db=db)
            filled = sum(1 for v in data.values() if v)
            print(f"{ticker}: financials cached ({filled}/{len(data)} endpoints returned data)")
        except Exception as exc:
            print(f"{ticker}: financials FAILED — {exc}")

    print("fetching macro indicators (FRED, 24h cache)...")
    macro = get_macro_data(db=db)
    print(f"macro: {len(macro)} series cached")

    print("computing market breadth (NYMO/NAMO)...")
    breadth = get_market_breadth(db=db)
    print(f"breadth: NYMO={breadth['nymo']['current']} ({breadth['nymo']['zone']}), "
          f"NAMO={breadth['namo']['current']} ({breadth['namo']['zone']})")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = db[FMP_USAGE].find_one({"date": today})
    print(f"FMP calls used today: {usage['count'] if usage else 0}/250")


if __name__ == "__main__":
    backfill([t.upper() for t in sys.argv[1:]])
