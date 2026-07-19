"""Per-match early resource, combat, and pressure comparisons."""

from math import hypot
from typing import Any, TypedDict

SNAPSHOT_MINUTE = 10

# Held-out residual standard deviations from expected_v1_2026-07-19_n524.
# They put gold, XP, and CS differences on comparable scales.
GD_STD = 851.4678595951622
XPD_STD = 686.3047434478606
CSD_STD = 15.718624597453456

GD_WEIGHT = 0.45
XPD_WEIGHT = 0.35
CSD_WEIGHT = 0.20
SCORE_Z_LIMIT = 3.0

EARLY_WINDOW_MS = SNAPSHOT_MINUTE * 60_000
KP_PRIOR_TAKEDOWNS = 1
KP_PRIOR_TEAM_KILLS = 2
KP_DIFF_WEIGHT = 40
DIRECT_TAKEDOWN_WEIGHT = 10
DIRECT_TAKEDOWN_LIMIT = 2

PRESSURE_START_MINUTE = 3
PRESSURE_MAX_DISTANCE = 3_500
LOW_HEALTH_RATIO = 0.35
MIN_PRESSURE_FRAMES = 3


class LaningMetric(TypedDict):
    score: int
    gd_at_10: int
    xpd_at_10: int
    csd_at_10: int
    role: str
    opponent_champion: str | None
    early_impact_score: int | None
    early_impact_confidence: str
    player_early_takedowns: int
    player_team_kills: int
    opponent_early_takedowns: int
    opponent_team_kills: int
    player_early_kp: float | None
    opponent_early_kp: float | None
    direct_takedown_diff: int
    pressure_comparable_frames: int
    player_low_health_frames: int
    opponent_low_health_frames: int


def calculate_laning_metric(
    participant: dict[str, Any],
    match: dict[str, Any],
    timeline: dict[str, Any],
) -> LaningMetric | None:
    """Compare a player with the opposite team's same-role participant at 10m."""
    role = participant.get("teamPosition") or participant.get("individualPosition")
    participant_id = participant.get("participantId")
    team_id = participant.get("teamId")
    if (
        not role
        or role == "Invalid"
        or not isinstance(participant_id, int)
        or not isinstance(team_id, int)
    ):
        return None

    opponent = next(
        (
            candidate
            for candidate in (match.get("info") or {}).get("participants") or []
            if candidate.get("teamId") != team_id
            and (candidate.get("teamPosition") or candidate.get("individualPosition")) == role
        ),
        None,
    )
    if (
        opponent is None
        or not isinstance(opponent.get("participantId"), int)
        or not isinstance(opponent.get("teamId"), int)
    ):
        return None

    frame = _frame_at_minute(timeline, SNAPSHOT_MINUTE)
    if frame is None:
        return None
    participant_frames = frame.get("participantFrames") or {}
    player_frame = _participant_frame(participant_frames, participant_id)
    opponent_frame = _participant_frame(
        participant_frames, int(opponent["participantId"])
    )
    if not player_frame or not opponent_frame:
        return None

    gd_at_10 = int(player_frame.get("totalGold") or 0) - int(
        opponent_frame.get("totalGold") or 0
    )
    xpd_at_10 = int(player_frame.get("xp") or 0) - int(opponent_frame.get("xp") or 0)
    csd_at_10 = _cs(player_frame) - _cs(opponent_frame)

    combined_z = (
        GD_WEIGHT * gd_at_10 / GD_STD
        + XPD_WEIGHT * xpd_at_10 / XPD_STD
        + CSD_WEIGHT * csd_at_10 / CSD_STD
    )
    bounded_z = max(-SCORE_Z_LIMIT, min(SCORE_Z_LIMIT, combined_z))
    score = round(50 + 50 * bounded_z / SCORE_Z_LIMIT)
    combat = _early_combat(
        timeline,
        participant_id=participant_id,
        participant_team_id=team_id,
        opponent_id=int(opponent["participantId"]),
        opponent_team_id=int(opponent["teamId"]),
        match=match,
    )
    pressure = _pressure_snapshots(
        timeline,
        participant_id=participant_id,
        opponent_id=int(opponent["participantId"]),
    )

    return {
        "score": score,
        "gd_at_10": gd_at_10,
        "xpd_at_10": xpd_at_10,
        "csd_at_10": csd_at_10,
        "role": str(role),
        "opponent_champion": opponent.get("championName"),
        **combat,
        **pressure,
    }


def laning_evidence(metric: LaningMetric) -> dict[str, Any]:
    tendency = (
        "우세에 가까웠습니다"
        if metric["score"] >= 60
        else "열세에 가까웠습니다"
        if metric["score"] <= 40
        else "비슷한 흐름이었습니다"
    )
    opponent = metric["opponent_champion"] or "동일 역할 상대"
    return {
        "minute": SNAPSHOT_MINUTE,
        "type": "laning_resource",
        "title": "10분 자원 우세도",
        "description": (
            f"{opponent} 대비 골드 {_signed(metric['gd_at_10'])}, "
            f"경험치 {_signed(metric['xpd_at_10'])}, CS {_signed(metric['csd_at_10'])}로 "
            f"자원 흐름은 {tendency}"
        ),
        "confidence": "medium",
    }


