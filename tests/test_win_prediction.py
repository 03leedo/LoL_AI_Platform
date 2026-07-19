import unittest

from app.services.win_prediction import build_served_win_curve


def make_feature(minute: int, **overrides) -> dict:
    feature = {
        "minute": minute,
        "timestamp_ms": minute * 60_000,
        "gold_diff": 0,
        "xp_diff": 0,
        "cs_diff": 0,
        "blue_tower_kills": 0,
        "red_tower_kills": 0,
        "blue_dragon_kills": 0,
        "red_dragon_kills": 0,
        "blue_herald_kills": 0,
        "red_herald_kills": 0,
        "blue_baron_kills": 0,
        "red_baron_kills": 0,
    }
    feature.update(overrides)
    return feature


class ServedWinPredictionTest(unittest.TestCase):
    def test_ranked_solo_uses_trained_model(self) -> None:
        result = build_served_win_curve(
            [make_feature(10), make_feature(11), make_feature(12)],
            queue_id=420,
        )

        self.assertEqual(result["source"], "model_v1_experimental")
        self.assertEqual(result["model_version"], 1)
        self.assertEqual(result["dataset_version"], 2)
        self.assertEqual(len(result["curve"]), 2)

    def test_each_prediction_only_uses_that_minutes_state(self) -> None:
        baseline = build_served_win_curve(
            [make_feature(10), make_feature(11), make_feature(12)],
            queue_id=420,
        )["curve"]
        changed = build_served_win_curve(
            [
                make_feature(10),
                make_feature(11, gold_diff=7000, xp_diff=5000),
                make_feature(12),
            ],
            queue_id=420,
        )["curve"]

        self.assertEqual(baseline[0]["blue_win_prob"], changed[0]["blue_win_prob"])
        self.assertGreater(changed[1]["blue_win_prob"], baseline[1]["blue_win_prob"])

    def test_non_solo_queue_uses_heuristic_fallback(self) -> None:
        result = build_served_win_curve(
            [make_feature(10), make_feature(11), make_feature(12)],
            queue_id=450,
        )

        self.assertEqual(result["source"], "heuristic_v0_fallback")
        self.assertIsNone(result["model_version"])
        self.assertEqual(len(result["curve"]), 3)


if __name__ == "__main__":
    unittest.main()
