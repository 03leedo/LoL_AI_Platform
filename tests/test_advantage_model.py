import json
import unittest

from app.ml.advantage_dataset import FEATURE_NAMES
from app.ml.advantage_model import (
    ADOPTION_MIN_MATCHES,
    brier_score,
    expected_calibration_error,
    heuristic_probabilities,
    log_loss,
    predict_from_artifact,
    roc_auc,
    run_training,
    train_logistic,
)


def make_row(
    match_id: str,
    minute: int,
    gold_diff: int,
    blue_win: int,
    game_creation: int,
) -> dict:
    row = {name: 0 for name in FEATURE_NAMES}
    row.update(
        {
            "match_id": match_id,
            "game_creation": game_creation,
            "patch": "14.10",
            "minute": minute,
            "gold_diff": gold_diff,
            "xp_diff": gold_diff // 2,
            "timestamp_ms": minute * 60_000,
            "blue_win": blue_win,
        }
    )
    for side in ("blue", "red"):
        for objective in ("tower", "dragon", "herald", "baron"):
            row[f"{side}_{objective}_kills"] = 0
    return row


def make_synthetic_rows(match_count: int = 12, minutes: int = 8) -> list[dict]:
    """Blue wins iff it holds a gold lead — cleanly learnable."""
    rows = []
    for m in range(match_count):
        blue_win = m % 2
        lead = 1_500 if blue_win else -1_500
        for minute in range(minutes):
            rows.append(
                make_row(
                    match_id=f"KR_{m}",
                    minute=minute,
                    gold_diff=lead * (minute + 1) // minutes,
                    blue_win=blue_win,
                    game_creation=1_000 + m,
                )
            )
    return rows


class MetricsTest(unittest.TestCase):
    def test_perfect_predictions(self) -> None:
        labels = [1, 0, 1, 0]
        probs = [1.0, 0.0, 1.0, 0.0]
        self.assertEqual(brier_score(labels, probs), 0.0)
        self.assertEqual(roc_auc(labels, probs), 1.0)
        self.assertLess(log_loss(labels, probs), 1e-4)

    def test_auc_handles_ties_and_single_class(self) -> None:
        self.assertEqual(roc_auc([1, 0], [0.5, 0.5]), 0.5)
        self.assertIsNone(roc_auc([1, 1], [0.7, 0.9]))

    def test_calibrated_constant_has_zero_ece(self) -> None:
        labels = [1, 0, 1, 0]
        self.assertAlmostEqual(expected_calibration_error(labels, [0.5] * 4), 0.0)

    def test_overconfident_predictions_have_high_ece(self) -> None:
        labels = [1, 0, 1, 0]
        ece = expected_calibration_error(labels, [0.99, 0.99, 0.99, 0.99])
        self.assertGreater(ece, 0.4)


class TrainLogisticTest(unittest.TestCase):
    def test_learns_separable_gold_signal(self) -> None:
        rows = make_synthetic_rows()
        artifact = train_logistic(rows)

        ahead = predict_from_artifact(artifact, make_row("x", 7, 1_500, 1, 0))
        behind = predict_from_artifact(artifact, make_row("x", 7, -1_500, 0, 0))
        self.assertGreater(ahead, 0.8)
        self.assertLess(behind, 0.2)

    def test_training_is_deterministic(self) -> None:
        rows = make_synthetic_rows()
        first = train_logistic(rows)
        second = train_logistic(rows)
        self.assertEqual(first["coefficients"], second["coefficients"])
        self.assertEqual(first["intercept"], second["intercept"])

    def test_artifact_json_round_trip_predicts_identically(self) -> None:
        rows = make_synthetic_rows()
        artifact = train_logistic(rows)
        restored = json.loads(json.dumps(artifact))

        probe = make_row("x", 5, 800, 1, 0)
        self.assertEqual(
            predict_from_artifact(artifact, probe), predict_from_artifact(restored, probe)
        )


class HeuristicBaselineTest(unittest.TestCase):
    def test_runs_on_snapshot_rows(self) -> None:
        probs = heuristic_probabilities(make_synthetic_rows(match_count=2))
        self.assertEqual(len(probs), 16)
        for p in probs:
            self.assertTrue(0.0 < p < 1.0)


class RunTrainingTest(unittest.TestCase):
    def _dataset(self, rows: list[dict], match_ids: list[str]) -> dict:
        return {
            "dataset_version": 1,
            "queue_id": 420,
            "domain": "soloq",
            "feature_names": FEATURE_NAMES,
            "matches_included": match_ids,
            "matches_excluded": {},
            "rows": rows,
        }

    def test_small_local_volume_keeps_heuristic(self) -> None:
        rows = make_synthetic_rows(match_count=12)
        report = run_training(self._dataset(rows, [f"KR_{m}" for m in range(12)]))

        self.assertEqual(report["status"], "trained")
        self.assertEqual(report["split"]["method"], "temporal_match_grouped")
        self.assertEqual(report["verdict"]["verdict"], "keep_heuristic")
        self.assertTrue(
            any("insufficient_data" in reason for reason in report["verdict"]["reasons"])
        )
        self.assertEqual(report["matches"], 12)
        self.assertLess(report["matches"], ADOPTION_MIN_MATCHES)
        # calibration report sections exist
        self.assertIn("reliability", report["model_eval"])
        self.assertIn("time_bucket_calibration", report)
        self.assertIn("patch_calibration", report)
        self.assertIn("heuristic_v0", report["baseline_evals"])

    def test_single_match_is_insufficient(self) -> None:
        rows = make_synthetic_rows(match_count=1)
        report = run_training(self._dataset(rows, ["KR_0"]))
        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["verdict"]["verdict"], "keep_heuristic")

    def test_snapshots_of_one_match_stay_in_one_split(self) -> None:
        rows = make_synthetic_rows(match_count=10)
        report = run_training(self._dataset(rows, [f"KR_{m}" for m in range(10)]))
        split = report["split"]
        self.assertEqual(split["train_rows"] % 8, 0)
        self.assertEqual(split["test_rows"] % 8, 0)
