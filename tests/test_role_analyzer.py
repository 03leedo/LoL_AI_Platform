import unittest

from app.services.role_analyzer import build_role_analysis


def make_record(role: str, win: bool, stability: int = 50, kp: float = 0.5) -> dict:
    return {
        "match_id": "KR_1",
        "role": role,
        "win": win,
        "scores": {"stability_score": stability, "objective_setup_score": 50},
        "challenges": {"killParticipation": kp},
    }


class RoleAnalyzerTest(unittest.TestCase):
    def test_small_hot_streak_does_not_outrank_solid_main_role(self) -> None:
        records = (
            # 10 TOP games at 60% win rate
            [make_record("TOP", win=i < 6) for i in range(10)]
            # 2 MIDDLE games, both wins — sample too small to trust
            + [make_record("MIDDLE", win=True) for _ in range(2)]
        )

        analysis = build_role_analysis(records)
        by_role = {role["role"]: role for role in analysis["roles"]}

        self.assertEqual(by_role["TOP"]["games"], 10)
        self.assertEqual(by_role["MIDDLE"]["games"], 2)
        # MIDDLE is excluded from recommendation despite its 100% win rate.
        self.assertIn("TOP", analysis["recommended"])
        self.assertNotIn("MIDDLE", analysis["recommended"])

    def test_shrinkage_pulls_small_samples_toward_neutral(self) -> None:
        two_wins = build_role_analysis([make_record("JUNGLE", win=True) for _ in range(2)])
        eight_wins = build_role_analysis([make_record("JUNGLE", win=True) for _ in range(8)])

        small = next(r for r in two_wins["roles"] if r["role"] == "JUNGLE")["fit_score"]
        large = next(r for r in eight_wins["roles"] if r["role"] == "JUNGLE")["fit_score"]

        self.assertLess(small, large)
        self.assertLessEqual(abs(small - 50), abs(large - 50))

    def test_caution_role_flagged_when_fit_is_low(self) -> None:
        records = (
            [make_record("MIDDLE", win=True) for _ in range(6)]
            # 5 UTILITY games, all losses with shaky stability
            + [make_record("UTILITY", win=False, stability=30, kp=0.3) for _ in range(5)]
        )

        analysis = build_role_analysis(records)

        self.assertEqual(analysis["caution"], "UTILITY")

    def test_unknown_roles_are_ignored(self) -> None:
        records = [make_record("", win=True), make_record("ARAM", win=True)]
        analysis = build_role_analysis(records)

        self.assertTrue(all(role["games"] == 0 for role in analysis["roles"]))
        self.assertEqual(analysis["recommended"], [])

    def test_confidence_by_sample_size(self) -> None:
        records = [make_record("BOTTOM", win=True) for _ in range(8)]
        analysis = build_role_analysis(records)
        bottom = next(r for r in analysis["roles"] if r["role"] == "BOTTOM")

        self.assertEqual(bottom["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
