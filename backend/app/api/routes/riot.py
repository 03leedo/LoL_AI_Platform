from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.repositories.matches import (
    replace_match_events,
    replace_match_participants,
    replace_timeline_features,
    upsert_match,
)
from app.repositories.summoners import upsert_summoner
from app.schemas.riot import (
    AccountResponse,
    MatchIdsResponse,
    MatchTimelineAnalysisResponse,
    SummonerLookupResponse,
)
from app.services.riot_client import RiotApiError, RiotClient
from app.services.timeline_analyzer import analyze_match_timeline

router = APIRouter()


def riot_error_to_http(exc: RiotApiError) -> HTTPException:
    status_code = exc.status_code if exc.status_code >= 400 else 502
    if exc.status_code == 0:
        status_code = 503
    return HTTPException(status_code=status_code, detail=exc.message)


@router.get("/account/{game_name}/{tag_line}", response_model=AccountResponse)
async def get_account(game_name: str, tag_line: str) -> AccountResponse:
    client = RiotClient()

    try:
        account = await client.get_account_by_riot_id(game_name, tag_line)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    return AccountResponse(
        puuid=account["puuid"],
        game_name=account.get("gameName", game_name),
        tag_line=account.get("tagLine", tag_line),
    )


@router.get("/summoner/{game_name}/{tag_line}", response_model=SummonerLookupResponse)
async def get_summoner(
    game_name: str,
    tag_line: str,
    db: AsyncSession = Depends(get_db),
) -> SummonerLookupResponse:
    settings = get_settings()
    client = RiotClient()

    try:
        account = await client.get_account_by_riot_id(game_name, tag_line)
        summoner = await client.get_summoner_by_puuid(account["puuid"])
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    saved = await upsert_summoner(
        db=db,
        account=account,
        summoner=summoner,
        platform_routing=settings.riot_platform_routing,
    )

    return SummonerLookupResponse(
        account=AccountResponse(
            puuid=account["puuid"],
            game_name=account.get("gameName", game_name),
            tag_line=account.get("tagLine", tag_line),
        ),
        summoner=saved,
    )


@router.get("/summoner/{game_name}/{tag_line}/matches", response_model=MatchIdsResponse)
async def get_recent_match_ids(
    game_name: str,
    tag_line: str,
    count: int = Query(default=10, ge=1, le=20),
) -> MatchIdsResponse:
    client = RiotClient()

    try:
        account = await client.get_account_by_riot_id(game_name, tag_line)
        match_ids = await client.get_match_ids(account["puuid"], count=count)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    return MatchIdsResponse(puuid=account["puuid"], match_ids=match_ids)


@router.get("/matches/{match_id}")
async def get_match_detail(match_id: str) -> dict[str, Any]:
    client = RiotClient()

    try:
        return await client.get_match(match_id)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc


@router.get("/matches/{match_id}/timeline", response_model=MatchTimelineAnalysisResponse)
async def get_match_timeline_analysis(
    match_id: str,
    db: AsyncSession = Depends(get_db),
) -> MatchTimelineAnalysisResponse:
    settings = get_settings()
    client = RiotClient()

    try:
        match = await client.get_match(match_id)
        timeline = await client.get_match_timeline(match_id)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    features = analyze_match_timeline(match_id=match_id, match=match, timeline=timeline)
    await upsert_match(
        db=db,
        match_id=match_id,
        match=match,
        platform_routing=settings.riot_platform_routing,
    )
    await replace_match_participants(db=db, match_id=match_id, match=match)
    await replace_match_events(db=db, match_id=match_id, timeline=timeline)
    saved_frames = await replace_timeline_features(db=db, match_id=match_id, features=features)

    return MatchTimelineAnalysisResponse(
        match_id=match_id,
        frame_count=len(saved_frames),
        frames=saved_frames,
    )
