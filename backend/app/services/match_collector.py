"""Data volume expansion: derived-table backfill and cohort snowball collection.

Two jobs, both runnable as a CLI inside the backend container:

    docker compose exec backend python -m app.services.match_collector --backfill
    docker compose exec backend python -m app.services.match_collector --max-new 100

- Backfill recomputes participants / events / timeline features for matches
  whose raw payloads are already stored — no Riot API calls.
- Collection snowballs from puuids already present in stored matches
  (registered summoners first), ingesting matches we have not stored yet.
  Cohort matches are denominators and model inputs only; no team-level
  analysis is derived from them.

The Riot client's built-in limiter (18/s, 95/120s) paces all API calls; an
invalid/expired key (dev keys rotate every 24h) aborts the run with a clear
message instead of hammering the API.
"""

import argparse
import asyncio
import logging
from typing import Any, Awaitable, Callable

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import MatchParticipant, RiotMatch, RiotMatchTimeline, Summoner
from app.repositories.matches import (
    replace_match_events,
    replace_match_participants,
    replace_timeline_features,
)
from app.services.ingest import ingest_single_match
from app.services.riot_client import RiotApiError, RiotClient
from app.services.timeline_analyzer import analyze_match_timeline

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_ID = 420
DEFAULT_MAX_NEW_MATCHES = 100
DEFAULT_PER_SEED_COUNT = 30
DEFAULT_MAX_SEEDS = 50
# Riot API keys that stopped working must abort the whole run.
_ABORT_STATUSES = {401, 403}


async def backfill_derived_tables(db: AsyncSession) -> dict[str, Any]:
    """Recompute derived tables from stored raw match+timeline payloads."""
    result = await db.execute(
        select(RiotMatch.match_id, RiotMatch.raw_json, RiotMatchTimeline.raw_json.label("timeline_json"))
        .join(RiotMatchTimeline, RiotMatchTimeline.match_id == RiotMatch.match_id)
        .order_by(RiotMatch.game_creation.asc(), RiotMatch.match_id.asc())
    )
    processed = 0
    failed = 0
    for record in result.mappings():
        match_id = record["match_id"]
        match = record["raw_json"] or {}
        timeline = record["timeline_json"] or {}
        try:
            features = analyze_match_timeline(match_id=match_id, match=match, timeline=timeline)
            await replace_match_participants(db=db, match_id=match_id, match=match)
            await replace_match_events(db=db, match_id=match_id, timeline=timeline)
            await replace_timeline_features(db=db, match_id=match_id, features=features)
            processed += 1
        except Exception as exc:  # noqa: BLE001 - one bad payload must not kill the backfill
            failed += 1
            logger.warning("Backfill skipped match %s: %s", match_id, exc)
            try:
                await db.rollback()
            except Exception:  # pragma: no cover
                pass
    return {"backfilled": processed, "failed": failed}


async def fetch_seed_puuids(db: AsyncSession, limit: int) -> list[str]:
    """Snowball seeds: registered summoners first, then recent participants."""
    seeds: list[str] = []
    seen: set[str] = set()

    summoners = await db.execute(select(Summoner.puuid))
    for (puuid,) in summoners.all():
        if puuid and puuid not in seen:
            seen.add(puuid)
            seeds.append(puuid)

    participants = await db.execute(
        select(MatchParticipant.puuid, RiotMatch.game_creation)
        .join(RiotMatch, RiotMatch.match_id == MatchParticipant.match_id)
        .order_by(desc(RiotMatch.game_creation), MatchParticipant.match_id, MatchParticipant.participant_id)
    )
    for puuid, _ in participants.all():
        if len(seeds) >= limit:
            break
        if puuid and puuid not in seen:
            seen.add(puuid)
            seeds.append(puuid)
    return seeds[:limit]


async def fetch_existing_match_ids(db: AsyncSession, match_ids: list[str]) -> set[str]:
    if not match_ids:
        return set()
    result = await db.execute(select(RiotMatch.match_id).where(RiotMatch.match_id.in_(match_ids)))
    return {row[0] for row in result.all()}


