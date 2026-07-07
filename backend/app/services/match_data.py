"""DB-first access to immutable Riot match data.

Match and timeline payloads never change once a game ends, so the database is
the cache: hit Riot only when a payload is missing locally. Freshly fetched
payloads are committed immediately so they survive any downstream failure in
the calling request.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import RiotMatch, RiotMatchTimeline
from app.repositories.matches import upsert_match
from app.services.riot_client import RiotClient

logger = logging.getLogger(__name__)


async def get_match_cached(
    db: AsyncSession,
    client: RiotClient,
    match_id: str,
    platform_routing: str,
) -> tuple[dict[str, Any], bool]:
    """Return (match, from_cache). Falls back to Riot when the DB row is absent."""
    row = await _load_row(db, RiotMatch, match_id)
    if row is not None and row.raw_json:
        return row.raw_json, True

    match = await client.get_match(match_id)
    await _store_fresh(db, match_id, lambda: upsert_match(
        db=db,
        match_id=match_id,
        match=match,
        platform_routing=platform_routing,
    ))
    return match, False


async def get_timeline_cached(
    db: AsyncSession,
    client: RiotClient,
    match_id: str,
) -> tuple[dict[str, Any], bool]:
    """Return (timeline, from_cache). Requires the match row to exist for the FK."""
    row = await _load_row(db, RiotMatchTimeline, match_id)
    if row is not None and row.raw_json:
        return row.raw_json, True

    timeline = await client.get_match_timeline(match_id)

    async def _merge_timeline() -> None:
        await db.merge(RiotMatchTimeline(match_id=match_id, raw_json=timeline))

    await _store_fresh(db, match_id, _merge_timeline)
    return timeline, False


async def _load_row(db: AsyncSession, model: type, match_id: str) -> Any:
    try:
        return await db.get(model, match_id)
    except Exception as exc:  # pragma: no cover - cache lookup must never block the request
        logger.warning("Cache lookup skipped for %s (%s): %s", match_id, model.__name__, exc)
        return None


async def _store_fresh(db: AsyncSession, match_id: str, persist) -> None:
    try:
        await persist()
        await db.commit()
    except Exception as exc:  # pragma: no cover - serving data beats caching it
        logger.warning("Cache persistence skipped for %s: %s", match_id, exc)
        try:
            await db.rollback()
        except Exception:  # pragma: no cover
            pass
