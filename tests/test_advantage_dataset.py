import asyncio
import unittest

from app.ml.advantage_dataset import (
    FEATURE_NAMES,
    build_dataset,
    derive_blue_win,
    full_feature_row,
    patch_of,
    snapshot_rows_for_match,
    temporal_match_split,
)


class FakeResult:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    def mappings(self) -> list[dict]:
        return self._records


class FakeDb:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    async def execute(self, query) -> FakeResult:
        return FakeResult(self._records)


def make_match(blue_win: bool | None = True, game_version: str = "14.10.556.789") -> dict:
    teams = []
    if blue_win is not None:
        teams = [
            {"teamId": 100, "win": blue_win},
            {"teamId": 200, "win": not blue_win},
        ]
    return {
        "info": {
            "gameVersion": game_version,
            "teams": teams,
            "participants": [
                {"participantId": pid, "teamId": 100 if pid <= 5 else 200}
                for pid in range(1, 11)
            ],
        }
    }


def make_timeline(minutes: int = 3, blue_gold_per_player: int = 600) -> dict:
    frames = []
    for minute in range(minutes):
        frames.append(
            {
                "timestamp": minute * 60_000,
                "events": [],
                "participantFrames": {
                    str(pid): {
                        "participantId": pid,
                        "totalGold": blue_gold_per_player if pid <= 5 else 500,
                        "xp": 400,
                        "minionsKilled": 10,
                    }
                    for pid in range(1, 11)
                },
            }
        )
    return {"info": {"frames": frames}}


class DeriveBlueWinTest(unittest.TestCase):
    def test_blue_win_true(self) -> None:
        self.assertTrue(derive_blue_win(make_match(blue_win=True)))

    def test_blue_win_false(self) -> None:
        self.assertFalse(derive_blue_win(make_match(blue_win=False)))

    def test_missing_teams_is_ambiguous(self) -> None:
        self.assertIsNone(derive_blue_win(make_match(blue_win=None)))

    def test_contradictory_flags_are_ambiguous(self) -> None:
        match = make_match(blue_win=True)
        match["info"]["teams"][1]["win"] = True
        self.assertIsNone(derive_blue_win(match))


class PatchOfTest(unittest.TestCase):
    def test_major_minor(self) -> None:
        self.assertEqual(patch_of(make_match(game_version="14.10.556.789")), "14.10")

    def test_missing_version(self) -> None:
        self.assertIsNone(patch_of({"info": {}}))


class SnapshotRowsTest(unittest.TestCase):
    def test_rows_carry_features_label_and_metadata(self) -> None:
        rows = snapshot_rows_for_match(
            "KR_1", make_match(blue_win=True), make_timeline(minutes=3), 1_700_000_000_000
        )

        # terminal frame excluded → 3 frames yield 2 snapshot rows
        self.assertEqual(len(rows), 2)
        row = rows[1]
        full = full_feature_row(row)
        for name in FEATURE_NAMES:
            self.assertIn(name, full)
        self.assertEqual(row["gold_diff"], (600 - 500) * 5)
        self.assertEqual(row["blue_win"], 1)
        self.assertEqual(row["patch"], "14.10")
        self.assertEqual(row["game_creation"], 1_700_000_000_000)
        # heuristic-baseline fields preserved for inference parity
        self.assertIn("blue_baron_kills", row)

    def test_terminal_frame_is_excluded(self) -> None:
        rows = snapshot_rows_for_match(
            "KR_1", make_match(blue_win=True), make_timeline(minutes=5), 1_700_000_000_000
        )
        self.assertEqual([r["minute"] for r in rows], [0, 1, 2, 3])

    def test_single_frame_match_yields_no_rows(self) -> None:
        rows = snapshot_rows_for_match(
            "KR_1", make_match(blue_win=True), make_timeline(minutes=1), 1_700_000_000_000
        )
        self.assertEqual(rows, [])

    def test_derived_interaction_features(self) -> None:
        row = {"minute": 30, "gold_diff": 2_000, "xp_diff": 1_000}
        full = full_feature_row(row)
        # time weight at 30min = min(1.5, 0.5 + 30/30) = 1.5
        self.assertEqual(full["gold_diff_x_time"], 3_000.0)
        self.assertEqual(full["xp_diff_x_time"], 1_500.0)
        early = full_feature_row({"minute": 0, "gold_diff": 2_000, "xp_diff": 0})
        self.assertEqual(early["gold_diff_x_time"], 1_000.0)

    def test_ambiguous_winner_yields_no_rows(self) -> None:
        rows = snapshot_rows_for_match(
            "KR_1", make_match(blue_win=None), make_timeline(), 1_700_000_000_000
        )
        self.assertEqual(rows, [])


