import unittest

from app.services.profiles import (
    MIN_COHORT_ROWS,
    build_player_profile,
    dominant_role,
)

NOW_MS = 1_800_000_000_000
DAY_MS = 86_400_000


def make_record(
    match_id: str = "KR_1",
    role: str = "BOTTOM",
    days_ago: float = 0,
    scores: dict | None = None,
    challenges: dict | None = None,
) -> dict:
    return {
        "match_id": match_id,
        "role": role,
        "win": True,
        "game_creation": NOW_MS - int(days_ago * DAY_MS),
        "scores": scores or {
            "gambler_index": 20,
            "death_acceleration_index": 10,
            "death_cost_index": 20,
            "objective_setup_score": 60,
            "teamfight_persistence_score": 60,
        },
        "challenges": challenges or {
            "laningPhaseGoldExpAdvantage": 1,
            "earlyLaningPhaseGoldExpAdvantage": 1,
            "maxCsAdvantageOnLaneOpponent": 15,
            "killParticipation": 0.55,
            "teamDamagePercentage": 0.28,
            "dragonTakedowns": 2,
            "baronTakedowns": 0,
            "riftHeraldTakedowns": 1,
        },
        # Keys below mirror fetch_player_match_records' record contract.
        "damage_to_champions": 24_000,
        "gold_earned": 12_000,
        "deaths": 4,
        "game_duration": 1800,
    }


def make_cohort(count: int = 60) -> list[dict]:
    rows = []
    for i in range(count):
        rows.append(
            {
                "kills": 5,
                "deaths": 5,
                "assists": 6,
                "damage_to_champions": 18_000 + (i % 10) * 800,
                "gold_earned": 12_000,
                "vision_score": 20,
                "game_duration": 1800,
                "challenges": {
                    "laningPhaseGoldExpAdvantage": (i % 2),
                    "maxCsAdvantageOnLaneOpponent": float(i % 20),
                    "killParticipation": 0.4 + (i % 10) * 0.02,
                    "teamDamagePercentage": 0.18 + (i % 10) * 0.01,
                    "dragonTakedowns": i % 3,
                    "baronTakedowns": 0,
                    "riftHeraldTakedowns": i % 2,
                },
            }
        )
    return rows


class DominantRoleTest(unittest.TestCase):
    def test_most_played_role_wins(self) -> None:
        records = [make_record(role="BOTTOM") for _ in range(5)] + [make_record(role="TOP") for _ in range(2)]
        self.assertEqual(dominant_role(records), "BOTTOM")

    def test_empty_records_return_none(self) -> None:
        self.assertIsNone(dominant_role([]))


class ProfileTest(unittest.TestCase):
    def test_roles_are_never_averaged_together(self) -> None:
        # 5 strong BOTTOM games + 5 catastrophic TOP games: the BOTTOM profile
        # must be computed from BOTTOM records only.
        bad_scores = {
            "gambler_index": 95, "death_acceleration_index": 95, "death_cost_index": 95,
            "objective_setup_score": 5, "teamfight_persistence_score": 5,
        }
        records = (
            [make_record(match_id=f"B{i}", role="BOTTOM") for i in range(5)]
            + [make_record(match_id=f"T{i}", role="TOP", scores=bad_scores) for i in range(5)]
        )

        profile = build_player_profile(records, make_cohort(), role="BOTTOM", now_ms=NOW_MS)

        self.assertEqual(profile["games"], 5)
        risk = next(d for d in profile["dimensions"] if d["key"] == "risk_management")
        self.assertGreater(risk["raw_score"], 70)  # unaffected by TOP disasters
        self.assertTrue(all(mid.startswith("B") for mid in risk["evidence_match_ids"]))

    def test_three_games_do_not_yield_high_confidence_or_extreme_scores(self) -> None:
        records = [make_record(match_id=f"B{i}") for i in range(3)]

        profile = build_player_profile(records, make_cohort(), role="BOTTOM", now_ms=NOW_MS)
        risk = next(d for d in profile["dimensions"] if d["key"] == "risk_management")

        self.assertEqual(risk["confidence"], "low")
        # shrinkage: 3/(3+8)=0.27 → adjusted pulled well toward baseline 50
        self.assertLess(risk["score"], risk["raw_score"])
        self.assertLess(abs(risk["score"] - 50), abs(risk["raw_score"] - 50))

    def test_recency_weighting_prefers_recent_games(self) -> None:
        strong_recent = make_record(match_id="R", days_ago=0)
        weak_old = make_record(
            match_id="O",
            days_ago=60,
            scores={"gambler_index": 90, "death_acceleration_index": 90, "death_cost_index": 90,
                    "objective_setup_score": 60, "teamfight_persistence_score": 60},
        )
        records = [strong_recent, weak_old, make_record(match_id="R2", days_ago=1)]

        profile = build_player_profile(records, make_cohort(), role="BOTTOM", now_ms=NOW_MS)
        risk = next(d for d in profile["dimensions"] if d["key"] == "risk_management")

        # Old horrible game (weight e^{-60/14} ≈ 0.014) barely moves the needle.
        self.assertGreater(risk["raw_score"], 65)

    def test_dimensions_expose_submetrics_and_evidence(self) -> None:
        records = [make_record(match_id=f"B{i}") for i in range(6)]

        profile = build_player_profile(records, make_cohort(), role="BOTTOM", now_ms=NOW_MS)

        self.assertEqual(len(profile["dimensions"]), 5)
        early = next(d for d in profile["dimensions"] if d["key"] == "early_growth")
        self.assertTrue(early["submetrics"])
        self.assertEqual(len(early["evidence_match_ids"]), 6)
        self.assertIsNotNone(early["percentile"])
        self.assertIn("로컬 수집 표본", early["comparison_group"])

    def test_small_cohort_omits_percentiles_and_says_so(self) -> None:
        records = [make_record(match_id=f"B{i}") for i in range(6)]
        small_cohort = make_cohort(MIN_COHORT_ROWS - 1)

        profile = build_player_profile(records, small_cohort, role="BOTTOM", now_ms=NOW_MS)
        early = next(d for d in profile["dimensions"] if d["key"] == "early_growth")

        self.assertIsNone(early["percentile"])
        self.assertIn("비교 표본 부족", profile["comparison_group"])

    def test_insufficient_games_flagged(self) -> None:
        profile = build_player_profile([make_record()], make_cohort(), role="BOTTOM", now_ms=NOW_MS)

        self.assertTrue(profile["insufficient_data"])
        self.assertEqual(profile["dimensions"], [])

    def test_deterministic_output(self) -> None:
        records = [make_record(match_id=f"B{i}", days_ago=i) for i in range(6)]
        cohort = make_cohort()

        first = build_player_profile(records, cohort, role="BOTTOM", now_ms=NOW_MS)
        second = build_player_profile(records, cohort, role="BOTTOM", now_ms=NOW_MS)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
