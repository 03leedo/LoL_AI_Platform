from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import MatchTimelineFeature, RiotMatch
from app.schemas.riot import TimelineFrameFeatureResponse


async def upsert_match(
    db: AsyncSession,
    match_id: str,
    match: dict[str, Any],
    platform_routing: str,
) -> None:
    info = match.get("info", {})
    riot_match = RiotMatch(
        match_id=match_id,
        platform_routing=platform_routing,
        queue_id=info.get("queueId"),
        game_creation=info.get("gameCreation"),
        game_duration=info.get("gameDuration"),
        raw_json=match,
    )
    await db.merge(riot_match)


async def replace_timeline_features(
    db: AsyncSession,
    match_id: str,
    features: list[dict[str, Any]],
) -> list[TimelineFrameFeatureResponse]:
    await db.execute(delete(MatchTimelineFeature).where(MatchTimelineFeature.match_id == match_id))

    rows = [MatchTimelineFeature(**feature) for feature in features]
    db.add_all(rows)
    await db.commit()

    return [
        TimelineFrameFeatureResponse(
            match_id=row.match_id,
            minute=row.minute,
            timestamp_ms=row.timestamp_ms,
            blue_gold=row.blue_gold,
            red_gold=row.red_gold,
            gold_diff=row.gold_diff,
            blue_xp=row.blue_xp,
            red_xp=row.red_xp,
            xp_diff=row.xp_diff,
            blue_cs=row.blue_cs,
            red_cs=row.red_cs,
            cs_diff=row.cs_diff,
            blue_tower_kills=row.blue_tower_kills,
            red_tower_kills=row.red_tower_kills,
            blue_dragon_kills=row.blue_dragon_kills,
            red_dragon_kills=row.red_dragon_kills,
            blue_herald_kills=row.blue_herald_kills,
            red_herald_kills=row.red_herald_kills,
            blue_baron_kills=row.blue_baron_kills,
            red_baron_kills=row.red_baron_kills,
        )
        for row in rows
    ]