async def collect_new_matches(
    db: AsyncSession,
    client: RiotClient,
    *,
    queue_id: int = DEFAULT_QUEUE_ID,
    max_new_matches: int = DEFAULT_MAX_NEW_MATCHES,
    per_seed_count: int = DEFAULT_PER_SEED_COUNT,
    max_seeds: int = DEFAULT_MAX_SEEDS,
    ingest: Callable[..., Awaitable[None]] = ingest_single_match,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Ingest up to max_new_matches not-yet-stored matches from seed players."""
    settings = get_settings()
    seeds = await fetch_seed_puuids(db, limit=max_seeds)
    stats: dict[str, Any] = {
        "seeds_available": len(seeds),
        "seeds_used": 0,
        "new_matches": 0,
        "already_stored": 0,
        "failed": 0,
        "aborted": None,
    }
    seen_this_run: set[str] = set()

    for puuid in seeds:
        if stats["new_matches"] >= max_new_matches:
            break
        stats["seeds_used"] += 1
        try:
            match_ids = await client.get_match_ids(puuid, count=per_seed_count, queue=queue_id)
        except RiotApiError as exc:
            if exc.status_code in _ABORT_STATUSES:
                stats["aborted"] = f"riot key rejected ({exc.status_code}) — rotate RIOT_API_KEY"
                break
            stats["failed"] += 1
            logger.warning("Seed %s… match-id fetch failed: %s", puuid[:8], exc.message)
            continue

        fresh = [m for m in match_ids if m not in seen_this_run]
        seen_this_run.update(fresh)
        existing = await fetch_existing_match_ids(db, fresh)
        stats["already_stored"] += len(match_ids) - len(fresh) + len(existing)

        for match_id in fresh:
            if match_id in existing:
                continue
            if stats["new_matches"] >= max_new_matches:
                break
            try:
                await ingest(
                    db=db,
                    client=client,
                    puuid=puuid,
                    match_id=match_id,
                    platform_routing=settings.riot_platform_routing,
                )
                stats["new_matches"] += 1
            except RiotApiError as exc:
                if exc.status_code in _ABORT_STATUSES:
                    stats["aborted"] = f"riot key rejected ({exc.status_code}) — rotate RIOT_API_KEY"
                    break
                stats["failed"] += 1
                logger.warning("Collect skipped match %s: %s", match_id, exc.message)
                await _safe_rollback(db)
            except Exception as exc:  # noqa: BLE001 - one bad match must not kill the run
                stats["failed"] += 1
                logger.warning("Collect skipped match %s: %s", match_id, exc)
                await _safe_rollback(db)
            if on_progress:
                on_progress(dict(stats))
        if stats["aborted"]:
            break
    return stats


async def _safe_rollback(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:  # pragma: no cover
        pass


def main() -> None:
    from app.core.database import AsyncSessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", action="store_true", help="recompute derived tables only (no API)")
    parser.add_argument("--max-new", type=int, default=DEFAULT_MAX_NEW_MATCHES)
    parser.add_argument("--per-seed", type=int, default=DEFAULT_PER_SEED_COUNT)
    parser.add_argument("--max-seeds", type=int, default=DEFAULT_MAX_SEEDS)
    parser.add_argument("--queue", type=int, default=DEFAULT_QUEUE_ID)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            if args.backfill:
                stats = await backfill_derived_tables(db)
                print(f"backfill: {stats}")
                return
            client = RiotClient()

            def progress(s: dict[str, Any]) -> None:
                if s["new_matches"] and s["new_matches"] % 10 == 0:
                    print(f"progress: {s['new_matches']} new matches (failed {s['failed']})")

            stats = await collect_new_matches(
                db,
                client,
                queue_id=args.queue,
                max_new_matches=args.max_new,
                per_seed_count=args.per_seed,
                max_seeds=args.max_seeds,
                on_progress=progress,
            )
            print(f"collect: {stats}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
