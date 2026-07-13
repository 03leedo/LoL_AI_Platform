import unittest

from app.services.timeline_analyzer import analyze_match_timeline


def make_match() -> dict:
    return {
        "info": {
            "participants": [
                {"participantId": pid, "teamId": 100 if pid <= 5 else 200}
                for pid in range(1, 11)
            ]
        }
    }


def make_frame(timestamp_ms: int, gold_per_player: int = 500) -> dict:
    return {
        "timestamp": timestamp_ms,
        "events": [],
        "participantFrames": {
            str(pid): {"participantId": pid, "totalGold": gold_per_player, "xp": 0, "minionsKilled": 0}
            for pid in range(1, 11)
        },
    }


class TimelineAnalyzerTest(unittest.TestCase):
    def test_final_frame_sharing_a_minute_does_not_duplicate(self) -> None:
        # Regression: the last frame lands at game end (e.g. 34m24s) and can
        # share minute 34 with the regular 34m frame, which violated the
        # (match_id, minute) primary key on persistence.
        timeline = {
            "info": {
                "frames": [
                    make_frame(0),
                    make_frame(2_040_627, gold_per_player=700),   # minute 34
                    make_frame(2_064_594, gold_per_player=750),   # also minute 34 (game end)
                ]
            }
        }

        features = analyze_match_timeline("KR_1", make_match(), timeline)

        minutes = [feature["minute"] for feature in features]
        self.assertEqual(minutes, [0, 34])
        # The later (end-of-game) frame wins.
        final = features[-1]
        self.assertEqual(final["timestamp_ms"], 2_064_594)
        self.assertEqual(final["blue_gold"], 750 * 5)

    def test_frames_stay_sorted_by_minute(self) -> None:
        timeline = {
            "info": {"frames": [make_frame(minute * 60_000) for minute in range(5)]}
        }

        features = analyze_match_timeline("KR_1", make_match(), timeline)

        self.assertEqual([f["minute"] for f in features], [0, 1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
