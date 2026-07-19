"""Per-minute win prediction model v1 and calibration report (Phase 7).

Pure-Python, deterministic full-batch gradient descent — 10 features and a few
thousand rows do not justify a numpy/sklearn dependency yet (recorded scope
decision; boosting arrives only if it beats this baseline on held-out data).

Each row is one minute snapshot and the target is the match's final blue-side
result. The model therefore answers "given the state at this minute, how often
would blue eventually win?" rather than predicting a match before it starts.

`decide_verdict` still applies the quality gate. The current model is exposed
as an explicitly experimental review curve while the heuristic remains the
fallback for unsupported queues or artifact failures.
"""

import math
from typing import Any

from app.ml.advantage_features import FEATURE_NAMES, full_feature_row
from app.ml.advantage_inference import predict_from_artifact, sigmoid as _sigmoid
from app.ml.advantage_dataset import (
    DATASET_VERSION,
    temporal_match_split,
)
from app.services.win_probability import build_win_curve

MODEL_VERSION = 1

# Training hyperparameters (deterministic: zero init, full batch, fixed epochs).
# Convergence probe 2026-07-19 (n=526): 1500@0.1 was underfit (test log loss
# 0.5739); 5000@0.3 reaches the plateau (0.5690; 15000 epochs changes nothing)
# with train≈test loss, i.e. capacity-limited, not overfit.
LEARNING_RATE = 0.3
EPOCHS = 5000
L2_LAMBDA = 1e-3

TEST_FRACTION = 0.3
CALIBRATION_BINS = 10
TIME_BUCKETS = [(0, 9), (10, 19), (20, 29), (30, 200)]

# Adoption gate — the model may replace the heuristic curve only when ALL pass
# on the held-out set. Volumes below the minimum yield insufficient_data.
ADOPTION_MIN_MATCHES = 300
ADOPTION_MIN_TEST_MATCHES = 60
ADOPTION_MAX_ECE = 0.05

PROB_CLIP = 1e-6


def _feature_vector(row: dict[str, Any]) -> list[float]:
    full = full_feature_row(row)
    return [float(full[name]) for name in FEATURE_NAMES]


