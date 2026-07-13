from typing import Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.analysis import IngestJob
from app.repositories.analysis import (
    fetch_player_match_records,
    replace_aggregate_scores,
    replace_match_metric_scores,
    replace_match_moments,
)
from app.repositories.matches import (
    replace_match_events,
    replace_match_participants,
    replace_timeline_features,
    upsert_player_skill_score,
)
from app.repositories.summoners import upsert_summoner
from app.schemas.riot import (
    AccountResponse,
    IngestJobResponse,
    MatchIdsResponse,
    MatchPlayerAnalysisResponse,
    MatchReviewResponse,
    MatchSummaryResponse,
    MatchTimelineAnalysisResponse,
    RankAnalysisResponse,
    RoleFitResponse,
    ScorecardResponse,
    SummonerHeatmapResponse,
    SummonerLookupResponse,
    SummonerMatchHistoryResponse,
    TimelineFrameFeatureResponse,
)
from app.services.custom_metrics import METRIC_VERSION, PlayerAnalysisError, analyze_player_match
from app.services.evidence_contexts import attach_evidence_contexts, build_review_assets
from app.services.habit_metrics import merge_habit_metrics
from app.services.heatmaps import build_summoner_heatmap
from app.services.ingest import create_ingest_job, job_to_dict, start_ingest_task
from app.services.key_events import extract_key_events
from app.services.role_analyzer import build_role_analysis, role_analysis_to_aggregate_rows
from app.services.scorecard import build_scorecard, scorecard_to_aggregate_rows
from app.services.turning_points import detect_turning_points
from app.services.llm_feedback import LlmFeedbackError, enrich_analysis_with_llm_feedback
from app.services.match_data import get_match_cached, get_timeline_cached
from app.services.match_summaries import summarize_match_for_player
from app.services.win_probability import build_win_curve
from app.services.riot_client import RiotApiError, RiotClient
from app.services.timeline_analyzer import analyze_match_timeline

