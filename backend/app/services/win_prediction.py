"""Serve per-minute win predictions from the trained solo-queue model."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from app.ml.advantage_inference import predict_from_artifact
from app.services.win_probability import build_win_curve

MODEL_ARTIFACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "ml"
    / "artifacts"
    / "advantage_v1_dataset_v2.json"
)

PredictionSource = Literal["model_v1_experimental", "heuristic_v0_fallback"]


class ServedWinCurve(TypedDict):
    curve: list[dict[str, Any]]
    source: PredictionSource
    model_version: int | None
    dataset_version: int | None


@lru_cache(maxsize=1)
def load_model_artifact() -> dict[str, Any]:
    with MODEL_ARTIFACT_PATH.open(encoding="utf-8") as artifact_file:
        return json.load(artifact_file)


def _model_row(feature: dict[str, Any]) -> dict[str, Any]:
    return {
        **feature,
        "tower_diff": int(feature.get("blue_tower_kills") or 0)
        - int(feature.get("red_tower_kills") or 0),
        "dragon_diff": int(feature.get("blue_dragon_kills") or 0)
        - int(feature.get("red_dragon_kills") or 0),
        "herald_diff": int(feature.get("blue_herald_kills") or 0)
        - int(feature.get("red_herald_kills") or 0),
        "baron_diff": int(feature.get("blue_baron_kills") or 0)
        - int(feature.get("red_baron_kills") or 0),
    }


def build_served_win_curve(
    features: list[dict[str, Any]],
    queue_id: int | None,
) -> ServedWinCurve:
    """Predict final blue-side win chance at each non-terminal minute.

    The trained artifact is solo-queue specific. Other queues retain the
    explainable heuristic fallback rather than silently crossing domains.
    """
    try:
        artifact = load_model_artifact()
    except (OSError, ValueError, KeyError, TypeError):
        artifact = None

    if artifact is None or queue_id != artifact.get("queue_id"):
        return {
            "curve": build_win_curve(features),
            "source": "heuristic_v0_fallback",
            "model_version": None,
            "dataset_version": None,
        }

    # Dataset v2 excludes the terminal frame because it nearly reveals the
    # match label. Serving keeps the same boundary for train/inference parity.
    inference_features = features[:-1] if len(features) > 1 else features
    curve = [
        {
            "minute": int(feature.get("minute") or 0),
            "timestamp_ms": int(feature.get("timestamp_ms") or 0),
            "blue_win_prob": round(
                predict_from_artifact(artifact, _model_row(feature)),
                3,
            ),
        }
        for feature in inference_features
    ]
    return {
        "curve": curve,
        "source": "model_v1_experimental",
        "model_version": int(artifact["model_version"]),
        "dataset_version": int(artifact["dataset_version"]),
    }
