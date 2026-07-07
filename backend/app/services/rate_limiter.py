"""App-level rate limiting for outbound Riot API requests.

Riot enforces application-wide limits (development key: 20 requests/1s and
100 requests/120s). Every RiotClient call must go through one shared limiter
so concurrent requests and background jobs stay under the budget together.
"""

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable

from app.core.config import get_settings

Clock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


class SlidingWindowRateLimiter:
    """Enforces multiple (max_requests, window_seconds) limits at once.

    acquire() blocks until a request slot is free in every window. The clock
    and sleeper are injectable so tests can run without real waiting.
    """

    def __init__(
        self,
        limits: list[tuple[int, float]],
        clock: Clock = time.monotonic,
        sleeper: Sleeper | None = None,
    ) -> None:
        if not limits:
            raise ValueError("limits must not be empty")
        self._limits = [(int(max_requests), float(window)) for max_requests, window in limits]
        self._history: list[deque[float]] = [deque() for _ in self._limits]
        self._lock = asyncio.Lock()
        self._clock = clock
        self._sleep: Sleeper = sleeper if sleeper is not None else asyncio.sleep

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = self._clock()
                wait = 0.0
                for (max_requests, window), history in zip(self._limits, self._history):
                    while history and history[0] <= now - window:
                        history.popleft()
                    if len(history) >= max_requests:
                        wait = max(wait, history[0] + window - now)
                if wait <= 0:
                    for history in self._history:
                        history.append(now)
                    return
            await self._sleep(wait)


_riot_rate_limiter: SlidingWindowRateLimiter | None = None


def get_riot_rate_limiter() -> SlidingWindowRateLimiter:
    """Process-wide limiter shared by every RiotClient instance."""
    global _riot_rate_limiter
    if _riot_rate_limiter is None:
        settings = get_settings()
        _riot_rate_limiter = SlidingWindowRateLimiter(
            limits=[
                (settings.riot_rate_limit_per_second, 1.0),
                (settings.riot_rate_limit_per_two_minutes, 120.0),
            ]
        )
    return _riot_rate_limiter
