"""Add analysis_reports cache table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("puuid", sa.String(length=128), nullable=False),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("window", sa.String(length=32), nullable=True),
        sa.Column("cache_key", sa.String(length=160), nullable=False),
        sa.Column("generated_by", sa.String(length=16), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_reports_puuid", "analysis_reports", ["puuid"])
    op.create_index("ix_analysis_reports_cache_key", "analysis_reports", ["cache_key"])


def downgrade() -> None:
    op.drop_index("ix_analysis_reports_cache_key", table_name="analysis_reports")
    op.drop_index("ix_analysis_reports_puuid", table_name="analysis_reports")
    op.drop_table("analysis_reports")
