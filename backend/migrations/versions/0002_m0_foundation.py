"""M0 foundation: timeline cache, moments, long-format metric scores, ingest jobs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "riot_match_timelines",
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["riot_matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id"),
    )

    op.create_table(
        "moments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("puuid", sa.String(length=128), nullable=True),
        sa.Column("t_start_ms", sa.BigInteger(), nullable=False),
        sa.Column("t_end_ms", sa.BigInteger(), nullable=False),
        sa.Column("moment_type", sa.String(length=32), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["riot_matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_moments_match_id", "moments", ["match_id"])
    op.create_index("ix_moments_puuid", "moments", ["puuid"])

    op.create_table(
        "metric_scores",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("puuid", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("match_id", sa.String(length=32), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column("window", sa.String(length=32), nullable=True),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("grade", sa.String(length=8), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("direction", sa.String(length=24), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("metric_version", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["riot_matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metric_scores_puuid", "metric_scores", ["puuid"])
    op.create_index("ix_metric_scores_match_id", "metric_scores", ["match_id"])
    op.create_index("ix_metric_scores_metric_key", "metric_scores", ["metric_key"])

    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("puuid", sa.String(length=128), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingest_jobs_puuid", "ingest_jobs", ["puuid"])
    op.create_index("ix_ingest_jobs_state", "ingest_jobs", ["state"])


def downgrade() -> None:
    op.drop_index("ix_ingest_jobs_state", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_puuid", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
    op.drop_index("ix_metric_scores_metric_key", table_name="metric_scores")
    op.drop_index("ix_metric_scores_match_id", table_name="metric_scores")
    op.drop_index("ix_metric_scores_puuid", table_name="metric_scores")
    op.drop_table("metric_scores")
    op.drop_index("ix_moments_puuid", table_name="moments")
    op.drop_index("ix_moments_match_id", table_name="moments")
    op.drop_table("moments")
    op.drop_table("riot_match_timelines")
