from typing import Any


def find_participant(
    match: dict[str, Any],
    puuid: str,
    game_name: str | None = None,
    tag_line: str | None = None,
) -> dict[str, Any] | None:
    """Locate the player's participant entry in a match payload.

    Primary key is the puuid; matches cached under a previous API key carry
    puuids encrypted for that app, so a riot-id fallback (case-insensitive)
    keeps old cached matches readable after key rotation.
    """
    participants = match.get("info", {}).get("participants", [])
    for item in participants:
        if item.get("puuid") == puuid:
            return item
    if game_name and tag_line:
        name_key = game_name.strip().lower()
        tag_key = tag_line.strip().lower()
        for item in participants:
            if (
                str(item.get("riotIdGameName") or "").strip().lower() == name_key
                and str(item.get("riotIdTagline") or "").strip().lower() == tag_key
            ):
                return item
    return None


def summarize_match_for_player(
    match_id: str,
    puuid: str,
    match: dict[str, Any],
    game_name: str | None = None,
    tag_line: str | None = None,
) -> dict[str, Any] | None:
    participant = find_participant(match, puuid, game_name=game_name, tag_line=tag_line)
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
