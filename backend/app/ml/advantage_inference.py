"""Dependency-free inference for the per-minute win prediction model."""

import math
from typing import Any

from app.ml.advantage_features import full_feature_row


def sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def predict_from_artifact(artifact: dict[str, Any], row: dict[str, Any]) -> float:
    """Predict final blue-side win chance from one minute snapshot."""
    full = full_feature_row(row)
    score = artifact["intercept"]
    for name, mean, std, weight in zip(
        artifact["feature_names"],
        artifact["means"],
        artifact["stds"],
        artifact["coefficients"],
    ):
        score += weight * ((float(full[name]) - mean) / std)
    return sigmoid(score)
