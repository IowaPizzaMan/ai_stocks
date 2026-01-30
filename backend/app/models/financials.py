from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    period_end = Column(Date, nullable=False, index=True)
    period_type = Column(String(10))  # 'quarterly' or 'annual'
    statement_type = Column(String(20))  # 'income', 'balance', 'cashflow'
    data = Column(JSONB, nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("stock_id", "period_end", "period_type", "statement_type", name="uix_stock_period_statement"),
    )

    stock = relationship("WatchedStock", back_populates="financial_statements")
