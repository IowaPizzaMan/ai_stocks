"""sector_etf_pull — daily price refresh for the 11 SPDR sector ETFs.
Spec: specs/028-dashboard-tweaks-batch US5.
Contract: specs/028-dashboard-tweaks-batch/contracts/sector-etf-series-api.md

Sector ETFs are ordinary tickers to price_store — reused entirely unchanged
(R5), which is what already provides delta refresh, budget guarding via
fmp_client, and fail-soft degradation to stored bars on a provider error.
This module only adds the 11-ticker loop, wrapping each ticker individually
so one failing does not abort the other ten (FR-021 at the data layer).

Not the same dataset as 017's `sector_performance_pull` — that job's
"today's sector performance snapshot" is a different shape entirely
(sector_performance collection, current-day percentages); this feeds
price_history like any other tracked ticker (R5).
"""
from logging_config import get_logger
from tools import price_store

logger = get_logger(__name__)

# Display label alongside each ticker — used by the read endpoint and chart
# legend, not by the pull itself.
SECTOR_ETF_LABELS: dict[str, str] = {
    "XLC": "Communication Services",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLV": "Health Care",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLK": "Technology",
    "XLU": "Utilities",
}

SECTOR_ETFS: list[str] = list(SECTOR_ETF_LABELS)


def run_sector_etf_pull(db) -> int:
    """work_queue admin-job handler for job_type="sector_etf_pull". Returns
    the count of tickers that returned usable bars, for dataset_meta."""
    usable = 0
    for ticker in SECTOR_ETFS:
        try:
            bars, _meta = price_store.get_series(ticker, refresh="delta", db=db)
        except Exception:
            logger.exception("sector_etf_pull: %s failed — continuing with the rest", ticker)
            continue
        if not bars.empty:
            usable += 1
    return usable
