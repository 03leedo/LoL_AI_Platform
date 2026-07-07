import asyncio
import unittest
from types import SimpleNamespace

from app.services.match_data import get_match_cached, get_timeline_cached


class StubSession:
    """Minimal AsyncSession stand-in for cache-path tests."""

    def __init__(self, rows: dict | None = None) -> None:
        self.rows = rows or {}
        self.merged: list = []
        self.commits = 0
        self.rollbacks = 0

    async def get(self, model, primary_key):
        return self.rows.get((model.__name__, primary_key))

    async def merge(self, obj):
        self.merged.append(obj)
        return obj

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class StubRiotClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def get_match(self, match_id: str) -> dict:
        self.calls.append(("match", match_id))
        return {"info": {"queueId": 420}}

    async def get_match_timeline(self, match_id: str) -> dict:
        self.calls.append(("timeline", match_id))
        return {"info": {"frames": []}}


class MatchDataCacheTest(unittest.TestCase):
    def test_match_cache_hit_skips_riot(self) -> None:
        cached = {"info": {"queueId": 999}}
        db = StubSession(rows={("RiotMatch", "KR_1"): SimpleNamespace(raw_json=cached)})
        client = StubRiotClient()

        match, from_cache = asyncio.run(get_match_cached(db, client, "KR_1", "kr"))

        self.assertTrue(from_cache)
        self.assertEqual(match, cached)
        self.assertEqual(client.calls, [])
        self.assertEqual(db.commits, 0)

    def test_match_cache_miss_fetches_and_persists(self) -> None:
        db = StubSession()
        client = StubRiotClient()

        match, from_cache = asyncio.run(get_match_cached(db, client, "KR_2", "kr"))

        self.assertFalse(from_cache)
        self.assertEqual(match["info"]["queueId"], 420)
        self.assertEqual(client.calls, [("match", "KR_2")])
        self.assertEqual(len(db.merged), 1)
        self.assertEqual(db.commits, 1)

    def test_timeline_cache_hit_skips_riot(self) -> None:
        cached = {"info": {"frames": [{"timestamp": 0}]}}
        db = StubSession(rows={("RiotMatchTimeline", "KR_3"): SimpleNamespace(raw_json=cached)})
        client = StubRiotClient()

        timeline, from_cache = asyncio.run(get_timeline_cached(db, client, "KR_3"))

        self.assertTrue(from_cache)
        self.assertEqual(timeline, cached)
        self.assertEqual(client.calls, [])

    def test_timeline_cache_miss_fetches_and_persists(self) -> None:
        db = StubSession()
        client = StubRiotClient()

        timeline, from_cache = asyncio.run(get_timeline_cached(db, client, "KR_4"))

        self.assertFalse(from_cache)
        self.assertEqual(timeline, {"info": {"frames": []}})
        self.assertEqual(client.calls, [("timeline", "KR_4")])
        self.assertEqual(len(db.merged), 1)
        self.assertEqual(db.commits, 1)

    def test_persistence_failure_still_returns_fresh_data(self) -> None:
        class FailingSession(StubSession):
            async def commit(self) -> None:
                raise RuntimeError("db down")

        db = FailingSession()
        client = StubRiotClient()

        match, from_cache = asyncio.run(get_match_cached(db, client, "KR_5", "kr"))

        self.assertFalse(from_cache)
        self.assertEqual(match["info"]["queueId"], 420)
        self.assertEqual(db.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
