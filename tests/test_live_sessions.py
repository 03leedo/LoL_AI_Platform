import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.services.live_sessions import complete_session, split_riot_id
from companion.live_collector import compact_snapshot, estimate_game_start_ms


class SplitRiotIdTest(unittest.TestCase):
    def test_valid(self) -> None:
        self.assertEqual(split_riot_id("Hide on bush#KR1"), ("Hide on bush", "KR1"))

    def test_hash_in_name(self) -> None:
        self.assertEqual(split_riot_id("a#b#KR1"), ("a#b", "KR1"))

    def test_invalid(self) -> None:
        self.assertIsNone(split_riot_id("no-tag"))
        self.assertIsNone(split_riot_id("#KR1"))
        self.assertIsNone(split_riot_id("name#"))


class FakeLiveSession:
    def __init__(self, riot_id: str = "미드왕#KR1", game_start_ms: int | None = 1_000_000) -> None:
        self.session_id = "abc12345-0000"
        self.riot_id = riot_id
        self.state = "collecting"
        self.game_start_ms = game_start_ms
        self.matched_match_id = None
        self.collector_version = "c1-0.1.0"


def run_complete(session: FakeLiveSession, candidates: list[str]):
    db = AsyncMock()
    db.get = AsyncMock(return_value=session)
    with patch(
        "app.services.live_sessions.fetch_candidate_match_ids",
        new=AsyncMock(return_value=candidates),
    ):
        return asyncio.run(complete_session(db, session.session_id, session.game_start_ms))


class CompleteSessionTest(unittest.TestCase):
    def test_single_candidate_reconciles(self) -> None:
        session = run_complete(FakeLiveSession(), ["KR_777"])
        self.assertEqual(session.state, "reconciled")
        self.assertEqual(session.matched_match_id, "KR_777")

    def test_zero_candidates_stays_complete(self) -> None:
        session = run_complete(FakeLiveSession(), [])
        self.assertEqual(session.state, "complete")
        self.assertIsNone(session.matched_match_id)

    def test_ambiguous_candidates_stay_unmatched(self) -> None:
        session = run_complete(FakeLiveSession(), ["KR_1", "KR_2"])
        self.assertEqual(session.state, "complete")
        self.assertIsNone(session.matched_match_id)

    def test_missing_game_start_skips_reconciliation(self) -> None:
        session = run_complete(FakeLiveSession(game_start_ms=None), ["KR_777"])
        self.assertEqual(session.state, "complete")
        self.assertIsNone(session.matched_match_id)


def make_allgamedata(game_time: float, event_ids: list[int]) -> dict:
    return {
        "gameData": {"gameTime": game_time},
        "activePlayer": {
            "riotId": "미드왕#KR1",
            "level": 9,
            "currentGold": 1234.5,
            "championStats": {"currentHealth": 850.0, "maxHealth": 1400.0, "armor": 60.0},
        },
        "events": {"Events": [{"EventID": i, "EventName": f"E{i}"} for i in event_ids]},
    }


class CompactSnapshotTest(unittest.TestCase):
    def test_extracts_c1_scope(self) -> None:
        payload, new_ids = compact_snapshot(make_allgamedata(612.4, [0, 1]), set())

        self.assertEqual(payload["game_time_s"], 612.4)
        self.assertEqual(payload["active"]["riot_id"], "미드왕#KR1")
        self.assertEqual(payload["active"]["current_gold"], 1234.5)
        self.assertEqual(payload["active"]["stats"]["currentHealth"], 850.0)
        self.assertEqual(new_ids, [0, 1])

    def test_only_new_events_are_kept(self) -> None:
        payload, new_ids = compact_snapshot(make_allgamedata(613.4, [0, 1, 2]), {0, 1})

        self.assertEqual(new_ids, [2])
        self.assertEqual([e["EventID"] for e in payload["events"]], [2])

    def test_game_start_estimate(self) -> None:
        # 10 minutes into the game at wall-clock 2_000_000 → started at 1_400_000
        self.assertEqual(estimate_game_start_ms(600.0, 2_000_000), 1_400_000)
