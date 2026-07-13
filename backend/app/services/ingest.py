"""Background multi-match ingestion (master-plan M2).

A queued IngestJob is processed by an asyncio task with its own DB session:
for each recent match it persists normalized data and computes per-match
metrics (custom + habit) WITHOUT LLM enrichment — batch work must not spend
LLM tokens; interactive review enriches on demand.
"""

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.analysis import IngestJob
from app.repositories.analysis import replace_match_metric_scores, replace_match_moments
from app.repositories.matches import (
    replace_match_events,
    replace_match_participants,
    replace_timeline_features,
    upsert_player_skill_score,
)
from app.services.custom_metrics import METRIC_VERSION, PlayerAnalysisError, analyze_player_match
from app.services.habit_metrics import merge_habit_metrics
from app.services.key_events import extract_key_events
from app.services.match_data import get_match_cached, get_timeline_cached
from app.services.riot_client import RiotApiError, RiotClient
from app.services.timeline_analyzer import analyze_match_timeline

logger = logging.getLogger(__name__)

RANKED_SOLO_QUEUE_ID = 420

# Keep references so fire-and-forget tasks are not garbage collected mid-run.
_running_tasks: set[asyncio.Task] = set()


async def create_ingest_job(db: AsyncSession, puuid: str, requested_count: int) -> IngestJob:
    job = IngestJob(
        puuid=puuid,
        job_type="match_history",
        requested_count=requested_count,
        state="queued",
        progress=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


def start_ingest_task(job_id: int, puuid: str, count: int, queue: int | None) -> None:
    task = asyncio.create_task(run_ingest_job(job_id=job_id, puuid=puuid, count=count, queue=queue))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def run_ingest_job(job_id: int, puuid: str, count: int, queue: int | None) -> None:
    settings = get_settings()
    client = RiotClient()

    async with AsyncSessionLocal() as db:
        await _update_job(db, job_id, state="running", progress=0)

        try:
            match_ids = await client.get_match_ids(puuid, count=count, queue=queue)
        except RiotApiError as exc:
            await _update_job(db, job_id, state="failed", error=exc.message)
            return

        if not match_ids:
            await _update_job(db, job_id, state="done", progress=100)
            return

        processed = 0
        failed = 0
        for match_id in match_ids:
            try:
                await ingest_single_match(
                    db=db,
                    client=client,
                    puuid=puuid,
                    match_id=match_id,
                    platform_routing=settings.riot_platform_routing,
                )
            except Exception as exc:  # noqa: BLE001 - one bad match must not kill the job
                failed += 1
                logger.warning("Ingest skipped match %s: %s", match_id, exc)
                try:
                    await db.rollback()
                except Exception:  # pragma: no cover
                    pass
            processed += 1
            await _update_job(db, job_id, progress=round(processed * 100 / len(match_ids)))

        error = f"{failed} of {len(match_ids)} matches failed" if failed else None
        await _update_job(db, job_id, state="done", progress=100, error=error)


async def ingest_single_match(
    db: AsyncSession,
    client: RiotClient,
    puuid: str,
    match_id: str,
    platform_routing: str,
) -> None:
    match, _ = await get_match_cached(db, client, match_id, platform_routing)
    timeline, _ = await get_timeline_cached(db, client, match_id)

    features = analyze_match_timeline(match_id=match_id, match=match, timeline=timeline)
    await replace_match_participants(db=db, match_id=match_id, match=match)
    await replace_match_events(db=db, match_id=match_id, timeline=timeline)
    await replace_timeline_features(db=db, match_id=match_id, features=features)

    try:
        analysis = analyze_player_match(
            match_id=match_id,
            puuid=puuid,
            match=match,
            timeline=timeline,
            features=features,
        )
    except PlayerAnalysisError:
        return

    analysis = merge_habit_metrics(analysis=analysis, match=match, timeline=timeline, features=features)
    key_events = extract_key_events(match=match, timeline=timeline, puuid=puuid)

    await upsert_player_skill_score(db=db, analysis=analysis)
    await replace_match_metric_scores(db=db, analysis=analysis, metric_version=METRIC_VERSION)
    await replace_match_moments(db=db, match_id=match_id, puuid=puuid, key_events=key_events)


async def _update_job(
    db: AsyncSession,
    job_id: int,
    state: str | None = None,
    progress: int | None = None,
    error: str | None = None,
) -> None:
    try:
        job = await db.get(IngestJob, job_id)
        if job is None:
            return
        if state is not None:
            job.state = state
        if progress is not None:
            job.progress = progress
        if error is not None:
            job.error = error[:2000]
        await db.commit()
    except Exception as exc:  # pragma: no cover - job bookkeeping must not crash the pipeline
        logger.warning("Ingest job %s status update failed: %s", job_id, exc)
        try:
            await db.rollback()
        except Exception:  # pragma: no cover
            pass


def job_to_dict(job: IngestJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "puuid": job.puuid,
        "job_type": job.job_type,
        "requested_count": job.requested_count,
        "state": job.state,
        "progress": job.progress,
        "error": job.error,
    }
