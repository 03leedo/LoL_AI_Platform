"""Pure feature definitions shared by training and serving."""

from typing import Any

FEATURE_NAMES = [
    "minute",
    "gold_diff",
    "xp_diff",
    "cs_diff",
    "tower_diff",
    "dragon_diff",
    "herald_diff",
    "baron_diff",
    "gold_diff_x_time",
    "xp_diff_x_time",
]


def _time_weight(minute: int) -> float:
    return min(1.5, 0.5 + minute / 30.0)


def derived_feature_values(row: dict[str, Any]) -> dict[str, float]:
    time_weight = _time_weight(int(row["minute"]))
    return {
        "gold_diff_x_time": float(row["gold_diff"]) * time_weight,
        "xp_diff_x_time": float(row["xp_diff"]) * time_weight,
    }


def full_feature_row(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, **derived_feature_values(row)}
