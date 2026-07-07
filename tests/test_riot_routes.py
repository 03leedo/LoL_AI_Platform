import unittest

from app.services.match_summaries import summarize_match_for_player


class RiotRoutesTest(unittest.TestCase):
    def test_summarize_match_for_player_includes_performance_stats(self) -> None:
        match = {
            "info": {
                "queueId": 420,
                "gameCreation": 1_720_000_000_000,
                "gameDuration": 1800,
                "participants": [
                    {
                        "puuid": "player-puuid",
                        "teamId": 100,
                        "championName": "Ahri",
                        "teamPosition": "MIDDLE",
                        "win": True,
                        "kills": 8,
                        "deaths": 2,
                        "assists": 7,
                        "totalMinionsKilled": 210,
                        "neutralMinionsKilled": 12,
                        "visionScore": 26,
                        "totalDamageDealtToChampions": 24_500,
                        "totalDamageTaken": 15_200,
                        "goldEarned": 13_400,
                    },
                    {"puuid": "ally-1", "teamId": 100, "kills": 5},
                    {"puuid": "ally-2", "teamId": 100, "kills": 7},
                    {"puuid": "ally-3", "teamId": 100, "kills": 0},
                    {"puuid": "ally-4", "teamId": 100, "kills": 0},
                ],
            }
        }

        summary = summarize_match_for_player(match_id="KR_1", puuid="player-puuid", match=match)

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["total_damage_dealt_to_champions"], 24_500)
        self.assertEqual(summary["total_damage_taken"], 15_200)
        self.assertEqual(summary["gold_earned"], 13_400)
        self.assertEqual(summary["kill_participation"], 75)

    def test_summarize_match_for_player_handles_zero_team_kills(self) -> None:
        match = {
            "info": {
                "participants": [
                    {
                        "puuid": "player-puuid",
                        "teamId": 100,
                        "kills": 0,
                        "assists": 0,
                    }
                ]
            }
        }

        summary = summarize_match_for_player(match_id="KR_2", puuid="player-puuid", match=match)

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertIsNone(summary["kill_participation"])


if __name__ == "__main__":
    unittest.main()
