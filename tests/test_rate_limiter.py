import asyncio
import unittest

from app.services.rate_limiter import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class RateLimiterTest(unittest.TestCase):
    def _make(self, limits):
        clock = FakeClock()
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            clock.now += seconds

        return SlidingWindowRateLimiter(limits, clock=clock, sleeper=fake_sleep), clock, sleeps

    def test_acquires_freely_under_the_limit(self) -> None:
        limiter, _, sleeps = self._make([(3, 1.0)])

        async def scenario() -> None:
            await limiter.acquire()
            await limiter.acquire()
            await limiter.acquire()

        asyncio.run(scenario())
        self.assertEqual(sleeps, [])

    def test_blocks_until_window_frees(self) -> None:
        limiter, clock, sleeps = self._make([(2, 1.0)])

        async def scenario() -> None:
            await limiter.acquire()
            await limiter.acquire()
            await limiter.acquire()

        asyncio.run(scenario())
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 1.0)
        self.assertAlmostEqual(clock.now, 1.0)

    def test_enforces_both_windows(self) -> None:
        limiter, clock, sleeps = self._make([(2, 1.0), (3, 10.0)])

        async def scenario() -> None:
            for _ in range(4):
                await limiter.acquire()

        asyncio.run(scenario())
        # 3rd acquire waits on the 1s window, 4th on the 10s window.
        self.assertEqual(len(sleeps), 2)
        self.assertAlmostEqual(sleeps[0], 1.0)
        self.assertAlmostEqual(sleeps[1], 9.0)
        self.assertAlmostEqual(clock.now, 10.0)

    def test_expired_entries_free_capacity(self) -> None:
        limiter, clock, sleeps = self._make([(2, 1.0)])

        async def scenario() -> None:
            await limiter.acquire()
            await limiter.acquire()
            clock.now = 5.0
            await limiter.acquire()

        asyncio.run(scenario())
        self.assertEqual(sleeps, [])


if __name__ == "__main__":
    unittest.main()
