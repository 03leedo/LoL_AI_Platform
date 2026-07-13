import unittest

from app.services.turning_points import detect_turning_points


def make_curve(probs: list[float]) -> list[dict]:
    return [
        {"minute": minute, "timestamp_ms": minute * 60_000, "blue_win_prob": prob}
        for minute, prob in enumerate(probs)
    ]


def make_event(minute: int, event_type: str, title: str) -> dict:
    return {
        "minute": minute,
        "timestamp_ms": minute * 60_000 - 10_000,
        "type": event_type,
        "title": title,
        "description": f"{title} 상세",
        "team": "blue",
    }


class TurningPointsTest(unittest.TestCase):
    def test_detects_biggest_swing_with_event_context(self) -> None:
        # Flat until a large drop at minute 3.
        curve = make_curve([0.5, 0.52, 0.51, 0.30, 0.31])
        events = [make_event(3, "baron", "레드팀 바론 처치")]

        points = detect_turning_points(curve, events, player_team="blue")

        self.assertEqual(len(points), 1)
        point = points[0]
        self.assertEqual(point["minute"], 3)
        self.assertLess(point["delta"], 0)
        self.assertEqual(point["title"], "레드팀 바론 처치")
        self.assertEqual(point["event_type"], "baron")

    def test_red_player_sees_flipped_perspective(self) -> None:
        curve = make_curve([0.5, 0.30])  # blue dropped → good for red

        points = detect_turning_points(curve, [], player_team="red")

        self.assertEqual(len(points), 1)
        self.assertGreater(points[0]["delta"], 0)
        self.assertAlmostEqual(points[0]["prob_after"], 0.7)

    def test_small_fluctuations_are_ignored(self) -> None:
        curve = make_curve([0.5, 0.53, 0.49, 0.52, 0.5])

        points = detect_turning_points(curve, [], player_team="blue")

        self.assertEqual(points, [])

    def test_caps_at_top_n_and_sorts_by_minute(self) -> None:
        curve = make_curve([0.5, 0.65, 0.5, 0.75, 0.55, 0.8, 0.55, 0.9])

        points = detect_turning_points(curve, [], player_team="blue", top_n=3)

        self.assertEqual(len(points), 3)
        minutes = [point["minute"] for point in points]
        self.assertEqual(minutes, sorted(minutes))

    def test_high_impact_event_preferred_over_kill(self) -> None:
        curve = make_curve([0.5, 0.5, 0.72])
        events = [
            make_event(2, "kill", "아리 -> 리신 처치"),
            make_event(2, "dragon", "블루팀 드래곤 처치"),
        ]

        points = detect_turning_points(curve, events, player_team="blue")

        self.assertEqual(points[0]["event_type"], "dragon")


if __name__ == "__main__":
    unittest.main()
