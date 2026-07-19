from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class LiveSession(Base):
    """One companion collection session (≈ one of the user's own games).

    The Live Client Data API exposes no match id, so a session is keyed by a
    client-generated UUID and reconciled with a stored match after the fact.
    """

    __tablename__ = "live_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    riot_id: Mapped[str] = mapped_column(String(96), nullable=False)
    collector_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # collecting → complete → reconciled (matched to a stored match)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="collecting")
    game_start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    matched_match_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class LiveSnapshot(Base):
    __tablename__ = "live_snapshots"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("live_sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_time_s: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