class BuildDatasetTest(unittest.TestCase):
    def _record(self, match_id: str, **overrides) -> dict:
        record = {
            "match_id": match_id,
            "game_creation": 1_700_000_000_000,
            "game_duration": 1_800,
            "raw_json": make_match(blue_win=True),
            "timeline_json": make_timeline(minutes=2),
        }
        record.update(overrides)
        return record

    def test_unmapped_queue_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            asyncio.run(build_dataset(FakeDb([]), queue_id=0))
        with self.assertRaises(ValueError):
            asyncio.run(build_dataset(FakeDb([]), queue_id=999))

    def test_domain_derived_from_queue_and_exclusions_recorded(self) -> None:
        records = [
            self._record("KR_OK", timeline_json=make_timeline(minutes=3)),
            self._record("KR_REMAKE", game_duration=120),
            self._record("KR_NO_CREATION", game_creation=None),
            self._record("KR_NO_WINNER", raw_json=make_match(blue_win=None)),
        ]
        dataset = asyncio.run(build_dataset(FakeDb(records), queue_id=420))

        self.assertEqual(dataset["domain"], "soloq")
        self.assertEqual(dataset["matches_included"], ["KR_OK"])
        self.assertEqual(
            dataset["matches_excluded"],
            {
                "KR_REMAKE": "remake_or_short",
                "KR_NO_CREATION": "missing_game_creation",
                "KR_NO_WINNER": "no_winner_or_no_frames",
            },
        )
        # 3 frames − terminal frame = 2 rows
        self.assertEqual(len(dataset["rows"]), 2)


def make_split_rows(match_count: int, minutes: int = 4) -> list[dict]:
    rows = []
    for m in range(match_count):
        for minute in range(minutes):
            rows.append(
                {
                    "match_id": f"KR_{m}",
                    "game_creation": 1_000 + m,
                    "minute": minute,
                    "blue_win": m % 2,
                }
            )
    return rows


class TemporalMatchSplitTest(unittest.TestCase):
    def test_matches_never_straddle_the_split(self) -> None:
        split = temporal_match_split(make_split_rows(10), test_fraction=0.3)

        train_ids = {row["match_id"] for row in split["train_rows"]}
        test_ids = {row["match_id"] for row in split["test_rows"]}
        self.assertEqual(train_ids & test_ids, set())
        self.assertEqual(len(split["test_match_ids"]), 3)
        self.assertEqual(len(split["train_rows"]), 7 * 4)

    def test_test_matches_are_the_newest(self) -> None:
        split = temporal_match_split(make_split_rows(10), test_fraction=0.3)

        max_train_creation = max(row["game_creation"] for row in split["train_rows"])
        min_test_creation = min(row["game_creation"] for row in split["test_rows"])
        self.assertLessEqual(max_train_creation, min_test_creation)

    def test_split_is_deterministic(self) -> None:
        rows = make_split_rows(9)
        first = temporal_match_split(rows, test_fraction=0.3)
        second = temporal_match_split(list(reversed(rows)), test_fraction=0.3)
        self.assertEqual(first["test_match_ids"], second["test_match_ids"])

    def test_single_match_goes_entirely_to_train(self) -> None:
        split = temporal_match_split(make_split_rows(1), test_fraction=0.3)
        self.assertEqual(split["test_rows"], [])
        self.assertEqual(len(split["train_rows"]), 4)

    def test_at_least_one_test_match_when_possible(self) -> None:
        split = temporal_match_split(make_split_rows(3), test_fraction=0.1)
        self.assertEqual(len(split["test_match_ids"]), 1)
