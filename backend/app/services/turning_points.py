"""Turning-point detection: where the win probability swung hardest (M2).

Combines the rule-based win curve with key events so the review page can say
"이 판의 변곡점: 24분 바론 한타 (-31%p)" instead of showing a bare graph.
Deltas are reported from the viewed player's team perspective.
"""

from typing import Any

MIN_DELTA = 0.08
TOP_N = 3
EVENT_MATCH_TAIL_MS = 30_000

HIGH_IMPACT_TYPES = {"baron", "dragon", "herald", "inhibitor", "atakhan"}


def detect_turning_points(
    win_curve: list[dict[str, Any]],
    key_events: list[dict[str, Any]],
    player_team: str,
    top_n: int = TOP_N,
) -> list[dict[str, Any]]:
    if len(win_curve) < 2:
        return []

    sign = 1.0 if player_team == "blue" else -1.0

    candidates: list[dict[str, Any]] = []
    for previous, current in zip(win_curve, win_curve[1:]):
        blue_delta = float(current.get("blue_win_prob") or 0.5) - float(previous.get("blue_win_prob") or 0.5)
        delta = blue_delta * sign
        if abs(delta) < MIN_DELTA:
            continue
        candidates.append(
            {
                "minute": int(current.get("minute") or 0),
                "window_start_ms": int(previous.get("timestamp_ms") or 0),
                "window_end_ms": int(current.get("timestamp_ms") or 0) + EVENT_MATCH_TAIL_MS,
                "prob_before": _team_prob(previous, sign),
                "prob_after": _team_prob(current, sign),
                "delta": round(delta, 3),
            }
        )

    top = sorted(candidates, key=lambda item: -abs(item["delta"]))[:top_n]

    points: list[dict[str, Any]] = []
    for candidate in top:
        event = _nearest_key_event(key_events, candidate)
        points.append(
            {
                "minute": candidate["minute"],
                "prob_before": candidate["prob_before"],
                "prob_after": candidate["prob_after"],
                "delta": candidate["delta"],
                "event_type": event.get("type") if event else None,
                "title": event.get("title") if event else None,
                "description": event.get("description") if event else None,
            }
        )

    points.sort(key=lambda item: item["minute"])
    return points


def _team_prob(point: dict[str, Any], sign: float) -> float:
    blue = float(point.get("blue_win_prob") or 0.5)
    return round(blue if sign > 0 else 1.0 - blue, 3)


def _nearest_key_event(
    key_events: list[dict[str, Any]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    window_events = [
        event
        for event in key_events
        if candidate["window_start_ms"] <= int(event.get("timestamp_ms") or 0) <= candidate["window_end_ms"]
    ]
    if not window_events:
        return None

    target_ms = candidate["minute"] * 60_000

    def rank(event: dict[str, Any]) -> tuple[int, int]:
        impact = 0 if event.get("type") in HIGH_IMPACT_TYPES else 1
        distance = abs(int(event.get("timestamp_ms") or 0) - target_ms)
        return (impact, distance)

    return min(window_events, key=rank)
