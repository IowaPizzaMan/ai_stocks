"""
Benchmarks for backend services.
Run with: python -m pytest benchmarks/ --benchmark-only -v
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create test database base that doesn't depend on config
from sqlalchemy.orm import declarative_base

TestBase = declarative_base()

# Re-define models for testing to avoid config dependency
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, BigInteger, ForeignKey, Text, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class TestWatchedStock(TestBase):
    __tablename__ = "watched_stocks"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    company_name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)


class TestPriceHistory(TestBase):
    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4))
    adj_close = Column(Numeric(12, 4))
    volume = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uix_stock_date"),)


class TestFinancialStatement(TestBase):
    __tablename__ = "financial_statements"
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    period_end = Column(Date, nullable=False)
    period_type = Column(String(20))
    statement_type = Column(String(20))
    data = Column(JSON)


class TestNewsArticle(TestBase):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    article_id = Column(String(255), unique=True, index=True)
    title = Column(Text, nullable=False)
    link = Column(Text)
    publisher = Column(String(255))
    published_at = Column(DateTime(timezone=True))
    sentiment = Column(String(20))
    sentiment_score = Column(Numeric(5, 4))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class TestSyncMetadata(TestBase):
    __tablename__ = "sync_metadata"
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    data_type = Column(String(50))
    last_sync_at = Column(DateTime(timezone=True))
    last_data_date = Column(Date)
    sync_status = Column(String(20))
    __table_args__ = (UniqueConstraint("stock_id", "data_type", name="uix_stock_data_type"),)


@pytest.fixture
def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def stock_with_data(db_session):
    """Create a stock with sample price history data."""
    stock = TestWatchedStock(
        ticker="AAPL",
        company_name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics"
    )
    db_session.add(stock)
    db_session.commit()

    # Add 5 years of price history (approx 1260 trading days)
    base_date = date.today() - timedelta(days=1260)
    for i in range(1260):
        current_date = base_date + timedelta(days=i)
        # Skip weekends
        if current_date.weekday() >= 5:
            continue
        price = TestPriceHistory(
            stock_id=stock.id,
            date=current_date,
            open=Decimal("150.00") + Decimal(str(i * 0.01)),
            high=Decimal("155.00") + Decimal(str(i * 0.01)),
            low=Decimal("145.00") + Decimal(str(i * 0.01)),
            close=Decimal("152.00") + Decimal(str(i * 0.01)),
            adj_close=Decimal("152.00") + Decimal(str(i * 0.01)),
            volume=1000000 + i * 1000
        )
        db_session.add(price)

    db_session.commit()
    return stock


@pytest.fixture
def stock_with_news(db_session, stock_with_data):
    """Add news articles to the stock."""
    for i in range(1000):
        article = TestNewsArticle(
            stock_id=stock_with_data.id,
            article_id=f"article_{i}",
            title=f"News article {i} about Apple",
            link=f"https://example.com/article/{i}",
            publisher="Test Publisher",
            published_at=datetime.now() - timedelta(days=i)
        )
        db_session.add(article)
    db_session.commit()
    return stock_with_data


# ============ Delta Tracker Benchmarks ============

def benchmark_get_last_price_date(db_session, stock_with_data):
    """Benchmark getting the last price date - involves ORDER BY DESC query."""
    from sqlalchemy import desc

    result = (
        db_session.query(TestPriceHistory.date)
        .filter(TestPriceHistory.stock_id == stock_with_data.id)
        .order_by(desc(TestPriceHistory.date))
        .first()
    )
    return result[0] if result else None


def test_get_last_price_date(benchmark, db_session, stock_with_data):
    """Benchmark: Query last price date from ~900 records."""
    result = benchmark(benchmark_get_last_price_date, db_session, stock_with_data)
    assert result is not None


def benchmark_get_existing_article_ids(db_session, stock_with_news):
    """Benchmark getting all existing article IDs."""
    results = db_session.query(TestNewsArticle.article_id).all()
    return {r[0] for r in results if r[0]}


def test_get_existing_article_ids(benchmark, db_session, stock_with_news):
    """Benchmark: Fetch all 1000 article IDs into a set."""
    result = benchmark(benchmark_get_existing_article_ids, db_session, stock_with_news)
    assert len(result) == 1000


def benchmark_get_existing_financial_periods(db_session, stock_with_data):
    """Benchmark getting existing financial periods."""
    # First add some financial statements
    for i in range(40):  # 10 years of quarterly data
        stmt = TestFinancialStatement(
            stock_id=stock_with_data.id,
            period_end=date.today() - timedelta(days=90 * i),
            period_type="quarterly",
            statement_type="income",
            data={"revenue": 1000000 * i}
        )
        db_session.add(stmt)
    db_session.commit()

    results = (
        db_session.query(TestFinancialStatement.period_end)
        .filter(
            TestFinancialStatement.stock_id == stock_with_data.id,
            TestFinancialStatement.statement_type == "income",
            TestFinancialStatement.period_type == "quarterly",
        )
        .all()
    )
    return {r[0] for r in results}


def test_get_existing_financial_periods(benchmark, db_session, stock_with_data):
    """Benchmark: Fetch financial period dates."""
    result = benchmark(benchmark_get_existing_financial_periods, db_session, stock_with_data)
    assert len(result) > 0


# ============ Price Sync Benchmarks ============

def benchmark_check_existing_price(db_session, stock_with_data):
    """Benchmark checking if a price record exists - N+1 query pattern."""
    # This simulates the per-row check in sync_prices
    target_date = date.today() - timedelta(days=100)
    existing = (
        db_session.query(TestPriceHistory)
        .filter(
            TestPriceHistory.stock_id == stock_with_data.id,
            TestPriceHistory.date == target_date,
        )
        .first()
    )
    return existing


def test_check_existing_price(benchmark, db_session, stock_with_data):
    """Benchmark: Single price existence check."""
    result = benchmark(benchmark_check_existing_price, db_session, stock_with_data)


def benchmark_bulk_price_check(db_session, stock_with_data):
    """Benchmark bulk checking for existing dates - optimized approach."""
    # Get all dates we want to check (simulating 100 days of new data)
    start_date = date.today() - timedelta(days=100)
    dates_to_check = [start_date + timedelta(days=i) for i in range(100)]

    existing_dates = set(
        r[0] for r in db_session.query(TestPriceHistory.date)
        .filter(
            TestPriceHistory.stock_id == stock_with_data.id,
            TestPriceHistory.date.in_(dates_to_check),
        )
        .all()
    )
    return existing_dates


def test_bulk_price_check(benchmark, db_session, stock_with_data):
    """Benchmark: Bulk date existence check (optimized pattern)."""
    result = benchmark(benchmark_bulk_price_check, db_session, stock_with_data)


def benchmark_n_plus_1_price_check(db_session, stock_with_data):
    """Simulate N+1 pattern - checking each date individually."""
    start_date = date.today() - timedelta(days=100)
    existing = []
    for i in range(100):
        target_date = start_date + timedelta(days=i)
        result = (
            db_session.query(TestPriceHistory)
            .filter(
                TestPriceHistory.stock_id == stock_with_data.id,
                TestPriceHistory.date == target_date,
            )
            .first()
        )
        if result:
            existing.append(target_date)
    return existing


def test_n_plus_1_price_check(benchmark, db_session, stock_with_data):
    """Benchmark: N+1 pattern (100 individual queries) - shows inefficiency."""
    result = benchmark(benchmark_n_plus_1_price_check, db_session, stock_with_data)


# ============ DataFrame Processing Benchmarks ============

def benchmark_dataframe_to_dict_naive(df):
    """Naive DataFrame to dict conversion."""
    result = {}
    for col in df.columns:
        values = []
        for val in df[col]:
            if pd.isna(val):
                values.append(None)
            elif hasattr(val, 'isoformat'):
                values.append(val.isoformat())
            elif isinstance(val, (int, float)):
                values.append(float(val) if pd.notna(val) else None)
            else:
                values.append(str(val))
        result[str(col)] = values
    return result


def benchmark_dataframe_to_dict_optimized(df):
    """Optimized DataFrame to dict using pandas native methods."""
    return df.to_dict(orient='list')


@pytest.fixture
def large_dataframe():
    """Create a large DataFrame simulating financial data."""
    dates = pd.date_range(start='2020-01-01', periods=1000, freq='D')
    data = {
        'Revenue': [1000000 + i * 1000 for i in range(1000)],
        'NetIncome': [100000 + i * 100 for i in range(1000)],
        'EPS': [1.5 + i * 0.01 for i in range(1000)],
        'Date': dates,
    }
    return pd.DataFrame(data)


def test_dataframe_to_dict_naive(benchmark, large_dataframe):
    """Benchmark: Naive DataFrame conversion with row-by-row iteration."""
    result = benchmark(benchmark_dataframe_to_dict_naive, large_dataframe)
    assert 'Revenue' in result


def test_dataframe_to_dict_optimized(benchmark, large_dataframe):
    """Benchmark: Optimized DataFrame conversion using pandas built-ins."""
    result = benchmark(benchmark_dataframe_to_dict_optimized, large_dataframe)
    assert 'Revenue' in result


# ============ Decimal Conversion Benchmarks ============

def benchmark_decimal_conversion_individual(values):
    """Convert values to Decimal one at a time."""
    results = []
    for val in values:
        if pd.notna(val):
            results.append(Decimal(str(val)))
        else:
            results.append(None)
    return results


def benchmark_decimal_conversion_list_comp(values):
    """Convert values using list comprehension."""
    return [Decimal(str(v)) if pd.notna(v) else None for v in values]


@pytest.fixture
def price_values():
    """Sample price values for conversion tests."""
    return [150.25 + i * 0.01 for i in range(1000)]


def test_decimal_conversion_individual(benchmark, price_values):
    """Benchmark: Individual Decimal conversions."""
    result = benchmark(benchmark_decimal_conversion_individual, price_values)
    assert len(result) == 1000


def test_decimal_conversion_list_comp(benchmark, price_values):
    """Benchmark: List comprehension Decimal conversion."""
    result = benchmark(benchmark_decimal_conversion_list_comp, price_values)
    assert len(result) == 1000


# ============ Set Operations Benchmarks ============

def benchmark_set_membership_list(existing_ids, new_ids):
    """Check membership using list iteration."""
    results = []
    for new_id in new_ids:
        if new_id not in existing_ids:
            results.append(new_id)
    return results


def benchmark_set_membership_set(existing_ids, new_ids):
    """Check membership using set difference."""
    return new_ids - existing_ids


@pytest.fixture
def id_sets():
    """Create test sets for membership checks."""
    existing = {f"article_{i}" for i in range(10000)}
    new = {f"article_{i}" for i in range(9900, 10100)}  # 100 overlap, 100 new
    return existing, new


def test_set_membership_list(benchmark, id_sets):
    """Benchmark: List-based membership check."""
    existing, new = id_sets
    result = benchmark(benchmark_set_membership_list, existing, new)


def test_set_membership_set(benchmark, id_sets):
    """Benchmark: Set difference operation."""
    existing, new = id_sets
    result = benchmark(benchmark_set_membership_set, existing, new)
    assert len(result) == 100
