import asyncio
import unittest

from app.services.heatmaps import (
    ZONE_ALLY_JUNGLE,
    ZONE_BOT,
    ZONE_ENEMY_JUNGLE,
    ZONE_MID,
    ZONE_TOP,
    build_summoner_heatmap,
    zone_of,
)


class ZoneOfTest(unittest.TestCase):
    def test_lane_classification(self) -> None:
        self.assertEqual(zone_of(7500, 7500, 100), ZONE_MID)
        self.assertEqual(zone_of(1000, 8000, 100), ZONE_TOP)
        self.assertEqual(zone_of(9000, 13_000, 100), ZONE_TOP)
        self.assertEqual(zone_of(8000, 1000, 100), ZONE_BOT)
        self.assertEqual(zone_of(13_000, 9000, 100), ZONE_BOT)

    def test_jungle_side_depends_on_team(self) -> None:
        # Both points sit well off the mid-lane diagonal (|x-y| >= 4000).
        blue_side_jungle = (4000, 8000)  # x+y < 15000
        red_side_jungle = (11_000, 7000)  # x+y > 15000

        self.assertEqual(zone_of(*blue_side_jungle, 100), ZONE_ALLY_JUNGLE)
        self.assertEqual(zone_of(*blue_side_jungle, 200), ZONE_ENEMY_JUNGLE)
        self.assertEqual(zone_of(*red_side_jungle, 100), ZONE_ENEMY_JUNGLE)
        self.assertEqual(zone_of(*red_side_jungle, 200), ZONE_ALLY_JUNGLE)


class StubSession:
    def __init__(self) -> None:
        self.commits = 0
        self.added: list = []

    async def get(self, model, primary_key):
        return None

    async def merge(self, obj):
        return obj

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    async def execute(self, stmt):
        return None

    def add_all(self, rows) -> None:
        self.added.extend(rows)


def make_match(puuid: str, participant_id: int, team_id: int) -> dict:
    participants = []
    for pid in range(1, 11):
        participants.append(
            {
                "participantId": pid,
                "puuid": puuid if pid == participant_id else f"other-{pid}",
                "teamId": 100 if pid <= 5 else 200,
            }
        )
    return {"info": {"queueId": 420, "participants": participants}}


def make_timeline(events: list[dict]) -> dict:
    return {"info": {"frames": [{"timestamp": 0, "events": events}]}}


class StubRiotClient:
    def __init__(self, matches: dict[str, dict], timelines: dict[str, dict]) -> None:
        self.matches = matches
        self.timelines = timelines

    async def get_match(self, match_id: str) -> dict:
        return self.matches[match_id]

    async def get_match_timeline(self, match_id: str) -> dict:
        return self.timelines[match_id]


class BuildHeatmapTest(unittest.TestCase):
    def test_extracts_kill_and_death_points_with_zones(self) -> None:
        puuid = "player-puuid"
        events = [
            {  # my kill in mid lane
                "type": "CHAMPION_KILL",
                "timestamp": 600_000,
                "killerId": 1,
                "victimId": 6,
                "position": {"x": 7500, "y": 7500},
            },
            {  # my death deep in red jungle
                "type": "CHAMPION_KILL",
                "timestamp": 900_000,
                "killerId": 7,
                "victimId": 1,
                "position": {"x": 11_000, "y": 7000},
            },
            {  # unrelated kill between other players
                "type": "CHAMPION_KILL",
                "timestamp": 950_000,
                "killerId": 8,
                "victimId": 3,
                "position": {"x": 5000, "y": 5000},
            },
        ]
        db = StubSession()
        client = StubRiotClient(
            matches={"KR_1": make_match(puuid, participant_id=1, team_id=100)},
            timelines={"KR_1": make_timeline(events)},
        )

        heatmap = asyncio.run(
            build_summoner_heatmap(db, client, puuid, ["KR_1"], platform_routing="kr")
        )

        self.assertEqual(heatmap["matches_analyzed"], 1)
        self.assertEqual(len(heatmap["kills"]), 1)
        self.assertEqual(len(heatmap["deaths"]), 1)
        self.assertEqual(heatmap["kills"][0]["zone"], ZONE_MID)
        self.assertEqual(heatmap["deaths"][0]["zone"], ZONE_ENEMY_JUNGLE)
        self.assertEqual(heatmap["deaths"][0]["side"], "blue")
        # Freshly fetched timeline events were persisted for future aggregates.
        self.assertGreater(len(db.added), 0)

    def test_zone_stats_share_and_death_zone_flag(self) -> None:
        puuid = "player-puuid"
        deaths = [
            {
                "type": "CHAMPION_KILL",
                "timestamp": (10 + i) * 60_000,
                "killerId": 7,
                "victimId": 1,
                "position": {"x": 11_000, "y": 7000},
            }
            for i in range(4)
        ] + [
            {
                "type": "CHAMPION_KILL",
                "timestamp": 20 * 60_000,
                "killerId": 7,
                "victimId": 1,
                "position": {"x": 7500, "y": 7500},
            }
        ]
        db = StubSession()
        client = StubRiotClient(
            matches={"KR_1": make_match(puuid, participant_id=1, team_id=100)},
            timelines={"KR_1": make_timeline(deaths)},
        )

        heatmap = asyncio.run(
            build_summoner_heatmap(db, client, puuid, ["KR_1"], platform_routing="kr")
        )

        top_zone = heatmap["death_zones"][0]
        self.assertEqual(top_zone["zone"], ZONE_ENEMY_JUNGLE)
        self.assertEqual(top_zone["count"], 4)
        self.assertAlmostEqual(top_zone["share"], 0.8)
        self.assertTrue(top_zone["is_death_zone"])

        mid_zone = next(z for z in heatmap["death_zones"] if z["zone"] == ZONE_MID)
        self.assertFalse(mid_zone["is_death_zone"])

    def test_missing_player_match_is_skipped(self) -> None:
        db = StubSession()
        client = StubRiotClient(
            matches={"KR_1": make_match("someone-else", participant_id=1, team_id=100)},
            timelines={"KR_1": make_timeline([])},
        )

        heatmap = asyncio.run(
            build_summoner_heatmap(db, client, "player-puuid", ["KR_1"], platform_routing="kr")
        )

        self.assertEqual(heatmap["matches_analyzed"], 0)
        self.assertEqual(heatmap["kills"], [])


if __name__ == "__main__":
    unittest.main()
