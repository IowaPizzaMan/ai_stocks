"""Form 4 insider transactions + MSPR via Finnhub.
Spec: specs/component-specs/agent-runner/tools/insider.md

Sourcing (verified 2026-08-02): FMP's insider endpoints are 402 paid-tier on
this key — Finnhub (free) is the primary and only source. Congressional trades
(Quiver) remain deferred per DATA_SOURCES.md.
"""
from datetime import date, datetime, timedelta

from tools.finnhub_client import finnhub_get

LOOKBACK_DAYS = 90
CLUSTER_WINDOW_DAYS = 30
CLUSTER_MIN_INSIDERS = 3

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
