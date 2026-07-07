from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class RiotMatch(Base):
    __tablename__ = "riot_matches"

    match_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    platform_routing: Mapped[str] = mapped_column(String(16), nullable=False, default="kr")
    queue_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_creation: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    game_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RiotMatchTimeline(Base):
    """Full Match-V5 timeline payload; immutable, acts as the fetch cache."""

    __tablename__ = "riot_match_timelines"

    match_id: Mapped[str] = mapped_column(
        ForeignKey("riot_matches.match_id", ondelete="CASCADE"),
        primary_key=True,
    )
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class SummonerMatch(Base):
    __tablename__ = "summoner_matches"

    summoner_puuid: Mapped[str] = mapped_column(
        ForeignKey("summoners.puuid", ondelete="CASCADE"),
        primary_key=True,
    )
    match_id: Mapped[str] = mapped_column(
        ForeignKey("riot_matches.match_id", ondelete="CASCADE"),
        primary_key=True,
    )
    participant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    champion_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_position: Mapped[str | None] = mapped_column(String(32), nullable=True)
    win: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    kills: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MatchParticipant(Base):
    __tablename__ = "match_participants"

    match_id: Mapped[str] = mapped_column(
        ForeignKey("riot_matches.match_id", ondelete="CASCADE"),
        primary_key=True,
    )
    participant_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    puuid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    champion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    champion_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_position: Mapped[str | None] = mapped_column(String(32), nullable=True)
    individual_position: Mapped[str | None] = mapped_column(String(32), nullable=True)
    win: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    kills: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    damage_to_champions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    damage_taken: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vision_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gold_earned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_minions_killed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    neutral_minions_killed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MatchEvent(Base):
    __tablename__ = "match_events"

    match_id: Mapped[str] = mapped_column(
        ForeignKey("riot_matches.match_id", ondelete="CASCADE"),
        primary_key=True,
    )
    event_sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    participant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    killer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    victim_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    killer_team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monster_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    building_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lane_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assisting_participant_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MatchTimelineFeature(Base):
    __tablename__ = "match_timeline_features"

    match_id: Mapped[str] = mapped_column(
        ForeignKey("riot_matches.match_id", ondelete="CASCADE"),
        primary_key=True,
    )
    minute: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)

    blue_gold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_gold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gold_diff: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    blue_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp_diff: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    blue_cs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_cs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cs_diff: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    blue_tower_kills: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_tower_kills: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blue_dragon_kills: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_dragon_kills: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blue_herald_kills: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_herald_kills: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blue_baron_kills: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_baron_kills: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    raw_frame: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PlayerSkillScore(Base):
    __tablename__ = "player_skill_scores"

    match_id: Mapped[str] = mapped_column(
        ForeignKey("riot_matches.match_id", ondelete="CASCADE"),
        primary_key=True,
    )
    puuid: Mapped[str] = mapped_column(String(128), primary_key=True)
    death_cost_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    throw_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    objective_setup_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    lead_conversion_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stability_score: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
