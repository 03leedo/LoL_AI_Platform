import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.laning_metrics import calculate_laning_metric, laning_evidence


ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def make_match() -> dict:
    participants = []
    for participant_id in range(1, 11):
        team_index = (participant_id - 1) % 5
        participants.append(
            {
                "participantId": participant_id,
                "puuid": f"puuid-{participant_id}",
                "teamId": 100 if participant_id <= 5 else 200,
                "championName": f"Champion{participant_id}",
                "teamPosition": ROLES[team_index],
            }
        )
    return {"info": {"participants": participants}}


def make_timeline(player_values: dict[int, tuple[int, int, int]]) -> dict:
    participant_frames = {
        str(participant_id): {
            "totalGold": values[0],
            "xp": values[1],
            "minionsKilled": values[2],
            "jungleMinionsKilled": 0,
        }
        for participant_id, values in player_values.items()
    }
    return {
        "info": {
            "frames": [
                {"timestamp": 9 * 60_000, "participantFrames": {}},
                {"timestamp": 10 * 60_000, "participantFrames": participant_frames},
            ]
        }
    }


class LaningMetricsTest(unittest.TestCase):
    def test_compares_same_role_opponents_at_ten_minutes(self) -> None:
        match = make_match()
        player = match["info"]["participants"][2]
        timeline = make_timeline({3: (4_200, 5_000, 82), 8: (3_500, 4_400, 67)})

        metric = calculate_laning_metric(player, match, timeline)

        self.assertIsNotNone(metric)
        assert metric is not None
        self.assertEqual(metric["gd_at_10"], 700)
        self.assertEqual(metric["xpd_at_10"], 600)
        self.assertEqual(metric["csd_at_10"], 15)
        self.assertEqual(metric["opponent_champion"], "Champion8")
        self.assertGreater(metric["score"], 50)

    def test_score_is_symmetric_for_opposing_players(self) -> None:
        match = make_match()
        timeline = make_timeline({3: (4_200, 5_000, 82), 8: (3_500, 4_400, 67)})

        blue = calculate_laning_metric(match["info"]["participants"][2], match, timeline)
        red = calculate_laning_metric(match["info"]["participants"][7], match, timeline)

        self.assertIsNotNone(blue)
        self.assertIsNotNone(red)
        assert blue is not None and red is not None
        self.assertEqual(blue["score"] + red["score"], 100)

    def test_missing_ten_minute_frame_returns_none(self) -> None:
        match = make_match()
        timeline = {"info": {"frames": [{"timestamp": 9 * 60_000}]}}

        metric = calculate_laning_metric(match["info"]["participants"][2], match, timeline)

        self.assertIsNone(metric)

    def test_evidence_keeps_raw_differences_and_medium_confidence(self) -> None:
        match = make_match()
        player = match["info"]["participants"][2]
        timeline = make_timeline({3: (4_200, 5_000, 82), 8: (3_500, 4_400, 67)})
        metric = calculate_laning_metric(player, match, timeline)

        assert metric is not None
        evidence = laning_evidence(metric)

        self.assertEqual(evidence["confidence"], "medium")
        self.assertIn("골드 +700", evidence["description"])
        self.assertIn("경험치 +600", evidence["description"])
        self.assertIn("CS +15", evidence["description"])

    def test_extreme_difference_is_clamped_to_score_range(self) -> None:
        match = make_match()
        player = match["info"]["participants"][2]
        timeline = make_timeline({3: (20_000, 20_000, 300), 8: (0, 0, 0)})

        metric = calculate_laning_metric(player, match, timeline)

        self.assertIsNotNone(metric)
        assert metric is not None
        self.assertEqual(metric["score"], 100)


if __name__ == "__main__":
    unittest.main()
