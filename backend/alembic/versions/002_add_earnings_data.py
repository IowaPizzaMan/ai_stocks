"""Add earnings_data table

Revision ID: 002
Revises: 001
Create Date: 2024-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('earnings_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('data_type', sa.String(length=50), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['watched_stocks.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'data_type', name='uix_stock_earnings_type')
    )
    op.create_index(op.f('ix_earnings_data_id'), 'earnings_data', ['id'], unique=False)
    op.create_index(op.f('ix_earnings_data_data_type'), 'earnings_data', ['data_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_earnings_data_data_type'), table_name='earnings_data')
    op.drop_index(op.f('ix_earnings_data_id'), table_name='earnings_data')
    op.drop_table('earnings_data')
