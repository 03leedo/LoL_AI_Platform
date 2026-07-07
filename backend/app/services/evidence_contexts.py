from copy import deepcopy
from typing import Any

BLUE_TEAM_ID = 100
RED_TEAM_ID = 200
CONTEXT_WINDOW_MS = 30_000
MAP_SIZE = 15000


def attach_evidence_contexts(
    analysis: dict[str, Any],
    match: dict[str, Any],
    timeline: dict[str, Any],
    puuid: str,
) -> dict[str, Any]:
    enriched = deepcopy(analysis)
    participants = _participant_index(match)
    player_id = _participant_id_for_puuid(participants, puuid)
    player_team_id = _team_for_participant(participants, player_id)
    frames = timeline.get("info", {}).get("frames", [])
    events = _flatten_events(timeline)

    for evidence_index, evidence in enumerate(enriched.get("evidence", [])):
        context = _build_evidence_context(
            evidence_index=evidence_index,
            evidence=evidence,
            events=events,
            frames=frames,
            participants=participants,
            player_id=player_id,
            player_team_id=player_team_id,
        )
        if context is not None:
            evidence["context"] = context

    return enriched


def build_review_assets(match: dict[str, Any]) -> dict[str, Any]:
    info = match.get("info", {})
    return {
        "data_dragon_version": _data_dragon_version(info.get("gameVersion")),
        "map_id": int(info.get("mapId") or 11),
    }


def _build_evidence_context(
    evidence_index: int,
    evidence: dict[str, Any],
    events: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    participants: dict[int, dict[str, Any]],
    player_id: int | None,
    player_team_id: int | None,
) -> dict[str, Any] | None:
    if _is_neutral_evidence(evidence):
        return None

    anchor_timestamp_ms = _anchor_timestamp(evidence, events, participants, player_id, player_team_id)
    window_start_ms = max(0, anchor_timestamp_ms - CONTEXT_WINDOW_MS)
    window_end_ms = anchor_timestamp_ms + CONTEXT_WINDOW_MS
    context_events = [
        parsed
        for event in events
        if window_start_ms <= _event_timestamp(event) <= window_end_ms
        for parsed in [_parse_context_event(event, participants, frames)]
        if parsed is not None
    ]

    snapshot_frames = _frames_in_window(frames, window_start_ms, window_end_ms, anchor_timestamp_ms)
    snapshots = [
        _snapshot_from_frame(
            frame=frame,
            participants=participants,
            player_id=player_id,
            ward_events=context_events,
            all_events=events,
            anchor_timestamp_ms=anchor_timestamp_ms,
        )
        for frame in snapshot_frames
    ]

    if not snapshots and not context_events:
        return None

    return {
        "evidence_index": evidence_index,
        "anchor_timestamp_ms": anchor_timestamp_ms,
        "window_start_ms": window_start_ms,
        "window_end_ms": window_end_ms,
        "summary": _context_summary(context_events, player_team_id),
        "insights": _context_insights(context_events, player_team_id, anchor_timestamp_ms),
        "snapshots": snapshots,
        "events": context_events,
    }


def _anchor_timestamp(
    evidence: dict[str, Any],
    events: list[dict[str, Any]],
    participants: dict[int, dict[str, Any]],
    player_id: int | None,
    player_team_id: int | None,
) -> int:
    target_ms = int(evidence.get("minute") or 0) * 60_000
    kind = evidence.get("type")
    candidates: list[dict[str, Any]] = []

    if kind in {"death_cost", "throw_index"} and player_id is not None:
        candidates = [
            event
            for event in events
            if event.get("type") == "CHAMPION_KILL" and _optional_int(event.get("victimId")) == player_id
        ]
    elif kind == "objective_setup":
        candidates = [event for event in events if _is_objective_or_building(event)]
    elif kind == "lead_conversion":
        candidates = [
            event
            for event in events
            if _is_objective_or_building(event)
            and _team_for_context_event(event, participants) == player_team_id
        ]

    if not candidates:
        candidates = [event for event in events if _is_context_event(event)]

    if not candidates:
        return target_ms

    return _event_timestamp(min(candidates, key=lambda event: abs(_event_timestamp(event) - target_ms)))


