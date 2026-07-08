"""Defensive access to Match-V5 `participant.challenges` fields.

Riot ships ~100 pre-computed stats there (skillshotsDodged, soloKills,
laningPhaseGoldExpAdvantage, ...) but the exact field set shifts between
patches, so metrics must degrade gracefully when a key is absent.
"""

from typing import Any


def get_challenge(participant: dict[str, Any], key: str, default: Any = None) -> Any:
    challenges = participant.get("challenges")
    if not isinstance(challenges, dict):
        return default
    return challenges.get(key, default)


def get_challenge_int(participant: dict[str, Any], key: str, default: int = 0) -> int:
    value = get_challenge(participant, key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_challenge_float(participant: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = get_challenge(participant, key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
