from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class StockAnalysis(Base):
    __tablename__ = "stock_analysis"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    analysis_date = Column(Date, nullable=False, index=True)
    bull_case = Column(Text)
    bear_case = Column(Text)
    short_term_outlook = Column(Text)
    long_term_outlook = Column(Text)
    confidence_score = Column(Numeric(5, 4))
    news_summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("stock_id", "analysis_date", name="uix_stock_analysis_date"),
    )

    stock = relationship("WatchedStock", back_populates="analyses")


class SyncMetadata(Base):
    __tablename__ = "sync_metadata"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    data_type = Column(String(50))  # 'price', 'financials', 'news'
    last_sync_at = Column(DateTime(timezone=True))
    last_data_date = Column(Date)
    sync_status = Column(String(20))  # 'success', 'failed', 'pending'

    __table_args__ = (
        UniqueConstraint("stock_id", "data_type", name="uix_stock_data_type"),
    )

    stock = relationship("WatchedStock", back_populates="sync_metadata")
