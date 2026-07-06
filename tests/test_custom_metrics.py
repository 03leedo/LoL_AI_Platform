import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.custom_metrics import analyze_player_match


PLAYER_PUUID = "player-puuid"
MATCH_ID = "KR_1"


def make_match(win: bool = True) -> dict:
    participants = []
    for participant_id in range(1, 11):
        team_id = 100 if participant_id <= 5 else 200
        participants.append(
            {
                "participantId": participant_id,
                "puuid": PLAYER_PUUID if participant_id == 1 else f"puuid-{participant_id}",
                "teamId": team_id,
                "championName": "Ahri" if participant_id == 1 else "Champion",
                "teamPosition": "MIDDLE" if participant_id == 1 else "UTILITY",
                "win": win if team_id == 100 else not win,
            }
        )

    return {
        "info": {
            "participants": participants,
            "teams": [
                {"teamId": 100, "win": win},
                {"teamId": 200, "win": not win},
            ],
        }
    }


def make_timeline(events: list[dict]) -> dict:
    return {
        "info": {
            "frames": [
                {
                    "timestamp": index * 60_000,
                    "events": [
                        event
                        for event in events
                        if index * 60_000 <= int(event.get("timestamp", 0)) < (index + 1) * 60_000
                    ],
                }
                for index in range(31)
            ]
        }
    }


def make_features(points: dict[int, int]) -> list[dict]:
    return [
        {
            "match_id": MATCH_ID,
            "minute": minute,
            "timestamp_ms": minute * 60_000,
            "gold_diff": gold_diff,
        }
        for minute, gold_diff in sorted(points.items())
    ]


class CustomMetricsTest(unittest.TestCase):
    def test_death_before_dragon_loss_increases_death_cost(self) -> None:
        timeline = make_timeline(
            [
                {"type": "CHAMPION_KILL", "timestamp": 16 * 60_000 + 10_000, "victimId": 1, "killerId": 6},
                {
                    "type": "ELITE_MONSTER_KILL",
                    "timestamp": 16 * 60_000 + 50_000,
                    "killerId": 6,
                    "killerTeamId": 200,
                    "monsterType": "DRAGON",
                },
            ]
        )

        analysis = analyze_player_match(
            match_id=MATCH_ID,
            puuid=PLAYER_PUUID,
            match=make_match(),
            timeline=timeline,
            features=make_features({16: 500, 18: -300}),
        )

        self.assertGreaterEqual(analysis["scores"]["death_cost_index"]["value"], 20)
        self.assertTrue(any(item["type"] == "death_cost" for item in analysis["evidence"]))

    def test_death_while_ahead_with_gold_reversal_increases_throw_index(self) -> None:
        timeline = make_timeline(
            [
                {"type": "CHAMPION_KILL", "timestamp": 21 * 60_000, "victimId": 1, "killerId": 6},
                {
                    "type": "BUILDING_KILL",
                    "timestamp": 22 * 60_000,
                    "killerId": 6,
                    "teamId": 100,
                    "buildingType": "TOWER_BUILDING",
                },
            ]
        )

        analysis = analyze_player_match(
            match_id=MATCH_ID,
            puuid=PLAYER_PUUID,
            match=make_match(),
            timeline=timeline,
            features=make_features({20: 2500, 21: 2500, 22: -200, 23: -200}),
        )

        self.assertGreaterEqual(analysis["scores"]["throw_index"]["value"], 30)
        self.assertTrue(any(item["type"] == "throw_index" for item in analysis["evidence"]))

    def test_clean_objective_take_improves_objective_setup(self) -> None:
        timeline = make_timeline(
            [
                {
                    "type": "ELITE_MONSTER_KILL",
                    "timestamp": 12 * 60_000,
                    "killerId": 1,
                    "killerTeamId": 100,
                    "monsterType": "DRAGON",
                },
            ]
        )

        analysis = analyze_player_match(
            match_id=MATCH_ID,
            puuid=PLAYER_PUUID,
            match=make_match(),
            timeline=timeline,
            features=make_features({10: 800, 12: 1200}),
        )

        self.assertGreater(analysis["scores"]["objective_setup_score"]["value"], 50)
        self.assertTrue(any(item["type"] == "objective_setup" for item in analysis["evidence"]))

    def test_early_lead_converted_to_midgame_objectives_scores_conversion(self) -> None:
        timeline = make_timeline(
            [
                {
                    "type": "ELITE_MONSTER_KILL",
                    "timestamp": 18 * 60_000,
                    "killerId": 1,
                    "killerTeamId": 100,
                    "monsterType": "RIFTHERALD",
                },
                {
                    "type": "BUILDING_KILL",
                    "timestamp": 20 * 60_000,
                    "killerId": 1,
                    "teamId": 200,
                    "buildingType": "TOWER_BUILDING",
                },
            ]
        )

        analysis = analyze_player_match(
            match_id=MATCH_ID,
            puuid=PLAYER_PUUID,
            match=make_match(win=True),
            timeline=timeline,
            features=make_features({10: 1200, 15: 1800, 20: 2600, 25: 3200}),
        )

        self.assertIsNotNone(analysis["scores"]["lead_conversion_score"]["value"])
        self.assertGreater(analysis["scores"]["lead_conversion_score"]["value"], 60)
        self.assertTrue(any(item["type"] == "lead_conversion" for item in analysis["evidence"]))


if __name__ == "__main__":
    unittest.main()