def _parse_context_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
) -> dict[str, Any] | None:
    event_type = event.get("type")
    if event_type == "CHAMPION_KILL":
        return _kill_context_event(event, participants, frames)
    if event_type == "ELITE_MONSTER_KILL":
        return _monster_context_event(event, participants, frames)
    if event_type == "BUILDING_KILL":
        return _building_context_event(event, participants, frames)
    if event_type == "WARD_PLACED":
        return _ward_context_event(event, participants, frames, action="placed")
    if event_type == "WARD_KILL":
        return _ward_context_event(event, participants, frames, action="killed")
    return None


def _kill_context_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
) -> dict[str, Any]:
    timestamp_ms = _event_timestamp(event)
    killer_id = _optional_int(event.get("killerId"))
    victim_id = _optional_int(event.get("victimId"))
    assist_ids = _participant_ids(event.get("assistingParticipantIds"))
    team_id = _team_for_participant(participants, killer_id)
    x, y, source = _event_position(event, frames, timestamp_ms, killer_id or victim_id)
    killer_name = _champion_name(participants, killer_id)
    victim_name = _champion_name(participants, victim_id)
    title = f"{killer_name} -> {victim_name}"
    description = f"{_team_phrase(team_id)} 킬"
    if assist_ids:
        description += f" · 어시스트 {len(assist_ids)}"

    return _context_event_payload(
        timestamp_ms=timestamp_ms,
        event_type="kill",
        title=title,
        description=description,
        team_id=team_id,
        position_x=x,
        position_y=y,
        position_source=source,
        participant_ids=[item for item in [killer_id, victim_id, *assist_ids] if item],
        victim_team=_team_key(_team_for_participant(participants, victim_id)),
    )


def _monster_context_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
) -> dict[str, Any] | None:
    key = _monster_key(event.get("monsterType"))
    if key is None:
        return None

    timestamp_ms = _event_timestamp(event)
    killer_id = _optional_int(event.get("killerId"))
    team_id = _optional_int(event.get("killerTeamId")) or _team_for_participant(participants, killer_id)
    x, y, source = _objective_event_position(event, frames, timestamp_ms, killer_id)
    title = f"{_monster_label(event.get('monsterType'), event.get('monsterSubType'))} 처치"

    return _context_event_payload(
        timestamp_ms=timestamp_ms,
        event_type=key,
        title=title,
        description=f"{_team_phrase(team_id)} 확보",
        team_id=team_id,
        position_x=x,
        position_y=y,
        position_source=source,
        participant_ids=[killer_id] if killer_id else [],
    )


def _building_context_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
) -> dict[str, Any] | None:
    key = _building_key(event.get("buildingType"))
    if key is None:
        return None

    timestamp_ms = _event_timestamp(event)
    killer_id = _optional_int(event.get("killerId"))
    scoring_team_id = _opponent_team_id(_optional_int(event.get("teamId")))
    x, y, source = _event_position(event, frames, timestamp_ms, killer_id)
    lane = _lane_label(event.get("laneType"))
    label = _building_label(event.get("buildingType"))
    title = f"{lane + ' ' if lane else ''}{label} 파괴"

    return _context_event_payload(
        timestamp_ms=timestamp_ms,
        event_type=key,
        title=title,
        description=f"{_team_phrase(scoring_team_id)} 압박",
        team_id=scoring_team_id,
        position_x=x,
        position_y=y,
        position_source=source,
        participant_ids=[killer_id] if killer_id else [],
    )


def _ward_context_event(
    event: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    frames: list[dict[str, Any]],
    action: str,
) -> dict[str, Any]:
    timestamp_ms = _event_timestamp(event)
    participant_id = _optional_int(event.get("creatorId") if action == "placed" else event.get("killerId"))
    team_id = _team_for_participant(participants, participant_id)
    x, y, source = _event_position(event, frames, timestamp_ms, participant_id)
    ward_type = _ward_label(event.get("wardType"))
    title = f"{ward_type} {'설치' if action == 'placed' else '제거'}"

    return _context_event_payload(
        timestamp_ms=timestamp_ms,
        event_type=f"ward_{action}",
        title=title,
        description=f"{_team_phrase(team_id)} 시야 이벤트",
        team_id=team_id,
        position_x=x,
        position_y=y,
        position_source=source,
        participant_ids=[participant_id] if participant_id else [],
        ward_type=event.get("wardType"),
    )


