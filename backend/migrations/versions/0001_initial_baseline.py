"""Initial baseline: tables that existed before Alembic was introduced.

For databases already created via SQLAlchemy create_all, run
`alembic stamp 0001` (or `alembic stamp head` after reviewing later
revisions) instead of upgrading.

Revision ID: 0001
Revises:
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "summoners",
        sa.Column("puuid", sa.String(length=128), nullable=False),
        sa.Column("game_name", sa.String(length=64), nullable=False),
        sa.Column("tag_line", sa.String(length=16), nullable=False),
        sa.Column("platform_routing", sa.String(length=16), nullable=False),
        sa.Column("summoner_id", sa.String(length=128), nullable=True),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("profile_icon_id", sa.Integer(), nullable=True),
        sa.Column("summoner_level", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("puuid"),
    )

    op.create_table(
        "riot_matches",
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("platform_routing", sa.String(length=16), nullable=False),
        sa.Column("queue_id", sa.Integer(), nullable=True),
        sa.Column("game_creation", sa.BigInteger(), nullable=True),
        sa.Column("game_duration", sa.Integer(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("match_id"),
    )

    op.create_table(
        "summoner_matches",
        sa.Column("summoner_puuid", sa.String(length=128), nullable=False),
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=True),
        sa.Column("champion_name", sa.String(length=64), nullable=True),
        sa.Column("team_position", sa.String(length=32), nullable=True),
        sa.Column("win", sa.Boolean(), nullable=True),
        sa.Column("kills", sa.Integer(), nullable=True),
        sa.Column("deaths", sa.Integer(), nullable=True),
        sa.Column("assists", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["summoner_puuid"], ["summoners.puuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["riot_matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("summoner_puuid", "match_id"),
    )

    op.create_table(
        "match_participants",
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("puuid", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("champion_id", sa.Integer(), nullable=True),
        sa.Column("champion_name", sa.String(length=64), nullable=True),
        sa.Column("team_position", sa.String(length=32), nullable=True),
        sa.Column("individual_position", sa.String(length=32), nullable=True),
        sa.Column("win", sa.Boolean(), nullable=True),
        sa.Column("kills", sa.Integer(), nullable=True),
        sa.Column("deaths", sa.Integer(), nullable=True),
        sa.Column("assists", sa.Integer(), nullable=True),
        sa.Column("damage_to_champions", sa.Integer(), nullable=True),
        sa.Column("damage_taken", sa.Integer(), nullable=True),
        sa.Column("vision_score", sa.Integer(), nullable=True),
        sa.Column("gold_earned", sa.Integer(), nullable=True),
        sa.Column("total_minions_killed", sa.Integer(), nullable=True),
        sa.Column("neutral_minions_killed", sa.Integer(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["riot_matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id", "participant_id"),
    )
    op.create_index("ix_match_participants_puuid", "match_participants", ["puuid"])

    op.create_table(
        "match_events",
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=True),
        sa.Column("killer_id", sa.Integer(), nullable=True),
        sa.Column("victim_id", sa.Integer(), nullable=True),
        sa.Column("killer_team_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("monster_type", sa.String(length=64), nullable=True),
        sa.Column("building_type", sa.String(length=64), nullable=True),
        sa.Column("lane_type", sa.String(length=64), nullable=True),
        sa.Column("position_x", sa.Integer(), nullable=True),
        sa.Column("position_y", sa.Integer(), nullable=True),
        sa.Column("assisting_participant_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["riot_matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id", "event_sequence"),
    )

    op.create_table(
        "match_timeline_features",
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=False),
        sa.Column("blue_gold", sa.Integer(), nullable=False),
        sa.Column("red_gold", sa.Integer(), nullable=False),
        sa.Column("gold_diff", sa.Integer(), nullable=False),
        sa.Column("blue_xp", sa.Integer(), nullable=False),
        sa.Column("red_xp", sa.Integer(), nullable=False),
        sa.Column("xp_diff", sa.Integer(), nullable=False),
        sa.Column("blue_cs", sa.Integer(), nullable=False),
        sa.Column("red_cs", sa.Integer(), nullable=False),
        sa.Column("cs_diff", sa.Integer(), nullable=False),
        sa.Column("blue_tower_kills", sa.Integer(), nullable=False),
        sa.Column("red_tower_kills", sa.Integer(), nullable=False),
        sa.Column("blue_dragon_kills", sa.Integer(), nullable=False),
        sa.Column("red_dragon_kills", sa.Integer(), nullable=False),
        sa.Column("blue_herald_kills", sa.Integer(), nullable=False),
        sa.Column("red_herald_kills", sa.Integer(), nullable=False),
        sa.Column("blue_baron_kills", sa.Integer(), nullable=False),
        sa.Column("red_baron_kills", sa.Integer(), nullable=False),
        sa.Column("raw_frame", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["riot_matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id", "minute"),
    )

    op.create_table(
        "player_skill_scores",
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("puuid", sa.String(length=128), nullable=False),
        sa.Column("death_cost_index", sa.Integer(), nullable=False),
        sa.Column("throw_index", sa.Integer(), nullable=False),
        sa.Column("objective_setup_score", sa.Integer(), nullable=False),
        sa.Column("lead_conversion_score", sa.Integer(), nullable=True),
        sa.Column("stability_score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["riot_matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id", "puuid"),
    )


def downgrade() -> None:
    op.drop_table("player_skill_scores")
    op.drop_table("match_timeline_features")
    op.drop_table("match_events")
    op.drop_index("ix_match_participants_puuid", table_name="match_participants")
    op.drop_table("match_participants")
    op.drop_table("summoner_matches")
    op.drop_table("riot_matches")
    op.drop_table("summoners")
