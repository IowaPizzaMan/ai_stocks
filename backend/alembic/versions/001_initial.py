"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('watched_stocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_watched_stocks_id'), 'watched_stocks', ['id'], unique=False)
    op.create_index(op.f('ix_watched_stocks_ticker'), 'watched_stocks', ['ticker'], unique=True)

    op.create_table('price_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('open', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('high', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('low', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('close', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('adj_close', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['watched_stocks.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'date', name='uix_stock_date')
    )
    op.create_index(op.f('ix_price_history_date'), 'price_history', ['date'], unique=False)
    op.create_index(op.f('ix_price_history_id'), 'price_history', ['id'], unique=False)

    op.create_table('financial_statements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('period_type', sa.String(length=10), nullable=True),
        sa.Column('statement_type', sa.String(length=20), nullable=True),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['watched_stocks.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'period_end', 'period_type', 'statement_type', name='uix_stock_period_statement')
    )
    op.create_index(op.f('ix_financial_statements_id'), 'financial_statements', ['id'], unique=False)
    op.create_index(op.f('ix_financial_statements_period_end'), 'financial_statements', ['period_end'], unique=False)

    op.create_table('news_articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('article_id', sa.String(length=255), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('link', sa.Text(), nullable=True),
        sa.Column('publisher', sa.String(length=255), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sentiment', sa.String(length=20), nullable=True),
        sa.Column('sentiment_score', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['watched_stocks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_news_articles_article_id'), 'news_articles', ['article_id'], unique=True)
    op.create_index(op.f('ix_news_articles_id'), 'news_articles', ['id'], unique=False)

    op.create_table('stock_analysis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('analysis_date', sa.Date(), nullable=False),
        sa.Column('bull_case', sa.Text(), nullable=True),
        sa.Column('bear_case', sa.Text(), nullable=True),
        sa.Column('short_term_outlook', sa.Text(), nullable=True),
        sa.Column('long_term_outlook', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('news_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['watched_stocks.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'analysis_date', name='uix_stock_analysis_date')
    )
    op.create_index(op.f('ix_stock_analysis_analysis_date'), 'stock_analysis', ['analysis_date'], unique=False)
    op.create_index(op.f('ix_stock_analysis_id'), 'stock_analysis', ['id'], unique=False)

    op.create_table('sync_metadata',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('data_type', sa.String(length=50), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_data_date', sa.Date(), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['watched_stocks.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'data_type', name='uix_stock_data_type')
    )
    op.create_index(op.f('ix_sync_metadata_id'), 'sync_metadata', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sync_metadata_id'), table_name='sync_metadata')
    op.drop_table('sync_metadata')
    op.drop_index(op.f('ix_stock_analysis_id'), table_name='stock_analysis')
    op.drop_index(op.f('ix_stock_analysis_analysis_date'), table_name='stock_analysis')
    op.drop_table('stock_analysis')
    op.drop_index(op.f('ix_news_articles_id'), table_name='news_articles')
    op.drop_index(op.f('ix_news_articles_article_id'), table_name='news_articles')
    op.drop_table('news_articles')
    op.drop_index(op.f('ix_financial_statements_period_end'), table_name='financial_statements')
    op.drop_index(op.f('ix_financial_statements_id'), table_name='financial_statements')
    op.drop_table('financial_statements')
    op.drop_index(op.f('ix_price_history_id'), table_name='price_history')
    op.drop_index(op.f('ix_price_history_date'), table_name='price_history')
    op.drop_table('price_history')
    op.drop_index(op.f('ix_watched_stocks_ticker'), table_name='watched_stocks')
    op.drop_index(op.f('ix_watched_stocks_id'), table_name='watched_stocks')
    op.drop_table('watched_stocks')
