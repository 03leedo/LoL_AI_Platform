import asyncio
import unittest

import httpx

from app.services.riot_client import RiotApiError, RiotClient


class NoopLimiter:
    def __init__(self) -> None:
        self.acquired = 0

    async def acquire(self) -> None:
        self.acquired += 1


def make_client(handler) -> tuple[RiotClient, list[float], NoopLimiter]:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    limiter = NoopLimiter()
    client = RiotClient(
        limiter=limiter,
        sleeper=fake_sleep,
        transport=httpx.MockTransport(handler),
    )
    client.api_key = "test-key"
    return client, sleeps, limiter


class RiotClientRetryTest(unittest.TestCase):
    def test_retries_on_429_honoring_retry_after(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if len(calls) == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "2"},
                    json={"status": {"message": "Rate limit exceeded"}},
                )
            return httpx.Response(200, json={"puuid": "abc"})

        client, sleeps, limiter = make_client(handler)
        result = asyncio.run(client.get_account_by_riot_id("Hide", "KR1"))

        self.assertEqual(result["puuid"], "abc")
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [2.0])
        self.assertEqual(limiter.acquired, 2)

    def test_gives_up_after_max_attempts_on_429(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(429, headers={"Retry-After": "1"}, json={})

        client, sleeps, _ = make_client(handler)

        with self.assertRaises(RiotApiError) as ctx:
            asyncio.run(client.get_match("KR_1"))

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(len(calls), client.max_attempts)
        self.assertEqual(len(sleeps), client.max_attempts - 1)

    def test_does_not_retry_on_404(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(404, json={"status": {"message": "Data not found"}})

        client, sleeps, _ = make_client(handler)

        with self.assertRaises(RiotApiError) as ctx:
            asyncio.run(client.get_match("KR_404"))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(len(calls), 1)
        self.assertEqual(sleeps, [])

    def test_retries_on_5xx_then_succeeds(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if len(calls) == 1:
                return httpx.Response(502, json={})
            return httpx.Response(200, json={"info": {"queueId": 420}})

        client, sleeps, _ = make_client(handler)
        result = asyncio.run(client.get_match("KR_2"))

        self.assertEqual(result["info"]["queueId"], 420)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(sleeps), 1)


if __name__ == "__main__":
    unittest.main()
