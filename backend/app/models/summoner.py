from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Summoner(Base):
    __tablename__ = "summoners"

    puuid: Mapped[str] = mapped_column(String(128), primary_key=True)
    game_name: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_line: Mapped[str] = mapped_column(String(16), nullable=False)
    platform_routing: Mapped[str] = mapped_column(String(16), nullable=False, default="kr")

    summoner_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    profile_icon_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summoner_level: Mapped[int | None] = mapped_column(Integer, nullable=True)

    solo_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    solo_division: Mapped[str | None] = mapped_column(String(8), nullable=True)
    solo_lp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    solo_wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    solo_losses: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
