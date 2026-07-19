"""Add live companion session/snapshot tables (Phase 9 / C1).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "live_sessions",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("riot_id", sa.String(length=96), nullable=False),
        sa.Column("collector_version", sa.String(length=32), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("game_start_ms", sa.BigInteger(), nullable=True),
        sa.Column("matched_match_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_table(
        "live_snapshots",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("game_time_s", sa.Float(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["live_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "seq"),
    )


def downgrade() -> None:
    op.drop_table("live_snapshots")
    op.drop_table("live_sessions")
