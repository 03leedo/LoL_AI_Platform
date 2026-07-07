from typing import Any

BLUE_TEAM_ID = 100
RED_TEAM_ID = 200
DEFAULT_EVENT_LIMIT = 28


def extract_key_events(
    match: dict[str, Any],
    timeline: dict[str, Any],
    puuid: str,
    limit: int = DEFAULT_EVENT_LIMIT,
) -> list[dict[str, Any]]:
    participants = _participant_index(match)
    player_id = _participant_id_for_puuid(participants, puuid)
    frames = timeline.get("info", {}).get("frames", [])
    events: list[dict[str, Any]] = []
    sequence = 0

    for frame in frames:
        for raw_event in frame.get("events", []):
            parsed = _parse_key_event(raw_event, participants, frames, player_id)
            if parsed is not None:
                parsed["_sequence"] = sequence
                parsed["_priority"] = _event_priority(parsed)
                events.append(parsed)
            sequence += 1

    if len(events) > limit:
        events = sorted(events, key=lambda item: (item["_priority"], item["timestamp_ms"], item["_sequence"]))[:limit]

    events.sort(key=lambda item: (item["timestamp_ms"], item["_sequence"]))
    for event in events:
        event.pop("_priority", None)
        event.pop("_sequence", None)
        event.pop("_actor_ids", None)
    return events


def _parse_key_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
    player_id: int | None,
) -> dict[str, Any] | None:
    event_type = event.get("type")

    if event_type == "CHAMPION_KILL":
        return _champion_kill_event(event, participants, frames, player_id)
    if event_type == "ELITE_MONSTER_KILL":
        return _elite_monster_event(event, participants, frames, player_id)
    if event_type == "BUILDING_KILL":
        return _building_event(event, participants, frames, player_id)
    return None


def _champion_kill_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
    player_id: int | None,
) -> dict[str, Any]:
    timestamp_ms = _event_timestamp(event)
    minute = timestamp_ms // 60000
    killer_id = _optional_int(event.get("killerId"))
    victim_id = _optional_int(event.get("victimId"))
    assist_ids = _participant_ids(event.get("assistingParticipantIds"))
    actor_ids = [item for item in [killer_id, victim_id, *assist_ids] if item]
    team_id = _team_for_participant(participants, killer_id)

    killer_name = _champion_name(participants, killer_id)
    victim_name = _champion_name(participants, victim_id)
    if killer_id:
        title = f"{killer_name} -> {victim_name} 처치"
        description = f"{_team_phrase(team_id)}이 {minute}분에 킬을 기록했습니다."
    else:
        title = f"{victim_name} 사망"
        description = f"{minute}분에 사망 이벤트가 기록됐습니다."

    if assist_ids:
        assist_names = ", ".join(_champion_name(participants, assist_id) for assist_id in assist_ids[:4])
        description += f" 어시스트: {assist_names}."
    if _optional_int(event.get("shutdownBounty")):
        description += " 제압골이 포함되어 결과적으로 손해가 커졌을 가능성이 높습니다."

    return _event_payload(
        key_type="kill",
        timestamp_ms=timestamp_ms,
        title=title,
        description=description,
        team_id=team_id,
        event=event,
        participants=participants,
        frames=frames,
        actor_ids=actor_ids,
        player_id=player_id,
    )


def _elite_monster_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
    player_id: int | None,
) -> dict[str, Any] | None:
    monster_type = event.get("monsterType")
    key_type = _monster_key(monster_type)
    if key_type is None:
        return None

    timestamp_ms = _event_timestamp(event)
    minute = timestamp_ms // 60000
    killer_id = _optional_int(event.get("killerId"))
    team_id = _optional_int(event.get("killerTeamId")) or _team_for_participant(participants, killer_id)
    label = _monster_label(monster_type, event.get("monsterSubType"))
    description = f"{_team_phrase(team_id)}이 {minute}분에 {label}을 확보했습니다."

    return _event_payload(
        key_type=key_type,
        timestamp_ms=timestamp_ms,
        title=f"{label} 처치",
        description=description,
        team_id=team_id,
        event=event,
        participants=participants,
        frames=frames,
        actor_ids=[killer_id] if killer_id else [],
        player_id=player_id,
    )


