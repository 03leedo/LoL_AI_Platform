import unittest

from app.services.match_summaries import find_participant, summarize_match_for_player


def make_match(puuid: str = "stored-puuid") -> dict:
    return {
        "info": {
            "queueId": 420,
            "gameCreation": 1_700_000_000_000,
            "gameDuration": 1_800,
            "participants": [
                {
                    "puuid": puuid,
                    "riotIdGameName": "Hide on bush",
                    "riotIdTagline": "KR1",
                    "teamId": 100,
                    "championName": "Yone",
                    "win": True,
                    "kills": 3,
                    "deaths": 2,
                    "assists": 11,
                },
                {
                    "puuid": "other",
                    "riotIdGameName": "다른사람",
                    "riotIdTagline": "KR2",
                    "teamId": 200,
                    "championName": "Ahri",
                    "win": False,
                    "kills": 1,
                    "deaths": 3,
                    "assists": 2,
                },
            ],
        }
    }


class FindParticipantTest(unittest.TestCase):
    def test_puuid_match_wins(self) -> None:
        participant = find_participant(make_match(), "stored-puuid")
        self.assertEqual(participant["championName"], "Yone")

    def test_riot_id_fallback_after_key_rotation(self) -> None:
        # Cached matches keep puuids encrypted for a previous API key; the
        # freshly resolved puuid won't match, but the riot id still does.
        participant = find_participant(
            make_match(), "fresh-puuid", game_name="hide ON bush", tag_line="kr1"
        )
        self.assertEqual(participant["championName"], "Yone")

    def test_no_match_returns_none(self) -> None:
        self.assertIsNone(find_participant(make_match(), "fresh-puuid"))
        self.assertIsNone(
            find_participant(make_match(), "fresh-puuid", game_name="없는사람", tag_line="KR1")
        )


class SummarizeTest(unittest.TestCase):
    def test_summary_via_fallback(self) -> None:
        summary = summarize_match_for_player(
            match_id="KR_1",
            puuid="fresh-puuid",
            match=make_match(),
            game_name="Hide on bush",
            tag_line="KR1",
        )
        self.assertIsNotNone(summary)
        self.assertEqual(summary["champion_name"], "Yone")
        self.assertTrue(summary["win"])
        self.assertEqual(summary["kill_participation"], round((3 + 11) / 3 * 100))

    def test_summary_none_without_any_match(self) -> None:
        self.assertIsNone(
            summarize_match_for_player(match_id="KR_1", puuid="fresh-puuid", match=make_match())
        )