def _context_event_payload(
    timestamp_ms: int,
    event_type: str,
    title: str,
    description: str,
    team_id: int | None,
    position_x: int | None,
    position_y: int | None,
    position_source: str,
    participant_ids: list[int],
    victim_team: str | None = None,
    ward_type: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp_ms": timestamp_ms,
        "minute": timestamp_ms // 60000,
        "type": event_type,
        "title": title,
        "description": description,
        "team": _team_key(team_id),
        "victim_team": victim_team,
        "ward_type": ward_type,
        "position_x": position_x,
        "position_y": position_y,
        "position_source": position_source,
        "participant_ids": participant_ids,
    }


def _snapshot_from_frame(
    frame: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    player_id: int | None,
    ward_events: list[dict[str, Any]],
    all_events: list[dict[str, Any]],
    anchor_timestamp_ms: int,
) -> dict[str, Any]:
    timestamp_ms = _optional_int(frame.get("timestamp")) or 0
    visible_ward_events = [
        event
        for event in ward_events
        if event["type"].startswith("ward_") and event["timestamp_ms"] <= timestamp_ms
    ]
    return {
        "timestamp_ms": timestamp_ms,
        "minute": timestamp_ms // 60000,
        "offset_seconds": round((timestamp_ms - anchor_timestamp_ms) / 1000),
        "participants": _snapshot_participants(frame, participants, player_id),
        "ward_events": visible_ward_events,
        "objective_state": _objective_state_at(all_events, participants, timestamp_ms),
    }


def _snapshot_participants(
    frame: dict[str, Any],
    participants: dict[int, dict[str, Any]],
    player_id: int | None,
) -> list[dict[str, Any]]:
    participant_frames = frame.get("participantFrames", {}) or {}
    snapshot: list[dict[str, Any]] = []

    for participant_id, participant in sorted(participants.items()):
        participant_frame = participant_frames.get(str(participant_id)) or participant_frames.get(participant_id) or {}
        position = participant_frame.get("position") or {}
        x = _bounded_map_coord(_optional_int(position.get("x")))
        y = _bounded_map_coord(_optional_int(position.get("y")))
        snapshot.append(
            {
                "participant_id": participant_id,
                "team": _team_key(_optional_int(participant.get("teamId"))),
                "champion_name": participant.get("championName"),
                "is_player": participant_id == player_id,
                "x": x,
                "y": y,
            }
        )

    return snapshot


def _context_summary(context_events: list[dict[str, Any]], player_team_id: int | None) -> dict[str, int]:
    player_team = _team_key(player_team_id)
    enemy_team = "red" if player_team == "blue" else "blue"
    ally_deaths = 0
    enemy_deaths = 0
    ally_ward_events = 0
    enemy_ward_events = 0
    objective_events = 0

    for event in context_events:
        if event["type"] == "kill":
            if event.get("victim_team") == player_team:
                ally_deaths += 1
            elif event.get("victim_team") == enemy_team:
                enemy_deaths += 1
        elif event["type"].startswith("ward_"):
            if event["team"] == player_team:
                ally_ward_events += 1
            elif event["team"] == enemy_team:
                enemy_ward_events += 1
        elif event["type"] in {"dragon", "herald", "baron", "tower", "inhibitor", "voidgrub", "atakhan"}:
            objective_events += 1

    return {
        "ally_deaths": ally_deaths,
        "enemy_deaths": enemy_deaths,
        "ally_ward_events": ally_ward_events,
        "enemy_ward_events": enemy_ward_events,
        "objective_events": objective_events,
    }


