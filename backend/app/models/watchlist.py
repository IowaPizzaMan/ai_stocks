from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


# Junction table for many-to-many relationship between watchlists and stocks
watchlist_stocks = Table(
    'watchlist_stocks',
    Base.metadata,
    Column('watchlist_id', Integer, ForeignKey('watchlists.id', ondelete='CASCADE'), primary_key=True),
    Column('stock_id', Integer, ForeignKey('watched_stocks.id', ondelete='CASCADE'), primary_key=True),
)


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship to stocks through junction table
    stocks = relationship("WatchedStock", secondary=watchlist_stocks, back_populates="watchlists")
