import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.laning_metrics import (
    calculate_laning_metric,
    early_impact_evidence,
    lane_pressure_evidence,
    laning_evidence,
)


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


def make_timeline(
    player_values: dict[int, tuple[int, int, int]],
    events: list[dict] | None = None,
) -> dict:
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
                {
                    "timestamp": 10 * 60_000,
                    "participantFrames": participant_frames,
                    "events": events or [],
                },
            ]
        }
    }


def make_pressure_frame(
    minute: int,
    player_health: int,
    opponent_health: int,
    distance: int = 1_000,
) -> dict:
    return {
        "timestamp": minute * 60_000,
        "participantFrames": {
            "3": {
                "totalGold": 4_000,
                "xp": 5_000,
                "minionsKilled": 80,
                "championStats": {"health": player_health, "healthMax": 1_000},
                "position": {"x": 5_000, "y": 5_000},
            },
            "8": {
                "totalGold": 4_000,
                "xp": 5_000,
                "minionsKilled": 80,
                "championStats": {"health": opponent_health, "healthMax": 1_000},
                "position": {"x": 5_000 + distance, "y": 5_000},
            },
        },
        "events": [],
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

    def test_early_impact_uses_smoothed_kp_and_direct_matchup(self) -> None:
        match = make_match()
        player = match["info"]["participants"][2]
        events = [
            {
                "type": "CHAMPION_KILL",
                "timestamp": 5 * 60_000,
                "killerId": 3,
                "victimId": 8,
            },
            {
                "type": "CHAMPION_KILL",
                "timestamp": 6 * 60_000,
                "killerId": 1,
                "victimId": 6,
                "assistingParticipantIds": [3],
            },
            {
                "type": "CHAMPION_KILL",
                "timestamp": 7 * 60_000,
                "killerId": 2,
                "victimId": 7,
            },
            {
                "type": "CHAMPION_KILL",
                "timestamp": 8 * 60_000,
                "killerId": 8,
                "victimId": 1,
            },
            {
                "type": "CHAMPION_KILL",
                "timestamp": 9 * 60_000,
                "killerId": 6,
                "victimId": 2,
            },
        ]
        timeline = make_timeline(
            {3: (4_000, 5_000, 80), 8: (4_000, 5_000, 80)}, events=events
        )

        metric = calculate_laning_metric(player, match, timeline)

        self.assertIsNotNone(metric)
        assert metric is not None
        self.assertEqual(metric["player_early_takedowns"], 2)
        self.assertEqual(metric["player_team_kills"], 3)
        self.assertEqual(metric["opponent_early_takedowns"], 1)
        self.assertEqual(metric["opponent_team_kills"], 2)
        self.assertEqual(metric["direct_takedown_diff"], 1)
        self.assertEqual(metric["early_impact_score"], 64)
        self.assertEqual(metric["early_impact_confidence"], "medium")
        self.assertIn("67%", early_impact_evidence(metric)["description"])

    def test_early_impact_is_symmetric_for_same_role_opponents(self) -> None:
        match = make_match()
        events = [
            {
                "type": "CHAMPION_KILL",
                "timestamp": 5 * 60_000,
                "killerId": 3,
                "victimId": 8,
            },
            {
                "type": "CHAMPION_KILL",
                "timestamp": 6 * 60_000,
                "killerId": 1,
                "victimId": 6,
                "assistingParticipantIds": [3],
            },
        ]
        timeline = make_timeline(
            {3: (4_000, 5_000, 80), 8: (4_000, 5_000, 80)}, events=events
        )

        blue = calculate_laning_metric(match["info"]["participants"][2], match, timeline)
        red = calculate_laning_metric(match["info"]["participants"][7], match, timeline)

        assert blue is not None and red is not None
        self.assertIsNotNone(blue["early_impact_score"])
        self.assertIsNotNone(red["early_impact_score"])
        assert blue["early_impact_score"] is not None
        assert red["early_impact_score"] is not None
        self.assertEqual(blue["early_impact_score"] + red["early_impact_score"], 100)

    def test_no_early_kills_returns_unscored_impact(self) -> None:
        match = make_match()
        player = match["info"]["participants"][2]
        timeline = make_timeline({3: (4_000, 5_000, 80), 8: (4_000, 5_000, 80)})

        metric = calculate_laning_metric(player, match, timeline)

        assert metric is not None
        self.assertIsNone(metric["early_impact_score"])
        evidence = early_impact_evidence(metric)
        self.assertEqual(evidence["confidence"], "low")
        self.assertIn("계산하지 않았습니다", evidence["description"])

    def test_low_health_pressure_is_evidence_only(self) -> None:
        match = make_match()
        player = match["info"]["participants"][2]
        timeline = {
            "info": {
                "frames": [
                    make_pressure_frame(3, 300, 800),
                    make_pressure_frame(4, 250, 750),
                    make_pressure_frame(5, 200, 700),
                    make_pressure_frame(10, 900, 900),
                ]
            }
        }

        metric = calculate_laning_metric(player, match, timeline)

        assert metric is not None
        self.assertEqual(metric["score"], 50)
        self.assertEqual(metric["pressure_comparable_frames"], 4)
        self.assertEqual(metric["player_low_health_frames"], 3)
        self.assertEqual(metric["opponent_low_health_frames"], 0)
        evidence = lane_pressure_evidence(metric)
        self.assertEqual(evidence["confidence"], "low")
        self.assertIn("플레이어 3회, 상대 0회", evidence["description"])

    def test_distant_health_snapshots_are_not_compared(self) -> None:
        match = make_match()
        player = match["info"]["participants"][2]
        timeline = {
            "info": {
                "frames": [
                    make_pressure_frame(3, 200, 900, distance=4_000),
                    make_pressure_frame(10, 900, 900),
                ]
            }
        }

        metric = calculate_laning_metric(player, match, timeline)

        assert metric is not None
        self.assertEqual(metric["pressure_comparable_frames"], 1)
        evidence = lane_pressure_evidence(metric)
        self.assertEqual(evidence["title"], "체력 압박은 점수에서 제외")


if __name__ == "__main__":
    unittest.main()