def early_impact_evidence(metric: LaningMetric) -> dict[str, Any]:
    opponent = metric["opponent_champion"] or "동일 역할 상대"
    if metric["early_impact_score"] is None:
        return {
            "minute": SNAPSHOT_MINUTE,
            "type": "early_impact",
            "title": "초반 교전 영향력 표본 부족",
            "description": (
                "10분 전 양 팀의 챔피언 처치가 없어 킬 관여 기반 점수는 계산하지 않았습니다."
            ),
            "confidence": "low",
        }

    player_kp = _percent(metric["player_early_kp"])
    opponent_kp = _percent(metric["opponent_early_kp"])
    direct = metric["direct_takedown_diff"]
    direct_text = (
        f"직접 교환은 {_signed(direct)}"
        if direct
        else "서로를 상대로 한 직접 킬 관여 차이는 없음"
    )
    return {
        "minute": SNAPSHOT_MINUTE,
        "type": "early_impact",
        "title": "10분 초반 교전 영향력",
        "description": (
            f"10분 전 킬 관여율은 {player_kp} "
            f"({metric['player_early_takedowns']}/{metric['player_team_kills']}), "
            f"{opponent}은 {opponent_kp} "
            f"({metric['opponent_early_takedowns']}/{metric['opponent_team_kills']})이며, "
            f"{direct_text}입니다. 팀 킬이 적을 때는 50% 사전값으로 표본을 보정했습니다."
        ),
        "confidence": metric["early_impact_confidence"],
    }


def lane_pressure_evidence(metric: LaningMetric) -> dict[str, Any]:
    comparable = metric["pressure_comparable_frames"]
    if comparable < MIN_PRESSURE_FRAMES:
        return {
            "minute": SNAPSHOT_MINUTE,
            "type": "lane_pressure",
            "title": "체력 압박은 점수에서 제외",
            "description": (
                f"3~10분 중 두 선수가 가까이 있고 살아 있던 비교 가능 프레임이 "
                f"{comparable}개뿐이라 체력 상태를 점수에 반영하지 않았습니다."
            ),
            "confidence": "low",
        }

    player_low = metric["player_low_health_frames"]
    opponent_low = metric["opponent_low_health_frames"]
    if player_low >= opponent_low + 2:
        interpretation = "플레이어가 저체력으로 포착된 경우가 더 많았습니다"
    elif opponent_low >= player_low + 2:
        interpretation = "상대가 저체력으로 포착된 경우가 더 많았습니다"
    else:
        interpretation = "저체력 포착 횟수 차이는 크지 않았습니다"
    return {
        "minute": SNAPSHOT_MINUTE,
        "type": "lane_pressure",
        "title": "체력 압박 참고 신호",
        "description": (
            f"가까이 있던 1분 프레임 {comparable}개에서 체력 35% 이하가 "
            f"플레이어 {player_low}회, 상대 {opponent_low}회였고, {interpretation}. "
            "연속 전투 기록이 아니므로 참고 신호로만 사용합니다."
        ),
        "confidence": "low",
    }


