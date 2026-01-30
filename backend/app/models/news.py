from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("watched_stocks.id"), nullable=False)
    article_id = Column(String(255), unique=True, index=True)  # Yahoo's unique ID
    title = Column(Text, nullable=False)
    link = Column(Text)
    publisher = Column(String(255))
    published_at = Column(DateTime(timezone=True))
    sentiment = Column(String(20))  # 'positive', 'negative', 'neutral'
    sentiment_score = Column(Numeric(5, 4))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("WatchedStock", back_populates="news_articles")
