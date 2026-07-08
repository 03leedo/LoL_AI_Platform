import unittest

from app.services.win_probability import PROB_CEILING, PROB_FLOOR, build_win_curve


def make_feature(minute: int, **overrides) -> dict:
    feature = {
        "minute": minute,
        "timestamp_ms": minute * 60_000,
        "gold_diff": 0,
        "xp_diff": 0,
        "blue_tower_kills": 0,
        "red_tower_kills": 0,
        "blue_dragon_kills": 0,
        "red_dragon_kills": 0,
        "blue_herald_kills": 0,
        "red_herald_kills": 0,
        "blue_baron_kills": 0,
        "red_baron_kills": 0,
    }
    feature.update(overrides)
    return feature


class WinProbabilityTest(unittest.TestCase):
    def test_even_game_is_a_coin_flip(self) -> None:
        curve = build_win_curve([make_feature(10)])
        self.assertAlmostEqual(curve[0]["blue_win_prob"], 0.5, places=2)

    def test_blue_gold_lead_raises_blue_probability(self) -> None:
        curve = build_win_curve([make_feature(15, gold_diff=3000)])
        self.assertGreater(curve[0]["blue_win_prob"], 0.6)

    def test_red_lead_lowers_blue_probability(self) -> None:
        curve = build_win_curve([make_feature(15, gold_diff=-3000, red_baron_kills=1)])
        self.assertLess(curve[0]["blue_win_prob"], 0.35)

    def test_probability_is_monotonic_in_gold(self) -> None:
        small = build_win_curve([make_feature(15, gold_diff=1000)])[0]["blue_win_prob"]
        large = build_win_curve([make_feature(15, gold_diff=5000)])[0]["blue_win_prob"]
        self.assertGreater(large, small)

    def test_same_lead_counts_more_later(self) -> None:
        early = build_win_curve([make_feature(5, gold_diff=3000)])[0]["blue_win_prob"]
        late = build_win_curve([make_feature(35, gold_diff=3000)])[0]["blue_win_prob"]
        self.assertGreater(late, early)

    def test_probability_is_clamped(self) -> None:
        stomp = build_win_curve([make_feature(40, gold_diff=30_000, blue_baron_kills=3, blue_tower_kills=11)])
        reverse = build_win_curve([make_feature(40, gold_diff=-30_000, red_baron_kills=3, red_tower_kills=11)])
        self.assertLessEqual(stomp[0]["blue_win_prob"], PROB_CEILING)
        self.assertGreaterEqual(reverse[0]["blue_win_prob"], PROB_FLOOR)

    def test_curve_preserves_frame_order_and_length(self) -> None:
        features = [make_feature(m, gold_diff=m * 100) for m in range(0, 31)]
        curve = build_win_curve(features)
        self.assertEqual(len(curve), 31)
        self.assertEqual([point["minute"] for point in curve], list(range(0, 31)))


if __name__ == "__main__":
    unittest.main()