router = APIRouter()
logger = logging.getLogger(__name__)


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

    try:
        league_entries = await client.get_league_entries_by_puuid(account["puuid"])
    except RiotApiError as exc:
        logger.warning("League lookup skipped for %s: %s", account["puuid"], exc.message)
        league_entries = None

    saved = await upsert_summoner(
        db=db,
        account=account,
        summoner=summoner,
        platform_routing=settings.riot_platform_routing,
        league_entries=league_entries,
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


@router.get("/summoner/{game_name}/{tag_line}/match-history", response_model=SummonerMatchHistoryResponse)
async def get_match_history(
    game_name: str,
    tag_line: str,
    count: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> SummonerMatchHistoryResponse:
    settings = get_settings()
    client = RiotClient()

    try:
        account = await client.get_account_by_riot_id(game_name, tag_line)
        match_ids = await client.get_match_ids(account["puuid"], count=count)
        matches = [
            (await get_match_cached(db, client, match_id, settings.riot_platform_routing))[0]
            for match_id in match_ids
        ]
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    summaries: list[MatchSummaryResponse] = []
    for match_id, match in zip(match_ids, matches, strict=False):
        try:
            await replace_match_participants(db=db, match_id=match_id, match=match)
        except Exception as exc:  # pragma: no cover - listing should survive local DB drift
            await db.rollback()
            logger.warning("Match history persistence skipped for %s: %s", match_id, exc)
        summary = summarize_match_for_player(match_id=match_id, puuid=account["puuid"], match=match)
        if summary:
            summaries.append(MatchSummaryResponse(**summary))

    try:
        await db.commit()
    except Exception as exc:  # pragma: no cover - listing can still return Riot summaries
        await db.rollback()
        logger.warning("Match history commit skipped: %s", exc)
    return SummonerMatchHistoryResponse(
        account=AccountResponse(
            puuid=account["puuid"],
            game_name=account.get("gameName", game_name),
            tag_line=account.get("tagLine", tag_line),
        ),
        matches=summaries,
    )


@router.get("/summoner/{game_name}/{tag_line}/heatmap", response_model=SummonerHeatmapResponse)
async def get_summoner_heatmap(
    game_name: str,
    tag_line: str,
    count: int = Query(default=10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> SummonerHeatmapResponse:
    settings = get_settings()
    client = RiotClient()

    try:
        account = await client.get_account_by_riot_id(game_name, tag_line)
        match_ids = await client.get_match_ids(account["puuid"], count=count)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    heatmap = await build_summoner_heatmap(
        db=db,
        client=client,
        puuid=account["puuid"],
        match_ids=match_ids,
        platform_routing=settings.riot_platform_routing,
    )
    return SummonerHeatmapResponse(**heatmap)


@router.post("/summoner/{game_name}/{tag_line}/ingest", response_model=IngestJobResponse)
async def start_summoner_ingest(
    game_name: str,
    tag_line: str,
    count: int = Query(default=20, ge=1, le=30),
    queue: int = Query(default=420, ge=0, description="Riot queue id filter; 0 disables the filter"),
    db: AsyncSession = Depends(get_db),
) -> IngestJobResponse:
    client = RiotClient()

    try:
        account = await client.get_account_by_riot_id(game_name, tag_line)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    job = await create_ingest_job(db=db, puuid=account["puuid"], requested_count=count)
    start_ingest_task(job_id=job.id, puuid=account["puuid"], count=count, queue=queue or None)
    return IngestJobResponse(**job_to_dict(job))


@router.get("/ingest-jobs/{job_id}", response_model=IngestJobResponse)
async def get_ingest_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> IngestJobResponse:
    job = await db.get(IngestJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    return IngestJobResponse(**job_to_dict(job))


@router.get("/summoner/{game_name}/{tag_line}/rank-analysis", response_model=RankAnalysisResponse)
async def get_rank_analysis(
    game_name: str,
    tag_line: str,
    window: int = Query(default=20, ge=5, le=30),
    db: AsyncSession = Depends(get_db),
) -> RankAnalysisResponse:
    client = RiotClient()

    try:
        account = await client.get_account_by_riot_id(game_name, tag_line)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    puuid = account["puuid"]
    records = await fetch_player_match_records(db=db, puuid=puuid, limit=window)
    scorecard = build_scorecard(records)
    role_analysis = build_role_analysis(records)

    window_key = f"recent{window}"
    try:
        await replace_aggregate_scores(
            db=db,
            puuid=puuid,
            window=window_key,
            rows=scorecard_to_aggregate_rows(scorecard) + role_analysis_to_aggregate_rows(role_analysis),
            metric_version=METRIC_VERSION,
        )
    except Exception as exc:  # pragma: no cover - analysis should still be returned
        logger.warning("Aggregate persistence skipped for %s: %s", puuid, exc)
        try:
            await db.rollback()
        except Exception:  # pragma: no cover
            pass

    return RankAnalysisResponse(
        puuid=puuid,
        window=window_key,
        games_analyzed=len(records),
        needs_ingest=len(records) < 5,
        scorecard=ScorecardResponse(**scorecard),
        roles=[RoleFitResponse(**role) for role in role_analysis["roles"]],
        recommended=role_analysis["recommended"],
        caution=role_analysis["caution"],
    )


@router.get("/matches/{match_id}")
async def get_match_detail(
    match_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    settings = get_settings()
    client = RiotClient()

    try:
        match, _ = await get_match_cached(db, client, match_id, settings.riot_platform_routing)
        return match
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
        match, _ = await get_match_cached(db, client, match_id, settings.riot_platform_routing)
        timeline, _ = await get_timeline_cached(db, client, match_id)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    features = analyze_match_timeline(match_id=match_id, match=match, timeline=timeline)
    await replace_match_participants(db=db, match_id=match_id, match=match)
    await replace_match_events(db=db, match_id=match_id, timeline=timeline)
    saved_frames = await replace_timeline_features(db=db, match_id=match_id, features=features)

    return MatchTimelineAnalysisResponse(
        match_id=match_id,
        frame_count=len(saved_frames),
        frames=saved_frames,
        win_curve=build_win_curve(features),
    )


@router.get("/matches/{match_id}/review", response_model=MatchReviewResponse)
async def get_match_review(
    match_id: str,
    puuid: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> MatchReviewResponse:
    settings = get_settings()
    client = RiotClient()

    try:
        match, _ = await get_match_cached(db, client, match_id, settings.riot_platform_routing)
        timeline, _ = await get_timeline_cached(db, client, match_id)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

    features = analyze_match_timeline(match_id=match_id, match=match, timeline=timeline)
    try:
        analysis = analyze_player_match(
            match_id=match_id,
            puuid=puuid,
            match=match,
            timeline=timeline,
            features=features,
        )
    except PlayerAnalysisError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    analysis = merge_habit_metrics(analysis=analysis, match=match, timeline=timeline, features=features)
    analysis = attach_evidence_contexts(
        analysis=analysis,
        match=match,
        timeline=timeline,
        puuid=puuid,
    )
    try:
        analysis = await enrich_analysis_with_llm_feedback(analysis)
    except LlmFeedbackError as exc:
        logger.warning("LLM feedback skipped for %s: %s", match_id, exc)

    key_events = extract_key_events(match=match, timeline=timeline, puuid=puuid)
    assets = build_review_assets(match)
    win_curve = build_win_curve(features)
    turning_points = detect_turning_points(
        win_curve=win_curve,
        key_events=key_events,
        player_team=analysis["player"]["team"],
    )

    try:
        await replace_match_participants(db=db, match_id=match_id, match=match)
        await replace_match_events(db=db, match_id=match_id, timeline=timeline)
        saved_frames = await replace_timeline_features(db=db, match_id=match_id, features=features)
        await upsert_player_skill_score(db=db, analysis=analysis)
        await replace_match_metric_scores(db=db, analysis=analysis, metric_version=METRIC_VERSION)
        await replace_match_moments(db=db, match_id=match_id, puuid=puuid, key_events=key_events)
    except Exception as exc:  # pragma: no cover - review should still return computed analysis
        await db.rollback()
        logger.warning("Match review persistence skipped for %s: %s", match_id, exc)
        saved_frames = [TimelineFrameFeatureResponse(**feature) for feature in features]

    return MatchReviewResponse(
        timeline=MatchTimelineAnalysisResponse(
            match_id=match_id,
            frame_count=len(saved_frames),
            frames=saved_frames,
            win_curve=win_curve,
        ),
        analysis=MatchPlayerAnalysisResponse(**analysis),
        key_events=key_events,
        assets=assets,
        turning_points=turning_points,
    )


@router.get("/matches/{match_id}/analysis", response_model=MatchPlayerAnalysisResponse)
async def get_match_player_analysis(
    match_id: str,
    puuid: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> MatchPlayerAnalysisResponse:
    settings = get_settings()
    client = RiotClient()

    try:
        match, _ = await get_match_cached(db, client, match_id, settings.riot_platform_routing)
        timeline, _ = await get_timeline_cached(db, client, match_id)
    except RiotApiError as exc:
        raise riot_error_to_http(exc) from exc

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
    except PlayerAnalysisError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    analysis = merge_habit_metrics(analysis=analysis, match=match, timeline=timeline, features=features)
    analysis = attach_evidence_contexts(
        analysis=analysis,
        match=match,
        timeline=timeline,
        puuid=puuid,
    )
    try:
        analysis = await enrich_analysis_with_llm_feedback(analysis)
    except LlmFeedbackError as exc:
        logger.warning("LLM feedback skipped for %s: %s", match_id, exc)

    await upsert_player_skill_score(db=db, analysis=analysis)
    await replace_match_metric_scores(db=db, analysis=analysis, metric_version=METRIC_VERSION)
    return MatchPlayerAnalysisResponse(**analysis)
