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
