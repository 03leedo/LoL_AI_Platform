import unittest

from app.services.scorecard import build_scorecard


def make_record(
    role: str = "MIDDLE",
    win: bool = True,
    scores: dict | None = None,
    challenges: dict | None = None,
) -> dict:
    return {
        "match_id": "KR_1",
        "role": role,
        "win": win,
        "scores": scores or {},
        "challenges": challenges or {},
    }


def solid_record(win: bool = True) -> dict:
    return make_record(
        win=win,
        scores={
            "stability_score": 70,
            "objective_setup_score": 62,
            "teamfight_persistence_score": 60,
            "gambler_index": 20,
            "death_acceleration_index": 10,
            "lead_conversion_score": 65,
        },
        challenges={
            "laningPhaseGoldExpAdvantage": 1,
            "earlyLaningPhaseGoldExpAdvantage": 1,
            "maxCsAdvantageOnLaneOpponent": 20,
            "killParticipation": 0.6,
            "teamDamagePercentage": 0.25,
            "dragonTakedowns": 2,
            "baronTakedowns": 1,
            "riftHeraldTakedowns": 0,
            "visionScoreAdvantageLaneOpponent": 0.4,
        },
    )


class ScorecardTest(unittest.TestCase):
    def test_empty_records_yield_null_abilities(self) -> None:
        scorecard = build_scorecard([])

        self.assertEqual(scorecard["games"], 0)
        for ability in scorecard["abilities"].values():
            self.assertIsNone(ability["value"])
            self.assertEqual(ability["confidence"], "low")

    def test_solid_sample_produces_positive_scores(self) -> None:
        records = [solid_record() for _ in range(6)]
        scorecard = build_scorecard(records)

        self.assertEqual(scorecard["games"], 6)
        abilities = scorecard["abilities"]
        self.assertGreater(abilities["laning"]["value"], 60)  # winning lane stats
        self.assertGreater(abilities["combat"]["value"], 50)
        self.assertGreater(abilities["objectives"]["value"], 50)
        self.assertGreater(abilities["map_awareness"]["value"], 50)
        self.assertEqual(abilities["lead_conversion"]["value"], 65)
        self.assertEqual(abilities["stability"]["value"], 70)
        # 6 games → medium confidence
        self.assertEqual(abilities["stability"]["confidence"], "medium")

    def test_confidence_scales_with_sample_size(self) -> None:
        high = build_scorecard([solid_record() for _ in range(10)])
        low = build_scorecard([solid_record() for _ in range(3)])

        self.assertEqual(high["abilities"]["stability"]["confidence"], "high")
        self.assertEqual(low["abilities"]["stability"]["confidence"], "low")

    def test_missing_challenges_disable_laning_only(self) -> None:
        records = [
            make_record(scores={"stability_score": 55, "gambler_index": 30})
            for _ in range(5)
        ]
        scorecard = build_scorecard(records)

        self.assertIsNone(scorecard["abilities"]["laning"]["value"])
        self.assertEqual(scorecard["abilities"]["laning"]["confidence"], "low")
        self.assertIsNotNone(scorecard["abilities"]["stability"]["value"])
        self.assertIsNotNone(scorecard["abilities"]["map_awareness"]["value"])

    def test_lead_conversion_requires_two_samples(self) -> None:
        records = [
            make_record(scores={"lead_conversion_score": 80}),
            make_record(scores={}),
        ]
        scorecard = build_scorecard(records)

        self.assertIsNone(scorecard["abilities"]["lead_conversion"]["value"])

    def test_values_are_clamped(self) -> None:
        records = [
            make_record(
                scores={"gambler_index": 100, "death_acceleration_index": 100},
                challenges={"visionScoreAdvantageLaneOpponent": -5},
            )
            for _ in range(5)
        ]
        scorecard = build_scorecard(records)

        self.assertGreaterEqual(scorecard["abilities"]["map_awareness"]["value"], 0)


if __name__ == "__main__":
    unittest.main()