def _context_insights(
    context_events: list[dict[str, Any]],
    player_team_id: int | None,
    anchor_timestamp_ms: int,
) -> list[dict[str, str]]:
    player_team = _team_key(player_team_id)
    enemy_team = "red" if player_team == "blue" else "blue"
    objective_types = {"dragon", "herald", "baron", "tower", "inhibitor", "voidgrub", "atakhan"}
    ally_deaths = [event for event in context_events if event["type"] == "kill" and event.get("victim_team") == player_team]
    enemy_deaths = [event for event in context_events if event["type"] == "kill" and event.get("victim_team") == enemy_team]
    ally_wards_before = [
        event
        for event in context_events
        if event["type"] == "ward_placed" and event["team"] == player_team and event["timestamp_ms"] <= anchor_timestamp_ms
    ]
    enemy_wards_before = [
        event
        for event in context_events
        if event["type"] == "ward_placed" and event["team"] == enemy_team and event["timestamp_ms"] <= anchor_timestamp_ms
    ]
    enemy_objectives = [
        event for event in context_events if event["type"] in objective_types and event["team"] == enemy_team
    ]
    ally_objectives = [
        event for event in context_events if event["type"] in objective_types and event["team"] == player_team
    ]
    insights: list[dict[str, str]] = []

    if enemy_wards_before and len(enemy_wards_before) >= len(ally_wards_before) and ally_deaths and enemy_objectives:
        insights.append(
            {
                "tone": "risk",
                "title": "상대가 먼저 자리 잡은 뒤 진입한 패턴",
                "description": (
                    "전투 전에 상대 시야 이벤트가 더 먼저 잡혔고, 이후 아군 사망과 오브젝트 손실이 이어졌습니다. "
                    "상대가 시야를 잡아둔 구역에 늦게 들어가다 잘렸을 가능성이 높습니다."
                ),
            }
        )
    elif ally_deaths and enemy_objectives:
        insights.append(
            {
                "tone": "risk",
                "title": "사망이 오브젝트 손실로 연결된 구간",
                "description": (
                    "이 구간에서는 아군 사망 이후 상대 오브젝트 획득이 이어졌습니다. "
                    "단순 교전 손실보다 다음 목적물까지 같이 잃은 흐름으로 보는 편이 좋습니다."
                ),
            }
        )

    if len(enemy_wards_before) > len(ally_wards_before) and not insights:
        insights.append(
            {
                "tone": "risk",
                "title": "시야 준비가 상대 쪽에 기운 구간",
                "description": (
                    "전투 전 상대 와드 이벤트가 더 많이 잡혔습니다. "
                    "진입하기 전에 렌즈나 제어 와드로 안전 구역을 넓히는 판단이 필요했을 가능성이 있습니다."
                ),
            }
        )

    if ally_wards_before and ally_objectives and not ally_deaths:
        insights.append(
            {
                "tone": "positive",
                "title": "시야 준비가 오브젝트로 연결된 구간",
                "description": (
                    "오브젝트 전에 아군 시야 이벤트가 있고, 큰 사망 없이 목적물 획득으로 이어졌습니다. "
                    "준비 후 전환이 비교적 깔끔했던 장면으로 볼 수 있습니다."
                ),
            }
        )

    if enemy_deaths and ally_objectives and not insights:
        insights.append(
            {
                "tone": "positive",
                "title": "교전 이득을 목적물로 전환한 구간",
                "description": (
                    "상대 사망 이후 아군 오브젝트 획득이 이어졌습니다. "
                    "킬 이후 맵 자원으로 연결한 좋은 전환으로 볼 수 있습니다."
                ),
            }
        )

    if not insights:
        insights.append(
            {
                "tone": "info",
                "title": "주변 로그를 함께 확인해야 하는 구간",
                "description": (
                    "이 근거는 단일 이벤트만으로 의도를 단정하기 어렵습니다. "
                    "미니맵 위치, 와드 이벤트, 오브젝트 로그를 같이 보면서 진입 타이밍을 복기하는 것이 좋습니다."
                ),
            }
        )

    return insights[:2]


