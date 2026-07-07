import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.evidence_contexts import attach_evidence_contexts, build_review_assets


PLAYER_PUUID = "player-puuid"


def make_match() -> dict:
    return {
        "info": {
            "gameVersion": "15.13.685.1234",
            "mapId": 11,
            "participants": [
                {
                    "participantId": participant_id,
                    "puuid": PLAYER_PUUID if participant_id == 1 else f"puuid-{participant_id}",
                    "teamId": 100 if participant_id <= 5 else 200,
                    "championName": "Ahri" if participant_id == 1 else f"Champion{participant_id}",
                }
                for participant_id in range(1, 11)
            ],
        }
    }


def make_timeline(events: list[dict] | None = None) -> dict:
    events = events or [
        {
            "type": "WARD_PLACED",
            "timestamp": 40_000,
            "creatorId": 1,
            "wardType": "CONTROL_WARD",
        },
        {
            "type": "CHAMPION_KILL",
            "timestamp": 65_000,
            "killerId": 6,
            "victimId": 1,
            "position": {"x": 5600, "y": 8400},
        },
        {
            "type": "ELITE_MONSTER_KILL",
            "timestamp": 90_000,
            "killerId": 6,
            "killerTeamId": 200,
            "monsterType": "DRAGON",
        },
    ]
    return {
        "info": {
            "frames": [
                {
                    "timestamp": minute * 60_000,
                    "participantFrames": {
                        str(participant_id): {
                            "participantId": participant_id,
                            "position": {
                                "x": 1000 + participant_id * 700 + minute * 50,
                                "y": 1400 + participant_id * 650 + minute * 70,
                            },
                        }
                        for participant_id in range(1, 11)
                    },
                    "events": [
                        event
                        for event in events
                        if minute * 60_000 <= int(event["timestamp"]) < (minute + 1) * 60_000
                    ],
                }
                for minute in range(4)
            ]
        }
    }


class EvidenceContextsTest(unittest.TestCase):
    def test_attaches_timeline_context_to_evidence(self) -> None:
        analysis = {
            "match_id": "KR_1",
            "player": {
                "puuid": PLAYER_PUUID,
                "champion": "Ahri",
                "role": "MIDDLE",
                "team": "blue",
                "win": False,
            },
            "scores": {},
            "evidence": [
                {
                    "minute": 1,
                    "type": "death_cost",
                    "title": "Death was followed by objective loss",
                    "description": "Within 90 seconds of this death, the opposing team secured Dragon.",
                    "confidence": "medium",
                }
            ],
        }

        enriched = attach_evidence_contexts(
            analysis=analysis,
            match=make_match(),
            timeline=make_timeline(),
            puuid=PLAYER_PUUID,
        )

        context = enriched["evidence"][0]["context"]
        self.assertEqual(context["anchor_timestamp_ms"], 65_000)
        self.assertEqual(context["window_start_ms"], 35_000)
        self.assertEqual(context["window_end_ms"], 95_000)
        self.assertGreaterEqual(len(context["snapshots"]), 1)
        self.assertTrue(any(event["type"] == "kill" for event in context["events"]))
        self.assertTrue(any(event["type"] == "dragon" for event in context["events"]))
        self.assertTrue(any(event["type"] == "ward_placed" for event in context["events"]))
        self.assertTrue(context["insights"])
        self.assertIn("상대", context["insights"][0]["description"])
        self.assertEqual(context["summary"]["ally_deaths"], 1)
        self.assertEqual(context["summary"]["objective_events"], 1)

        dragon = next(event for event in context["events"] if event["type"] == "dragon")
        self.assertEqual(dragon["position_source"], "objective_spawn")
        self.assertEqual(dragon["position_x"], 9866)

        final_snapshot = context["snapshots"][-1]
        self.assertEqual(final_snapshot["objective_state"]["red_dragons"], 0)
        self.assertTrue(any(event["type"] == "dragon" and event["team"] == "red" for event in context["events"]))
        self.assertTrue(any(item["is_player"] for item in final_snapshot["participants"]))
        self.assertTrue(final_snapshot["ward_events"])

    def test_review_assets_include_ddragon_version(self) -> None:
        self.assertEqual(build_review_assets(make_match())["data_dragon_version"], "15.13.1")

    def test_teamfight_loss_insight_is_prioritized_over_vision(self) -> None:
        timeline = make_timeline(
            [
                {
                    "type": "WARD_PLACED",
                    "timestamp": 38_000,
                    "creatorId": 6,
                    "wardType": "CONTROL_WARD",
                },
                {"type": "CHAMPION_KILL", "timestamp": 62_000, "killerId": 6, "victimId": 1},
                {"type": "CHAMPION_KILL", "timestamp": 66_000, "killerId": 7, "victimId": 2},
                {"type": "CHAMPION_KILL", "timestamp": 70_000, "killerId": 3, "victimId": 8},
                {
                    "type": "ELITE_MONSTER_KILL",
                    "timestamp": 84_000,
                    "killerId": 6,
                    "killerTeamId": 200,
                    "monsterType": "DRAGON",
                },
            ]
        )
        analysis = {
            "match_id": "KR_1",
            "player": {
                "puuid": PLAYER_PUUID,
                "champion": "Ahri",
                "role": "MIDDLE",
                "team": "blue",
                "win": False,
            },
            "scores": {},
            "evidence": [
                {
                    "minute": 1,
                    "type": "death_cost",
                    "title": "Death was followed by objective loss",
                    "description": "The opposing team secured Dragon after the fight.",
                    "confidence": "medium",
                }
            ],
        }

        enriched = attach_evidence_contexts(
            analysis=analysis,
            match=make_match(),
            timeline=timeline,
            puuid=PLAYER_PUUID,
        )

        insights = enriched["evidence"][0]["context"]["insights"]
        self.assertIn("한타", insights[0]["title"])
        self.assertIn("시야", insights[1]["title"])


if __name__ == "__main__":
    unittest.main()
