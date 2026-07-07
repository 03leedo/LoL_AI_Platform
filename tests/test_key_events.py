import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.key_events import extract_key_events


PLAYER_PUUID = "player-puuid"


def make_match() -> dict:
    champion_names = {
        1: "Ahri",
        2: "LeeSin",
        3: "Garen",
        4: "Ezreal",
        5: "Nami",
        6: "Jinx",
        7: "Leona",
        8: "Orianna",
        9: "Darius",
        10: "KhaZix",
    }
    return {
        "info": {
            "participants": [
                {
                    "participantId": participant_id,
                    "puuid": PLAYER_PUUID if participant_id == 1 else f"puuid-{participant_id}",
                    "teamId": 100 if participant_id <= 5 else 200,
                    "championName": champion_names[participant_id],
                }
                for participant_id in range(1, 11)
            ]
        }
    }


def make_timeline(events: list[dict]) -> dict:
    return {
        "info": {
            "frames": [
                {
                    "timestamp": minute * 60_000,
                    "participantFrames": {
                        str(participant_id): {
                            "participantId": participant_id,
                            "position": {
                                "x": 900 + participant_id * 1000,
                                "y": 1100 + participant_id * 900,
                            },
                        }
                        for participant_id in range(1, 11)
                    },
                    "events": [
                        event
                        for event in events
                        if minute * 60_000 <= int(event.get("timestamp", 0)) < (minute + 1) * 60_000
                    ],
                }
                for minute in range(4)
            ]
        }
    }


class KeyEventsTest(unittest.TestCase):
    def test_kill_event_contains_log_and_minimap_snapshot(self) -> None:
        events = [
            {
                "type": "CHAMPION_KILL",
                "timestamp": 65_000,
                "killerId": 6,
                "victimId": 1,
                "assistingParticipantIds": [7],
                "position": {"x": 5600, "y": 8400},
                "shutdownBounty": 150,
            }
        ]

        key_events = extract_key_events(match=make_match(), timeline=make_timeline(events), puuid=PLAYER_PUUID)

        self.assertEqual(len(key_events), 1)
        kill = key_events[0]
        self.assertEqual(kill["type"], "kill")
        self.assertEqual(kill["team"], "red")
        self.assertIn("Jinx", kill["title"])
        self.assertIn("Ahri", kill["title"])
        self.assertEqual(kill["position_x"], 5600)
        self.assertEqual(kill["position_y"], 8400)

        player = next(item for item in kill["participants"] if item["participant_id"] == 1)
        killer = next(item for item in kill["participants"] if item["participant_id"] == 6)
        self.assertTrue(player["is_player"])
        self.assertTrue(player["is_actor"])
        self.assertTrue(killer["is_actor"])
        self.assertIsNotNone(player["x"])
        self.assertIsNotNone(player["y"])

    def test_dragon_event_contains_team_and_snapshot(self) -> None:
        events = [
            {
                "type": "ELITE_MONSTER_KILL",
                "timestamp": 125_000,
                "killerId": 2,
                "killerTeamId": 100,
                "monsterType": "DRAGON",
                "monsterSubType": "FIRE_DRAGON",
                "position": {"x": 9866, "y": 4414},
            }
        ]

        key_events = extract_key_events(match=make_match(), timeline=make_timeline(events), puuid=PLAYER_PUUID)

        self.assertEqual(len(key_events), 1)
        dragon = key_events[0]
        self.assertEqual(dragon["type"], "dragon")
        self.assertEqual(dragon["team"], "blue")
        self.assertIn("드래곤", dragon["title"])
        self.assertEqual(dragon["position_x"], 9866)
        self.assertEqual(len(dragon["participants"]), 10)

        killer = next(item for item in dragon["participants"] if item["participant_id"] == 2)
        self.assertTrue(killer["is_actor"])
        self.assertEqual(killer["team"], "blue")


if __name__ == "__main__":
    unittest.main()
