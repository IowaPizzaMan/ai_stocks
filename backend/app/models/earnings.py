from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class EarningsData(Base):
    """Stores earnings-related data from yfinance.

    Data types:
    - annual_earnings: Annual revenue and earnings by year
    - quarterly_earnings: Quarterly earnings by quarter
    - earnings_dates: Past and upcoming earnings dates with EPS estimates/actuals
    - earnings_estimate: EPS estimates (current qtr, next qtr, current yr, next yr)
    - revenue_estimate: Revenue estimates with avg, low, high, growth
    - earnings_trend: EPS trend analysis
    - growth_estimates: Growth projections (stock vs industry vs sector)
    - eps_revisions: EPS revision history
    """
    __tablename__ = "earnings_data"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    data_type = Column(String(50), nullable=False, index=True)
    data = Column(JSONB, nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("stock_id", "data_type", name="uix_stock_earnings_type"),
    )

    stock = relationship("WatchedStock", back_populates="earnings_data")
