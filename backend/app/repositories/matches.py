from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import MatchEvent, MatchParticipant, MatchTimelineFeature, RiotMatch
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


async def replace_match_participants(
    db: AsyncSession,
    match_id: str,
    match: dict[str, Any],
) -> None:
    await db.execute(delete(MatchParticipant).where(MatchParticipant.match_id == match_id))

    rows = [
        MatchParticipant(
            match_id=match_id,
            participant_id=int(participant.get("participantId") or 0),
            puuid=participant.get("puuid", ""),
            team_id=int(participant.get("teamId") or 0),
            champion_id=participant.get("championId"),
            champion_name=participant.get("championName"),
            team_position=participant.get("teamPosition"),
            individual_position=participant.get("individualPosition"),
            win=participant.get("win"),
            kills=participant.get("kills"),
            deaths=participant.get("deaths"),
            assists=participant.get("assists"),
            damage_to_champions=participant.get("totalDamageDealtToChampions"),
            damage_taken=participant.get("totalDamageTaken"),
            vision_score=participant.get("visionScore"),
            gold_earned=participant.get("goldEarned"),
            total_minions_killed=participant.get("totalMinionsKilled"),
            neutral_minions_killed=participant.get("neutralMinionsKilled"),
            raw_json=participant,
        )
        for participant in match.get("info", {}).get("participants", [])
        if participant.get("participantId") is not None and participant.get("puuid")
    ]
    db.add_all(rows)


async def replace_match_events(
    db: AsyncSession,
    match_id: str,
    timeline: dict[str, Any],
) -> None:
    await db.execute(delete(MatchEvent).where(MatchEvent.match_id == match_id))

    rows: list[MatchEvent] = []
    event_sequence = 0
    for frame_index, frame in enumerate(timeline.get("info", {}).get("frames", [])):
        for event_index, event in enumerate(frame.get("events", [])):
            timestamp_ms = int(event.get("timestamp") or frame.get("timestamp") or 0)
            position = event.get("position") or {}
            participant_id = event.get("participantId") or event.get("killerId")
            rows.append(
                MatchEvent(
                    match_id=match_id,
                    event_sequence=event_sequence,
                    frame_index=frame_index,
                    event_index=event_index,
                    timestamp_ms=timestamp_ms,
                    minute=timestamp_ms // 60000,
                    event_type=event.get("type", "UNKNOWN"),
                    participant_id=participant_id,
                    killer_id=event.get("killerId"),
                    victim_id=event.get("victimId"),
                    killer_team_id=event.get("killerTeamId"),
                    team_id=event.get("teamId"),
                    monster_type=event.get("monsterType"),
                    building_type=event.get("buildingType"),
                    lane_type=event.get("laneType"),
                    position_x=position.get("x"),
                    position_y=position.get("y"),
                    assisting_participant_ids=event.get("assistingParticipantIds"),
                    raw_json=event,
                )
            )
            event_sequence += 1

    db.add_all(rows)


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
