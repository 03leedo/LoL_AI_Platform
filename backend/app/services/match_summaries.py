from typing import Any


def summarize_match_for_player(
    match_id: str,
    puuid: str,
    match: dict[str, Any],
) -> dict[str, Any] | None:
    participant = next(
        (
            item
            for item in match.get("info", {}).get("participants", [])
            if item.get("puuid") == puuid
        ),
        None,
    )
    if participant is None:
        return None

    info = match.get("info", {})
    participants = info.get("participants", [])
    team_id = participant.get("teamId")
    team_kills = sum(
        _safe_int(item.get("kills"))
        for item in participants
        if isinstance(item, dict) and item.get("teamId") == team_id
    )
    kills = _safe_int(participant.get("kills"))
    assists = _safe_int(participant.get("assists"))
    kill_participation = round(((kills + assists) / team_kills) * 100) if team_kills else None

    return {
        "match_id": match_id,
        "queue_id": info.get("queueId"),
        "game_creation": info.get("gameCreation"),
        "game_duration": info.get("gameDuration"),
        "champion_name": participant.get("championName"),
        "team_position": participant.get("teamPosition") or participant.get("individualPosition"),
        "win": participant.get("win"),
        "kills": participant.get("kills"),
        "deaths": participant.get("deaths"),
        "assists": participant.get("assists"),
        "total_minions_killed": participant.get("totalMinionsKilled"),
        "neutral_minions_killed": participant.get("neutralMinionsKilled"),
        "vision_score": participant.get("visionScore"),
        "total_damage_dealt_to_champions": participant.get("totalDamageDealtToChampions"),
        "total_damage_taken": participant.get("totalDamageTaken"),
        "gold_earned": participant.get("goldEarned"),
        "kill_participation": kill_participation,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
