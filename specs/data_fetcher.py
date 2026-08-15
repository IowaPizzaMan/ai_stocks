"""
data_fetcher.py — Cache-aware data layer for StockAI

RETIRED (specs/017-fmp-migration-admin, 2026-08-15): this was a design
reference that never had a live importer in agent-runner/ — the equivalent
agent-runner/data_fetcher.py had zero live imports (confirmed) and was
deleted. Actual live data access is agent-runner/tools/*.py (price.py,
breadth.py, financials.py, earnings_calendar.py, institutional.py), all
FMP-sourced as of this feature. Kept here only as historical design context.

Strategy:
  - First call for any ticker/series: fetch full available history, store in MongoDB.
  - Every subsequent call: query MongoDB for the latest stored record, fetch only the gap.

This keeps API usage (especially FMP's 250 calls/day) minimal on daily runs.

Dependencies:
    pip install yfinance pymongo fredapi finnhub-python quiverquant requests
"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional

import pandas as pd
import yfinance as yf
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# MongoDB setup
# ──────────────────────────────────────────────────────────────────────────────

def get_db(mongo_uri: str = "mongodb://localhost:27017", db_name: str = "stockai"):
    client = MongoClient(mongo_uri)
    return client[db_name]


def ensure_indexes(db):
    """
    Call once at startup. Creates indexes so every 'find latest record' query
    is O(log n) instead of a full collection scan.
    """
    db["price_history"].create_index([("ticker", ASCENDING), ("date", DESCENDING)])
    db["price_history"].create_index([("ticker", ASCENDING), ("date", ASCENDING)], unique=True)

    for stmt in ("income", "balance", "cashflow"):
        for period in ("quarter", "annual"):
            coll = f"financials_{stmt}_{period}"
            db[coll].create_index([("ticker", ASCENDING), ("date", DESCENDING)])
            db[coll].create_index([("ticker", ASCENDING), ("date", ASCENDING)], unique=True)

    db["insider_transactions"].create_index([("ticker", ASCENDING), ("filingDate", DESCENDING)])
    db["insider_transactions"].create_index(
        [("ticker", ASCENDING), ("filingDate", ASCENDING),
         ("transactionDate", ASCENDING), ("reportingName", ASCENDING),
         ("securitiesTransacted", ASCENDING)],
        unique=True, sparse=True
    )

    db["macro_fred"].create_index([("series_id", ASCENDING), ("date", DESCENDING)])
    db["macro_fred"].create_index([("series_id", ASCENDING), ("date", ASCENDING)], unique=True)

    db["congressional_trades"].create_index([("ticker", ASCENDING), ("disclosureDate", DESCENDING)])

    db["earnings_dates"].create_index([("ticker", ASCENDING), ("earningsDate", DESCENDING)])
    db["earnings_dates"].create_index([("ticker", ASCENDING), ("earningsDate", ASCENDING)], unique=True)

    db["institutional_holders"].create_index([("ticker", ASCENDING), ("dateReported", DESCENDING)])

    db["quiver_gov_contracts"].create_index([("ticker", ASCENDING), ("Date", DESCENDING)])
    db["quiver_offexchange"].create_index([("ticker", ASCENDING), ("Date", DESCENDING)])

    logger.info("MongoDB indexes ensured")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _latest_date(db, collection: str, ticker_field: str, ticker: str, date_field: str) -> Optional[datetime]:
    """Return the most recent date stored for a ticker in a collection, or None."""
    doc = db[collection].find_one(
        {ticker_field: ticker},
        sort=[(date_field, DESCENDING)],
        projection={date_field: 1}
    )
    if doc:
        val = doc[date_field]
        if isinstance(val, str):
            return datetime.strptime(val[:10], "%Y-%m-%d")
        return val
    return None


def _today() -> date:
    return datetime.utcnow().date()


# ──────────────────────────────────────────────────────────────────────────────
# 1. PRICE HISTORY  (yfinance)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_price_history(db, ticker: str) -> pd.DataFrame:
    """
    First call : yf.download(period="max")  — full history, can be 20+ years.
    Daily delta: yf.download(start=last_stored_date + 1 day).

    Stores: open, high, low, close (adjusted), volume per date.
    Collection: price_history  { ticker, date, open, high, low, close, volume }
    """
    collection = db["price_history"]
    last_dt = _latest_date(db, "price_history", "ticker", ticker, "date")

    if last_dt is None:
        logger.info(f"{ticker}: price — first pull (max history)")
        df = yf.download(ticker, period="max", auto_adjust=True, progress=False, multi_level_index=False)
    else:
        start = (last_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        if last_dt.date() >= _today():
            logger.info(f"{ticker}: price — already current")
            return _load_price_history(db, ticker)
        logger.info(f"{ticker}: price — delta from {start}")
        df = yf.download(ticker, start=start, auto_adjust=True, progress=False, multi_level_index=False)

    if df.empty:
        logger.info(f"{ticker}: price — no new bars")
        return _load_price_history(db, ticker)

    # Flatten MultiIndex columns if present (happens with single ticker in some yf versions)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    ops = []
    for ts, row in df.iterrows():
        dt = ts.to_pydatetime().replace(tzinfo=None)
        doc = {
            "ticker": ticker,
            "date": dt,
            "open":   round(float(row["Open"]),   4),
            "high":   round(float(row["High"]),   4),
            "low":    round(float(row["Low"]),    4),
            "close":  round(float(row["Close"]),  4),
            "volume": int(row["Volume"]),
        }
        ops.append(UpdateOne(
            {"ticker": ticker, "date": dt},
            {"$set": doc},
            upsert=True
        ))

    if ops:
        result = collection.bulk_write(ops, ordered=False)
        logger.info(f"{ticker}: price — upserted {result.upserted_count} new, modified {result.modified_count}")

    return _load_price_history(db, ticker)


def _load_price_history(db, ticker: str) -> pd.DataFrame:
    docs = list(db["price_history"].find(
        {"ticker": ticker},
        sort=[("date", ASCENDING)],
        projection={"_id": 0, "ticker": 0}
    ))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs).set_index("date")
    df.index = pd.DatetimeIndex(df.index)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# 2. FINANCIAL STATEMENTS  (FMP)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_financial_statement(db, ticker: str, fmp, statement: str = "income", period: str = "quarter"):
    """
    statement : "income" | "balance" | "cashflow"
    period    : "quarter" | "annual"

    First call : fetches up to 40 periods (full available FMP history).
    Daily delta: fetches only the 2 most recent periods and inserts any that
                 aren't already stored (keyed on ticker + date).

    Each FMP endpoint costs 1 API call — call this sparingly.
    Collections: financials_income_quarter, financials_income_annual, etc.
    """
    endpoint_map = {
        "income":   "income-statement",
        "balance":  "balance-sheet-statement",
        "cashflow": "cash-flow-statement",
    }
    coll_name = f"financials_{statement}_{period}"
    collection = db[coll_name]

    last_dt = _latest_date(db, coll_name, "ticker", ticker, "date")

    # First pull: get deep history. Delta: check only last 2 periods.
    limit = 40 if last_dt is None else 2
    action = "first pull" if last_dt is None else f"delta check (last stored: {last_dt.date()})"
    logger.info(f"{ticker} {statement} {period}: {action}")

    endpoint = endpoint_map[statement]
    data = fmp.get(f"v3/{endpoint}/{ticker}", params={"period": period, "limit": limit})

    if not data:
        logger.warning(f"{ticker} {statement} {period}: No data from FMP")
        return

    new_docs = []
    for record in data:
        record_date = record.get("date")
        if not record_date:
            continue
        exists = collection.find_one({"ticker": ticker, "date": record_date})
        if not exists:
            record["ticker"] = ticker
            record["_fetchedAt"] = datetime.utcnow()
            new_docs.append(record)

    if new_docs:
        collection.insert_many(new_docs)
        logger.info(f"{ticker} {statement} {period}: Stored {len(new_docs)} new period(s)")
    else:
        logger.info(f"{ticker} {statement} {period}: Already up to date")


def fetch_all_financials(db, ticker: str, fmp):
    """Convenience: fetch income, balance, and cashflow for both quarter and annual."""
    for stmt in ("income", "balance", "cashflow"):
        for period in ("quarter", "annual"):
            fetch_financial_statement(db, ticker, fmp, stmt, period)


# ──────────────────────────────────────────────────────────────────────────────
# 3. KEY RATIOS & METRICS  (FMP)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_ratios(db, ticker: str, fmp, period: str = "quarter"):
    """
    Fetches P/E, EV/EBITDA, gross margin, FCF yield, debt/equity, ROE, ROA, etc.
    Same delta pattern: full history on first pull, 2 periods on subsequent runs.
    Collection: ratios_quarter / ratios_annual
    """
    coll_name = f"ratios_{period}"
    collection = db[coll_name]
    last_dt = _latest_date(db, coll_name, "ticker", ticker, "date")
    limit = 40 if last_dt is None else 2

    data = fmp.get(f"v3/ratios/{ticker}", params={"period": period, "limit": limit})
    if not data:
        return

    new_docs = [r for r in data if not collection.find_one({"ticker": ticker, "date": r.get("date")})]
    for r in new_docs:
        r["ticker"] = ticker
        r["_fetchedAt"] = datetime.utcnow()

    if new_docs:
        collection.insert_many(new_docs)
        logger.info(f"{ticker} ratios {period}: Stored {len(new_docs)} new period(s)")


# ──────────────────────────────────────────────────────────────────────────────
# 4. INSIDER TRANSACTIONS  (FMP)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_insider_transactions(db, ticker: str, fmp):
    """
    Keyed on (ticker, filingDate, transactionDate, reportingName, securitiesTransacted).
    First call: fetches 200 most recent transactions (FMP max per call).
    Daily delta: fetches with from=last_filing_date, skips duplicates via upsert key.

    Collection: insider_transactions
    """
    collection = db["insider_transactions"]
    last_dt = _latest_date(db, "insider_transactions", "ticker", ticker, "filingDate")

    params = {"symbol": ticker, "limit": 200}
    if last_dt:
        # FMP accepts 'from' as YYYY-MM-DD
        params["from"] = (last_dt - timedelta(days=1)).strftime("%Y-%m-%d")  # -1 day overlap for safety
        logger.info(f"{ticker} insiders: delta from {params['from']}")
    else:
        logger.info(f"{ticker} insiders: first pull")

    data = fmp.get("v4/insider-trading", params=params)
    if not data:
        return

    new_count = 0
    for record in data:
        record["ticker"] = ticker
        record["_fetchedAt"] = datetime.utcnow()
        # Deduplicate on the natural composite key
        key = {
            "ticker":               ticker,
            "filingDate":           record.get("filingDate"),
            "transactionDate":      record.get("transactionDate"),
            "reportingName":        record.get("reportingName"),
            "securitiesTransacted": record.get("securitiesTransacted"),
        }
        result = collection.update_one(key, {"$setOnInsert": record}, upsert=True)
        if result.upserted_id:
            new_count += 1

    logger.info(f"{ticker} insiders: {new_count} new transactions stored")


# ──────────────────────────────────────────────────────────────────────────────
# 5. EARNINGS DATES  (yfinance)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_earnings_dates(db, ticker: str):
    """
    Fetches the last 20 quarters of earnings dates + upcoming.
    Keyed on (ticker, earningsDate) — safe to re-run, new rows upserted.
    Good to refresh daily so upcoming estimates stay current.

    Collection: earnings_dates
    """
    collection = db["earnings_dates"]

    try:
        t = yf.Ticker(ticker)
        df = t.get_earnings_dates(limit=20)
    except Exception as e:
        logger.warning(f"{ticker} earnings dates: {e}")
        return

    if df is None or df.empty:
        return

    ops = []
    for ts, row in df.iterrows():
        dt = ts.to_pydatetime().replace(tzinfo=None)
        doc = {
            "ticker":        ticker,
            "earningsDate":  dt,
            "epsEstimate":   row.get("EPS Estimate"),
            "reportedEPS":   row.get("Reported EPS"),
            "surprisePct":   row.get("Surprise(%)"),
            "_fetchedAt":    datetime.utcnow(),
        }
        ops.append(UpdateOne(
            {"ticker": ticker, "earningsDate": dt},
            {"$set": doc},
            upsert=True
        ))

    if ops:
        result = collection.bulk_write(ops, ordered=False)
        logger.info(f"{ticker} earnings dates: {result.upserted_count} new, {result.modified_count} updated")


# ──────────────────────────────────────────────────────────────────────────────
# 6. INSTITUTIONAL HOLDERS  (yfinance)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_institutional_holders(db, ticker: str):
    """
    Top institutional holders snapshot. These change quarterly — safe to
    overwrite/upsert on each run since we key on (ticker, holder, dateReported).

    Collection: institutional_holders
    """
    collection = db["institutional_holders"]

    try:
        t = yf.Ticker(ticker)
        df = t.get_institutional_holders()
    except Exception as e:
        logger.warning(f"{ticker} institutional holders: {e}")
        return

    if df is None or df.empty:
        return

    ops = []
    for _, row in df.iterrows():
        date_reported = row.get("Date Reported") or row.get("dateReported")
        if hasattr(date_reported, "to_pydatetime"):
            date_reported = date_reported.to_pydatetime().replace(tzinfo=None)
        doc = {
            "ticker":       ticker,
            "holder":       row.get("Holder"),
            "shares":       row.get("Shares"),
            "dateReported": date_reported,
            "pctHeld":      row.get("% Out"),
            "value":        row.get("Value"),
            "_fetchedAt":   datetime.utcnow(),
        }
        ops.append(UpdateOne(
            {"ticker": ticker, "holder": doc["holder"], "dateReported": doc["dateReported"]},
            {"$set": doc},
            upsert=True
        ))

    if ops:
        result = collection.bulk_write(ops, ordered=False)
        logger.info(f"{ticker} institutional holders: {result.upserted_count} new, {result.modified_count} updated")


# ──────────────────────────────────────────────────────────────────────────────
# 7. FRED MACRO DATA
# ──────────────────────────────────────────────────────────────────────────────

FRED_SERIES = {
    "CPIAUCSL": "CPI all items urban consumers (monthly)",
    "PCEPI":    "PCE price index (monthly)",
    "FEDFUNDS": "Federal funds effective rate (monthly)",
    "UNRATE":   "Civilian unemployment rate (monthly)",
    "GDP":      "Gross domestic product (quarterly)",
    "GDPC1":    "Real GDP inflation-adjusted (quarterly)",
    "DGS10":    "10-year treasury yield (daily)",
    "DGS2":     "2-year treasury yield (daily)",
    "T10Y2Y":   "10Y minus 2Y yield spread (daily)",
    "T10Y3M":   "10Y minus 3M yield spread (daily)",
    "VIXCLS":   "CBOE VIX volatility index (daily)",
    "UMCSENT":  "U Michigan consumer sentiment (monthly)",
    "INDPRO":   "Industrial production index (monthly)",
    "RETAILSMNSA": "Retail sales not seasonally adjusted (monthly)",
}


def fetch_fred_series(db, series_id: str, fred_client):
    """
    First call : fetches full available history for the series (can go back decades).
    Daily delta: fetches only observations after the last stored date.

    Collection: macro_fred  { series_id, date, value }
    """
    collection = db["macro_fred"]
    last_dt = _latest_date(db, "macro_fred", "series_id", series_id, "date")

    kwargs = {}
    if last_dt:
        start_str = (last_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        kwargs["observation_start"] = start_str
        logger.info(f"FRED {series_id}: delta from {start_str}")
    else:
        logger.info(f"FRED {series_id}: first pull (full history)")

    try:
        series = fred_client.get_series(series_id, **kwargs)
    except Exception as e:
        logger.warning(f"FRED {series_id}: fetch failed — {e}")
        return

    if series is None or series.empty:
        logger.info(f"FRED {series_id}: no new observations")
        return

    ops = []
    for ts, value in series.items():
        if pd.isna(value):
            continue
        dt = ts.to_pydatetime().replace(tzinfo=None)
        doc = {"series_id": series_id, "date": dt, "value": float(value)}
        ops.append(UpdateOne(
            {"series_id": series_id, "date": dt},
            {"$set": doc},
            upsert=True
        ))

    if ops:
        result = collection.bulk_write(ops, ordered=False)
        logger.info(f"FRED {series_id}: {result.upserted_count} new observations stored")


def fetch_all_fred(db, fred_client):
    """Refresh all configured FRED series."""
    for series_id in FRED_SERIES:
        fetch_fred_series(db, series_id, fred_client)


# ──────────────────────────────────────────────────────────────────────────────
# 8. MARKET BREADTH — NYMO / NAMO  (yfinance)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_market_breadth(db):
    """
    Fetches McClellan Oscillator for NYSE ($NYMO) and NASDAQ ($NAMO).
    Uses the same price_history collection and delta logic as equity prices.
    """
    for breadth_ticker in ["^NYMO", "^NAMO"]:
        fetch_price_history(db, breadth_ticker)


# ──────────────────────────────────────────────────────────────────────────────
# 9. CONGRESSIONAL TRADES  (Quiver Quantitative)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_congressional_trades(db, ticker: str, quiver_client):
    """
    Delta: only stores trades with a disclosureDate newer than the latest stored.
    Collection: congressional_trades  { ticker, disclosureDate, tradeDate, politician, ... }
    """
    collection = db["congressional_trades"]
    last_dt = _latest_date(db, "congressional_trades", "ticker", ticker, "disclosureDate")

    try:
        df = quiver_client.congress_trading(ticker)
    except Exception as e:
        logger.warning(f"{ticker} congress trades: {e}")
        return

    if df is None or df.empty:
        return

    # Normalize column name capitalisation
    date_col = next((c for c in df.columns if c.lower() == "disclosuredate"), None)
    if not date_col:
        logger.warning(f"{ticker} congress trades: no disclosureDate column found")
        return

    df[date_col] = pd.to_datetime(df[date_col])

    if last_dt:
        df = df[df[date_col] > pd.Timestamp(last_dt)]

    if df.empty:
        logger.info(f"{ticker} congress trades: up to date")
        return

    records = df.to_dict("records")
    for r in records:
        r["ticker"] = ticker
        r["_fetchedAt"] = datetime.utcnow()
        # Convert Timestamps to datetime for MongoDB
        for k, v in r.items():
            if isinstance(v, pd.Timestamp):
                r[k] = v.to_pydatetime()

    collection.insert_many(records)
    logger.info(f"{ticker} congress trades: stored {len(records)} new trades")


# ──────────────────────────────────────────────────────────────────────────────
# 10. GOVERNMENT CONTRACTS  (Quiver Quantitative)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_gov_contracts(db, ticker: str, quiver_client):
    """
    Delta by contract Date field.
    Collection: quiver_gov_contracts
    """
    collection = db["quiver_gov_contracts"]
    last_dt = _latest_date(db, "quiver_gov_contracts", "ticker", ticker, "Date")

    try:
        df = quiver_client.gov_contracts(ticker)
    except Exception as e:
        logger.warning(f"{ticker} gov contracts: {e}")
        return

    if df is None or df.empty:
        return

    df["Date"] = pd.to_datetime(df["Date"])
    if last_dt:
        df = df[df["Date"] > pd.Timestamp(last_dt)]

    if df.empty:
        logger.info(f"{ticker} gov contracts: up to date")
        return

    records = df.to_dict("records")
    for r in records:
        r["ticker"] = ticker
        r["_fetchedAt"] = datetime.utcnow()
        for k, v in r.items():
            if isinstance(v, pd.Timestamp):
                r[k] = v.to_pydatetime()

    collection.insert_many(records)
    logger.info(f"{ticker} gov contracts: stored {len(records)} new contracts")


# ──────────────────────────────────────────────────────────────────────────────
# 11. OFF-EXCHANGE / DARK POOL VOLUME  (Quiver Quantitative)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_offexchange(db, ticker: str, quiver_client):
    """
    Daily short volume and off-exchange activity.
    Delta by Date field.
    Collection: quiver_offexchange
    """
    collection = db["quiver_offexchange"]
    last_dt = _latest_date(db, "quiver_offexchange", "ticker", ticker, "Date")

    try:
        df = quiver_client.offexchange(ticker)
    except Exception as e:
        logger.warning(f"{ticker} off-exchange: {e}")
        return

    if df is None or df.empty:
        return

    df["Date"] = pd.to_datetime(df["Date"])
    if last_dt:
        df = df[df["Date"] > pd.Timestamp(last_dt)]

    if df.empty:
        logger.info(f"{ticker} off-exchange: up to date")
        return

    records = df.to_dict("records")
    for r in records:
        r["ticker"] = ticker
        r["_fetchedAt"] = datetime.utcnow()
        for k, v in r.items():
            if isinstance(v, pd.Timestamp):
                r[k] = v.to_pydatetime()

    collection.insert_many(records)
    logger.info(f"{ticker} off-exchange: stored {len(records)} new rows")


# ──────────────────────────────────────────────────────────────────────────────
# CONVENIENCE — refresh one ticker across all sources
# ──────────────────────────────────────────────────────────────────────────────

def refresh_ticker(
    db,
    ticker: str,
    fmp=None,
    quiver_client=None,
):
    """
    Run all data fetchers for a single ticker.
    Pass None for clients you haven't configured yet — those fetchers are skipped.

    Price history and earnings dates run unconditionally (yfinance, no key needed).
    FMP fetchers run only if fmp client is provided.
    Quiver fetchers run only if quiver_client is provided.

    Usage:
        db = get_db()
        ensure_indexes(db)
        fmp = FMPClient(api_key="YOUR_KEY")
        quiver = quiverquant.quiver("YOUR_TOKEN")
        refresh_ticker(db, "AAPL", fmp=fmp, quiver_client=quiver)
    """
    logger.info(f"=== Refreshing {ticker} ===")

    # Always free, no key required
    fetch_price_history(db, ticker)
    fetch_earnings_dates(db, ticker)
    fetch_institutional_holders(db, ticker)

    # FMP (costs API calls)
    if fmp is not None:
        fetch_all_financials(db, ticker, fmp)
        fetch_ratios(db, ticker, fmp, period="quarter")
        fetch_ratios(db, ticker, fmp, period="annual")
        fetch_insider_transactions(db, ticker, fmp)

    # Quiver ($30/month)
    if quiver_client is not None:
        fetch_congressional_trades(db, ticker, quiver_client)
        fetch_gov_contracts(db, ticker, quiver_client)
        fetch_offexchange(db, ticker, quiver_client)

    logger.info(f"=== {ticker} done ===")


# ──────────────────────────────────────────────────────────────────────────────
# Minimal FMP HTTP client
# ──────────────────────────────────────────────────────────────────────────────

class FMPClient:
    """
    Thin wrapper around FMP's REST API.
    Handles auth and JSON parsing. Pass this to the fetch_* functions above.
    """
    BASE = "https://financialmodelingprep.com/api"

    def __init__(self, api_key: str):
        self.api_key = api_key
        try:
            import requests as _requests
            self._session = _requests.Session()
        except ImportError:
            raise ImportError("pip install requests")

    def get(self, path: str, params: dict = None) -> list:
        """GET {BASE}/{path}?apikey=...&{params} → list of dicts"""
        url = f"{self.BASE}/{path}"
        p = {"apikey": self.api_key}
        if params:
            p.update(params)
        try:
            r = self._session.get(url, params=p, timeout=15)
            r.raise_for_status()
            data = r.json()
            # FMP returns either a list or {"Error Message": "..."}
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "Error Message" in data:
                logger.warning(f"FMP error for {path}: {data['Error Message']}")
                return []
            return data if data else []
        except Exception as e:
            logger.error(f"FMP request failed ({path}): {e}")
            return []


# ──────────────────────────────────────────────────────────────────────────────
# Example usage / quick test
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    db = get_db()
    ensure_indexes(db)

    fmp = FMPClient(api_key=os.environ["FMP_API_KEY"])

    # Optional clients — comment out if you don't have keys yet
    try:
        import quiverquant
        quiver = quiverquant.quiver(os.environ["QUIVER_API_KEY"])
    except Exception:
        quiver = None

    # FRED — refresh all macro series
    try:
        import fredapi
        fred = fredapi.Fred(api_key=os.environ["FRED_API_KEY"])
        fetch_all_fred(db, fred)
    except Exception as e:
        logger.warning(f"FRED skipped: {e}")

    # Market breadth
    fetch_market_breadth(db)

    # Example tickers
    watchlist = ["AAPL", "NVDA", "MSFT", "TSLA"]
    for ticker in watchlist:
        refresh_ticker(db, ticker, fmp=fmp, quiver_client=quiver)