def _early_combat(
    timeline: dict[str, Any],
    participant_id: int,
    participant_team_id: int,
    opponent_id: int,
    opponent_team_id: int,
    match: dict[str, Any],
) -> dict[str, Any]:
    participant_teams = {
        int(item["participantId"]): int(item["teamId"])
        for item in (match.get("info") or {}).get("participants") or []
        if isinstance(item.get("participantId"), int)
        and isinstance(item.get("teamId"), int)
    }
    team_kills = {participant_team_id: 0, opponent_team_id: 0}
    player_takedowns = 0
    opponent_takedowns = 0
    player_direct = 0
    opponent_direct = 0

    for frame in (timeline.get("info") or {}).get("frames") or []:
        for event in frame.get("events") or []:
            if event.get("type") != "CHAMPION_KILL":
                continue
            if int(event.get("timestamp") or 0) > EARLY_WINDOW_MS:
                continue
            killer_id = _optional_int(event.get("killerId"))
            victim_id = _optional_int(event.get("victimId"))
            killer_team_id = participant_teams.get(killer_id or 0)
            if killer_team_id not in team_kills:
                continue

            team_kills[killer_team_id] += 1
            involved = _event_participant_ids(event)
            if participant_id in involved:
                player_takedowns += 1
                if victim_id == opponent_id:
                    player_direct += 1
            if opponent_id in involved:
                opponent_takedowns += 1
                if victim_id == participant_id:
                    opponent_direct += 1

    player_team_kills = team_kills[participant_team_id]
    opponent_team_kills = team_kills[opponent_team_id]
    total_kills = player_team_kills + opponent_team_kills
    player_kp = player_takedowns / player_team_kills if player_team_kills else None
    opponent_kp = (
        opponent_takedowns / opponent_team_kills if opponent_team_kills else None
    )
    direct_diff = player_direct - opponent_direct

    if total_kills:
        smoothed_player_kp = (player_takedowns + KP_PRIOR_TAKEDOWNS) / (
            player_team_kills + KP_PRIOR_TEAM_KILLS
        )
        smoothed_opponent_kp = (opponent_takedowns + KP_PRIOR_TAKEDOWNS) / (
            opponent_team_kills + KP_PRIOR_TEAM_KILLS
        )
        impact_score = round(
            50
            + KP_DIFF_WEIGHT * (smoothed_player_kp - smoothed_opponent_kp)
            + DIRECT_TAKEDOWN_WEIGHT
            * max(-DIRECT_TAKEDOWN_LIMIT, min(DIRECT_TAKEDOWN_LIMIT, direct_diff))
        )
        impact_score = max(0, min(100, impact_score))
    else:
        impact_score = None

    return {
        "early_impact_score": impact_score,
        "early_impact_confidence": "medium" if total_kills >= 4 else "low",
        "player_early_takedowns": player_takedowns,
        "player_team_kills": player_team_kills,
        "opponent_early_takedowns": opponent_takedowns,
        "opponent_team_kills": opponent_team_kills,
        "player_early_kp": player_kp,
        "opponent_early_kp": opponent_kp,
        "direct_takedown_diff": direct_diff,
    }


def _pressure_snapshots(
    timeline: dict[str, Any],
    participant_id: int,
    opponent_id: int,
) -> dict[str, int]:
    comparable = 0
    player_low = 0
    opponent_low = 0
    for frame in (timeline.get("info") or {}).get("frames") or []:
        minute = int(frame.get("timestamp") or 0) // 60_000
        if not PRESSURE_START_MINUTE <= minute <= SNAPSHOT_MINUTE:
            continue
        participant_frames = frame.get("participantFrames") or {}
        player_frame = _participant_frame(participant_frames, participant_id)
        opponent_frame = _participant_frame(participant_frames, opponent_id)
        if not player_frame or not opponent_frame:
            continue
        player_health = _health_ratio(player_frame)
        opponent_health = _health_ratio(opponent_frame)
        player_position = _position(player_frame)
        opponent_position = _position(opponent_frame)
        if (
            player_health is None
            or opponent_health is None
            or player_position is None
            or opponent_position is None
            or hypot(
                player_position[0] - opponent_position[0],
                player_position[1] - opponent_position[1],
            )
            > PRESSURE_MAX_DISTANCE
        ):
            continue
        comparable += 1
        player_low += int(player_health <= LOW_HEALTH_RATIO)
        opponent_low += int(opponent_health <= LOW_HEALTH_RATIO)
    return {
        "pressure_comparable_frames": comparable,
        "player_low_health_frames": player_low,
        "opponent_low_health_frames": opponent_low,
    }


def _frame_at_minute(timeline: dict[str, Any], minute: int) -> dict[str, Any] | None:
    for frame in (timeline.get("info") or {}).get("frames") or []:
        if int(frame.get("timestamp") or 0) // 60_000 == minute:
            return frame
    return None


def _participant_frame(
    participant_frames: dict[str, Any], participant_id: int
) -> dict[str, Any] | None:
    return participant_frames.get(str(participant_id)) or participant_frames.get(
        participant_id
    )


def _event_participant_ids(event: dict[str, Any]) -> set[int]:
    participant_ids: set[int] = set()
    killer_id = _optional_int(event.get("killerId"))
    if killer_id:
        participant_ids.add(killer_id)
    for value in event.get("assistingParticipantIds") or []:
        participant_id = _optional_int(value)
        if participant_id:
            participant_ids.add(participant_id)
    return participant_ids


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _health_ratio(frame: dict[str, Any]) -> float | None:
    stats = frame.get("championStats") or {}
    health = stats.get("health", stats.get("currentHealth"))
    maximum = stats.get("healthMax", stats.get("maxHealth"))
    if not isinstance(health, (int, float)) or not isinstance(maximum, (int, float)):
        return None
    if health <= 0 or maximum <= 0:
        return None
    return max(0.0, min(1.0, float(health) / float(maximum)))


def _position(frame: dict[str, Any]) -> tuple[float, float] | None:
    position = frame.get("position") or {}
    x = position.get("x")
    y = position.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return float(x), float(y)


def _cs(frame: dict[str, Any]) -> int:
    return int(frame.get("minionsKilled") or 0) + int(
        frame.get("jungleMinionsKilled") or 0
    )


def _signed(value: int) -> str:
    return f"{value:+,}"


def _percent(value: float | None) -> str:
    return "기회 없음" if value is None else f"{round(value * 100)}%"
