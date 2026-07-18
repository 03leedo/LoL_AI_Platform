import asyncio
import unittest

from app.ml.expected_performance import (
    MIN_GROUP_N,
    TARGETS,
    build_expected_dataset,
    fit_grouped_baseline,
    participant_rows_for_match,
    predict_expected,
    run_expected_report,
)

ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def make_match(positions: list[str] | None = None) -> dict:
    positions = positions if positions is not None else ROLES
    participants = []
    for index, role in enumerate(positions):
        participants.append({"participantId": index + 1, "teamId": 100, "teamPosition": role})
    for index, role in enumerate(positions):
        participants.append({"participantId": index + 6, "teamId": 200, "teamPosition": role})
    return {"info": {"gameVersion": "14.10.1.1", "participants": participants}}


def make_timeline(minutes: int = 12, blue_gold: int = 3_500, red_gold: int = 3_000) -> dict:
    frames = []
    for minute in range(minutes):
        frames.append(
            {
                "timestamp": minute * 60_000,
                "participantFrames": {
                    str(pid): {
                        "participantId": pid,
                        "totalGold": blue_gold if pid <= 5 else red_gold,
                        "xp": 4_000 if pid <= 5 else 3_800,
                        "minionsKilled": 70 if pid <= 5 else 60,
                        "jungleMinionsKilled": 8 if pid <= 5 else 4,
                    }
                    for pid in range(1, 11)
                },
            }
        )
    return {"info": {"frames": frames}}


class ParticipantRowsTest(unittest.TestCase):
    def test_pairs_all_roles_and_diffs_are_antisymmetric(self) -> None:
        rows, reason = participant_rows_for_match(
            "KR_1", make_match(), make_timeline(), 1_700_000_000_000
        )

        self.assertIsNone(reason)
        self.assertEqual(len(rows), 10)
        blue_top = next(r for r in rows if r["role"] == "TOP" and r["side"] == "BLUE")
        red_top = next(r for r in rows if r["role"] == "TOP" and r["side"] == "RED")
        self.assertEqual(blue_top["gd_at_10"], 500)
        for target in TARGETS:
            self.assertEqual(blue_top[target], -red_top[target])
        # CS includes jungle camps
        self.assertEqual(blue_top["csd_at_10"], (70 + 8) - (60 + 4))
        self.assertEqual(blue_top["patch"], "14.10")

    def test_short_game_without_minute_10_is_excluded(self) -> None:
        rows, reason = participant_rows_for_match(
            "KR_1", make_match(), make_timeline(minutes=8), 1_700_000_000_000
        )
        self.assertEqual(rows, [])
        self.assertEqual(reason, "no_minute_10_frame")

    def test_duplicate_position_skips_that_role_only(self) -> None:
        rows, reason = participant_rows_for_match(
            "KR_1",
            make_match(positions=["TOP", "TOP", "MIDDLE", "BOTTOM", "UTILITY"]),
            make_timeline(),
            1_700_000_000_000,
        )
        self.assertIsNone(reason)
        roles = {row["role"] for row in rows}
        self.assertEqual(roles, {"MIDDLE", "BOTTOM", "UTILITY"})
        self.assertEqual(len(rows), 6)

    def test_no_valid_positions_is_excluded(self) -> None:
        match = {"info": {"participants": [{"participantId": 1, "teamId": 100}]}}
        rows, reason = participant_rows_for_match("KR_1", match, make_timeline(), 1)
        self.assertEqual(rows, [])
        self.assertEqual(reason, "no_pairable_roles")


def make_rows(match_count: int, gd: int = 400) -> list[dict]:
    rows = []
    for m in range(match_count):
        for role in ROLES:
            for side, sign in (("BLUE", 1), ("RED", -1)):
                rows.append(
                    {
                        "match_id": f"KR_{m}",
                        "game_creation": 1_000 + m,
                        "patch": "14.10",
                        "role": role,
                        "side": side,
                        "gd_at_10": sign * gd,
                        "csd_at_10": sign * 10,
                        "xpd_at_10": sign * 200,
                    }
                )
    return rows


