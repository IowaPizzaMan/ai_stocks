from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
from .watchlist import watchlist_stocks


class WatchedStock(Base):
    __tablename__ = "watched_stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    company_name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    price_history = relationship("PriceHistory", back_populates="stock", cascade="all, delete-orphan")
    financial_statements = relationship("FinancialStatement", back_populates="stock", cascade="all, delete-orphan")
    news_articles = relationship("NewsArticle", back_populates="stock", cascade="all, delete-orphan")
    analyses = relationship("StockAnalysis", back_populates="stock", cascade="all, delete-orphan")
    sync_metadata = relationship("SyncMetadata", back_populates="stock", cascade="all, delete-orphan")
    earnings_data = relationship("EarningsData", back_populates="stock", cascade="all, delete-orphan")
    watchlists = relationship("Watchlist", secondary=watchlist_stocks, back_populates="stocks")