def _building_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
    player_id: int | None,
) -> dict[str, Any] | None:
    building_type = event.get("buildingType")
    key_type = _building_key(building_type)
    if key_type is None:
        return None

    timestamp_ms = _event_timestamp(event)
    minute = timestamp_ms // 60000
    destroyed_team_id = _optional_int(event.get("teamId"))
    scoring_team_id = _opponent_team_id(destroyed_team_id)
    killer_id = _optional_int(event.get("killerId"))
    lane = _lane_label(event.get("laneType"))
    label = _building_label(building_type)
    target = f"{lane} {label}" if lane else label
    description = f"{_team_phrase(scoring_team_id)}이 {minute}분에 {target}를 파괴했습니다."

    return _event_payload(
        key_type=key_type,
        timestamp_ms=timestamp_ms,
        title=f"{target} 파괴",
        description=description,
        team_id=scoring_team_id,
        event=event,
        participants=participants,
        frames=frames,
        actor_ids=[killer_id] if killer_id else [],
        player_id=player_id,
    )


def _event_payload(
    key_type: str,
    timestamp_ms: int,
    title: str,
    description: str,
    team_id: int | None,
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
    actor_ids: list[int],
    player_id: int | None,
) -> dict[str, Any]:
    position = event.get("position") or {}
    return {
        "minute": timestamp_ms // 60000,
        "timestamp_ms": timestamp_ms,
        "type": key_type,
        "title": title,
        "description": description,
        "team": _team_key(team_id),
        "position_x": _optional_int(position.get("x")),
        "position_y": _optional_int(position.get("y")),
        "participants": _participant_snapshot(
            participants=participants,
            frames=frames,
            timestamp_ms=timestamp_ms,
            actor_ids=actor_ids,
            player_id=player_id,
        ),
        "_actor_ids": set(actor_ids),
    }


def _participant_snapshot(
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
    timestamp_ms: int,
    actor_ids: list[int],
    player_id: int | None,
) -> list[dict[str, Any]]:
    frame = _nearest_frame(frames, timestamp_ms)
    participant_frames = frame.get("participantFrames", {}) if frame else {}
    actor_set = set(actor_ids)
    snapshot: list[dict[str, Any]] = []

    for participant_id, participant in sorted(participants.items()):
        participant_frame = participant_frames.get(str(participant_id)) or participant_frames.get(participant_id) or {}
        position = participant_frame.get("position") or {}
        snapshot.append(
            {
                "participant_id": participant_id,
                "team": _team_key(_optional_int(participant.get("teamId"))),
                "champion_name": participant.get("championName"),
                "is_player": participant_id == player_id,
                "is_actor": participant_id in actor_set,
                "x": _optional_int(position.get("x")),
                "y": _optional_int(position.get("y")),
            }
        )

    return snapshot


def _event_priority(event: dict[str, Any]) -> int:
    actor_ids = event.get("_actor_ids") or set()
    player_actor = any(item.get("is_player") and item.get("is_actor") for item in event.get("participants", []))
    if player_actor:
        return 0
    if event["type"] in {"dragon", "herald", "baron", "voidgrub", "atakhan"}:
        return 1
    if event["type"] in {"tower", "inhibitor"}:
        return 2
    if actor_ids:
        return 3
    return 4


def _nearest_frame(frames: list[dict[str, Any]], timestamp_ms: int) -> dict[str, Any] | None:
    if not frames:
        return None
    return min(frames, key=lambda frame: abs((_optional_int(frame.get("timestamp")) or 0) - timestamp_ms))