def _objective_state_at(
    events: list[dict[str, Any]],
    participants: dict[int, dict[str, Any]],
    timestamp_ms: int,
) -> dict[str, int]:
    state = {
        "blue_dragons": 0,
        "red_dragons": 0,
        "blue_heralds": 0,
        "red_heralds": 0,
        "blue_barons": 0,
        "red_barons": 0,
        "blue_towers": 0,
        "red_towers": 0,
        "blue_inhibitors": 0,
        "red_inhibitors": 0,
        "blue_voidgrubs": 0,
        "red_voidgrubs": 0,
        "blue_atakhans": 0,
        "red_atakhans": 0,
    }

    for event in events:
        if _event_timestamp(event) > timestamp_ms:
            break

        event_type = event.get("type")
        if event_type == "ELITE_MONSTER_KILL":
            objective = _monster_key(event.get("monsterType"))
            team = _team_key(_team_for_context_event(event, participants))
        elif event_type == "BUILDING_KILL":
            objective = _building_key(event.get("buildingType"))
            team = _team_key(_team_for_context_event(event, participants))
        else:
            continue

        if team not in {"blue", "red"} or objective is None:
            continue

        state_key = {
            "dragon": f"{team}_dragons",
            "herald": f"{team}_heralds",
            "baron": f"{team}_barons",
            "tower": f"{team}_towers",
            "inhibitor": f"{team}_inhibitors",
            "voidgrub": f"{team}_voidgrubs",
            "atakhan": f"{team}_atakhans",
        }.get(objective)
        if state_key:
            state[state_key] += 1

    return state


def _frames_in_window(
    frames: list[dict[str, Any]],
    window_start_ms: int,
    window_end_ms: int,
    anchor_timestamp_ms: int,
) -> list[dict[str, Any]]:
    selected = [
        frame
        for frame in frames
        if window_start_ms <= (_optional_int(frame.get("timestamp")) or 0) <= window_end_ms
    ]
    if selected:
        return _unique_frames(selected + [_nearest_frame(frames, anchor_timestamp_ms)])
    nearest = _nearest_frame(frames, anchor_timestamp_ms)
    return [nearest] if nearest else []


