"""Add watchlists table and junction table

Revision ID: 003
Revises: 002
Create Date: 2024-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create watchlists table
    op.create_table('watchlists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_watchlists_id'), 'watchlists', ['id'], unique=False)

    # Create junction table for many-to-many relationship
    op.create_table('watchlist_stocks',
        sa.Column('watchlist_id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['watchlist_id'], ['watchlists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stock_id'], ['watched_stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('watchlist_id', 'stock_id')
    )

    # Insert default watchlist
    op.execute(
        "INSERT INTO watchlists (name, description, is_default, is_active) "
        "VALUES ('My Watchlist', 'Default watchlist', true, true)"
    )

    # Migrate existing active stocks to the default watchlist
    op.execute(
        "INSERT INTO watchlist_stocks (watchlist_id, stock_id) "
        "SELECT (SELECT id FROM watchlists WHERE is_default = true LIMIT 1), id "
        "FROM watched_stocks WHERE is_active = true"
    )


def downgrade() -> None:
    op.drop_table('watchlist_stocks')
    op.drop_index(op.f('ix_watchlists_id'), table_name='watchlists')
    op.drop_table('watchlists')
