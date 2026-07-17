import unittest

from app.services.representative_matches import build_match_selections
from tests.test_profiles import NOW_MS, make_record


def scores(quality: int) -> dict:
    """quality 0-100 → coherent per-match metric scores."""
    return {
        "gambler_index": 100 - quality,
        "death_acceleration_index": 100 - quality,
        "death_cost_index": 100 - quality,
        "objective_setup_score": quality,
        "teamfight_persistence_score": quality,
    }


def typical(match_id: str, days_ago: float = 0) -> dict:
    return make_record(match_id=match_id, days_ago=days_ago, scores=scores(60))


class SelectionTest(unittest.TestCase):
    def test_outlier_is_deviation_and_typical_is_representative(self) -> None:
        records = [typical(f"T{i}", days_ago=i) for i in range(5)] + [
            make_record(match_id="OUTLIER", days_ago=2, scores=scores(98))
        ]

        result = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)

        self.assertFalse(result["insufficient_data"])
        self.assertEqual(result["deviation"]["match_id"], "OUTLIER")
        self.assertTrue(result["representative"]["match_id"].startswith("T"))

    def test_deviation_can_be_a_positive_game(self) -> None:
        records = [typical(f"T{i}") for i in range(5)] + [
            make_record(match_id="GREAT", scores=scores(98))
        ]

        result = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)
        deviation = result["deviation"]

        self.assertEqual(deviation["match_id"], "GREAT")
        # Drivers show positive diffs — deviation ≠ worst game.
        self.assertTrue(any(d["diff"] > 0 for d in deviation["drivers"]))
        self.assertIn("달랐던", deviation["reason"])

    def test_best_is_highest_context_adjusted_mean(self) -> None:
        records = (
            [typical(f"T{i}") for i in range(4)]
            + [make_record(match_id="BEST", scores=scores(95))]
            + [make_record(match_id="BAD", scores=scores(15))]
        )

        result = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)

        self.assertEqual(result["best"]["match_id"], "BEST")

    def test_low_data_matches_are_excluded_and_counted(self) -> None:
        sparse = make_record(match_id="SPARSE")
        sparse["scores"] = {}  # make_record treats {} as falsy, so overwrite directly
        sparse["challenges"] = {}
        sparse["damage_to_champions"] = None
        sparse["gold_earned"] = None
        records = [typical(f"T{i}") for i in range(5)] + [sparse]

        result = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)

        self.assertEqual(result["excluded_matches"], 1)
        self.assertEqual(result["eligible_matches"], 5)
        for selection in (result["representative"], result["best"], result["deviation"]):
            self.assertNotEqual(selection["match_id"], "SPARSE")

    def test_insufficient_eligible_matches_flagged(self) -> None:
        records = [typical(f"T{i}") for i in range(4)]

        result = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)

        self.assertTrue(result["insufficient_data"])
        self.assertIsNone(result["representative"])

    def test_other_roles_are_ignored(self) -> None:
        records = [typical(f"B{i}") for i in range(5)] + [
            make_record(match_id=f"TOP{i}", role="TOP", scores=scores(99)) for i in range(3)
        ]

        result = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)

        self.assertEqual(result["games_considered"], 5)
        self.assertFalse(result["best"]["match_id"].startswith("TOP"))

    def test_deterministic_and_tie_breaks_by_recency(self) -> None:
        # NEWER and OLDER share an identical vector (exact distance tie);
        # fillers are extreme so the tied pair is clearly the closest.
        newer = typical("NEWER", days_ago=0)
        older = typical("OLDER", days_ago=5)
        filler = [make_record(match_id=f"F{i}", days_ago=1, scores=scores(95)) for i in range(4)]
        records = [older, newer] + filler

        first = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)
        second = build_match_selections(list(reversed(records)), role="BOTTOM", now_ms=NOW_MS)

        self.assertEqual(first["representative"]["match_id"], second["representative"]["match_id"])
        self.assertEqual(first["deviation"]["match_id"], second["deviation"]["match_id"])
        self.assertEqual(first["best"]["match_id"], second["best"]["match_id"])
        # Exact distance tie between NEWER and OLDER → the newer game wins.
        if first["representative"]["match_id"] in {"NEWER", "OLDER"}:
            self.assertEqual(first["representative"]["match_id"], "NEWER")
        else:
            self.assertEqual(first["deviation"]["match_id"], "NEWER")

    def test_partial_dimension_match_stays_eligible_and_best_prefers_coverage(self) -> None:
        # Strip challenges + damage/gold so exactly 3 dimensions compute
        # (risk_management, objective_readiness, fight_contribution).
        partial = make_record(match_id="PARTIAL", scores=scores(99))
        partial["challenges"] = {}
        partial["damage_to_champions"] = None
        partial["gold_earned"] = None
        records = [typical(f"T{i}") for i in range(5)] + [partial]

        result = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)

        self.assertEqual(result["eligible_matches"], 6)
        self.assertEqual(result["excluded_matches"], 0)
        # Best prefers full-coverage matches: PARTIAL's 3-dim 99-mean must not
        # beat 5-dim matches.
        self.assertNotEqual(result["best"]["match_id"], "PARTIAL")
        self.assertEqual(result["best"]["dimensions_used"], 5)
        # PARTIAL's vector carries explicit Nones for missing dimensions.
        deviation = result["deviation"]
        self.assertEqual(deviation["match_id"], "PARTIAL")
        self.assertIsNone(deviation["vector"]["early_growth"])

        # Determinism holds with mixed coverage.
        again = build_match_selections(list(reversed(records)), role="BOTTOM", now_ms=NOW_MS)
        self.assertEqual(result["best"]["match_id"], again["best"]["match_id"])

    def test_selection_metadata_is_complete(self) -> None:
        records = [typical(f"T{i}") for i in range(6)]
        result = build_match_selections(records, role="BOTTOM", now_ms=NOW_MS)

        for selection in (result["representative"], result["best"], result["deviation"]):
            self.assertTrue(selection["reason"])
            self.assertEqual(len(selection["drivers"]), 2)
            self.assertIn("early_growth", selection["vector"])
        self.assertEqual(result["selection_version"], 1)
        self.assertTrue(result["method"])


if __name__ == "__main__":
    unittest.main()
