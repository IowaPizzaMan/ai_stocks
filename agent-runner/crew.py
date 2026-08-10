"""Per-ticker analysis pipeline: prefetch → deterministic skills → LLM agents.
Spec: specs/component-specs/agent-runner/crew.md

Full Phase 5 roster: Technical, Fundamental, Macro, Insider, Institutional,
Sentiment, Recommender, then PortfolioStrategist synthesizing everything.
Agents call Ollama directly with structured output (see llm.py) — no CrewAI
tool-calling.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

from agents import (
    fundamental_analyst,
    insider_analyst,
    institutional_analyst,
    macro_analyst,
    portfolio_strategist,
    recommender_agent,
    sentiment_analyst,
    technical_analyst,
)
from logging_config import get_logger
from skills import accumulation, gap_analysis, market_flow, the_strat
from tools import breadth as breadth_tool
from tools import financials as financials_tool
from tools import insider as insider_tool
from tools import institutional as institutional_tool
from tools import macro as macro_tool
from tools import price as price_tool
from tools import sentiment as sentiment_tool
from tools import superinvestor as superinvestor_tool
from tools.db import TICKER_INDEX, get_db

logger = get_logger(__name__)


class TickerDelistedError(Exception):
    """Raised when a ticker fails the yfinance existence check AND has no financials."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"{ticker}: no price or financials data available — likely delisted or ticker changed")


def _earnings_dates(earnings: dict) -> list:
    dates = []
    for record in earnings.get("earnings_dates") or []:
        for key in ("Earnings Date", "Date", "date"):
            if key in record and record[key] is not None:
                try:
                    dates.append(pd.to_datetime(record[key]).date())
                except (ValueError, TypeError):
                    pass
                break
    return dates


def _latest_price_date(daily: list[dict]) -> str | None:
    """Date of the most recent daily bar — chronological (oldest→newest), so last."""
    if not daily:
        return None
    date = daily[-1].get("Date") or daily[-1].get("date")
    return str(date)[:10] if date is not None else None


def _latest_statement_date(financials: dict) -> str | None:
    """Most recent reported statement date — FMP arrays are newest-first."""
    for key in ("income_quarterly", "income_annual"):
        rows = financials.get(key) or []
        if rows and rows[0].get("date"):
            return str(rows[0]["date"])[:10]
    return None


def _latest_dated(items: list[dict], key: str = "date") -> str | None:
    """Max date across a list of dicts — insider transactions and news aren't
    guaranteed sorted, so don't assume order."""
    dates = [item[key] for item in items if item.get(key)]
    return max(dates) if dates else None


def _price_summary(daily: list[dict]) -> dict:
    df = pd.DataFrame(daily)
    if df.empty or "Close" not in df:
        return {}
    closes, lows, highs = df["Close"], df["Low"], df["High"]
    return {
        "last_close": round(float(closes.iloc[-1]), 2),
        "change_20d_pct": round(float(closes.iloc[-1] / closes.iloc[-21] - 1) * 100, 1) if len(closes) > 21 else None,
        "high_20d": round(float(highs.tail(20).max()), 2),
        "low_20d": round(float(lows.tail(20).min()), 2),
        "high_60d": round(float(highs.tail(60).max()), 2),
        "low_60d": round(float(lows.tail(60).min()), 2),
    }


