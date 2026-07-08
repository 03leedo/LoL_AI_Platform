"""Rule-based win probability curve (v0, master-plan §4.6).

A hand-tuned logistic over per-minute team differentials. Deliberately simple
and explainable; the M4 milestone replaces the weights with a trained model
behind the same output shape.
"""

import math
from typing import Any

# Weight of 1k gold grows as the game ages (late-game gold is harder to flip).
GOLD_WEIGHT = 0.55
XP_WEIGHT = 0.25
TOWER_WEIGHT = 0.28
DRAGON_WEIGHT = 0.22
HERALD_WEIGHT = 0.12
BARON_WEIGHT = 0.90
LOGISTIC_SCALE = 0.55
PROB_FLOOR = 0.03
PROB_CEILING = 0.97


def build_win_curve(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map per-minute timeline features to blue-side win probabilities."""
    curve: list[dict[str, Any]] = []
    for feature in features:
        minute = int(feature.get("minute") or 0)
        time_weight = min(1.5, 0.5 + minute / 30)

        z = (
            (int(feature.get("gold_diff") or 0) / 1000.0) * GOLD_WEIGHT * time_weight
            + (int(feature.get("xp_diff") or 0) / 1000.0) * XP_WEIGHT
            + (int(feature.get("blue_tower_kills") or 0) - int(feature.get("red_tower_kills") or 0)) * TOWER_WEIGHT
            + (int(feature.get("blue_dragon_kills") or 0) - int(feature.get("red_dragon_kills") or 0)) * DRAGON_WEIGHT
            + (int(feature.get("blue_herald_kills") or 0) - int(feature.get("red_herald_kills") or 0)) * HERALD_WEIGHT
            + (int(feature.get("blue_baron_kills") or 0) - int(feature.get("red_baron_kills") or 0)) * BARON_WEIGHT
        )

        probability = 1.0 / (1.0 + math.exp(-LOGISTIC_SCALE * z))
        probability = min(PROB_CEILING, max(PROB_FLOOR, probability))

        curve.append(
            {
                "minute": minute,
                "timestamp_ms": int(feature.get("timestamp_ms") or 0),
                "blue_win_prob": round(probability, 3),
            }
        )
    return curve