def train_logistic(train_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit standardized logistic regression; returns a self-contained artifact."""
    vectors = [_feature_vector(row) for row in train_rows]
    labels = [row["blue_win"] for row in train_rows]
    n = len(vectors)
    d = len(FEATURE_NAMES)

    means = [sum(v[j] for v in vectors) / n for j in range(d)]
    stds = []
    for j in range(d):
        variance = sum((v[j] - means[j]) ** 2 for v in vectors) / n
        stds.append(math.sqrt(variance) if variance > 0 else 1.0)
    standardized = [[(v[j] - means[j]) / stds[j] for j in range(d)] for v in vectors]

    weights = [0.0] * d
    intercept = 0.0
    for _ in range(EPOCHS):
        grad_w = [0.0] * d
        grad_b = 0.0
        for x, y in zip(standardized, labels):
            error = _sigmoid(intercept + sum(w * xj for w, xj in zip(weights, x))) - y
            for j in range(d):
                grad_w[j] += error * x[j]
            grad_b += error
        for j in range(d):
            weights[j] -= LEARNING_RATE * (grad_w[j] / n + L2_LAMBDA * weights[j])
        intercept -= LEARNING_RATE * (grad_b / n)

    return {
        "model_version": MODEL_VERSION,
        "dataset_version": DATASET_VERSION,
        "model_type": "logistic_regression_gd",
        "hyperparameters": {"epochs": EPOCHS, "learning_rate": LEARNING_RATE, "l2": L2_LAMBDA},
        "feature_names": list(FEATURE_NAMES),
        "means": means,
        "stds": stds,
        "coefficients": weights,
        "intercept": intercept,
    }


def log_loss(labels: list[int], probs: list[float]) -> float:
    total = 0.0
    for y, p in zip(labels, probs):
        p = min(1.0 - PROB_CLIP, max(PROB_CLIP, p))
        total += -(y * math.log(p) + (1 - y) * math.log(1.0 - p))
    return total / len(labels)


def brier_score(labels: list[int], probs: list[float]) -> float:
    return sum((p - y) ** 2 for y, p in zip(labels, probs)) / len(labels)


def roc_auc(labels: list[int], probs: list[float]) -> float | None:
    """Rank-based AUC with tie handling; None when one class is absent."""
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    pairs = sorted(zip(probs, labels))
    rank_sum_pos = 0.0
    index = 0
    while index < len(pairs):
        end = index
        while end < len(pairs) and pairs[end][0] == pairs[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        for k in range(index, end):
            if pairs[k][1] == 1:
                rank_sum_pos += average_rank
        index = end
    u_statistic = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return u_statistic / (n_pos * n_neg)


def reliability_bins(labels: list[int], probs: list[float]) -> list[dict[str, Any]]:
    bins: list[dict[str, Any]] = []
    for b in range(CALIBRATION_BINS):
        low = b / CALIBRATION_BINS
        high = (b + 1) / CALIBRATION_BINS
        members = [
            (y, p)
            for y, p in zip(labels, probs)
            if (low <= p < high) or (b == CALIBRATION_BINS - 1 and p == 1.0)
        ]
        entry: dict[str, Any] = {"bin_low": low, "bin_high": high, "count": len(members)}
        if members:
            entry["mean_predicted"] = sum(p for _, p in members) / len(members)
            entry["observed_rate"] = sum(y for y, _ in members) / len(members)
        bins.append(entry)
    return bins


def expected_calibration_error(labels: list[int], probs: list[float]) -> float:
    total = len(labels)
    ece = 0.0
    for entry in reliability_bins(labels, probs):
        if entry["count"]:
            ece += (entry["count"] / total) * abs(
                entry["observed_rate"] - entry["mean_predicted"]
            )
    return ece


def evaluate(labels: list[int], probs: list[float]) -> dict[str, Any]:
    return {
        "n": len(labels),
        "roc_auc": roc_auc(labels, probs),
        "log_loss": log_loss(labels, probs),
        "brier": brier_score(labels, probs),
        "ece": expected_calibration_error(labels, probs),
        "reliability": reliability_bins(labels, probs),
    }


def _bucketed(rows: list[dict[str, Any]], probs: list[float]) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    for low, high in TIME_BUCKETS:
        members = [
            (row["blue_win"], p)
            for row, p in zip(rows, probs)
            if low <= row["minute"] <= high
        ]
        entry: dict[str, Any] = {"minutes": f"{low}-{high}", "n": len(members)}
        if members:
            labels = [y for y, _ in members]
            member_probs = [p for _, p in members]
            entry["brier"] = brier_score(labels, member_probs)
            entry["ece"] = expected_calibration_error(labels, member_probs)
        buckets.append(entry)
    return buckets


def _by_patch(rows: list[dict[str, Any]], probs: list[float]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[tuple[int, float]]] = {}
    for row, p in zip(rows, probs):
        grouped.setdefault(row["patch"] or "unknown", []).append((row["blue_win"], p))
    report: dict[str, dict[str, Any]] = {}
    for patch, members in sorted(grouped.items()):
        labels = [y for y, _ in members]
        member_probs = [p for _, p in members]
        report[patch] = {
            "n": len(members),
            "brier": brier_score(labels, member_probs),
            "ece": expected_calibration_error(labels, member_probs),
        }
    return report


def heuristic_probabilities(rows: list[dict[str, Any]]) -> list[float]:
    """Production heuristic v0 evaluated on the same snapshots (baseline)."""
    curve = build_win_curve(rows)
    return [point["blue_win_prob"] for point in curve]


def decide_verdict(
    model_eval: dict[str, Any],
    baseline_evals: dict[str, dict[str, Any]],
    total_matches: int,
    test_matches: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    if total_matches < ADOPTION_MIN_MATCHES:
        reasons.append(
            f"insufficient_data: {total_matches} matches < {ADOPTION_MIN_MATCHES} required"
        )
    if test_matches < ADOPTION_MIN_TEST_MATCHES:
        reasons.append(
            f"insufficient_test_data: {test_matches} test matches < {ADOPTION_MIN_TEST_MATCHES}"
        )
    for name, baseline in baseline_evals.items():
        if model_eval["log_loss"] >= baseline["log_loss"]:
            reasons.append(f"log_loss_not_better_than_{name}")
        if model_eval["brier"] >= baseline["brier"]:
            reasons.append(f"brier_not_better_than_{name}")
    if model_eval["ece"] > ADOPTION_MAX_ECE:
        reasons.append(f"ece_above_threshold: {model_eval['ece']:.4f} > {ADOPTION_MAX_ECE}")

    return {
        "verdict": "adopt" if not reasons else "keep_heuristic",
        "reasons": reasons,
        "thresholds": {
            "min_matches": ADOPTION_MIN_MATCHES,
            "min_test_matches": ADOPTION_MIN_TEST_MATCHES,
            "max_ece": ADOPTION_MAX_ECE,
        },
    }


def run_training(dataset: dict[str, Any], test_fraction: float = TEST_FRACTION) -> dict[str, Any]:
    """Full pipeline: split → train → evaluate vs baselines → gated verdict."""
    rows = dataset["rows"]
    total_matches = len(dataset["matches_included"])
    if total_matches < 2 or not rows:
        return {
            "status": "insufficient_data",
            "model_version": MODEL_VERSION,
            "dataset_version": dataset["dataset_version"],
            "matches": total_matches,
            "verdict": {
                "verdict": "keep_heuristic",
                "reasons": [f"insufficient_data: {total_matches} matches, cannot split"],
                "thresholds": {
                    "min_matches": ADOPTION_MIN_MATCHES,
                    "min_test_matches": ADOPTION_MIN_TEST_MATCHES,
                    "max_ece": ADOPTION_MAX_ECE,
                },
            },
        }

    split = temporal_match_split(rows, test_fraction)
    train_rows, test_rows = split["train_rows"], split["test_rows"]
    artifact = train_logistic(train_rows)
    artifact["domain"] = dataset["domain"]
    artifact["queue_id"] = dataset["queue_id"]
    artifact["train_matches"] = len(split["train_match_ids"])
    artifact["train_rows"] = len(train_rows)

    test_labels = [row["blue_win"] for row in test_rows]
    model_probs = [predict_from_artifact(artifact, row) for row in test_rows]

    train_rate = sum(row["blue_win"] for row in train_rows) / len(train_rows)
    baseline_evals = {
        "constant_train_rate": evaluate(test_labels, [train_rate] * len(test_rows)),
        "heuristic_v0": evaluate(test_labels, heuristic_probabilities(test_rows)),
    }
    model_eval = evaluate(test_labels, model_probs)

    return {
        "status": "trained",
        "model_version": MODEL_VERSION,
        "dataset_version": dataset["dataset_version"],
        "domain": dataset["domain"],
        "queue_id": dataset["queue_id"],
        "matches": total_matches,
        "snapshot_rows": len(rows),
        "split": {
            "method": "temporal_match_grouped",
            "test_fraction": test_fraction,
            "train_matches": len(split["train_match_ids"]),
            "test_matches": len(split["test_match_ids"]),
            "train_rows": len(train_rows),
            "test_rows": len(test_rows),
        },
        "model_eval": model_eval,
        "baseline_evals": baseline_evals,
        "time_bucket_calibration": _bucketed(test_rows, model_probs),
        "patch_calibration": _by_patch(test_rows, model_probs),
        "verdict": decide_verdict(
            model_eval,
            baseline_evals,
            total_matches,
            len(split["test_match_ids"]),
        ),
        "artifact": artifact,
    }
