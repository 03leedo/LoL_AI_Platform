"""Per-match 10-minute role-opponent laning comparison."""

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


class LaningMetric(TypedDict):
    score: int
    gd_at_10: int
    xpd_at_10: int
    csd_at_10: int
    role: str
    opponent_champion: str | None


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
    if opponent is None or not isinstance(opponent.get("participantId"), int):
        return None

    frame = _frame_at_minute(timeline, SNAPSHOT_MINUTE)
    if frame is None:
        return None
    participant_frames = frame.get("participantFrames") or {}
    player_frame = participant_frames.get(str(participant_id))
    opponent_frame = participant_frames.get(str(opponent["participantId"]))
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

    return {
        "score": score,
        "gd_at_10": gd_at_10,
        "xpd_at_10": xpd_at_10,
        "csd_at_10": csd_at_10,
        "role": str(role),
        "opponent_champion": opponent.get("championName"),
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
        "type": "laning",
        "title": "10분 동일 역할 상대 비교",
        "description": (
            f"{opponent} 대비 골드 {_signed(metric['gd_at_10'])}, "
            f"경험치 {_signed(metric['xpd_at_10'])}, CS {_signed(metric['csd_at_10'])}로 "
            f"초반 구도는 {tendency}"
        ),
        "confidence": "medium",
    }


def _frame_at_minute(timeline: dict[str, Any], minute: int) -> dict[str, Any] | None:
    for frame in (timeline.get("info") or {}).get("frames") or []:
        if int(frame.get("timestamp") or 0) // 60_000 == minute:
            return frame
    return None


def _cs(frame: dict[str, Any]) -> int:
    return int(frame.get("minionsKilled") or 0) + int(
        frame.get("jungleMinionsKilled") or 0
    )


def _signed(value: int) -> str:
    return f"{value:+,}"
