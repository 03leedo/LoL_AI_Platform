"""Companion (C1) upload endpoints: collection-only live-game data.

Session ids are client-generated UUIDs (the Live Client API exposes no match
id); snapshot upload is idempotent so companion retries are safe.
"""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import LiveSession
from app.schemas.live import (
    LiveCompleteRequest,
    LiveSessionResponse,
    LiveSnapshotBatchRequest,
    LiveSnapshotBatchResponse,
)
from app.services.live_sessions import (
    complete_session,
    session_to_dict,
    store_snapshots,
    upsert_session,
)

router = APIRouter()

SESSION_ID = Path(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


@router.post("/sessions/{session_id}/snapshots", response_model=LiveSnapshotBatchResponse)
async def upload_snapshots(
    body: LiveSnapshotBatchRequest,
    session_id: str = SESSION_ID,
    db: AsyncSession = Depends(get_db),
) -> LiveSnapshotBatchResponse:
    stats = await store_snapshots(
        db=db,
        session_id=session_id,
        riot_id=body.riot_id,
        collector_version=body.collector_version,
        snapshots=[snapshot.model_dump() for snapshot in body.snapshots],
    )
    return LiveSnapshotBatchResponse(session_id=session_id, **stats)


@router.post("/sessions/{session_id}/complete", response_model=LiveSessionResponse)
async def mark_complete(
    body: LiveCompleteRequest,
    session_id: str = SESSION_ID,
    db: AsyncSession = Depends(get_db),
) -> LiveSessionResponse:
    await upsert_session(db, session_id, body.riot_id, body.collector_version)
    session = await complete_session(db, session_id, body.game_start_ms)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown live session")
    return LiveSessionResponse(**session_to_dict(session))


@router.get("/sessions/{session_id}", response_model=LiveSessionResponse)
async def get_session(
    session_id: str = SESSION_ID,
    db: AsyncSession = Depends(get_db),
) -> LiveSessionResponse:
    session = await db.get(LiveSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown live session")
    return LiveSessionResponse(**session_to_dict(session))
