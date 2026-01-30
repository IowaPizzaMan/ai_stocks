from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..models import PriceHistory, FinancialStatement, NewsArticle, SyncMetadata


class DeltaTracker:
    def __init__(self, db: Session, stock_id: int):
        self.db = db
        self.stock_id = stock_id

    def get_last_price_date(self) -> date | None:
        """Get the most recent price date we have stored."""
        result = (
            self.db.query(PriceHistory.date)
            .filter(PriceHistory.stock_id == self.stock_id)
            .order_by(desc(PriceHistory.date))
            .first()
        )
        return result[0] if result else None

    def get_existing_financial_periods(self, statement_type: str, period_type: str) -> set[date]:
        """Get all period_end dates we have for a given statement type."""
        results = (
            self.db.query(FinancialStatement.period_end)
            .filter(
                FinancialStatement.stock_id == self.stock_id,
                FinancialStatement.statement_type == statement_type,
                FinancialStatement.period_type == period_type,
            )
            .all()
        )
        return {r[0] for r in results}

    def get_existing_article_ids(self) -> set[str]:
        """Get all article IDs we have stored (globally, since article_id is unique)."""
        # Check globally because article_id has a unique constraint across all stocks
        results = (
            self.db.query(NewsArticle.article_id)
            .all()
        )
        return {r[0] for r in results if r[0]}

    def update_sync_metadata(self, data_type: str, status: str, last_data_date: date = None):
        """Update or create sync metadata for tracking."""
        metadata = (
            self.db.query(SyncMetadata)
            .filter(
                SyncMetadata.stock_id == self.stock_id,
                SyncMetadata.data_type == data_type,
            )
            .first()
        )

        if metadata:
            metadata.last_sync_at = datetime.utcnow()
            metadata.sync_status = status
            if last_data_date:
                metadata.last_data_date = last_data_date
        else:
            metadata = SyncMetadata(
                stock_id=self.stock_id,
                data_type=data_type,
                last_sync_at=datetime.utcnow(),
                last_data_date=last_data_date,
                sync_status=status,
            )
            self.db.add(metadata)

        self.db.commit()

    def get_price_fetch_start_date(self) -> date | None:
        """Calculate the start date for fetching prices (day after last stored)."""
        last_date = self.get_last_price_date()
        if last_date:
            return last_date + timedelta(days=1)
        return None  # Will fetch all history