def _unique_frames(frames: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for frame in frames:
        if frame is None:
            continue
        timestamp_ms = _optional_int(frame.get("timestamp")) or 0
        if timestamp_ms in seen:
            continue
        seen.add(timestamp_ms)
        unique.append(frame)
    unique.sort(key=lambda item: _optional_int(item.get("timestamp")) or 0)
    return unique


def _nearest_frame(frames: list[dict[str, Any]], timestamp_ms: int) -> dict[str, Any] | None:
    if not frames:
        return None
    return min(frames, key=lambda frame: abs((_optional_int(frame.get("timestamp")) or 0) - timestamp_ms))


def _event_position(
    event: dict[str, Any],
    frames: list[dict[str, Any]],
    timestamp_ms: int,
    participant_id: int | None,
) -> tuple[int | None, int | None, str]:
    position = event.get("position") or {}
    x = _bounded_map_coord(_optional_int(position.get("x")))
    y = _bounded_map_coord(_optional_int(position.get("y")))
    if x is not None and y is not None:
        return x, y, "event"

    if participant_id is None:
        return None, None, "unknown"

    frame = _nearest_frame(frames, timestamp_ms)
    participant_frames = frame.get("participantFrames", {}) if frame else {}
    participant_frame = participant_frames.get(str(participant_id)) or participant_frames.get(participant_id) or {}
    frame_position = participant_frame.get("position") or {}
    x = _bounded_map_coord(_optional_int(frame_position.get("x")))
    y = _bounded_map_coord(_optional_int(frame_position.get("y")))
    if x is not None and y is not None:
        return x, y, "participant_frame"
    return None, None, "unknown"


def _objective_event_position(
    event: dict[str, Any],
    frames: list[dict[str, Any]],
    timestamp_ms: int,
    participant_id: int | None,
) -> tuple[int | None, int | None, str]:
    x, y, source = _event_position(event, frames, timestamp_ms, None)
    if x is not None and y is not None:
        return x, y, source

    objective_position = _objective_position(event.get("monsterType"))
    if objective_position is not None:
        return objective_position[0], objective_position[1], "objective_spawn"

    return _event_position(event, frames, timestamp_ms, participant_id)


def _objective_position(monster_type: Any) -> tuple[int, int] | None:
    positions = {
        "DRAGON": (9866, 4414),
        "RIFTHERALD": (5007, 10471),
        "BARON_NASHOR": (5007, 10471),
        "HORDE": (5007, 10471),
    }
    return positions.get(str(monster_type))


def _flatten_events(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in timeline.get("info", {}).get("frames", []):
        events.extend(frame.get("events", []))
    events.sort(key=_event_timestamp)
    return events


def _is_neutral_evidence(evidence: dict[str, Any]) -> bool:
    title = str(evidence.get("title") or "").lower()
    description = str(evidence.get("description") or "").lower()
    if int(evidence.get("minute") or 0) == 0 and ("no " in title or "not " in title):
        return True
    return "not enough" in description or "did not include" in description


def _is_context_event(event: dict[str, Any]) -> bool:
    return event.get("type") in {
        "CHAMPION_KILL",
        "ELITE_MONSTER_KILL",
        "BUILDING_KILL",
        "WARD_PLACED",
        "WARD_KILL",
    }


def _is_objective_or_building(event: dict[str, Any]) -> bool:
    return event.get("type") == "ELITE_MONSTER_KILL" or (
        event.get("type") == "BUILDING_KILL" and _building_key(event.get("buildingType")) is not None
    )


def _team_for_context_event(event: dict[str, Any], participants: dict[int, dict[str, Any]]) -> int | None:
    if event.get("type") == "ELITE_MONSTER_KILL":
        return _optional_int(event.get("killerTeamId")) or _team_for_participant(
            participants, _optional_int(event.get("killerId"))
        )
    if event.get("type") == "BUILDING_KILL":
        return _opponent_team_id(_optional_int(event.get("teamId")))
    if event.get("type") == "WARD_PLACED":
        return _team_for_participant(participants, _optional_int(event.get("creatorId")))
    if event.get("type") == "WARD_KILL":
        return _team_for_participant(participants, _optional_int(event.get("killerId")))
    return _team_for_participant(participants, _optional_int(event.get("killerId")))


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


def _bounded_map_coord(value: int | None) -> int | None:
    if value is None:
        return None
    return max(0, min(MAP_SIZE, value))


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


def _data_dragon_version(game_version: Any) -> str | None:
    if not game_version:
        return None
    parts = str(game_version).split(".")
    if len(parts) < 2:
        return None
    major, minor = parts[0], parts[1]
    if not major.isdigit() or not minor.isdigit():
        return None
    return f"{major}.{minor}.1"


def _monster_key(monster_type: Any) -> str | None:
    labels = {
        "DRAGON": "dragon",
        "RIFTHERALD": "herald",
        "BARON_NASHOR": "baron",
        "HORDE": "voidgrub",
        "ATAKHAN": "atakhan",
    }
    return labels.get(str(monster_type))


def _monster_label(monster_type: Any, monster_sub_type: Any) -> str:
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


def _building_key(building_type: Any) -> str | None:
    labels = {
        "TOWER_BUILDING": "tower",
        "INHIBITOR_BUILDING": "inhibitor",
    }
    return labels.get(str(building_type))


def _building_label(building_type: Any) -> str:
    labels = {
        "TOWER_BUILDING": "타워",
        "INHIBITOR_BUILDING": "억제기",
    }
    return labels.get(str(building_type), "건물")


def _lane_label(lane_type: Any) -> str | None:
    labels = {
        "TOP_LANE": "탑",
        "MID_LANE": "미드",
        "BOT_LANE": "바텀",
    }
    return labels.get(str(lane_type))


def _ward_label(ward_type: Any) -> str:
    labels = {
        "CONTROL_WARD": "제어 와드",
        "SIGHT_WARD": "와드",
        "YELLOW_TRINKET": "장신구 와드",
        "BLUE_TRINKET": "망원 와드",
        "UNDEFINED": "와드",
    }
    return labels.get(str(ward_type), "와드")