class GroupedBaselineTest(unittest.TestCase):
    def test_zero_baseline_predicts_zero(self) -> None:
        model = fit_grouped_baseline("zero", make_rows(4), "gd_at_10")
        self.assertEqual(predict_expected(model, make_rows(1)[0]), 0.0)

    def test_role_side_mean_captures_side_asymmetry(self) -> None:
        rows = make_rows(MIN_GROUP_N)  # 10 per (role, side) group
        model = fit_grouped_baseline("role_side_mean", rows, "gd_at_10")
        blue_row = {"role": "TOP", "side": "BLUE"}
        red_row = {"role": "TOP", "side": "RED"}
        self.assertEqual(predict_expected(model, blue_row), 400.0)
        self.assertEqual(predict_expected(model, red_row), -400.0)

    def test_small_group_falls_back_to_parent(self) -> None:
        rows = make_rows(2)  # 2 per (role, side): below MIN_GROUP_N
        model = fit_grouped_baseline("role_side_mean", rows, "gd_at_10")
        # falls back through role_mean (n=4, also small) to zero
        self.assertEqual(predict_expected(model, {"role": "TOP", "side": "BLUE"}), 0.0)


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


class BuildExpectedDatasetTest(unittest.TestCase):
    def test_exclusions_and_domain(self) -> None:
        records = [
            {
                "match_id": "KR_OK",
                "game_creation": 1_700_000_000_000,
                "game_duration": 1_800,
                "raw_json": make_match(),
                "timeline_json": make_timeline(),
            },
            {
                "match_id": "KR_SHORT",
                "game_creation": 1_700_000_000_001,
                "game_duration": 1_800,
                "raw_json": make_match(),
                "timeline_json": make_timeline(minutes=5),
            },
        ]
        dataset = asyncio.run(build_expected_dataset(FakeDb(records), queue_id=420))

        self.assertEqual(dataset["domain"], "soloq")
        self.assertEqual(dataset["matches_included"], ["KR_OK"])
        self.assertEqual(dataset["matches_excluded"], {"KR_SHORT": "no_minute_10_frame"})
        self.assertEqual(len(dataset["rows"]), 10)

    def test_unmapped_queue_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            asyncio.run(build_expected_dataset(FakeDb([]), queue_id=999))


class RunExpectedReportTest(unittest.TestCase):
    def _dataset(self, rows: list[dict], match_count: int) -> dict:
        return {
            "expected_version": 1,
            "queue_id": 420,
            "domain": "soloq",
            "targets": TARGETS,
            "snapshot_minute": 10,
            "matches_included": [f"KR_{m}" for m in range(match_count)],
            "matches_excluded": {},
            "rows": rows,
        }

    def test_report_shape_and_verdict(self) -> None:
        report = run_expected_report(self._dataset(make_rows(40), 40))

        self.assertEqual(report["status"], "evaluated")
        self.assertEqual(report["split"]["method"], "temporal_match_grouped")
        self.assertEqual(report["verdict"]["verdict"], "report_only")
        self.assertTrue(
            any("insufficient_data" in reason for reason in report["verdict"]["reasons"])
        )
        for target in TARGETS:
            self.assertIn(target, report["baseline_evaluations"])
            self.assertIn(report["best_baselines"][target], report["baseline_evaluations"][target])
            self.assertEqual(report["residual_summary"][target]["definition"], "actual - expected")

    def test_side_signal_prefers_role_side_baseline(self) -> None:
        # Deterministic +400 blue / -400 red per pair: role_side_mean is exact.
        report = run_expected_report(self._dataset(make_rows(40), 40))
        self.assertEqual(report["best_baselines"]["gd_at_10"], "role_side_mean")
        self.assertAlmostEqual(
            report["baseline_evaluations"]["gd_at_10"]["role_side_mean"]["mae"], 0.0
        )

    def test_insufficient_data_path(self) -> None:
        report = run_expected_report(self._dataset(make_rows(1), 1))
        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["verdict"]["verdict"], "report_only")

    def test_snapshots_of_one_match_stay_in_one_split(self) -> None:
        report = run_expected_report(self._dataset(make_rows(10), 10))
        self.assertEqual(report["split"]["train_rows"] % 10, 0)
        self.assertEqual(report["split"]["test_rows"] % 10, 0)
