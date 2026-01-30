import yfinance as yf
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
import pandas as pd
from sqlalchemy.orm import Session
from ..models import WatchedStock, PriceHistory, FinancialStatement, NewsArticle, EarningsData
from ..utils.delta_tracker import DeltaTracker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class YahooFinanceService:
    def __init__(self, db: Session):
        self.db = db

    def get_stock_info(self, ticker: str) -> dict:
        """Fetch basic stock info from Yahoo Finance."""
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "company_name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

    def sync_prices(self, stock: WatchedStock) -> int:
        """Sync price history with delta tracking. Returns number of new records."""
        tracker = DeltaTracker(self.db, stock.id)
        yf_ticker = yf.Ticker(stock.ticker)

        start_date = tracker.get_price_fetch_start_date()

        if start_date:
            if start_date > date.today():
                tracker.update_sync_metadata("price", "success", tracker.get_last_price_date())
                return 0
            history = yf_ticker.history(start=start_date.isoformat())
        else:
            history = yf_ticker.history(period="5y")

        if history.empty:
            tracker.update_sync_metadata("price", "success", tracker.get_last_price_date())
            return 0

        # Extract all dates from history to check in bulk (avoids N+1 queries)
        history_dates = [idx.date() if hasattr(idx, "date") else idx for idx in history.index]

        # Fetch all existing dates in a single query
        existing_dates = set(
            r[0] for r in self.db.query(PriceHistory.date)
            .filter(
                PriceHistory.stock_id == stock.id,
                PriceHistory.date.in_(history_dates),
            )
            .all()
        )

        count = 0
        last_date = None
        for idx, row in history.iterrows():
            price_date = idx.date() if hasattr(idx, "date") else idx
            last_date = price_date

            if price_date not in existing_dates:
                price_record = PriceHistory(
                    stock_id=stock.id,
                    date=price_date,
                    open=Decimal(str(row["Open"])) if pd.notna(row["Open"]) else None,
                    high=Decimal(str(row["High"])) if pd.notna(row["High"]) else None,
                    low=Decimal(str(row["Low"])) if pd.notna(row["Low"]) else None,
                    close=Decimal(str(row["Close"])) if pd.notna(row["Close"]) else None,
                    adj_close=Decimal(str(row.get("Adj Close", row["Close"]))) if pd.notna(row.get("Adj Close", row["Close"])) else None,
                    volume=int(row["Volume"]) if pd.notna(row["Volume"]) else None,
                )
                self.db.add(price_record)
                count += 1

        self.db.commit()
        tracker.update_sync_metadata("price", "success", last_date)
        return count

    def sync_financials(self, stock: WatchedStock) -> int:
        """Sync financial statements with delta tracking."""
        tracker = DeltaTracker(self.db, stock.id)
        yf_ticker = yf.Ticker(stock.ticker)

        count = 0

        statement_map = {
            ("income", "quarterly"): yf_ticker.quarterly_income_stmt,
            ("income", "annual"): yf_ticker.income_stmt,
            ("balance", "quarterly"): yf_ticker.quarterly_balance_sheet,
            ("balance", "annual"): yf_ticker.balance_sheet,
            ("cashflow", "quarterly"): yf_ticker.quarterly_cashflow,
            ("cashflow", "annual"): yf_ticker.cashflow,
        }

        for (stmt_type, period_type), df in statement_map.items():
            if df is None or df.empty:
                continue

            existing_periods = tracker.get_existing_financial_periods(stmt_type, period_type)

            for col in df.columns:
                period_date = col.date() if hasattr(col, "date") else col
                if period_date in existing_periods:
                    continue

                data = df[col].dropna().to_dict()
                data = {k: float(v) if isinstance(v, (int, float)) else str(v) for k, v in data.items()}

                statement = FinancialStatement(
                    stock_id=stock.id,
                    period_end=period_date,
                    period_type=period_type,
                    statement_type=stmt_type,
                    data=data,
                )
                self.db.add(statement)
                count += 1

        self.db.commit()
        tracker.update_sync_metadata("financials", "success")
        return count

    def sync_news(self, stock: WatchedStock) -> list[NewsArticle]:
        """Sync news articles with delta tracking. Returns new articles for sentiment analysis."""
        tracker = DeltaTracker(self.db, stock.id)
        yf_ticker = yf.Ticker(stock.ticker)

        existing_ids = tracker.get_existing_article_ids()

        # yfinance news API - try to get news
        try:
            news_data = yf_ticker.news
            # Handle different yfinance versions - news might be a list or None
            if news_data is None:
                news = []
            elif isinstance(news_data, list):
                news = news_data
            else:
                news = []
        except Exception as e:
            logger.error(f"Error fetching news for {stock.ticker}: {e}")
            news = []

        logger.info(f"Fetched {len(news)} news items for {stock.ticker}")

        new_articles = []
        for article in news:
            # yfinance returns news with nested 'content' structure
            content = article.get("content", {})

            # Get article ID from top level or content
            article_id = article.get("id") or content.get("id") or ""

            if not article_id or article_id in existing_ids:
                continue

            # Get published time from content.pubDate (ISO format string)
            published_at = None
            pub_date = content.get("pubDate")
            if pub_date:
                try:
                    published_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                except Exception:
                    pass

            # Get title from content
            title = content.get("title") or "No title"

            # Get link from content.canonicalUrl.url or content.clickThroughUrl.url
            link = None
            canonical_url = content.get("canonicalUrl", {})
            if canonical_url:
                link = canonical_url.get("url")
            if not link:
                click_url = content.get("clickThroughUrl", {})
                if click_url:
                    link = click_url.get("url")

            # Get publisher from content.provider.displayName
            publisher = None
            provider = content.get("provider", {})
            if provider:
                publisher = provider.get("displayName")

            news_record = NewsArticle(
                stock_id=stock.id,
                article_id=article_id,
                title=title,
                link=link,
                publisher=publisher,
                published_at=published_at,
            )
            self.db.add(news_record)
            new_articles.append(news_record)

        self.db.commit()
        tracker.update_sync_metadata("news", "success")
        logger.info(f"Saved {len(new_articles)} new articles for {stock.ticker}")
        return new_articles

    def get_valuation_metrics(self, ticker: str) -> dict:
        """Get valuation metrics from ticker.info."""
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info

        return {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "pb_ratio": info.get("priceToBook"),
            "peg_ratio": info.get("pegRatio"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "current_ratio": info.get("currentRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
        }

    def _dataframe_to_dict(self, df: pd.DataFrame) -> dict:
        """Convert DataFrame to JSON-serializable dict."""
        if df is None or df.empty:
            return {}

        # Reset index to make it a column if it's a DatetimeIndex or similar
        df_reset = df.reset_index()

        # Convert datetime columns to ISO format strings
        for col in df_reset.columns:
            if pd.api.types.is_datetime64_any_dtype(df_reset[col]):
                df_reset[col] = df_reset[col].dt.strftime('%Y-%m-%dT%H:%M:%S')

        # Use pandas native to_dict which is optimized in C
        # Replace NaN/NaT with None for JSON compatibility
        result = df_reset.where(pd.notnull(df_reset), None).to_dict(orient='list')

        # Ensure column names are strings
        return {str(k): v for k, v in result.items()}

    def sync_earnings(self, stock: WatchedStock) -> int:
        """Sync earnings-related data. Returns number of data types synced."""
        tracker = DeltaTracker(self.db, stock.id)
        yf_ticker = yf.Ticker(stock.ticker)

        count = 0

        # Define available earnings data sources (excluding deprecated ones)
        # Note: ticker.earnings, ticker.quarterly_earnings, and ticker.earnings_trend are deprecated/unavailable
        earnings_sources = {
            "earnings_dates": lambda: yf_ticker.earnings_dates,
            "earnings_estimate": lambda: yf_ticker.earnings_estimate,
            "revenue_estimate": lambda: yf_ticker.revenue_estimate,
            "growth_estimates": lambda: yf_ticker.growth_estimates,
            "eps_revisions": lambda: yf_ticker.eps_revisions,
        }

        for data_type, fetch_func in earnings_sources.items():
            try:
                df = fetch_func()
                if df is None or (hasattr(df, 'empty') and df.empty):
                    logger.info(f"No {data_type} data for {stock.ticker}")
                    continue

                # Convert DataFrame to dict
                if isinstance(df, pd.DataFrame):
                    data = self._dataframe_to_dict(df)
                else:
                    data = {"value": str(df)}

                if not data:
                    continue

                logger.info(f"Fetched {data_type} for {stock.ticker}: {list(data.keys())}")

                # Upsert - check if exists and update, otherwise insert
                existing = (
                    self.db.query(EarningsData)
                    .filter(
                        EarningsData.stock_id == stock.id,
                        EarningsData.data_type == data_type,
                    )
                    .first()
                )

                if existing:
                    existing.data = data
                    existing.fetched_at = datetime.now()
                else:
                    earnings_record = EarningsData(
                        stock_id=stock.id,
                        data_type=data_type,
                        data=data,
                    )
                    self.db.add(earnings_record)

                count += 1

            except Exception as e:
                logger.warning(f"Failed to fetch {data_type} for {stock.ticker}: {e}")
                continue

        self.db.commit()
        tracker.update_sync_metadata("earnings", "success")
        logger.info(f"Synced {count} earnings data types for {stock.ticker}")
        return count
