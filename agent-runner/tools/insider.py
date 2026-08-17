"""Form 4 insider transactions + MSPR via Finnhub, quarterly aggregates via FMP.
Spec: specs/component-specs/agent-runner/tools/insider.md,
      specs/021-stock-page-redesign (US7 — FR-015, FR-016)

Sourcing: Finnhub supplies the 90-day transaction detail and MSPR (its insider
endpoints are free on this key). FMP's `insider-trading/statistics` — verified
entitled 2026-08-16 — supplies multi-year quarterly aggregates that Finnhub's
90-day window can't show. Congressional trades (Quiver) remain deferred per
DATA_SOURCES.md.
"""
from datetime import date, datetime, timedelta

import requests
from pymongo.database import Database

from logging_config import get_logger
from tools.finnhub_client import finnhub_get
from tools.fmp_client import FmpBudgetExceededError, fmp_get

logger = get_logger(__name__)

LOOKBACK_DAYS = 90
CLUSTER_WINDOW_DAYS = 30
CLUSTER_MIN_INSIDERS = 3
MAX_QUARTERS = 8

# Finnhub/SEC Form 4 transaction codes
CODE_MAP = {
    "P": "purchase",
    "S": "sale",
    "G": "gift",
    "M": "option_exercise",
    "A": "award",
    "F": "tax_withholding",
    "D": "disposition",
    "C": "conversion",
}


def _normalize(raw: list[dict]) -> list[dict]:
    out = []
    for t in raw:
        code = (t.get("transactionCode") or "").upper()
        change = t.get("change") or 0
        price = t.get("transactionPrice") or 0
        ttype = CODE_MAP.get(code, "other")
        # Finnhub reports sales as negative change under code S
        out.append({
            "name": t.get("name"),
            "transaction_type": ttype,
            "shares": abs(int(change)),
            "price_per_share": float(price),
            "total_value": round(abs(change) * price, 2),
            "date": t.get("transactionDate"),
            "filing_date": t.get("filingDate"),
            "is_open_market": code in ("P", "S"),
        })
    return out


def detect_cluster(transactions: list[dict],
                   window_days: int = CLUSTER_WINDOW_DAYS,
                   min_insiders: int = CLUSTER_MIN_INSIDERS) -> dict:
    """Cluster buying: 3+ distinct insiders making open-market purchases within
    a rolling 30-day window — the highest-conviction insider signal."""
    buys = sorted(
        (t for t in transactions
         if t["transaction_type"] == "purchase" and t["is_open_market"] and t["date"]),
        key=lambda t: t["date"],
    )
    best: dict = {"detected": False, "insiders": [], "window_days": None}
    for i, anchor in enumerate(buys):
        start = datetime.fromisoformat(anchor["date"]).date()
        names = {}
        for t in buys[i:]:
            d = datetime.fromisoformat(t["date"]).date()
            if (d - start).days > window_days:
                break
            names[t["name"]] = d
        if len(names) >= min_insiders and len(names) > len(best["insiders"]):
            span = (max(names.values()) - start).days
            best = {"detected": True, "insiders": sorted(names), "window_days": span}
    return best


def summarize_counts(buy_count: int, sell_count: int) -> str | None:
    """Feed-card summary of open-market activity ("10 buys, 2 sells"), or None
    when there's nothing to say — absent renders as no badge, not "0 buys"."""
    if not buy_count and not sell_count:
        return None
    buys = f"{buy_count} buy{'s' if buy_count != 1 else ''}"
    sells = f"{sell_count} sell{'s' if sell_count != 1 else ''}"
    return f"{buys}, {sells}"


def _int(value) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def normalize_quarterly_stats(raw: list[dict]) -> list[dict]:
    """FMP's camelCase quarterly aggregates → the snake_case shape the UI reads
    (specs/021-stock-page-redesign/data-model.md §4), newest quarter first."""
    rows = [
        {
            "year": _int(r.get("year")),
            "quarter": _int(r.get("quarter")),
            "acquired_transactions": _int(r.get("acquiredTransactions")),
            "disposed_transactions": _int(r.get("disposedTransactions")),
            "acquired_disposed_ratio": _float(r.get("acquiredDisposedRatio")),
            "total_acquired": _int(r.get("totalAcquired")),
            "total_disposed": _int(r.get("totalDisposed")),
            "total_purchases": _int(r.get("totalPurchases")),
            "total_sales": _int(r.get("totalSales")),
        }
        for r in raw or []
    ]
    rows.sort(key=lambda r: (r["year"], r["quarter"]), reverse=True)
    return rows[:MAX_QUARTERS]


def get_insider_quarterly_stats(ticker: str, db: Database | None = None) -> list[dict]:
    """Quarterly acquired/disposed aggregates from FMP. Returns [] rather than
    raising when FMP is unavailable or the daily budget is spent — the tab
    renders its empty state and the rest of the analysis proceeds (FR-026)."""
    ticker = ticker.upper()
    try:
        raw = fmp_get(f"insider-trading/statistics?symbol={ticker}", db=db)
    except FmpBudgetExceededError:
        logger.warning("%s: FMP budget spent — no quarterly insider stats this run", ticker)
        return []
    except (requests.HTTPError, requests.RequestException) as exc:
        logger.warning("%s: insider statistics fetch failed: %s", ticker, exc)
        return []
    return normalize_quarterly_stats(raw if isinstance(raw, list) else [])


def get_insider_activity(ticker: str) -> dict:
    ticker = ticker.upper()
    to_date = date.today()
    from_date = to_date - timedelta(days=LOOKBACK_DAYS)

    raw = finnhub_get("stock/insider-transactions", symbol=ticker,
                      **{"from": from_date.isoformat(), "to": to_date.isoformat()})
    transactions = _normalize(raw.get("data", []))

    mspr = finnhub_get("stock/insider-sentiment", symbol=ticker,
                       **{"from": from_date.isoformat(), "to": to_date.isoformat()})

    buys = sum(t["total_value"] for t in transactions
               if t["transaction_type"] == "purchase" and t["is_open_market"])
    sells = sum(t["total_value"] for t in transactions
                if t["transaction_type"] == "sale" and t["is_open_market"])
    buy_count = sum(1 for t in transactions
                    if t["transaction_type"] == "purchase" and t["is_open_market"])
    sell_count = sum(1 for t in transactions
                     if t["transaction_type"] == "sale" and t["is_open_market"])

    return {
        "transactions": transactions,
        "mspr_monthly": mspr.get("data", []),
        "cluster_signal": detect_cluster(transactions),
        "open_market_buy_value": round(buys, 2),
        "open_market_sell_value": round(sells, 2),
        "open_market_buy_count": buy_count,
        "open_market_sell_count": sell_count,
        "recent_summary": summarize_counts(buy_count, sell_count),
        "net_direction": ("net_buyer" if buys > sells
                          else "net_seller" if sells > buys else "balanced"),
    }