class Crew:
    def __init__(self, db=None, client=None):
        self.db = db if db is not None else get_db()
        self.client = client  # None → llm.py default Ollama client
        # fetchers as attributes so tests can swap them out
        self.is_ticker_valid = price_tool.is_ticker_valid
        self.get_price_history = price_tool.get_price_history
        self.get_technical_indicators = price_tool.get_technical_indicators
        self.get_financials = financials_tool.get_financials
        self.get_earnings_data = financials_tool.get_earnings_data
        self.get_market_breadth = breadth_tool.get_market_breadth
        self.get_macro_data = macro_tool.get_macro_data
        self.get_yield_curve_status = macro_tool.get_yield_curve_status
        self.get_insider_activity = insider_tool.get_insider_activity
        self.get_institutional_holdings = institutional_tool.get_institutional_holdings
        self.get_superinvestor_activity = superinvestor_tool.get_superinvestor_activity
        self.get_earnings_sentiment = sentiment_tool.get_earnings_sentiment

    def _prefetch(self, ticker: str, parallel: bool) -> dict:
        jobs = {
            "price": lambda: self.get_price_history(ticker),
            "indicators": lambda: self.get_technical_indicators(ticker),
            "financials": lambda: self.get_financials(ticker, db=self.db),
            "earnings": lambda: self.get_earnings_data(ticker),
            "breadth": lambda: self.get_market_breadth(db=self.db),
            "macro": lambda: self.get_macro_data(db=self.db),
            "yield_curve": lambda: self.get_yield_curve_status(db=self.db),
            "insider": lambda: self.get_insider_activity(ticker),
            "institutional": lambda: self.get_institutional_holdings(ticker, db=self.db),
            "sentiment": lambda: self.get_earnings_sentiment(ticker),
        }
        if parallel:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {key: pool.submit(fn) for key, fn in jobs.items()}
                return {key: f.result(timeout=120) for key, f in futures.items()}
        return {key: fn() for key, fn in jobs.items()}

    def run(self, ticker: str, parallel_prefetch: bool = False) -> dict:
        ticker = ticker.upper()

        # 0. cheap existence check before burning LLM time; financials get one
        # chance to disagree so a single flaky source can't delist a ticker
        if not self.is_ticker_valid(ticker):
            fin = self.get_financials(ticker, db=self.db)
            if not fin or not any(fin.get(k) for k in ("income_annual", "income_quarterly")):
                raise TickerDelistedError(ticker)
            logger.info("%s: yfinance check failed but financials resolve — proceeding", ticker)

        # 1. data prefetch
        data = self._prefetch(ticker, parallel_prefetch)
        price_history = data["price"]

        # 2. deterministic skills
        strat_out = the_strat.run(ticker, price_history)
        gap_out = gap_analysis.run(
            ticker, price_history,
            earnings_dates=_earnings_dates(data["earnings"]),
            nymo=data["breadth"]["nymo"]["current"],
        )
        peg_score = gap_out["peg"]["peg_score"] if gap_out.get("peg") else None
        accumulation_out = accumulation.run(ticker, price_history, gap_score=peg_score)
        flow_out = market_flow.run(ticker, {"breadth": data["breadth"], "gap": gap_out})

        # superinvestor is best-effort (Playwright + scrape) — never sinks a run
        try:
            superinvestor = self.get_superinvestor_activity(ticker, db=self.db, client=self.client)
        except Exception as exc:
            logger.info("superinvestor unavailable for %s: %s", ticker, exc)
            superinvestor = {"moves": [], "available": False, "note": str(exc)}

        record = self.db[TICKER_INDEX].find_one({"ticker": ticker}) or {}

        # 3. LLM agents (sequential; each one structured-output call)
        technical = technical_analyst.run(ticker, {
            "strat": strat_out,
            "accumulation": accumulation_out,
            "gap": gap_out,
            "indicators": data["indicators"],
            "price_summary": _price_summary(price_history["daily"]),
        }, client=self.client)
        technical["as_of"] = _latest_price_date(price_history["daily"])

        fundamental = fundamental_analyst.run(ticker, {
            "financials": data["financials"],
            "earnings": data["earnings"],
        }, client=self.client)
        fundamental["as_of"] = _latest_statement_date(data["financials"] or {})

        macro = macro_analyst.run(ticker, {
            "macro": data["macro"],
            "yield_curve": data["yield_curve"],
            "sector": record.get("sector"),
        }, client=self.client, db=self.db)

        insider = insider_analyst.run(ticker, {"insider": data["insider"]}, client=self.client)
        insider["as_of"] = _latest_dated((data["insider"] or {}).get("transactions", []))

        institutional = institutional_analyst.run(ticker, {
            "institutional": data["institutional"],
            "superinvestor": superinvestor,
        }, client=self.client)
        institutional["as_of"] = (data["institutional"] or {}).get("as_of")

        sentiment = sentiment_analyst.run(ticker, {"sentiment": data["sentiment"]},
                                          client=self.client)
        sentiment["as_of"] = _latest_dated((data["sentiment"] or {}).get("news", []))

        recommendation = recommender_agent.run(ticker, {
            "market_flow": flow_out,
            "breadth": data["breadth"],
            "gap": gap_out,
        }, client=self.client)

        sub_reports = {
            "technical": technical,
            "fundamental": fundamental,
            "macro": macro,
            "insider": insider,
            "institutional": institutional,
            "sentiment": sentiment,
            "recommendation": recommendation,
        }

        recent_lows = [float(r["Low"]) for r in price_history["daily"][-3:] if pd.notna(r.get("Low"))]
        synthesis = portfolio_strategist.run(ticker, sub_reports, recent_lows=recent_lows,
                                             client=self.client)

        # 4. final analyses document — the two recent_* flags ride top-level
        # (like sector/signal) so the feed projection serves them to the cards
        return {
            "ticker": ticker,
            "timestamp": datetime.now(timezone.utc),
            **synthesis,
            "recent_institutional_activity":
                institutional_tool.recent_activity_direction(data["institutional"] or {}),
            "recent_insider_summary": (data["insider"] or {}).get("recent_summary"),
            "sub_reports": sub_reports,
        }


def run_crew(ticker: str, parallel_prefetch: bool = False) -> dict:
    """Module-level convenience wrapper used by scripts/tests."""
    return Crew().run(ticker, parallel_prefetch=parallel_prefetch)
