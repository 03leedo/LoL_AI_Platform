"""Live Client companion sessions (Phase 9 / C1): storage and reconciliation.

The companion collects during the user's OWN games only (opt-in, collection
only — nothing is ever shown in-game, PRD §19.3). The Live Client Data API
exposes no match id, so sessions are client-keyed UUIDs; after the game the
session is reconciled with a stored match by riot id + game-creation window.
Snapshot upload is idempotent: (session_id, seq) conflicts are ignored, so
companion retries can never duplicate rows.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LiveSession, LiveSnapshot, MatchParticipant, RiotMatch

logger = logging.getLogger(__name__)

LIVE_SCHEMA_VERSION = 1
MAX_SNAPSHOTS_PER_BATCH = 500
# The collector may start mid-game: accept a stored match that began up to
# 45 min before the session started polling, or up to 10 min after.
RECONCILE_BEFORE_MS = 45 * 60 * 1000
RECONCILE_AFTER_MS = 10 * 60 * 1000


def split_riot_id(riot_id: str) -> tuple[str, str] | None:
    if "#" not in riot_id:
        return None
    name, _, tag = riot_id.rpartition("#")
    name, tag = name.strip(), tag.strip()
    if not name or not tag:
        return None
    return name, tag


async def upsert_session(
    db: AsyncSession,
    session_id: str,
    riot_id: str,
    collector_version: str | None,
) -> LiveSession:
    session = await db.get(LiveSession, session_id)
    if session is None:
        session = LiveSession(
            session_id=session_id,
            riot_id=riot_id,
            collector_version=collector_version,
            state="collecting",
        )
        db.add(session)
    else:
        session.riot_id = riot_id
        if collector_version:
            session.collector_version = collector_version
    return session


async def store_snapshots(
    db: AsyncSession,
    session_id: str,
    riot_id: str,
    collector_version: str | None,
    snapshots: list[dict[str, Any]],
) -> dict[str, int]:
    """Idempotently persist a snapshot batch; duplicate seqs are ignored."""
    await upsert_session(db, session_id, riot_id, collector_version)
    accepted = 0
    if snapshots:
        statement = (
            pg_insert(LiveSnapshot)
            .values(
                [
                    {
                        "session_id": session_id,
                        "seq": snapshot["seq"],
                        "game_time_s": snapshot["game_time_s"],
                        "payload": snapshot.get("payload"),
                    }
                    for snapshot in snapshots
                ]
            )
            .on_conflict_do_nothing(index_elements=["session_id", "seq"])
        )
        result = await db.execute(statement)
        accepted = result.rowcount or 0
    await db.commit()
    return {"received": len(snapshots), "accepted": accepted}


async def fetch_candidate_match_ids(
    db: AsyncSession,
    game_name: str,
    tag_line: str,
    window_start_ms: int,
    window_end_ms: int,
) -> list[str]:
    result = await db.execute(
        select(RiotMatch.match_id)
        .join(MatchParticipant, MatchParticipant.match_id == RiotMatch.match_id)
        .where(
            MatchParticipant.raw_json["riotIdGameName"].astext == game_name,
            MatchParticipant.raw_json["riotIdTagline"].astext == tag_line,
            RiotMatch.game_creation >= window_start_ms,
            RiotMatch.game_creation <= window_end_ms,
        )
        .order_by(RiotMatch.game_creation.desc())
    )
    return [row[0] for row in result.all()]


async def complete_session(
    db: AsyncSession,
    session_id: str,
    game_start_ms: int | None,
) -> LiveSession | None:
    """Mark a session complete and try to match it to a stored match.

    Reconciliation is conservative: only an unambiguous single candidate is
    linked; zero or multiple candidates leave the session unmatched (the
    match may simply not be ingested yet — re-completion retries the link).
    """
    session = await db.get(LiveSession, session_id)
    if session is None:
        return None
    if game_start_ms:
        session.game_start_ms = game_start_ms
    session.state = "complete"

    parsed = split_riot_id(session.riot_id)
    if parsed and session.game_start_ms:
        game_name, tag_line = parsed
        candidates = await fetch_candidate_match_ids(
            db,
            game_name,
            tag_line,
            window_start_ms=session.game_start_ms - RECONCILE_BEFORE_MS,
            window_end_ms=session.game_start_ms + RECONCILE_AFTER_MS,
        )
        if len(candidates) == 1:
            session.matched_match_id = candidates[0]
            session.state = "reconciled"
        elif len(candidates) > 1:
            logger.info(
                "Live session %s: %d candidate matches — leaving unmatched",
                session_id,
                len(candidates),
            )
    await db.commit()
    return session


def session_to_dict(session: LiveSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "riot_id": session.riot_id,
        "state": session.state,
        "game_start_ms": session.game_start_ms,
        "matched_match_id": session.matched_match_id,
        "collector_version": session.collector_version,
        "schema_version": LIVE_SCHEMA_VERSION,
    }
