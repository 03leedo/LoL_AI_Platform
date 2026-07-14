import unittest

from app.services.episodes import (
    attribute_objectives_to_deaths,
    build_fight_episodes,
    elite_availability_windows,
    is_objective_analyzable_death,
)


def kill(ts_ms: int, killer: int = 1, victim: int = 6, x: int | None = 7500, y: int | None = 7500) -> dict:
    event: dict = {"type": "CHAMPION_KILL", "timestamp": ts_ms, "killerId": killer, "victimId": victim}
    if x is not None and y is not None:
        event["position"] = {"x": x, "y": y}
    return event


class FightEpisodeTest(unittest.TestCase):
    def test_close_kills_cluster_into_one_episode(self) -> None:
        episodes = build_fight_episodes([
            kill(100_000), kill(110_000, killer=2, victim=7), kill(118_000, killer=8, victim=3),
        ])

        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["kill_count"], 3)
        self.assertEqual(episodes[0]["confidence"], "high")
        self.assertEqual(episodes[0]["start_ms"], 100_000)
        self.assertEqual(episodes[0]["end_ms"], 118_000)

    def test_spatially_distant_kills_are_not_merged_by_time_alone(self) -> None:
        # 10s apart but on opposite sides of the map (top lane vs bot lane).
        episodes = build_fight_episodes([
            kill(100_000, x=2_000, y=12_000),
            kill(110_000, x=12_000, y=2_000),
        ])

        self.assertEqual(len(episodes), 2)

    def test_time_gap_splits_episodes(self) -> None:
        episodes = build_fight_episodes([kill(100_000), kill(130_000)])

        self.assertEqual(len(episodes), 2)

    def test_missing_positions_merge_by_time_with_lower_confidence(self) -> None:
        episodes = build_fight_episodes([
            kill(100_000),
            kill(110_000, x=None, y=None),
        ])

        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["confidence"], "medium")

    def test_output_is_deterministic(self) -> None:
        events = [kill(100_000), kill(110_000, killer=2, victim=7), kill(200_000)]
        self.assertEqual(build_fight_episodes(events), build_fight_episodes(list(reversed(events))))


class ObjectiveAvailabilityTest(unittest.TestCase):
    def test_dragon_windows_follow_respawn_chain(self) -> None:
        windows = elite_availability_windows([
            {"timestamp_ms": 6 * 60_000, "monster_type": "DRAGON"},
        ])

        # Death at 3:00 (horizon 4:30) — dragon spawns at 5:00 → not analyzable.
        self.assertFalse(is_objective_analyzable_death(3 * 60_000, windows))
        # Death at 4:40 (horizon 6:10) — dragon spawn 5:00 falls inside → analyzable.
        self.assertTrue(is_objective_analyzable_death(4 * 60_000 + 40_000, windows))
        # Death at 6:30 (horizon 8:00) — herald spawn at exactly 8:00 → analyzable.
        self.assertTrue(is_objective_analyzable_death(6 * 60_000 + 30_000, windows))
        # Death at 6:10 (horizon 7:40) — dragon respawns 11:00, herald 8:00,
        # baron 20:00 → nothing live or imminent → not analyzable.
        self.assertFalse(is_objective_analyzable_death(6 * 60_000 + 10_000, windows))

    def test_baron_becomes_available_at_twenty_minutes(self) -> None:
        windows = elite_availability_windows([])
        self.assertTrue(is_objective_analyzable_death(25 * 60_000, windows))

    def test_side_agnostic(self) -> None:
        # Availability depends only on kill times: events attributed to blue
        # and to red must produce identical windows.
        blue_kill = [{"timestamp_ms": 600_000, "monster_type": "DRAGON", "killer_team_id": 100}]
        red_kill = [{"timestamp_ms": 600_000, "monster_type": "DRAGON", "killer_team_id": 200}]

        self.assertEqual(elite_availability_windows(blue_kill), elite_availability_windows(red_kill))


class AttributionTest(unittest.TestCase):
    def test_one_objective_goes_to_nearest_preceding_death_only(self) -> None:
        deaths = [100_000, 130_000, 150_000, 160_000]
        objectives = [170_000]

        attribution = attribute_objectives_to_deaths(deaths, objectives)

        self.assertEqual(attribution, {3: [0]})  # only the 160s death is charged

    def test_objective_outside_window_is_unattributed(self) -> None:
        attribution = attribute_objectives_to_deaths([100_000], [300_000])
        self.assertEqual(attribution, {})

    def test_multiple_objectives_can_attach_to_one_death(self) -> None:
        attribution = attribute_objectives_to_deaths([100_000], [130_000, 160_000])
        self.assertEqual(attribution, {0: [0, 1]})

    def test_deterministic_regardless_of_death_order(self) -> None:
        a = attribute_objectives_to_deaths([100_000, 150_000], [170_000])
        b = attribute_objectives_to_deaths([100_000, 150_000], [170_000])
        self.assertEqual(a, b)
        self.assertEqual(a, {1: [0]})


class DeathCostDedupIntegrationTest(unittest.TestCase):
    def test_one_dragon_is_not_charged_to_four_deaths(self) -> None:
        from tests.test_custom_metrics import make_features, make_match, make_timeline
        from app.services.custom_metrics import analyze_player_match

        base = 16 * 60_000
        events = [
            {"type": "CHAMPION_KILL", "timestamp": base + offset, "victimId": 1, "killerId": 6}
            for offset in (0, 20_000, 40_000, 60_000)
        ] + [
            {
                "type": "ELITE_MONSTER_KILL",
                "timestamp": base + 80_000,
                "killerId": 6,
                "killerTeamId": 200,
                "monsterType": "DRAGON",
            }
        ]

        analysis = analyze_player_match(
            match_id="KR_1",
            puuid="player-puuid",
            match=make_match(),
            timeline=make_timeline(events),
            features=make_features({16: 0, 18: -500}),
        )

        # 4 deaths x base 8 = 32, dragon weight 16 charged ONCE = 48 total
        # (pre-Phase-3 this was 32 + 4x16 = 96).
        self.assertEqual(analysis["scores"]["death_cost_index"]["value"], 48)

        objective_evidence = [
            item for item in analysis["evidence"]
            if item["type"] == "death_cost" and "objective loss" in item["title"]
        ]
        self.assertEqual(len(objective_evidence), 1)


if __name__ == "__main__":
    unittest.main()
