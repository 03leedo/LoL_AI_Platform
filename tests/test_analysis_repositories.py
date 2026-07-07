import unittest

from app.repositories.analysis import MOMENT_WINDOW_MS, build_metric_scores, build_moments
from app.services.custom_metrics import METRIC_VERSION


def make_key_events() -> list[dict]:
    return [
        {
            "minute": 0,
            "timestamp_ms": 5_000,
            "type": "kill",
            "title": "아리 -> 리신 처치",
            "team": "blue",
            "participants": [
                {"participant_id": 1, "is_player": True, "is_actor": True},
                {"participant_id": 6, "is_player": False, "is_actor": True},
            ],
        },
        {
            "minute": 20,
            "timestamp_ms": 1_200_000,
            "type": "baron",
            "title": "블루팀 바론 처치",
            "team": "blue",
            "participants": [{"participant_id": 3, "is_player": False, "is_actor": True}],
        },
        {
            "minute": 25,
            "timestamp_ms": 1_500_000,
            "type": "tower",
            "title": "레드팀 포탑 파괴",
            "team": "red",
            "participants": [],
        },
    ]


def make_analysis() -> dict:
    return {
        "match_id": "KR_1",
        "player": {"puuid": "player-puuid", "champion": "Ahri", "role": "MIDDLE", "team": "blue", "win": True},
        "scores": {
            "death_cost_index": {"value": 24, "confidence": "medium", "direction": "higher_is_worse"},
            "throw_index": {"value": 10, "confidence": "medium", "direction": "higher_is_worse"},
            "objective_setup_score": {"value": 62, "confidence": "medium", "direction": "higher_is_better"},
            "lead_conversion_score": {"value": None, "confidence": "low", "direction": "higher_is_better"},
            "stability_score": {"value": 81, "confidence": "medium", "direction": "higher_is_better"},
        },
        "evidence": [
            {"type": "death_cost", "minute": 16, "title": "드래곤 직전 데스"},
            {"type": "death_cost", "minute": 24, "title": "바론 직전 데스"},
            {"type": "objective_setup", "minute": 20, "title": "바론 앞 시야 부족"},
        ],
    }


class BuildMomentsTest(unittest.TestCase):
    def test_maps_key_events_to_moment_rows(self) -> None:
        moments = build_moments(match_id="KR_1", puuid="player-puuid", key_events=make_key_events())

        self.assertEqual(len(moments), 3)
        self.assertTrue(all(m.match_id == "KR_1" and m.puuid == "player-puuid" for m in moments))
        self.assertEqual([m.moment_type for m in moments], ["kill", "baron", "tower"])
        self.assertTrue(all(m.source == "api" for m in moments))

    def test_window_is_clamped_at_zero(self) -> None:
        moments = build_moments(match_id="KR_1", puuid="p", key_events=make_key_events())

        first = moments[0]
        self.assertEqual(first.t_start_ms, 0)  # 5000 - 15000 clamps to 0
        self.assertEqual(first.t_end_ms, 5_000 + MOMENT_WINDOW_MS)

    def test_importance_prefers_player_actions_then_elite_objectives(self) -> None:
        moments = build_moments(match_id="KR_1", puuid="p", key_events=make_key_events())

        kill, baron, tower = moments
        self.assertEqual(kill.importance, 3)  # player is the actor
        self.assertEqual(baron.importance, 2)  # elite objective
        self.assertEqual(tower.importance, 1)  # background event

    def test_evidence_preserves_original_event(self) -> None:
        events = make_key_events()
        moments = build_moments(match_id="KR_1", puuid="p", key_events=events)

        self.assertEqual(moments[0].evidence, events[0])


class BuildMetricScoresTest(unittest.TestCase):
    def test_builds_long_format_rows_for_every_score(self) -> None:
        rows = build_metric_scores(analysis=make_analysis(), metric_version=METRIC_VERSION)

        self.assertEqual(len(rows), 5)
        keys = {row.metric_key for row in rows}
        self.assertIn("death_cost_index", keys)
        self.assertIn("stability_score", keys)
        self.assertTrue(all(row.scope == "match" and row.match_id == "KR_1" for row in rows))
        self.assertTrue(all(row.metric_version == METRIC_VERSION for row in rows))
        self.assertTrue(all(row.role == "MIDDLE" for row in rows))

    def test_null_values_are_preserved(self) -> None:
        rows = build_metric_scores(analysis=make_analysis(), metric_version=1)

        lead = next(row for row in rows if row.metric_key == "lead_conversion_score")
        self.assertIsNone(lead.value)
        self.assertEqual(lead.confidence, "low")

    def test_evidence_is_filtered_per_metric(self) -> None:
        rows = build_metric_scores(analysis=make_analysis(), metric_version=1)
        by_key = {row.metric_key: row for row in rows}

        death_cost_evidence = by_key["death_cost_index"].evidence
        self.assertIsNotNone(death_cost_evidence)
        self.assertEqual(len(death_cost_evidence["items"]), 2)

        setup_evidence = by_key["objective_setup_score"].evidence
        self.assertIsNotNone(setup_evidence)
        self.assertEqual(len(setup_evidence["items"]), 1)

        self.assertIsNone(by_key["stability_score"].evidence)
        self.assertIsNone(by_key["throw_index"].evidence)

    def test_direction_passthrough(self) -> None:
        rows = build_metric_scores(analysis=make_analysis(), metric_version=1)
        by_key = {row.metric_key: row for row in rows}

        self.assertEqual(by_key["death_cost_index"].direction, "higher_is_worse")
        self.assertEqual(by_key["objective_setup_score"].direction, "higher_is_better")


if __name__ == "__main__":
    unittest.main()
