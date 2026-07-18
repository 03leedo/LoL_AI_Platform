import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.services.match_collector import collect_new_matches
from app.services.riot_client import RiotApiError


class FakeClient:
    def __init__(self, ids_by_seed: dict[str, object]) -> None:
        self._ids_by_seed = ids_by_seed
        self.calls: list[str] = []

    async def get_match_ids(self, puuid: str, count: int, queue: int) -> list[str]:
        self.calls.append(puuid)
        value = self._ids_by_seed.get(puuid, [])
        if isinstance(value, Exception):
            raise value
        return list(value)


def run_collect(client: FakeClient, seeds: list[str], existing: set[str], **kwargs) -> tuple[dict, list[str]]:
    ingested: list[str] = []

    async def fake_ingest(db, client, puuid, match_id, platform_routing) -> None:
        if isinstance(kwargs.get("ingest_error"), Exception) and match_id in kwargs.get(
            "failing_matches", set()
        ):
            raise kwargs["ingest_error"]
        ingested.append(match_id)

    async def _run() -> dict:
        with patch(
            "app.services.match_collector.fetch_seed_puuids", new=AsyncMock(return_value=seeds)
        ), patch(
            "app.services.match_collector.fetch_existing_match_ids",
            new=AsyncMock(side_effect=lambda db, ids: {m for m in ids if m in existing}),
        ):
            return await collect_new_matches(
                db=AsyncMock(),
                client=client,
                max_new_matches=kwargs.get("max_new_matches", 100),
                per_seed_count=30,
                max_seeds=len(seeds),
                ingest=fake_ingest,
            )

    return asyncio.run(_run()), ingested


class CollectNewMatchesTest(unittest.TestCase):
    def test_skips_stored_and_duplicate_matches(self) -> None:
        client = FakeClient(
            {
                "seed_a": ["KR_1", "KR_2", "KR_3"],
                "seed_b": ["KR_2", "KR_4"],  # KR_2 already seen via seed_a
            }
        )
        stats, ingested = run_collect(client, ["seed_a", "seed_b"], existing={"KR_1"})

        self.assertEqual(ingested, ["KR_2", "KR_3", "KR_4"])
        self.assertEqual(stats["new_matches"], 3)
        self.assertEqual(stats["already_stored"], 2)  # KR_1 stored + KR_2 duplicate
        self.assertIsNone(stats["aborted"])

    def test_stops_at_max_new_matches(self) -> None:
        client = FakeClient({"seed_a": [f"KR_{i}" for i in range(20)], "seed_b": ["KR_X"]})
        stats, ingested = run_collect(
            client, ["seed_a", "seed_b"], existing=set(), max_new_matches=5
        )

        self.assertEqual(len(ingested), 5)
        self.assertEqual(stats["new_matches"], 5)
        # second seed never queried once the cap is reached
        self.assertEqual(client.calls, ["seed_a"])

    def test_rejected_key_aborts_the_run(self) -> None:
        client = FakeClient(
            {
                "seed_a": RiotApiError("forbidden", 403),
                "seed_b": ["KR_1"],
            }
        )
        stats, ingested = run_collect(client, ["seed_a", "seed_b"], existing=set())

        self.assertEqual(ingested, [])
        self.assertIn("rotate RIOT_API_KEY", stats["aborted"])
        self.assertEqual(client.calls, ["seed_a"])  # no further seeds hammered

    def test_transient_seed_failure_continues(self) -> None:
        client = FakeClient(
            {
                "seed_a": RiotApiError("service unavailable", 503),
                "seed_b": ["KR_1"],
            }
        )
        stats, ingested = run_collect(client, ["seed_a", "seed_b"], existing=set())

        self.assertEqual(ingested, ["KR_1"])
        self.assertEqual(stats["failed"], 1)
        self.assertIsNone(stats["aborted"])

    def test_single_match_failure_does_not_kill_the_run(self) -> None:
        client = FakeClient({"seed_a": ["KR_1", "KR_2"]})
        stats, ingested = run_collect(
            client,
            ["seed_a"],
            existing=set(),
            ingest_error=RuntimeError("bad payload"),
            failing_matches={"KR_1"},
        )

        self.assertEqual(ingested, ["KR_2"])
        self.assertEqual(stats["new_matches"], 1)
        self.assertEqual(stats["failed"], 1)
