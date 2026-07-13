from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Moment(Base):
    """A meaningful in-match window from one player's perspective.

    Moments are the shared currency between AI report citations, highlight
    clips, and vision analysis attachments (master-plan §2). `source` tracks
    provenance: api | approx | replay | vision.
    """

    __tablename__ = "moments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("riot_matches.match_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    puuid: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    t_start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    t_end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    moment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="api")
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MetricScore(Base):
    """Long-format metric storage: adding a metric is an INSERT, not a schema change.

    scope: "match" (per match) or "aggregate" (multi-match window, M2+).
    """

    __tablename__ = "metric_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    puuid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="match")
    match_id: Mapped[str | None] = mapped_column(
        ForeignKey("riot_matches.match_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    window: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metric_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    direction: Mapped[str] = mapped_column(String(24), nullable=False, default="higher_is_better")
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="api")
    metric_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AnalysisReport(Base):
    """Cached AI/rule-based reports keyed by (puuid, cache_key).

    cache_key encodes report version, metric version, window, and the latest
    match id — so a report is regenerated only when new data or new formulas
    exist (LLM cost guard).
    """

    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    puuid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, default="summary")
    window: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cache_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    generated_by: Mapped[str] = mapped_column(String(16), nullable=False, default="rules")
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class IngestJob(Base):
    """Tracks background multi-match ingestion requests (queued by M2 role analysis)."""

    __tablename__ = "ingest_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    puuid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, default="match_history")
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
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