def _participant_index(match: dict[str, Any]) -> dict[int, dict[str, Any]]:
    index: dict[int, dict[str, Any]] = {}
    for participant in match.get("info", {}).get("participants", []):
        participant_id = _optional_int(participant.get("participantId"))
        if participant_id is not None:
            index[participant_id] = participant
    return index


def _participant_id_for_puuid(participants: dict[int, dict[str, Any]], puuid: str) -> int | None:
    for participant_id, participant in participants.items():
        if participant.get("puuid") == puuid:
            return participant_id
    return None


def _team_for_participant(participants: dict[int, dict[str, Any]], participant_id: int | None) -> int | None:
    if participant_id is None or participant_id == 0:
        return None
    participant = participants.get(participant_id)
    if participant:
        return _optional_int(participant.get("teamId"))
    if 1 <= participant_id <= 10:
        return BLUE_TEAM_ID if participant_id <= 5 else RED_TEAM_ID
    return None


def _champion_name(participants: dict[int, dict[str, Any]], participant_id: int | None) -> str:
    if not participant_id:
        return "Unknown"
    participant = participants.get(participant_id)
    if participant and participant.get("championName"):
        return str(participant["championName"])
    return f"P{participant_id}"


def _participant_ids(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    ids: list[int] = []
    for value in values:
        parsed = _optional_int(value)
        if parsed is not None:
            ids.append(parsed)
    return ids


def _event_timestamp(event: dict[str, Any]) -> int:
    return _optional_int(event.get("timestamp")) or 0


def _optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _team_key(team_id: int | None) -> str:
    if team_id == BLUE_TEAM_ID:
        return "blue"
    if team_id == RED_TEAM_ID:
        return "red"
    return "neutral"


def _team_phrase(team_id: int | None) -> str:
    if team_id == BLUE_TEAM_ID:
        return "블루 팀"
    if team_id == RED_TEAM_ID:
        return "레드 팀"
    return "한 팀"


def _opponent_team_id(team_id: int | None) -> int | None:
    if team_id == BLUE_TEAM_ID:
        return RED_TEAM_ID
    if team_id == RED_TEAM_ID:
        return BLUE_TEAM_ID
    return None


def _monster_key(monster_type: str | None) -> str | None:
    labels = {
        "DRAGON": "dragon",
        "RIFTHERALD": "herald",
        "BARON_NASHOR": "baron",
        "HORDE": "voidgrub",
        "ATAKHAN": "atakhan",
    }
    return labels.get(str(monster_type))


def _monster_label(monster_type: str | None, monster_sub_type: str | None) -> str:
    dragon_labels = {
        "AIR_DRAGON": "바람 드래곤",
        "CHEMTECH_DRAGON": "화학공학 드래곤",
        "EARTH_DRAGON": "대지 드래곤",
        "FIRE_DRAGON": "화염 드래곤",
        "HEXTECH_DRAGON": "마법공학 드래곤",
        "WATER_DRAGON": "바다 드래곤",
        "ELDER_DRAGON": "장로 드래곤",
    }
    if monster_type == "DRAGON" and monster_sub_type in dragon_labels:
        return dragon_labels[monster_sub_type]

    labels = {
        "DRAGON": "드래곤",
        "RIFTHERALD": "전령",
        "BARON_NASHOR": "바론",
        "HORDE": "공허 유충",
        "ATAKHAN": "아타칸",
    }
    return labels.get(str(monster_type), "오브젝트")


def _building_key(building_type: str | None) -> str | None:
    labels = {
        "TOWER_BUILDING": "tower",
        "INHIBITOR_BUILDING": "inhibitor",
    }
    return labels.get(str(building_type))


def _building_label(building_type: str | None) -> str:
    labels = {
        "TOWER_BUILDING": "타워",
        "INHIBITOR_BUILDING": "억제기",
    }
    return labels.get(str(building_type), "건물")


def _lane_label(lane_type: str | None) -> str | None:
    labels = {
        "TOP_LANE": "탑",
        "MID_LANE": "미드",
        "BOT_LANE": "바텀",
    }
    return labels.get(str(lane_type))
