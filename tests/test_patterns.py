import unittest

from app.services.patterns import detect_patterns, summarize_death_autopsy


def make_context(
    team_id: int = 100,
    deaths: list[dict] | None = None,
    kills: list[dict] | None = None,
    enemy_objectives: list[dict] | None = None,
) -> dict:
    return {
        "participant_id": 1,
        "team_id": team_id,
        "deaths": deaths or [],
        "kills": kills or [],
        "enemy_objectives": enemy_objectives or [],
    }


def death(minute: int, x: int = 7500, y: int = 7500, shutdown: int = 0) -> dict:
    return {
        "timestamp_ms": minute * 60_000,
        "minute": minute,
        "x": x,
        "y": y,
        "shutdown_bounty": shutdown,
    }


def record(match_id: str, win: bool = True, scores: dict | None = None) -> dict:
    return {"match_id": match_id, "win": win, "scores": scores or {}, "challenges": {}}


class FirstDeathWindowTest(unittest.TestCase):
    def test_clustered_first_deaths_are_detected(self) -> None:
        history = {
            f"KR_{i}": make_context(deaths=[death(minute)])
            for i, minute in enumerate([8, 9, 10, 11, 12])
        }
        records = [record(match_id) for match_id in history]

        patterns = detect_patterns(records, history)
        keys = [p["key"] for p in patterns]

        self.assertIn("first_death_window", keys)
        pattern = next(p for p in patterns if p["key"] == "first_death_window")
        self.assertEqual(len(pattern["matches"]), 5)

    def test_scattered_first_deaths_are_not_flagged(self) -> None:
        history = {
            f"KR_{i}": make_context(deaths=[death(minute)])
            for i, minute in enumerate([3, 11, 19, 27])
        }
        records = [record(match_id) for match_id in history]

        patterns = detect_patterns(records, history)

        self.assertNotIn("first_death_window", [p["key"] for p in patterns])


class DeathZoneTest(unittest.TestCase):
    def test_repeated_enemy_jungle_deaths_flagged(self) -> None:
        # Blue-side player dying deep in red jungle (11000, 7000) repeatedly.
        history = {
            f"KR_{i}": make_context(deaths=[death(10 + i, x=11_000, y=7_000)])
            for i in range(5)
        }
        history["KR_safe"] = make_context(deaths=[death(20, x=7_500, y=7_500)])
        records = [record(match_id) for match_id in history]

        patterns = detect_patterns(records, history)
        pattern = next((p for p in patterns if p["key"] == "death_zone"), None)

        self.assertIsNotNone(pattern)
        self.assertIn("적 정글", pattern["title"])
        self.assertEqual(len(pattern["matches"]), 5)


class ObjectiveLinkedDeathTest(unittest.TestCase):
    def test_deaths_followed_by_objectives_are_critical(self) -> None:
        history = {}
        for i in range(5):
            minute = 15 + i
            history[f"KR_{i}"] = make_context(
                deaths=[death(minute)],
                enemy_objectives=[{"timestamp_ms": minute * 60_000 + 45_000, "minute": minute, "event_type": "ELITE_MONSTER_KILL", "monster_type": "DRAGON", "building_type": None}],
            )
        records = [record(match_id) for match_id in history]

        patterns = detect_patterns(records, history)
        pattern = next((p for p in patterns if p["key"] == "objective_linked_deaths"), None)

        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["severity"], "critical")

    def test_objective_long_after_death_not_linked(self) -> None:
        history = {
            "KR_1": make_context(
                deaths=[death(10)],
                enemy_objectives=[{"timestamp_ms": 10 * 60_000 + 300_000, "minute": 15, "event_type": "ELITE_MONSTER_KILL", "monster_type": "DRAGON", "building_type": None}],
            )
        }
        autopsy = summarize_death_autopsy(history)

        self.assertEqual(autopsy["objective_linked_deaths"], 0)


class ChronicMetricsTest(unittest.TestCase):
    def test_high_gold_retention_average_is_a_weakness(self) -> None:
        records = [record(f"KR_{i}", scores={"gold_retention_score": 50}) for i in range(5)]

        patterns = detect_patterns(records, {})
        pattern = next((p for p in patterns if p["key"] == "gold_retention_score"), None)

        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["severity"], "warn")

    def test_high_stability_is_a_strength(self) -> None:
        records = [record(f"KR_{i}", scores={"stability_score": 80}) for i in range(5)]

        patterns = detect_patterns(records, {})
        pattern = next((p for p in patterns if p["key"] == "strength.stability_score"), None)

        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["severity"], "positive")

    def test_two_samples_are_not_enough(self) -> None:
        records = [record(f"KR_{i}", scores={"gold_retention_score": 90}) for i in range(2)]

        patterns = detect_patterns(records, {})

        self.assertNotIn("gold_retention_score", [p["key"] for p in patterns])


class AutopsyTest(unittest.TestCase):
    def test_summary_counts(self) -> None:
        history = {
            "KR_1": make_context(
                deaths=[death(8, shutdown=300), death(12)],
                kills=[death(15)],
                enemy_objectives=[{"timestamp_ms": 12 * 60_000 + 30_000, "minute": 12, "event_type": "BUILDING_KILL", "monster_type": None, "building_type": "TOWER_BUILDING"}],
            ),
            "KR_2": make_context(deaths=[death(10)]),
        }

        autopsy = summarize_death_autopsy(history)

        self.assertEqual(autopsy["deaths"], 3)
        self.assertEqual(autopsy["kills"], 1)
        self.assertEqual(autopsy["shutdown_deaths"], 1)
        self.assertEqual(autopsy["shutdown_gold_conceded"], 300)
        self.assertEqual(autopsy["objective_linked_deaths"], 1)
        self.assertEqual(autopsy["avg_first_death_minute"], 9.0)


if __name__ == "__main__":
    unittest.main()
